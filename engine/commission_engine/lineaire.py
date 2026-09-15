"""Commissions linéaires (L) : pourcentage des cotisations encaissées à partir de la deuxième année."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date

from .catalog import Catalog, Perimeter
from .exposure import describe_exposure, exposure
from .formatting import format_date, format_eur, format_rate
from .models import (
    CommissionLine,
    CommissionType,
    Exclusion,
    ExclusionReason,
    PremiumRecord,
    SectionResult,
    normalize_token,
    round_money,
)


def compute_lineaire(
    perimeter: Perimeter, catalog: Catalog, month: date, premiums: Sequence[PremiumRecord]
) -> SectionResult:
    lines: list[CommissionLine] = []
    exclusions: list[Exclusion] = []
    for record in premiums:
        record = replace(record, product=perimeter.product_for(record.contract_id, record.product))
        outcome = _linear_outcome(record, perimeter, catalog)
        if isinstance(outcome, CommissionLine):
            lines.append(outcome)
        else:
            exclusions.append(outcome)
    return SectionResult(tuple(lines), tuple(exclusions))


def _linear_outcome(record: PremiumRecord, perimeter: Perimeter, catalog: Catalog) -> CommissionLine | Exclusion:
    policy = perimeter.linear
    movement = normalize_token(record.movement)
    if movement and any(movement.startswith(normalize_token(p)) for p in policy.excluded_movement_prefixes):
        return Exclusion(record.contract_id, ExclusionReason.LINEAR_MOVEMENT, f"Mouvement « {record.movement} »")
    if normalize_token(record.premium_type) in {normalize_token(t) for t in policy.excluded_premium_types}:
        return Exclusion(record.contract_id, ExclusionReason.LINEAR_PREMIUM_TYPE,
                         f"Type de cotisation « {record.premium_type} »")
    if policy.first_year_filter:
        share = exposure(record.effective_date, record.period_start, perimeter.exposure_base)
        if share <= 1:
            fraction = describe_exposure(record.effective_date, record.period_start, perimeter.exposure_base)
            return Exclusion(record.contract_id, ExclusionReason.LINEAR_FIRST_YEAR,
                             f"Exposition {fraction} ≤ 1 au {format_date(record.period_start)}")
    if normalize_token(record.product) in {normalize_token(p) for p in policy.excluded_products}:
        return Exclusion(record.contract_id, ExclusionReason.LINEAR_PRODUCT, f"Produit « {record.product} »")

    resolution = catalog.resolve_rate_year_2_plus(perimeter, record.product, record.subscription_date)
    if resolution is None:
        return Exclusion(record.contract_id, ExclusionReason.MISSING_RATE,
                         f"Aucun taux années 2+ pour « {record.product} » souscrit le "
                         f"{format_date(record.subscription_date)}")
    amount = round_money(record.amount_excl_tax * resolution.rate)
    formula = f"{format_eur(record.amount_excl_tax)} × {format_rate(resolution.rate)} = {format_eur(amount)}"
    return CommissionLine(record.contract_id, record.product, CommissionType.L, amount, "R-L1", formula,
                          resolution.source)
