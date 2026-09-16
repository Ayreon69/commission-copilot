"""Rapport comparatif des évaluations enregistrées dans evals/results/.

    python -m evals.report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_PATH = Path(__file__).parent / "RAPPORT.md"

CATEGORY_LABELS = {
    "explication": "Explication d'un contrat",
    "simulation": "Simulation d'un cas",
    "regles": "Règles et paramétrage",
    "info_manquante": "Informations manquantes",
    "limites": "Limites et pièges",
    "conversation": "Suivi de conversation",
}


def load_runs(results_dir: Path = RESULTS_DIR) -> list[dict[str, Any]]:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(results_dir.glob("*.json"))]
    return sorted(runs, key=lambda run: run["summary"]["pass_rate"] or 0, reverse=True)


def _ratio(passed: int, total: int) -> str:
    return f"{round(100 * passed / total)} % ({passed}/{total})" if total else "—"


def render(runs: list[dict[str, Any]]) -> str:
    lines = [
        "# Évaluation de l'assistant",
        "",
        "Rapport généré par `python -m evals.run`. Chaque modèle répond seul (sans modèle de secours) au jeu de "
        "questions de [dataset.yaml](dataset.yaml). Les vérifications sont déterministes, sans modèle juge : outils "
        "appelés, montants exacts, règles citées, termes attendus, montants interdits, et aucun montant sans source.",
        "",
    ]
    if not runs:
        return "\n".join([*lines, "Aucune évaluation enregistrée.", ""])

    lines += [
        "## Synthèse",
        "",
        "| Modèle | Questions réussies | Vérifications | Montants sans source | Produits ou règles inexistants "
        "| Erreurs d'infrastructure | Latence médiane | Appels au modèle | Date |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        s = run["summary"]
        model = run["model"] + ("" if run["complete"] else " (incomplet)")
        latency = f"{s['median_latency_s']:.1f} s" if s["median_latency_s"] is not None else "—"
        lines.append(
            f"| `{model}` | {_ratio(s['passed'], s['evaluated'])} | {_ratio(s['checks_passed'], s['checks_total'])} "
            f"| {s['unverified_amounts']} | {s.get('unknown_products', 0) + s.get('unknown_rules', 0)} "
            f"| {s['errors']} | {latency} | {run['llm_calls']} | {run['date'][:10]} |"
        )

    lines += ["", "## Par catégorie", "", "| Catégorie | " + " | ".join(f"`{r['model']}`" for r in runs) + " |",
              "|---|" + "---|" * len(runs)]
    for category, label in CATEGORY_LABELS.items():
        cells = []
        for run in runs:
            stats = run["summary"]["by_category"].get(category)
            cells.append(_ratio(stats["passed"], stats["total"]) if stats else "—")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "## Questions échouées", ""]
    for run in runs:
        failures = [case for case in run["cases"] if case["status"] != "passed"]
        lines += [f"### `{run['model']}`", ""]
        if not failures:
            lines += ["Aucune.", ""]
            continue
        for case in failures:
            if case["status"] == "error":
                lines.append(f"- **{case['id']}** : erreur d'infrastructure ({case['error']})")
                continue
            failed = "; ".join(f"{c['name']}" + (f" ({c['detail']})" if c["detail"] else "")
                               for c in case["checks"] if not c["passed"])
            lines.append(f"- **{case['id']}** : {failed}")
        lines.append("")
    return "\n".join(lines)


def write_report(results_dir: Path = RESULTS_DIR, report_path: Path = REPORT_PATH) -> Path:
    report_path.write_text(render(load_runs(results_dir)), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Rapport écrit dans {write_report()}")
