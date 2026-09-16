"""Chargement du jeu de questions et vérifications déterministes d'une réponse de l'assistant."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from commission_engine.models import normalize_token
from pydantic import BaseModel, ConfigDict, Field, model_validator

from commission_api.assistant.agent import AssistantAnswer
from commission_api.assistant.guard import amounts_in_text
from commission_api.schemas import LookupRequest, SimulationRequest

DATASET_PATH = Path(__file__).parent / "dataset.yaml"

# Formulations par lesquelles l'assistant réclame une information, même sans point d'interrogation.
REQUEST_MARKERS = ("j'ai besoin", "merci de", "pouvez-vous", "pourriez-vous", "indiquez", "precisez",
                   "transmettre", "communiquer", "une fois ces elements")

Category = Literal["explication", "simulation", "regles", "info_manquante", "limites", "conversation"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Expectations(_Strict):
    tools: list[str] = Field(default_factory=list)
    any_tools: list[str] = Field(default_factory=list)
    tool_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    amounts: list[Decimal] = Field(default_factory=list)
    forbidden_amounts: list[Decimal] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    mentions: list[list[str]] = Field(default_factory=list)
    no_tool_calls: bool = False
    no_amounts: bool = False
    asks_question: bool = False


class GroundTruth(_Strict):
    lookup: LookupRequest | None = None
    simulation: SimulationRequest | None = None


class Turn(_Strict):
    role: Literal["user", "assistant"]
    content: str


class EvalCase(_Strict):
    id: str
    category: Category
    question: str
    history: list[Turn] = Field(default_factory=list)
    expect: Expectations
    ground_truth: GroundTruth | None = None


class Dataset(_Strict):
    version: int
    cases: list[EvalCase]

    @model_validator(mode="after")
    def _unique_ids(self) -> Dataset:
        ids = [case.id for case in self.cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise ValueError(f"identifiants en double : {', '.join(duplicates)}")
        return self


def load_dataset(path: Path = DATASET_PATH) -> Dataset:
    with path.open(encoding="utf-8") as fh:
        return Dataset.model_validate(yaml.safe_load(fh))


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


def evaluate(case: EvalCase, answer: AssistantAnswer) -> list[Check]:
    expect = case.expect
    checks: list[Check] = []
    called = [trace.name for trace in answer.tool_calls if trace.ok]
    called_detail = f"outils appelés avec succès : {', '.join(called) or 'aucun'}"

    for tool in expect.tools:
        checks.append(Check(f"appelle {tool}", tool in called, called_detail))
    if expect.any_tools:
        checks.append(Check(f"appelle {' ou '.join(expect.any_tools)}", bool(set(expect.any_tools) & set(called)),
                            called_detail))
    for tool, expected in expect.tool_arguments.items():
        arguments = [trace.arguments for trace in answer.tool_calls if trace.name == tool]
        checks.append(Check(f"arguments de {tool}", any(contains(actual, expected) for actual in arguments),
                            f"arguments reçus : {arguments or 'aucun appel'}"))

    cited = set(amounts_in_text(answer.content))
    cited_detail = f"montants cités : {', '.join(str(a) for a in sorted(cited)) or 'aucun'}"
    for amount in expect.amounts:
        checks.append(Check(f"cite {amount} €", abs(amount) in cited, cited_detail))
    for amount in expect.forbidden_amounts:
        checks.append(Check(f"ne cite pas {amount} €", abs(amount) not in cited, cited_detail))

    text = normalize_token(answer.content)
    for rule_id in expect.rule_ids:
        checks.append(Check(f"cite la règle {rule_id}", normalize_token(rule_id) in text))
    for group in expect.mentions:
        checks.append(Check(f"mentionne « {' » ou « '.join(group)} »",
                            any(normalize_token(term) in text for term in group)))

    if expect.no_tool_calls:
        checks.append(Check("n'appelle aucun outil", not answer.tool_calls, called_detail))
    if expect.no_amounts:
        checks.append(Check("ne cite aucun montant", not cited, cited_detail))
    if expect.asks_question:
        asks = "?" in answer.content or any(normalize_token(marker) in text for marker in REQUEST_MARKERS)
        checks.append(Check("demande les informations manquantes", asks))

    checks.append(Check("tous les montants ont une source", not answer.unverified_amounts,
                        f"montants sans source : {', '.join(answer.unverified_amounts)}"))
    return checks


def contains(actual: Any, expected: Any) -> bool:
    """Vrai si `expected` est inclus dans `actual` : dictionnaires imbriqués, valeurs sans casse ni accents."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value)
                                                for key, value in expected.items())
    return normalize_token(actual) == normalize_token(expected)
