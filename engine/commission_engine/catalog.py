"""Catalogue de paramétrage : assureurs, périmètres, produits et grilles de taux.

Tout ce qui varie d'un périmètre à l'autre est déclaré ici (dans `data/catalog.json`) plutôt que codé en dur
dans le moteur : ajouter un périmètre ne demande aucune modification du code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

from .exposure import ExposureBase
from .formatting import format_date
from .keys import KeyStrategy
from .models import ContractRecord, normalize_token


class RateSource(StrEnum):
    REFERENTIAL = "REFERENTIAL"  # taux lu dans les grilles produit du catalogue
    INSURER_FILE = "INSURER_FILE"  # taux transmis ligne à ligne par l'assureur, grille produit en secours


@dataclass(frozen=True)
class RateWindow:
    rate: Decimal
    start: date
    end: date | None = None

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


@dataclass(frozen=True)
class Product:
    code: str
    label: str
    perimeter: str
    year_1: tuple[RateWindow, ...]
    year_2_plus: tuple[RateWindow, ...]


@dataclass(frozen=True)
class RateOverride:
    """Taux de première année imposé pour une combinaison produit / garantie / segment."""

    rate_year_1: Decimal
    reason: str
    product: str | None = None
    guarantee: str | None = None
    segment: str | None = None

    def matches(self, record: ContractRecord) -> bool:
        criteria = (
            (self.product, record.product),
            (self.guarantee, record.guarantee),
            (self.segment, record.segment),
        )
        return all(expected is None or normalize_token(expected) == normalize_token(actual)
                   for expected, actual in criteria)


@dataclass(frozen=True)
class ProductRule:
    """Réaffecte un produit selon le numéro de contrat (ex. portefeuille repris d'un autre gestionnaire)."""

    contract_prefix: str
    product: str
    reason: str

    def applies_to(self, contract_id: str) -> bool:
        return normalize_token(contract_id).startswith(normalize_token(self.contract_prefix))


@dataclass(frozen=True)
class LinearPolicy:
    excluded_movement_prefixes: tuple[str, ...] = ()
    excluded_premium_types: tuple[str, ...] = ()
    excluded_products: tuple[str, ...] = ()
    first_year_filter: bool = True


@dataclass(frozen=True)
class Perimeter:
    code: str
    label: str
    insurer: str
    line_of_business: str
    key_strategy: KeyStrategy
    exposure_base: ExposureBase
    active: bool = True
    description: str = ""
    rate_source: RateSource = RateSource.REFERENTIAL
    tariff_regularisation: bool = False
    seniority_months: int | None = None
    old_contract_threshold_years: Decimal = Decimal(1)
    max_future_effect_months: int | None = None
    rate_overrides: tuple[RateOverride, ...] = ()
    product_rules: tuple[ProductRule, ...] = ()
    linear: LinearPolicy = LinearPolicy()

    def product_for(self, contract_id: str, product: str) -> str:
        for rule in self.product_rules:
            if rule.applies_to(contract_id):
                return rule.product
        return product


@dataclass(frozen=True)
class RateResolution:
    rate: Decimal
    source: str


class Catalog:
    def __init__(
        self,
        company: dict[str, str],
        insurers: dict[str, str],
        perimeters: dict[str, Perimeter],
        products: dict[str, Product],
    ):
        self.company = company
        self.insurers = insurers
        self.perimeters = perimeters
        self.products = products
        self._validate()

    @classmethod
    def load(cls, path: str | Path) -> Catalog:
        with Path(path).open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh, parse_float=Decimal))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        insurers = {normalize_token(i["code"]): i["label"] for i in data["insurers"]}
        perimeters: dict[str, Perimeter] = {}
        for raw in data["perimeters"]:
            perimeter = _parse_perimeter(raw)
            _add_unique(perimeters, normalize_token(perimeter.code), perimeter, "Périmètre")
        products: dict[str, Product] = {}
        for raw in data["products"]:
            product = Product(
                code=raw["code"],
                label=raw["label"],
                perimeter=raw["perimeter"],
                year_1=_parse_windows(raw["year_1"], f"{raw['code']} (année 1)"),
                year_2_plus=_parse_windows(raw["year_2_plus"], f"{raw['code']} (années 2+)"),
            )
            _add_unique(products, normalize_token(product.code), product, "Produit")
        return cls(data.get("company", {}), insurers, perimeters, products)

    def perimeter(self, code: str) -> Perimeter:
        try:
            return self.perimeters[normalize_token(code)]
        except KeyError:
            known = ", ".join(p.code for p in self.perimeters.values())
            raise KeyError(f"Périmètre inconnu : {code!r} (périmètres disponibles : {known})") from None

    def product(self, code: str) -> Product | None:
        return self.products.get(normalize_token(code))

    def resolve_rate_year_1(self, perimeter: Perimeter, record: ContractRecord) -> RateResolution | None:
        """Ordre de priorité : taux spécifique du périmètre > taux du fichier assureur > grille produit."""
        for override in perimeter.rate_overrides:
            if override.matches(record):
                return RateResolution(override.rate_year_1, f"Taux spécifique : {override.reason}")
        if perimeter.rate_source is RateSource.INSURER_FILE and record.file_rate_year_1 is not None:
            return RateResolution(record.file_rate_year_1, "Taux transmis dans le fichier de l'assureur")
        return self._from_grid(perimeter, record.product, record.subscription_date, year_2_plus=False)

    def resolve_rate_year_2_plus(
        self, perimeter: Perimeter, product_code: str, subscription_date: date
    ) -> RateResolution | None:
        return self._from_grid(perimeter, product_code, subscription_date, year_2_plus=True)

    def _from_grid(
        self, perimeter: Perimeter, product_code: str, subscription_date: date, *, year_2_plus: bool
    ) -> RateResolution | None:
        # Le taux est figé par la date de souscription : il ne change jamais pour un même contrat.
        product = self.product(product_code)
        if product is None or normalize_token(product.perimeter) != normalize_token(perimeter.code):
            return None
        windows = product.year_2_plus if year_2_plus else product.year_1
        for window in windows:
            if window.covers(subscription_date):
                period = (f"du {format_date(window.start)} au {format_date(window.end)}" if window.end
                          else f"depuis le {format_date(window.start)}")
                grid = "années 2 et suivantes" if year_2_plus else "année 1"
                return RateResolution(window.rate, f"Grille {grid} du produit {product.label} ({period})")
        return None

    def _validate(self) -> None:
        for perimeter in self.perimeters.values():
            if normalize_token(perimeter.insurer) not in self.insurers:
                raise ValueError(f"Périmètre {perimeter.code} : assureur inconnu {perimeter.insurer!r}")
            for rule in perimeter.product_rules:
                target = self.product(rule.product)
                if target is None or normalize_token(target.perimeter) != normalize_token(perimeter.code):
                    raise ValueError(f"Périmètre {perimeter.code} : produit cible inconnu {rule.product!r}")
        for product in self.products.values():
            if normalize_token(product.perimeter) not in self.perimeters:
                raise ValueError(f"Produit {product.code} : périmètre inconnu {product.perimeter!r}")


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _add_unique(target: dict, key: str, value: Any, kind: str) -> None:
    if key in target:
        raise ValueError(f"{kind} défini deux fois : {key}")
    target[key] = value


def _parse_windows(raw: list[dict[str, Any]], label: str) -> tuple[RateWindow, ...]:
    windows = sorted(
        (RateWindow(_decimal(w["rate"]), date.fromisoformat(w["start"]),
                    date.fromisoformat(w["end"]) if w.get("end") else None) for w in raw),
        key=lambda w: w.start,
    )
    if not windows:
        raise ValueError(f"{label} : au moins une grille de taux est requise")
    for before, after in pairwise(windows):
        if before.end is None or before.end >= after.start:
            raise ValueError(f"{label} : grilles de taux qui se chevauchent ({before.start} et {after.start})")
    return tuple(windows)


def _parse_override(raw: dict[str, Any], perimeter_code: str) -> RateOverride:
    override = RateOverride(
        rate_year_1=_decimal(raw["rate_year_1"]),
        reason=raw["reason"],
        product=raw.get("product"),
        guarantee=raw.get("guarantee"),
        segment=raw.get("segment"),
    )
    if override.product is None and override.guarantee is None and override.segment is None:
        raise ValueError(f"Périmètre {perimeter_code} : un taux spécifique doit cibler un produit, "
                         "une garantie ou un segment")
    return override


def _parse_perimeter(raw: dict[str, Any]) -> Perimeter:
    code = raw["code"]
    linear = raw.get("linear", {})
    return Perimeter(
        code=code,
        label=raw["label"],
        insurer=raw["insurer"],
        line_of_business=raw["line_of_business"],
        key_strategy=KeyStrategy(raw["key_strategy"]),
        exposure_base=ExposureBase(raw["exposure_base"]),
        active=raw.get("active", True),
        description=raw.get("description", ""),
        rate_source=RateSource(raw.get("rate_source", RateSource.REFERENTIAL)),
        tariff_regularisation=raw.get("tariff_regularisation", False),
        seniority_months=raw.get("seniority_months"),
        old_contract_threshold_years=_decimal(raw.get("old_contract_threshold_years", 1)),
        max_future_effect_months=raw.get("max_future_effect_months"),
        rate_overrides=tuple(_parse_override(o, code) for o in raw.get("rate_overrides", [])),
        product_rules=tuple(
            ProductRule(r["contract_prefix"], r["product"], r["reason"]) for r in raw.get("product_rules", [])
        ),
        linear=LinearPolicy(
            excluded_movement_prefixes=tuple(linear.get("excluded_movement_prefixes", [])),
            excluded_premium_types=tuple(linear.get("excluded_premium_types", [])),
            excluded_products=tuple(linear.get("excluded_products", [])),
            first_year_filter=linear.get("first_year_filter", True),
        ),
    )
