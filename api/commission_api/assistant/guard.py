"""Contrôle a posteriori des réponses : tout montant en euros cité doit provenir d'une source connue.

Sources admises : résultats des outils, règles métier de référence et messages de l'utilisateur.
Un montant absent de ces sources est signalé (il n'est pas bloqué) : l'interface peut l'afficher comme non vérifié.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

_AMOUNT = re.compile(
    r"(?<![\w,.])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:,(\d{1,2}))?\s?(?:€|euros?\b)",
    re.IGNORECASE,
)
_PLAIN_NUMBER = re.compile(r"^[−-]?\d+(?:\.\d+)?$")


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
