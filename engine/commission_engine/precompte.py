"""Commissions précomptées (P) et reprises (RP) d'un mois M, par comparaison avec le bordereau de M-1.

Principe : seules les lignes dont la clé métier n'existait pas en M-1 génèrent un mouvement. Un contrat présent
deux mois de suite dans le même état a déjà été commissionné et ne produit rien, sauf régularisation de prime.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from .catalog import Catalog, Perimeter, RateResolution
from .exposure import ExposureBase, describe_exposure, exposure
from .formatting import format_date, format_eur, format_rate
from .keys import Key, business_key, lineage_key
from .models import (
    CommissionLine,
    CommissionType,
    ContractRecord,
    Exclusion,
    ExclusionReason,
    SectionResult,
    State,
    round_money,
)
from .periods import add_months, month_end
from .preparation import prepare_contracts

Outcome = CommissionLine | Exclusion


def compute_precompte(
    perimeter: Perimeter,
    catalog: Catalog,
    month: date,
    current: Sequence[ContractRecord],
    previous: Sequence[ContractRecord],
) -> SectionResult:
    # Même date limite absolue pour M et M-1, calculée à partir du mois M.
    cutoff = add_months(month, -perimeter.seniority_months) if perimeter.seniority_months is not None else None
    current_kept, exclusions = prepare_contracts(current, perimeter, month, cutoff)
    previous_kept, _ = prepare_contracts(previous, perimeter, add_months(month, -1), cutoff)

    old_ids = _old_contract_ids(current_kept, perimeter, month)
    exclusions.extend(
        Exclusion(r.contract_id, ExclusionReason.OLD_CONTRACT,
                  f"En portefeuille depuis au moins {perimeter.old_contract_threshold_years} an(s)")
        for r in current_kept if r.contract_id in old_ids
    )
    current_kept = [r for r in current_kept if r.contract_id not in old_ids]
    previous_kept = [r for r in previous_kept if r.contract_id not in old_ids]

    strategy = perimeter.key_strategy
    blocked = _blocked_transitions(current_kept, previous_kept, perimeter)
    previous_by_key: dict[Key, ContractRecord] = {}
    for record in previous_kept:
        previous_by_key.setdefault(business_key(record, strategy), record)

    lines: list[CommissionLine] = []
    for record in current_kept:
        key = business_key(record, strategy)
        known = previous_by_key.get(key)
        if key in blocked:
            reason, detail = blocked[key]
            outcome: Outcome = Exclusion(record.contract_id, reason, detail)
        elif known is None:
            outcome = _new_movement(record, perimeter, catalog, month)
        elif perimeter.tariff_regularisation and known.annual_premium != record.annual_premium:
            outcome = _regularisation(record, known, perimeter, catalog)
        else:
            outcome = _already_known(record, known)

        if isinstance(outcome, CommissionLine):
            lines.append(outcome)
        else:
            exclusions.append(outcome)
    return SectionResult(tuple(lines), tuple(exclusions))


def _old_contract_ids(records: Sequence[ContractRecord], perimeter: Perimeter, month: date) -> set[str]:
    reference = month_end(month)
    return {
        r.contract_id for r in records
        if exposure(r.effective_date, reference, ExposureBase.DAYS_365_25) >= perimeter.old_contract_threshold_years
    }


def _blocked_transitions(
    current: Sequence[ContractRecord], previous: Sequence[ContractRecord], perimeter: Perimeter
) -> dict[Key, tuple[ExclusionReason, str]]:
    """Compare le premier et le dernier état connu de chaque lignée sur M-1 et M.

    - passage sans effet <-> résilié : incohérent, la ligne est mise de côté ;
    - résilié ou sans effet dès la première apparition, et toujours : rien n'a été versé, rien à reprendre.
    """
    strategy = perimeter.key_strategy
    history: dict[Key, list[ContractRecord]] = {}
    for record in [*previous, *current]:
        history.setdefault(lineage_key(record, strategy), []).append(record)

    blocked: dict[Key, tuple[ExclusionReason, str]] = {}
    for records in history.values():
        first, last = State(records[0].state), State(records[-1].state)
        if {first, last} == {State.SEF, State.RES}:
            reason = ExclusionReason.STATE_ANOMALY
        elif first == last and first in (State.SEF, State.RES):
            reason = ExclusionReason.STABLE_TERMINATION
        else:
            continue
        blocked[business_key(records[-1], strategy)] = (reason, f"Transition {first} → {last}")
    return blocked


def _new_movement(record: ContractRecord, perimeter: Perimeter, catalog: Catalog, month: date) -> Outcome:
    resolution = catalog.resolve_rate_year_1(perimeter, record)
    if resolution is None:
        return _missing_rate(record)
    premium, rate = record.annual_premium, resolution.rate
    full = round_money(premium * rate)
    base = f"{format_eur(premium)} × {format_rate(rate)}"

    match State(record.state):
        case State.AFN:
            if record.end_date == record.effective_date:
                return Exclusion(record.contract_id, ExclusionReason.ZERO_DURATION,
                                 f"Effet et fin le même jour ({format_date(record.effective_date)})")
            return _line(record, CommissionType.P, full, "R-P1", f"{base} = {format_eur(full)}", resolution)
        case State.SEF:
            return _line(record, CommissionType.RP, -full, "R-RP1", f"−({base}) = {format_eur(-full)}", resolution)
        case State.RES:
            end = record.end_date or month_end(month)
            share = exposure(record.effective_date, end, perimeter.exposure_base)
            fraction = describe_exposure(record.effective_date, end, perimeter.exposure_base)
            if share >= 1:
                return Exclusion(record.contract_id, ExclusionReason.FULL_YEAR_SERVED, f"Exposition {fraction} ≥ 1")
            earned = round_money(premium * rate * share)
            amount = earned - full
            formula = (f"({base} × {fraction}) − ({base}) = "
                       f"{format_eur(earned)} − {format_eur(full)} = {format_eur(amount)}")
            return _line(record, CommissionType.RP, amount, "R-RP2", formula, resolution)


def _regularisation(
    record: ContractRecord, known: ContractRecord, perimeter: Perimeter, catalog: Catalog
) -> Outcome:
    resolution = catalog.resolve_rate_year_1(perimeter, record)
    if resolution is None:
        return _missing_rate(record)
    rate = resolution.rate
    new, old = round_money(record.annual_premium * rate), round_money(known.annual_premium * rate)
    delta = new - old
    if delta == 0:
        return _already_known(record, known)
    formula = (f"{format_eur(record.annual_premium)} × {format_rate(rate)} − "
               f"{format_eur(known.annual_premium)} × {format_rate(rate)} = {format_eur(delta)}")
    kind = CommissionType.P if delta > 0 else CommissionType.RP
    return _line(record, kind, delta, "R-REG", formula, resolution)


def _already_known(record: ContractRecord, known: ContractRecord) -> Exclusion:
    detail = ("Même clé qu'en M-1 ; la prime a changé mais le périmètre ne prévoit pas de régularisation"
              if known.annual_premium != record.annual_premium else "Même clé qu'en M-1 : déjà commissionné")
    return Exclusion(record.contract_id, ExclusionReason.ALREADY_KNOWN, detail)


def _missing_rate(record: ContractRecord) -> Exclusion:
    return Exclusion(record.contract_id, ExclusionReason.MISSING_RATE,
                     f"Aucun taux année 1 pour « {record.product} » souscrit le "
                     f"{format_date(record.subscription_date)}")


def _line(
    record: ContractRecord, kind: CommissionType, amount, rule_id: str, formula: str, resolution: RateResolution
) -> CommissionLine:
    return CommissionLine(record.contract_id, record.product, kind, amount, rule_id, formula, resolution.source)
