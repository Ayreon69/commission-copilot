from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal
from typing import Any

from commission_engine.catalog import Catalog
from commission_engine.models import ContractRecord, PremiumRecord

TEST_CATALOG: dict[str, Any] = {
    "company": {"name": "Cabinet de test"},
    "insurers": [{"code": "INS", "label": "Assureur de test"}],
    "perimeters": [
        {
            "code": "SANTE",
            "label": "Santé",
            "insurer": "INS",
            "line_of_business": "SANTE",
            "key_strategy": "CONTRACT",
            "exposure_base": "MONTHS_12",
            "tariff_regularisation": True,
            "seniority_months": 16,
            "old_contract_threshold_years": 1,
            "rate_overrides": [{"guarantee": "OPTION", "rate_year_1": "0.20", "reason": "Option à taux réduit"}],
            "product_rules": [{"contract_prefix": "MIG", "product": "REPRIS", "reason": "Portefeuille repris"}],
            "linear": {
                "excluded_movement_prefixes": ["A", "E"],
                "excluded_premium_types": ["P2"],
                "excluded_products": ["EXCLU"],
                "first_year_filter": True,
            },
        },
        {
            "code": "FICHIER",
            "label": "Taux fichier",
            "insurer": "INS",
            "line_of_business": "PREVOYANCE",
            "key_strategy": "GUARANTEE",
            "exposure_base": "DAYS_365",
            "rate_source": "INSURER_FILE",
            "max_future_effect_months": 4,
            "rate_overrides": [{"segment": "PRIMO", "rate_year_1": "0.30", "reason": "Primo-accédants"}],
            "linear": {"first_year_filter": False},
        },
        {
            "code": "INACTIF",
            "label": "Arrêté",
            "insurer": "INS",
            "line_of_business": "SANTE",
            "key_strategy": "CONTRACT",
            "exposure_base": "MONTHS_12",
            "active": False,
        },
    ],
    "products": [
        {
            "code": "BASE", "label": "Produit de base", "perimeter": "SANTE",
            "year_1": [{"rate": "0.80", "start": "2018-01-01", "end": "2023-12-31"},
                       {"rate": "1.00", "start": "2024-01-01"}],
            "year_2_plus": [{"rate": "0.10", "start": "2018-01-01"}],
        },
        {
            "code": "REPRIS", "label": "Produit repris", "perimeter": "SANTE",
            "year_1": [{"rate": "0.50", "start": "2018-01-01"}],
            "year_2_plus": [{"rate": "0.10", "start": "2018-01-01"}],
        },
        {
            "code": "EXCLU", "label": "Produit sans linéaire", "perimeter": "SANTE",
            "year_1": [{"rate": "0.50", "start": "2018-01-01"}],
            "year_2_plus": [{"rate": "0.10", "start": "2018-01-01"}],
        },
        {
            "code": "PREV", "label": "Prévoyance", "perimeter": "FICHIER",
            "year_1": [{"rate": "0.40", "start": "2018-01-01"}],
            "year_2_plus": [{"rate": "0.05", "start": "2018-01-01"}],
        },
    ],
}


def catalog_data() -> dict[str, Any]:
    return copy.deepcopy(TEST_CATALOG)


def make_catalog() -> Catalog:
    return Catalog.from_dict(catalog_data())


def contract(
    contract_id: str = "C-001",
    *,
    product: str = "BASE",
    state: str = "En cours",
    subscription: str = "2026-02-10",
    effective: str = "2026-03-01",
    premium: str = "1200",
    end: str | None = None,
    **extra: Any,
) -> ContractRecord:
    return ContractRecord(
        contract_id=contract_id,
        product=product,
        state=state,
        subscription_date=date.fromisoformat(subscription),
        effective_date=date.fromisoformat(effective),
        annual_premium=Decimal(premium),
        end_date=date.fromisoformat(end) if end else None,
        **extra,
    )


def premium(
    contract_id: str = "C-001",
    *,
    product: str = "BASE",
    subscription: str = "2023-12-01",
    effective: str = "2024-01-01",
    period: str = "2026-03-01",
    amount: str = "100",
    movement: str = "C01",
    premium_type: str = "P1",
) -> PremiumRecord:
    return PremiumRecord(
        contract_id=contract_id,
        product=product,
        subscription_date=date.fromisoformat(subscription),
        effective_date=date.fromisoformat(effective),
        period_start=date.fromisoformat(period),
        amount_excl_tax=Decimal(amount),
        movement=movement,
        premium_type=premium_type,
    )
