from decimal import Decimal

import pytest
from helpers import contract, make_catalog, premium

from commission_engine import CommissionType, compute_month, simulate_contract
from commission_engine.csv_io import read_contracts, read_premiums, write_contracts, write_premiums


def test_inactive_perimeter_is_refused():
    with pytest.raises(ValueError, match="désactivé"):
        compute_month(make_catalog(), "INACTIF", "2026-03", [contract()])


def test_invalid_month_is_refused():
    with pytest.raises(ValueError, match="AAAA-MM"):
        compute_month(make_catalog(), "SANTE", "mars 2026", [contract()])


def test_totals_by_commission_type():
    result = compute_month(make_catalog(), "SANTE", "2026-03", [contract(premium="1200")], [], [premium()])
    assert result.total(CommissionType.P) == Decimal("1200.00")
    assert result.total(CommissionType.L) == Decimal("10.00")
    assert result.total() == Decimal("1210.00")


def test_simulate_single_contract():
    common = {"subscription": "2026-01-20", "effective": "2026-02-01", "premium": "900"}
    result = simulate_contract(make_catalog(), "SANTE", "2026-03",
                               current=contract(**common, state="Sans effet"), previous=contract(**common))
    assert result.total() == Decimal("-900.00")


def test_csv_round_trip(tmp_path):
    contracts = [contract(end="2026-03-15", file_rate_year_1=Decimal("0.38")), contract("C-002")]
    premiums = [premium()]
    write_contracts(tmp_path / "contracts.csv", contracts)
    write_premiums(tmp_path / "premiums.csv", premiums)
    assert read_contracts(tmp_path / "contracts.csv") == contracts
    assert read_premiums(tmp_path / "premiums.csv") == premiums


def test_csv_with_missing_columns_is_refused(tmp_path):
    path = tmp_path / "contracts.csv"
    path.write_text("contract_id,product\nC-1,BASE\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colonnes obligatoires"):
        read_contracts(path)
