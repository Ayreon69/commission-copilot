from decimal import Decimal

import pytest
from helpers import make_catalog, premium

from commission_engine import CommissionType, ExclusionReason, compute_month


@pytest.fixture(scope="module")
def catalog():
    return make_catalog()


def run(catalog, premiums, perimeter="SANTE"):
    return compute_month(catalog, perimeter, "2026-03", [], [], premiums)


def test_premium_after_first_year_earns_linear_commission(catalog):
    result = run(catalog, [premium(amount="100")])
    line = result.lines[0]
    assert (line.commission_type, line.amount, line.rule_id) == (CommissionType.L, Decimal("10.00"), "R-L1")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"movement": "A01"}, ExclusionReason.LINEAR_MOVEMENT),
        ({"movement": "E01"}, ExclusionReason.LINEAR_MOVEMENT),
        ({"premium_type": "P2"}, ExclusionReason.LINEAR_PREMIUM_TYPE),
        ({"product": "EXCLU"}, ExclusionReason.LINEAR_PRODUCT),
        ({"effective": "2025-06-01", "subscription": "2025-05-20"}, ExclusionReason.LINEAR_FIRST_YEAR),
        ({"effective": "2025-04-01", "subscription": "2025-03-20"}, ExclusionReason.LINEAR_FIRST_YEAR),
        ({"product": "INCONNU"}, ExclusionReason.MISSING_RATE),
    ],
)
def test_linear_exclusions(catalog, overrides, reason):
    result = run(catalog, [premium(**overrides)])
    assert not result.lines
    assert result.exclusions[0].reason == reason


def test_perimeter_without_first_year_filter_pays_linear_immediately(catalog):
    record = premium(product="PREV", subscription="2025-12-15", effective="2026-01-01")
    assert run(catalog, [record], perimeter="FICHIER").lines[0].amount == Decimal("5.00")
