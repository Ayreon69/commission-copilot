"""Contrôles a posteriori des réponses de l'assistant.

- Montants : tout montant en euros cité doit provenir d'une source (résultats d'outils, règles métier de référence,
  messages de l'utilisateur).
- Règles : les identifiants cités doivent exister ; on indique aussi si la règle a réellement servi à un calcul.
- Produits : tout nom de produit cité doit exister dans le catalogue.

Ces contrôles signalent, ils ne bloquent pas : l'interface peut afficher les éléments non vérifiés.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from commission_engine.models import normalize_token

_AMOUNT = re.compile(
    r"(?<![\w,.])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:,(\d{1,2}))?\s?(?:€|euros?\b)",
    re.IGNORECASE,
)
_PLAIN_NUMBER = re.compile(r"^[−-]?\d+(?:\.\d+)?$")
_RULE_ID = re.compile(r"\bR-[A-Z]{1,4}\d?\b", re.IGNORECASE)


# --- Montants -----------------------------------------------------------------------------------------------------


def amounts_in_text(text: str) -> dict[Decimal, str]:
    """Montants en euros d'un texte (valeur absolue -> forme écrite)."""
    found: dict[Decimal, str] = {}
    for match in _AMOUNT.finditer(text):
        integer = re.sub(r"\D", "", match.group(1))
        found.setdefault(Decimal(f"{integer}.{match.group(2) or '0'}"), match.group(0))
    return found


def amounts_in_payload(payload: Any) -> set[Decimal]:
    """Nombres d'un résultat d'outil : montants affichés et valeurs brutes (primes, cotisations…)."""
    if isinstance(payload, dict):
        return set().union(*(amounts_in_payload(value) for value in payload.values()))
    if isinstance(payload, list):
        return set().union(*(amounts_in_payload(value) for value in payload))
    if isinstance(payload, bool) or payload is None:
        return set()
    if isinstance(payload, int | float):
        return {abs(Decimal(str(payload)))}
    text = str(payload)
    found = set(amounts_in_text(text))
    plain = text.replace("−", "-")
    if _PLAIN_NUMBER.match(plain):
        found.add(abs(Decimal(plain)))
    return found


def unverified_amounts(answer: str, texts: Iterable[str], payloads: Iterable[Any]) -> list[str]:
    known: set[Decimal] = set()
    for text in texts:
        known.update(amounts_in_text(text))
    for payload in payloads:
        known.update(amounts_in_payload(payload))
    return [written for value, written in amounts_in_text(answer).items() if value not in known]


# --- Règles -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    rule_id: str
    label: str
    in_answer: bool  # l'identifiant figure dans le texte de la réponse
    from_calculation: bool  # la règle a été appliquée par le moteur dans un résultat d'outil


def rule_citations(answer: str, payloads: Iterable[Any],
                   labels: Mapping[str, str]) -> tuple[list[Citation], list[str]]:
    """Règles citées ou appliquées, et identifiants cités qui n'existent pas."""
    cited = {match.group(0).upper() for match in _RULE_ID.finditer(answer)}
    applied: set[str] = set()
    for payload in payloads:
        applied |= _rule_ids_in(payload)
    citations = [Citation(rule_id, label, rule_id in cited, rule_id in applied)
                 for rule_id, label in labels.items() if rule_id in cited | applied]
    return citations, sorted(cited - set(labels))


def _rule_ids_in(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        found = {payload["rule_id"]} if isinstance(payload.get("rule_id"), str) else set()
        return found.union(*(_rule_ids_in(value) for value in payload.values()))
    if isinstance(payload, list):
        return set().union(*(_rule_ids_in(value) for value in payload))
    return set()


# --- Produits -----------------------------------------------------------------------------------------------------


def unknown_products(answer: str, product_labels: Iterable[str], other_names: Iterable[str] = ()) -> list[str]:
    """Noms de produits cités qui n'existent pas dans le catalogue.

    Un nom de produit est repéré par sa marque (premier mot des libellés du catalogue, ex. « Verdance ») suivie de
    mots à majuscule sur la même ligne. Il est connu s'il correspond au début d'un libellé du catalogue
    (« Verdance Compagnon ») ou s'il commence par un libellé complet suivi d'autres mots (« Nordale Santé Confort Pour
    ce contrat »). « Verdance Essentiel » ou « Nordale Santé Premium » sont signalés.
    """
    labels = [label for label in product_labels if label.split()]
    brands = sorted({label.split()[0] for label in labels})
    if not brands:
        return []
    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, brands)) + r")(?:[ \t]+[A-ZÀ-ÖØ-Þ][\w'’-]*)*")
    known = [_words(name) for name in [*labels, *other_names]]
    flagged: list[str] = []
    for match in pattern.finditer(answer):
        words = _words(match.group(0))
        if len(words) >= 2 and not _is_known(words, known) and match.group(0) not in flagged:
            flagged.append(match.group(0))
    return flagged


def _words(text: str) -> list[str]:
    return normalize_token(text).replace("(", " ").replace(")", " ").split()


def _is_known(words: list[str], known: list[list[str]]) -> bool:
    for size in range(len(words), 0, -1):
        matching = [name for name in known if name[:size] == words[:size]]
        if matching:
            return size == len(words) or any(len(name) == size for name in matching)
    return False
