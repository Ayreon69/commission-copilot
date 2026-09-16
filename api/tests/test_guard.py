from decimal import Decimal

import pytest

from commission_api.assistant.guard import amounts_in_text, unverified_amounts


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 044,50 €", Decimal("1044.50")),
        ("une reprise de −1 044,50 €", Decimal("1044.50")),
        ("475 €", Decimal("475")),
        ("1 440 euros", Decimal("1440")),
        ("1044,5€", Decimal("1044.50")),
        ("12 345,67 €", Decimal("12345.67")),
    ],
)
def test_french_amount_formats(text, expected):
    assert list(amounts_in_text(text)) == [expected]


def test_year_is_not_merged_with_following_amount():
    assert set(amounts_in_text("En 2026 1 200 € ont été versés")) == {Decimal("1200")}


def test_percentages_and_plain_numbers_are_ignored():
    assert amounts_in_text("un taux de 120 % sur 12 mois") == {}


def test_raw_values_of_tool_results_are_sources():
    payload = {"current_records": [{"annual_premium": "2089", "file_rate_year_1": None}]}
    assert unverified_amounts("Prime annuelle de 2 089 €.", [], [payload]) == []


def test_displayed_amounts_of_tool_results_are_sources():
    payload = {"lines": [{"amount": "-1044.50", "formula": "… = 1 462,30 € − 2 506,80 € = −1 044,50 €"}]}
    answer = "Sur 2 506,80 €, 1 462,30 € restent acquis : la reprise est de 1 044,50 €, et non 1 000 €."
    assert unverified_amounts(answer, [], [payload]) == ["1 000 €"]
