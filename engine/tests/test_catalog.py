from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from helpers import catalog_data, contract, make_catalog

from commission_engine.catalog import Catalog

REAL_CATALOG = Path(__file__).resolve().parents[2] / "data" / "catalog.json"


def test_rate_depends_on_subscription_date():
    catalog = make_catalog()
    sante = catalog.perimeter("SANTE")
    assert catalog.resolve_rate_year_1(sante, contract(subscription="2023-12-31")).rate == Decimal("0.80")
    assert catalog.resolve_rate_year_1(sante, contract(subscription="2024-01-01")).rate == Decimal("1.00")
    assert catalog.resolve_rate_year_1(sante, contract(subscription="2017-12-31")) is None


def test_override_wins_over_insurer_file_and_grid():
    catalog = make_catalog()
    fichier = catalog.perimeter("FICHIER")
    record = contract(product="PREV", segment="PRIMO", file_rate_year_1=Decimal("0.38"))
    resolution = catalog.resolve_rate_year_1(fichier, record)
    assert resolution.rate == Decimal("0.30")
    assert "Primo-accédants" in resolution.source


def test_insurer_file_rate_falls_back_to_grid():
    catalog = make_catalog()
    fichier = catalog.perimeter("FICHIER")
    assert catalog.resolve_rate_year_1(fichier, contract(product="PREV", file_rate_year_1=Decimal("0.38"))).rate \
        == Decimal("0.38")
    assert catalog.resolve_rate_year_1(fichier, contract(product="PREV")).rate == Decimal("0.40")


def test_product_of_another_perimeter_has_no_rate():
    catalog = make_catalog()
    assert catalog.resolve_rate_year_1(catalog.perimeter("SANTE"), contract(product="PREV")) is None
    assert catalog.resolve_rate_year_2_plus(catalog.perimeter("SANTE"), "PREV", date(2024, 1, 1)) is None


def test_lookups_ignore_case_and_accents():
    catalog = make_catalog()
    assert catalog.perimeter("sante").code == "SANTE"
    assert catalog.product(" base ").code == "BASE"


def test_unknown_perimeter_lists_available_codes():
    with pytest.raises(KeyError, match="SANTE"):
        make_catalog().perimeter("AUTO")


def test_overlapping_rate_windows_are_rejected():
    data = catalog_data()
    data["products"][0]["year_1"][1]["start"] = "2023-06-01"
    with pytest.raises(ValueError, match="chevauchent"):
        Catalog.from_dict(data)


def test_override_without_target_is_rejected():
    data = catalog_data()
    data["perimeters"][0]["rate_overrides"] = [{"rate_year_1": "0.5", "reason": "trop large"}]
    with pytest.raises(ValueError, match="doit cibler"):
        Catalog.from_dict(data)


def test_product_with_unknown_perimeter_is_rejected():
    data = catalog_data()
    data["products"][0]["perimeter"] = "AUTO"
    with pytest.raises(ValueError, match="périmètre inconnu"):
        Catalog.from_dict(data)


def test_demo_catalog_is_valid():
    catalog = Catalog.load(REAL_CATALOG)
    assert catalog.company["name"]
    assert any(not p.active for p in catalog.perimeters.values())
