"""Préparation d'un bordereau de contrats : normalisation des états, produits réaffectés et filtres de dates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date

from .catalog import Perimeter
from .formatting import format_date
from .models import ContractRecord, Exclusion, ExclusionReason, normalize_state
from .periods import add_months


def prepare_contracts(
    records: Sequence[ContractRecord],
    perimeter: Perimeter,
    snapshot_month: date,
    seniority_cutoff: date | None,
) -> tuple[list[ContractRecord], list[Exclusion]]:
    future_limit = (add_months(snapshot_month, perimeter.max_future_effect_months)
                    if perimeter.max_future_effect_months is not None else None)
    kept: list[ContractRecord] = []
    exclusions: list[Exclusion] = []
    for record in records:
        state = normalize_state(record.state)
        if state is None:
            exclusions.append(Exclusion(record.contract_id, ExclusionReason.UNKNOWN_STATE,
                                        f"État « {record.state} » non reconnu"))
        elif future_limit is not None and record.effective_date >= future_limit:
            exclusions.append(Exclusion(
                record.contract_id, ExclusionReason.FUTURE_EFFECT,
                f"Effet au {format_date(record.effective_date)}, au-delà de la limite du {format_date(future_limit)}",
            ))
        elif seniority_cutoff is not None and record.effective_date < seniority_cutoff:
            exclusions.append(Exclusion(
                record.contract_id, ExclusionReason.SENIORITY,
                f"Effet au {format_date(record.effective_date)}, avant la limite du {format_date(seniority_cutoff)}",
            ))
        else:
            kept.append(replace(
                record,
                state=state.value,
                product=perimeter.product_for(record.contract_id, record.product),
            ))
    return kept, exclusions
