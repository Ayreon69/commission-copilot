from datetime import date
from decimal import Decimal

import pytest

from commission_engine.exposure import ExposureBase, describe_exposure, exposure


def test_same_day_contract_has_no_exposure():
    assert exposure(date(2026, 3, 5), date(2026, 3, 5), ExposureBase.DAYS_365) == 0


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        (ExposureBase.MONTHS_12, Decimal(3) / 12),  # janvier, février, mars entamés
        (ExposureBase.MONTHS_24, Decimal(3) / 24),
        (ExposureBase.DAYS_365, Decimal(55) / Decimal(365)),
        (ExposureBase.DAYS_365_25, Decimal(55) / Decimal("365.25")),
        (ExposureBase.DAYS_730, Decimal(55) / Decimal(730)),
    ],
)
def test_exposure_bases(base, expected):
    assert exposure(date(2026, 1, 15), date(2026, 3, 10), base) == expected


def test_anniversary_base_uses_real_contract_year():
    # Année 2026-2027 non bissextile : 365 jours jusqu'à l'anniversaire.
    assert exposure(date(2026, 1, 1), date(2026, 1, 31), ExposureBase.ANNIVERSARY) == Decimal(31) / 365


@pytest.mark.parametrize(
    ("base", "expected"),
    [(ExposureBase.MONTHS_12, "3/12"), (ExposureBase.DAYS_365_25, "55/365,25"), (ExposureBase.ANNIVERSARY, "55/365")],
)
def test_exposure_is_described_as_exact_fraction(base, expected):
    assert describe_exposure(date(2026, 1, 15), date(2026, 3, 10), base) == expected


def test_anniversary_of_february_29_falls_on_february_28():
    assert exposure(date(2024, 2, 29), date(2024, 3, 30), ExposureBase.ANNIVERSARY) == Decimal(31) / 365
