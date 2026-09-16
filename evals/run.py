"""Évalue l'assistant sur le jeu de questions de référence, un modèle après l'autre.

    python -m evals.run                                          # modèles de LLM_MODELS
    python -m evals.run --model gemini-3.5-flash-lite
    python -m evals.run --model gemini-3.5-flash-lite --cases contrat-resilie,hors-sujet   # essai, non enregistré

Chaque modèle est évalué seul, sans modèle de secours, pour que les scores soient comparables. Les surcharges et
quotas du plan gratuit sont absorbés par des attentes : on mesure le modèle, pas la disponibilité du service.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commission_engine import Catalog

from commission_api.assistant.agent import Assistant
from commission_api.assistant.llm import (
    LLMClient,
    LLMError,
    LLMReply,
    ModelUnavailableError,
    OpenAICompatibleClient,
    QuotaExceededError,
)
from commission_api.config import Settings
from commission_api.main import build_assistant
from commission_api.schemas import ChatMessage
from commission_api.services import CommissionService

from .checks import EvalCase, evaluate, load_dataset
from .report import RESULTS_DIR, write_report

logger = logging.getLogger("evals")

MAX_CONSECUTIVE_ERRORS = 3


class PatientLLM:
    """Réessaie après une attente quand le modèle est saturé ou que le quota par minute est atteint."""

    def __init__(self, client: LLMClient, waits: Sequence[float] = (15, 30, 60),
                 sleep: Callable[[float], None] = time.sleep):
        self._client = client
        self._waits = tuple(waits)
        self._sleep = sleep
        self.calls = 0

    @property
    def model(self) -> str:
        return self._client.model

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        for wait in (*self._waits, None):
            self.calls += 1
            try:
                return self._client.complete(messages, tools)
            except (QuotaExceededError, ModelUnavailableError) as exc:
                if wait is None:
                    raise
                logger.warning("%s ; nouvel essai dans %.0f s", exc, wait)
                self._sleep(wait)
        raise AssertionError("inaccessible")


def run_case(assistant: Assistant, case: EvalCase) -> dict[str, Any]:
    history = [ChatMessage(role=turn.role, content=turn.content) for turn in case.history]
    history.append(ChatMessage(role="user", content=case.question))
    started = time.perf_counter()
    base = {"id": case.id, "category": case.category, "question": case.question}
    try:
        answer = assistant.answer(history)
    except LLMError as exc:
        return base | {"status": "error", "error": str(exc), "latency_s": round(time.perf_counter() - started, 2)}

    checks = evaluate(case, answer)
    return base | {
        "status": "passed" if all(check.passed for check in checks) else "failed",
        "checks": [asdict(check) for check in checks],
        "answer": answer.content,
        "model": answer.model,
        "tool_calls": [{"name": t.name, "arguments": t.arguments, "ok": t.ok} for t in answer.tool_calls],
        "unverified_amounts": list(answer.unverified_amounts),
        "unknown_products": list(answer.unknown_products),
        "unknown_rules": list(answer.unknown_rules),
        "cited_rules": [citation.rule_id for citation in answer.citations if citation.in_answer],
        "latency_s": round(time.perf_counter() - started, 2),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in results if r["status"] != "error"]
    passed = sum(r["status"] == "passed" for r in evaluated)
    by_category: dict[str, dict[str, int]] = {}
    for result in evaluated:
        stats = by_category.setdefault(result["category"], {"passed": 0, "total": 0})
        stats["total"] += 1
        stats["passed"] += result["status"] == "passed"
    checks = [check for r in evaluated for check in r["checks"]]
    return {
        "cases": len(results),
        "evaluated": len(evaluated),
        "passed": passed,
        "errors": len(results) - len(evaluated),
        "pass_rate": round(passed / len(evaluated), 3) if evaluated else None,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "unverified_amounts": sum(len(r["unverified_amounts"]) for r in evaluated),
        "unknown_products": sum(len(r.get("unknown_products", [])) for r in evaluated),
        "unknown_rules": sum(len(r.get("unknown_rules", [])) for r in evaluated),
        "median_latency_s": round(statistics.median(r["latency_s"] for r in evaluated), 2) if evaluated else None,
        "by_category": by_category,
    }


def run_model(settings: Settings, service: CommissionService, model: str, cases: Sequence[EvalCase],
              dataset_version: int, delay_s: float, sleep: Callable[[float], None] = time.sleep,
              client: LLMClient | None = None) -> dict[str, Any]:
    llm = PatientLLM(client or OpenAICompatibleClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
                                                      model=model, reasoning_effort=settings.llm_reasoning_effort),
                     sleep=sleep)
    assistant = build_assistant(settings, llm, service)
    results: list[dict[str, Any]] = []
    consecutive_errors = 0
    for index, case in enumerate(cases, start=1):
        if index > 1:
            sleep(delay_s)
        result = run_case(assistant, case)
        results.append(result)
        outcome = {"passed": "réussi", "failed": "échoué", "error": "erreur"}[result["status"]]
        logger.info("[%s %d/%d] %s : %s (%.1f s)", model, index, len(cases), case.id, outcome, result["latency_s"])
        consecutive_errors = consecutive_errors + 1 if result["status"] == "error" else 0
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.error("%d erreurs d'infrastructure de suite : quota journalier probablement épuisé, arrêt de %s",
                         consecutive_errors, model)
            break
    return {
        "model": model,
        "provider": settings.llm_base_url,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset_version": dataset_version,
        "complete": len(results) == len(cases),
        "llm_calls": llm.calls,
        "summary": summarize(results),
        "cases": results,
    }


def result_path(model: str, results_dir: Path = RESULTS_DIR) -> Path:
    return results_dir / f"{model.replace('/', '__')}.json"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="evals.run", description="Évalue l'assistant sur le jeu de référence.")
    parser.add_argument("--model", action="append", help="modèle à évaluer (répétable), par défaut LLM_MODELS")
    parser.add_argument("--cases", help="identifiants de questions séparés par des virgules (essai non enregistré)")
    parser.add_argument("--delay", type=float, default=4.0, help="pause entre deux questions, en secondes")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("commission_api").setLevel(logging.WARNING)

    settings = Settings.from_env()
    if not settings.llm_api_key:
        print("LLM_API_KEY n'est pas configurée (voir .env.example).", file=sys.stderr)
        return 2

    dataset = load_dataset()
    cases = dataset.cases
    if args.cases:
        wanted = [case_id.strip() for case_id in args.cases.split(",") if case_id.strip()]
        unknown = set(wanted) - {case.id for case in cases}
        if unknown:
            print(f"Questions inconnues : {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        cases = [case for case in cases if case.id in wanted]
    save = not args.cases

    service = CommissionService(Catalog.load(settings.catalog_path), settings.samples_dir)
    for model in args.model or settings.llm_models:
        run = run_model(settings, service, model, cases, dataset.version, args.delay)
        s = run["summary"]
        print(f"\n{model} : {s['passed']}/{s['evaluated']} questions réussies, "
              f"{s['checks_passed']}/{s['checks_total']} vérifications, {s['errors']} erreur(s) d'infrastructure\n")
        for case in run["cases"]:
            if case["status"] == "failed":
                failed = [c["name"] for c in case["checks"] if not c["passed"]]
                print(f"  ✗ {case['id']} : {', '.join(failed)}")
        if save:
            RESULTS_DIR.mkdir(exist_ok=True)
            result_path(model).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    if save:
        print(f"\nRapport : {write_report()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
