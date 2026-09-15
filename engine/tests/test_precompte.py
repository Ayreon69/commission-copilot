from decimal import Decimal

import pytest
from helpers import contract, make_catalog

from commission_engine import CommissionType, ExclusionReason, compute_month


@pytest.fixture(scope="module")
def catalog():
    return make_catalog()


def run(catalog, current, previous=(), perimeter="SANTE"):
    return compute_month(catalog, perimeter, "2026-03", current, previous)


def single_line(result):
    assert len(result.lines) == 1, result
    return result.lines[0]


def single_exclusion(result):
    assert not result.lines, result
    assert len(result.exclusions) == 1, result
    return result.exclusions[0]


def test_new_business_earns_first_year_commission(catalog):
    line = single_line(run(catalog, [contract(premium="1200")]))
    assert line.commission_type == CommissionType.P
    assert line.amount == Decimal("1200.00")
    assert line.rule_id == "R-P1"
    assert line.formula == "1 200,00 € × 100 % = 1 200,00 €"


def test_contract_already_present_last_month_earns_nothing(catalog):
    record = contract(effective="2025-11-01", subscription="2025-10-20")
    assert single_exclusion(run(catalog, [record], [record])).reason == ExclusionReason.ALREADY_KNOWN


def test_state_labels_are_normalised_before_comparison(catalog):
    previous = contract(effective="2025-11-01", subscription="2025-10-20", state="En cours")
    current = contract(effective="2025-11-01", subscription="2025-10-20", state="Suspendu")
    assert single_exclusion(run(catalog, [current], [previous])).reason == ExclusionReason.ALREADY_KNOWN


def test_contract_without_effect_triggers_full_clawback(catalog):
    previous = contract(subscription="2026-01-20", effective="2026-02-01", premium="900")
    current = contract(subscription="2026-01-20", effective="2026-02-01", premium="900", state="Sans effet")
    line = single_line(run(catalog, [current], [previous]))
    assert (line.commission_type, line.amount, line.rule_id) == (CommissionType.RP, Decimal("-900.00"), "R-RP1")


def test_termination_claws_back_the_uncovered_share(catalog):
    common = {"subscription": "2025-09-20", "effective": "2025-10-01", "premium": "1000"}
    previous = contract(**common)
    current = contract(**common, state="Résilié", end="2026-03-15")
    line = single_line(run(catalog, [current], [previous]))
    # 6 mois entamés sur 12 : 50 % du précompte reste acquis, 50 % est repris.
    assert (line.commission_type, line.amount, line.rule_id) == (CommissionType.RP, Decimal("-500.00"), "R-RP2")
    assert line.formula == ("(1 000,00 € × 100 % × 6/12) − (1 000,00 € × 100 %) = "
                            "500,00 € − 1 000,00 € = −500,00 €")


def test_termination_after_a_full_year_is_not_clawed_back(catalog):
    common = {"subscription": "2025-03-20", "effective": "2025-04-01"}
    previous = contract(**common)
    current = contract(**common, state="Résilié", end="2026-03-31")
    assert single_exclusion(run(catalog, [current], [previous])).reason == ExclusionReason.FULL_YEAR_SERVED


def test_termination_without_active_history_is_ignored(catalog):
    record = contract(state="Résilié", subscription="2025-11-20", effective="2025-12-01", end="2026-03-10")
    assert single_exclusion(run(catalog, [record])).reason == ExclusionReason.STABLE_TERMINATION


def test_switch_between_without_effect_and_terminated_is_an_anomaly(catalog):
    common = {"subscription": "2025-12-20", "effective": "2026-01-01"}
    previous = contract(**common, state="Sans effet")
    current = contract(**common, state="Résilié", end="2026-03-01")
    assert single_exclusion(run(catalog, [current], [previous])).reason == ExclusionReason.STATE_ANOMALY


def test_zero_duration_contract_is_ignored(catalog):
    record = contract(effective="2026-03-05", end="2026-03-05")
    assert single_exclusion(run(catalog, [record])).reason == ExclusionReason.ZERO_DURATION


def test_old_contract_is_excluded(catalog):
    record = contract(subscription="2025-01-01", effective="2025-01-15")
    assert single_exclusion(run(catalog, [record])).reason == ExclusionReason.OLD_CONTRACT


def test_contract_before_seniority_limit_is_excluded(catalog):
    record = contract(subscription="2024-09-15", effective="2024-10-01")
    assert single_exclusion(run(catalog, [record])).reason == ExclusionReason.SENIORITY


def test_unknown_state_is_reported(catalog):
    assert single_exclusion(run(catalog, [contract(state="En attente")])).reason == ExclusionReason.UNKNOWN_STATE


def test_missing_rate_is_reported(catalog):
    assert single_exclusion(run(catalog, [contract(product="INCONNU")])).reason == ExclusionReason.MISSING_RATE


@pytest.mark.parametrize(
    ("new_premium", "expected_type", "expected_amount"),
    [("1100", CommissionType.P, Decimal("100.00")), ("850", CommissionType.RP, Decimal("-150.00"))],
)
def test_premium_change_is_regularised(catalog, new_premium, expected_type, expected_amount):
    common = {"subscription": "2026-01-10", "effective": "2026-02-01"}
    previous = contract(**common, premium="1000")
    current = contract(**common, premium=new_premium)
    line = single_line(run(catalog, [current], [previous]))
    assert (line.commission_type, line.amount, line.rule_id) == (expected_type, expected_amount, "R-REG")


def test_premium_change_without_regularisation_policy(catalog):
    common = {"product": "PREV", "subscription": "2026-01-10", "effective": "2026-02-01"}
    previous = contract(**common, premium="1000")
    current = contract(**common, premium="1100")
    exclusion = single_exclusion(run(catalog, [current], [previous], perimeter="FICHIER"))
    assert exclusion.reason == ExclusionReason.ALREADY_KNOWN
    assert "régularisation" in exclusion.detail


def test_guarantee_override_applies_reduced_rate(catalog):
    line = single_line(run(catalog, [contract(premium="500", guarantee="OPTION")]))
    assert line.amount == Decimal("100.00")
    assert "Option à taux réduit" in line.rate_source


def test_contract_prefix_reassigns_product(catalog):
    line = single_line(run(catalog, [contract("MIG-001", premium="400")]))
    assert (line.product, line.amount) == ("REPRIS", Decimal("200.00"))


def test_insurer_file_rate_is_used(catalog):
    record = contract(product="PREV", premium="1000", file_rate_year_1=Decimal("0.38"))
    assert single_line(run(catalog, [record], perimeter="FICHIER")).amount == Decimal("380.00")


@pytest.mark.parametrize(("effective", "excluded"), [("2026-06-30", False), ("2026-07-01", True)])
def test_effect_too_far_in_the_future_is_excluded(catalog, effective, excluded):
    result = run(catalog, [contract(product="PREV", subscription="2026-02-01", effective=effective)],
                 perimeter="FICHIER")
    assert bool(result.exclusions) is excluded
    if excluded:
        assert result.exclusions[0].reason == ExclusionReason.FUTURE_EFFECT


def test_guarantee_key_commissions_each_guarantee(catalog):
    records = [contract("G-1", product="PREV", guarantee="DECES"), contract("G-1", product="PREV", guarantee="IJ")]
    assert len(run(catalog, records, perimeter="FICHIER").lines) == 2
