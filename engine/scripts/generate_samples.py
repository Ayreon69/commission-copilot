"""Génère les bordereaux d'exemple (données 100 % fictives) utilisés par la démo et les tests.

    python scripts/generate_samples.py        (depuis le dossier engine/)

La génération est déterministe : relancer le script produit exactement les mêmes fichiers.
Chaque périmètre contient des contrats « scénario » dont le numéro décrit le cas illustré
(ex. SI-SANS-EFFET), noyés dans un portefeuille aléatoire réaliste.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from commission_engine.catalog import Catalog, Perimeter, RateSource  # noqa: E402
from commission_engine.csv_io import write_contracts, write_premiums  # noqa: E402
from commission_engine.models import ContractRecord, PremiumRecord, State, normalize_state, round_money  # noqa: E402
from commission_engine.periods import add_months, format_month  # noqa: E402

DATA_DIR = ENGINE_DIR.parent / "data"
SEED = 2026
CURRENT_MONTH = date(2026, 3, 1)
PREVIOUS_MONTH = add_months(CURRENT_MONTH, -1)


@dataclass(frozen=True)
class Profile:
    prefix: str
    products: tuple[str, ...]
    premium_range: tuple[int, int]


PROFILES = {
    "SANTE_INDIV": Profile("SI", ("NS-ESSENTIEL", "NS-CONFORT", "NS-SENIOR"), (600, 2400)),
    "PREVOYANCE_TNS": Profile("PT", ("CP-TNS-INDEMNITES", "CP-TNS-DECES"), (300, 1800)),
    "ANIMAUX": Profile("AN", ("VA-COMPAGNON", "VA-COMPAGNON-PLUS"), (120, 600)),
    "EMPRUNTEUR": Profile("EM", ("NE-EMPRUNT-CLASSIQUE", "NE-EMPRUNT-FLEX"), (200, 1500)),
    "DEPENDANCE": Profile("DE", ("CA-AUTONOMIE",), (400, 1600)),
}


class Portfolio:
    """Contrats de M-1 et de M, et cotisations encaissées en M, pour un périmètre."""

    def __init__(self, perimeter: Perimeter, profile: Profile, rng: random.Random):
        self.perimeter = perimeter
        self.profile = profile
        self.rng = rng
        self.previous: list[ContractRecord] = []
        self.current: list[ContractRecord] = []
        self.premiums: list[PremiumRecord] = []

    def contract(self, suffix: str, *, effective: date, state: str = "En cours", product: str | None = None,
                 end: date | None = None, contract_id: str | None = None, **extra) -> ContractRecord:
        contract_id = contract_id or f"{self.profile.prefix}-{suffix}"
        fields = {
            "subscriber_id": f"SOUS-{contract_id}",
            "beneficiary_code": "01",
            "person_id": f"PERS-{contract_id}",
            "guarantee": "BASE",
        }
        if self.perimeter.rate_source is RateSource.INSURER_FILE:
            fields["segment"] = self.rng.choice(["", "", "PRIMO", "RACHAT"])
            fields["file_rate_year_1"] = self.rng.choice([None, Decimal("0.36"), Decimal("0.38")])
        fields.update(extra)
        return ContractRecord(
            contract_id=contract_id,
            product=product or self.rng.choice(self.profile.products),
            state=state,
            subscription_date=effective - timedelta(days=self.rng.randint(0, 30)),
            effective_date=effective,
            annual_premium=Decimal(self.rng.randint(*self.profile.premium_range)),
            end_date=end,
            **fields,
        )

    def both_months(self, record: ContractRecord, **changes) -> None:
        self.previous.append(record)
        self.current.append(replace(record, **changes) if changes else record)

    def random_date(self, start: date, end: date) -> date:
        return start + timedelta(days=self.rng.randint(0, (end - start).days))


def build_scenarios(p: Portfolio) -> None:
    per = p.perimeter
    p.current.append(p.contract("NOUVEAU", effective=CURRENT_MONTH))
    p.both_months(p.contract("STABLE", effective=date(2025, 11, 1)))
    p.both_months(p.contract("SANS-EFFET", effective=PREVIOUS_MONTH), state="Sans effet")
    p.both_months(p.contract("RESILIE", effective=date(2025, 9, 1)), state="Résilié", end_date=date(2026, 3, 15))
    p.current.append(p.contract("RESILIE-SANS-HISTORIQUE", state="Résilié", effective=date(2025, 12, 1),
                                end=date(2026, 3, 10)))
    p.both_months(p.contract("ANOMALIE", state="Sans effet", effective=date(2026, 1, 1)),
                  state="Résilié", end_date=CURRENT_MONTH)
    old_effective = date(2024, 3, 1) if per.old_contract_threshold_years >= 2 else date(2025, 1, 15)
    p.current.append(p.contract("ANCIEN", effective=old_effective))
    if per.seniority_months is not None:
        p.current.append(p.contract("TROP-ANCIEN", effective=add_months(CURRENT_MONTH, -(per.seniority_months + 2))))
    if per.max_future_effect_months is not None:
        p.current.append(p.contract("EFFET-DIFFERE",
                                    effective=add_months(CURRENT_MONTH, per.max_future_effect_months + 1)))
    record = p.contract("HAUSSE-PRIME", effective=date(2026, 1, 1))
    p.both_months(record, annual_premium=round_money(record.annual_premium * Decimal("1.10")))
    record = p.contract("BAISSE-PRIME", effective=date(2026, 1, 1))
    p.both_months(record, annual_premium=round_money(record.annual_premium * Decimal("0.85")))
    p.current.append(p.contract("DUREE-NULLE", effective=date(2026, 3, 5), end=date(2026, 3, 5)))
    p.current.append(p.contract("PRODUIT-INCONNU", effective=CURRENT_MONTH, product="PRODUIT-INCONNU",
                                file_rate_year_1=None))

    for index, override in enumerate(per.rate_overrides, start=1):
        p.current.append(p.contract(
            f"TAUX-SPECIFIQUE-{index}", effective=CURRENT_MONTH, product=override.product,
            guarantee=override.guarantee or "BASE", segment=override.segment or "",
        ))
    for rule in per.product_rules:
        p.current.append(p.contract("", effective=CURRENT_MONTH,
                                    contract_id=f"{rule.contract_prefix}-{p.profile.prefix}-NOUVEAU"))


def build_random_portfolio(p: Portfolio) -> None:
    for index in range(1, 26):
        record = p.contract(f"{index:04d}", effective=p.random_date(date(2025, 5, 1), date(2026, 2, 1)),
                            state=p.rng.choice(["En cours"] * 4 + ["Suspendu", "Mis en demeure"]))
        roll = p.rng.random()
        if roll < 0.08 and record.effective_date >= date(2026, 1, 1):
            p.both_months(record, state="Sans effet")
        elif roll < 0.16:
            p.both_months(record, state="Résilié", end_date=CURRENT_MONTH + timedelta(days=p.rng.randint(0, 27)))
        else:
            p.both_months(record, state=p.rng.choice(["En cours", record.state]))
    for index in range(26, 34):
        p.current.append(p.contract(f"{index:04d}", effective=p.random_date(date(2026, 2, 15), date(2026, 4, 1))))


def build_premiums(p: Portfolio) -> None:
    def premium(contract_id: str, product: str, effective: date, annual: Decimal, **extra) -> PremiumRecord:
        fields = {"movement": "C01", "premium_type": "P1"} | extra
        return PremiumRecord(contract_id, product, effective - timedelta(days=p.rng.randint(0, 30)), effective,
                             CURRENT_MONTH, round_money(annual / 12), **fields)

    for record in p.current:
        if normalize_state(record.state) is State.AFN and record.effective_date <= CURRENT_MONTH:
            p.premiums.append(premium(record.contract_id, record.product, record.effective_date,
                                      record.annual_premium))
    # Contrats en portefeuille depuis plusieurs années : ils ne relèvent plus que du linéaire.
    for index in range(1, 16):
        p.premiums.append(premium(f"{p.profile.prefix}-PORTEFEUILLE-{index:03d}", p.rng.choice(p.profile.products),
                                  p.random_date(date(2022, 6, 1), date(2024, 12, 31)),
                                  Decimal(p.rng.randint(*p.profile.premium_range))))
    seasoned = date(2023, 5, 1)
    product = p.profile.products[0]
    p.premiums.append(premium(f"{p.profile.prefix}-ANNULATION", product, seasoned, Decimal(-900), movement="A01"))
    p.premiums.append(premium(f"{p.profile.prefix}-EXTOURNE", product, seasoned, Decimal(-600), movement="E01"))
    for premium_type in p.perimeter.linear.excluded_premium_types:
        p.premiums.append(premium(f"{p.profile.prefix}-COTISATION-{premium_type}", product, seasoned,
                                  Decimal(1200), premium_type=premium_type))
    for excluded in p.perimeter.linear.excluded_products:
        p.premiums.append(premium(f"{p.profile.prefix}-PRODUIT-SANS-LINEAIRE", excluded, seasoned, Decimal(1200)))


def generate(catalog: Catalog, output_dir: Path) -> None:
    for code, profile in PROFILES.items():
        perimeter = catalog.perimeter(code)
        portfolio = Portfolio(perimeter, profile, random.Random(f"{SEED}-{code}"))
        build_scenarios(portfolio)
        build_random_portfolio(portfolio)
        build_premiums(portfolio)

        folder = output_dir / perimeter.code
        write_contracts(folder / f"contracts_{format_month(PREVIOUS_MONTH)}.csv", portfolio.previous)
        write_contracts(folder / f"contracts_{format_month(CURRENT_MONTH)}.csv", portfolio.current)
        write_premiums(folder / f"premiums_{format_month(CURRENT_MONTH)}.csv", portfolio.premiums)


if __name__ == "__main__":
    generate(Catalog.load(DATA_DIR / "catalog.json"), DATA_DIR / "samples")
    print(f"Bordereaux générés dans {DATA_DIR / 'samples'}")
