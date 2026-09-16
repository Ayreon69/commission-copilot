"""Vérifie que les bordereaux d'exemple sont à jour et illustrent bien chaque règle."""

import importlib.util
import sys
from pathlib import Path

import pytest

from commission_engine import Catalog, ExclusionReason, compute_month
from commission_engine.csv_io import read_contracts, read_premiums
from commission_engine.models import RULE_LABELS

ENGINE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ENGINE_DIR.parent / "data"
SAMPLES_DIR = DATA_DIR / "samples"

_spec = importlib.util.spec_from_file_location("generate_samples", ENGINE_DIR / "scripts" / "generate_samples.py")
generator = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = generator  # requis par @dataclass pendant l'exécution du module
_spec.loader.exec_module(generator)

CATALOG = Catalog.load(DATA_DIR / "catalog.json")


def test_committed_samples_match_generator(tmp_path):
    generator.generate(CATALOG, tmp_path)
    generated = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.csv")}
    committed = {p.relative_to(SAMPLES_DIR): p.read_bytes() for p in SAMPLES_DIR.rglob("*.csv")}
    assert generated.keys() == committed.keys()
    stale = [str(path) for path, content in generated.items() if committed[path] != content]
    assert not stale, f"Relancer scripts/generate_samples.py : {stale}"


def outcomes(code):
    folder = SAMPLES_DIR / code
    result = compute_month(CATALOG, code, "2026-03", read_contracts(folder / "contracts_2026-03.csv"),
                           read_contracts(folder / "contracts_2026-02.csv"))
    found = {line.contract_id: str(line.commission_type) for line in result.lines}
    found |= {exclusion.contract_id: str(exclusion.reason) for exclusion in result.exclusions}
    return found


@pytest.mark.parametrize("code", sorted(generator.PROFILES))
def test_scenarios_produce_expected_outcomes(code):
    perimeter = CATALOG.perimeter(code)
    prefix = generator.PROFILES[code].prefix
    expected = {
        "NOUVEAU": "P",
        "STABLE": ExclusionReason.ALREADY_KNOWN,
        "SANS-EFFET": "RP",
        "RESILIE": "RP",
        "RESILIE-SANS-HISTORIQUE": ExclusionReason.STABLE_TERMINATION,
        "ANOMALIE": ExclusionReason.STATE_ANOMALY,
        "ANCIEN": ExclusionReason.OLD_CONTRACT,
        "HAUSSE-PRIME": "P" if perimeter.tariff_regularisation else ExclusionReason.ALREADY_KNOWN,
        "BAISSE-PRIME": "RP" if perimeter.tariff_regularisation else ExclusionReason.ALREADY_KNOWN,
        "DUREE-NULLE": ExclusionReason.ZERO_DURATION,
        "PRODUIT-INCONNU": ExclusionReason.MISSING_RATE,
    }
    if perimeter.seniority_months is not None:
        expected["TROP-ANCIEN"] = ExclusionReason.SENIORITY
    if perimeter.max_future_effect_months is not None:
        expected["EFFET-DIFFERE"] = ExclusionReason.FUTURE_EFFECT

    found = outcomes(code)
    assert {f"{prefix}-{name}": found.get(f"{prefix}-{name}") for name in expected} == \
        {f"{prefix}-{name}": str(value) for name, value in expected.items()}


@pytest.mark.parametrize("code", sorted(generator.PROFILES))
def test_every_rule_used_has_a_label(code):
    folder = SAMPLES_DIR / code
    result = compute_month(CATALOG, code, "2026-03", read_contracts(folder / "contracts_2026-03.csv"),
                           read_contracts(folder / "contracts_2026-02.csv"),
                           read_premiums(folder / "premiums_2026-03.csv"))
    assert {line.rule_id for line in result.lines} <= set(RULE_LABELS)


@pytest.mark.parametrize("code", sorted(generator.PROFILES))
def test_samples_produce_linear_commissions(code):
    folder = SAMPLES_DIR / code
    result = compute_month(CATALOG, code, "2026-03", [], [], read_premiums(folder / "premiums_2026-03.csv"))
    assert result.lines
    assert result.exclusion_counts()[ExclusionReason.LINEAR_MOVEMENT] == 2
