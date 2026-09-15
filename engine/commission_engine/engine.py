"""Points d'entrée du moteur : calcul d'un mois complet ou simulation d'un contrat isolé."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .catalog import Catalog
from .lineaire import compute_lineaire
from .models import CommissionLine, CommissionType, ContractRecord, Exclusion, ExclusionReason, PremiumRecord
from .periods import format_month, parse_month
from .precompte import compute_precompte


@dataclass(frozen=True)
class MonthlyResult:
    perimeter: str
    month: str
    lines: tuple[CommissionLine, ...]
    exclusions: tuple[Exclusion, ...]

    def total(self, commission_type: CommissionType | None = None) -> Decimal:
        return sum(
            (line.amount for line in self.lines if commission_type is None or line.commission_type == commission_type),
            Decimal(0),
        )

    def exclusion_counts(self) -> Counter[ExclusionReason]:
        return Counter(exclusion.reason for exclusion in self.exclusions)


def compute_month(
    catalog: Catalog,
    perimeter_code: str,
    month: str,
    current: Sequence[ContractRecord],
    previous: Sequence[ContractRecord] = (),
    premiums: Sequence[PremiumRecord] = (),
) -> MonthlyResult:
    perimeter = catalog.perimeter(perimeter_code)
    if not perimeter.active:
        raise ValueError(f"Le périmètre {perimeter.code} est désactivé : aucun calcul n'est effectué")
    first_day = parse_month(month)
    precompte = compute_precompte(perimeter, catalog, first_day, current, previous)
    lineaire = compute_lineaire(perimeter, catalog, first_day, premiums)
    return MonthlyResult(
        perimeter=perimeter.code,
        month=format_month(first_day),
        lines=precompte.lines + lineaire.lines,
        exclusions=precompte.exclusions + lineaire.exclusions,
    )


def simulate_contract(
    catalog: Catalog,
    perimeter_code: str,
    month: str,
    current: ContractRecord,
    previous: ContractRecord | None = None,
) -> MonthlyResult:
    """Calcule le mouvement d'un seul contrat entre M-1 et M (simulateur, appel d'outil par l'assistant)."""
    return compute_month(catalog, perimeter_code, month, [current], [previous] if previous else [])
