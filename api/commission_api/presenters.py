"""Conversion des objets du moteur en réponses d'API lisibles (libellés français, montants affichables)."""

from __future__ import annotations

from decimal import Decimal

from commission_engine import Catalog, CommissionLine, CommissionType, Exclusion, MonthlyResult
from commission_engine.catalog import Perimeter, Product, RateSource, RateWindow
from commission_engine.exposure import ExposureBase
from commission_engine.formatting import format_eur, format_rate
from commission_engine.keys import KeyStrategy
from commission_engine.models import RULE_LABELS, normalize_token

from .schemas import (
    AmountOut,
    CalculationOut,
    CommissionLineOut,
    ExclusionOut,
    LinearPolicyOut,
    PerimeterDetailsOut,
    PerimeterSummaryOut,
    ProductOut,
    ProductRuleOut,
    RateOverrideOut,
    RateWindowOut,
    TotalsOut,
)

COMMISSION_LABELS = {CommissionType.P: "Précompte", CommissionType.RP: "Reprise", CommissionType.L: "Linéaire"}

KEY_STRATEGY_LABELS = {
    KeyStrategy.CONTRACT: "n° de contrat + état + date de souscription",
    KeyStrategy.GUARANTEE: "souscripteur + bénéficiaire + n° de contrat + état + garantie",
    KeyStrategy.CONTRACT_GUARANTEE: "n° de contrat + état + garantie",
    KeyStrategy.PERSON_GUARANTEE: "n° de personne + état + garantie",
}

EXPOSURE_LABELS = {
    ExposureBase.MONTHS_12: "mois entamés sur 12",
    ExposureBase.MONTHS_24: "mois entamés sur 24",
    ExposureBase.DAYS_365: "jours sur 365",
    ExposureBase.DAYS_365_25: "jours sur 365,25",
    ExposureBase.DAYS_730: "jours sur 730",
    ExposureBase.ANNIVERSARY: "jours jusqu'à la date anniversaire du contrat",
}

RATE_SOURCE_LABELS = {
    RateSource.REFERENTIAL: "grille du produit",
    RateSource.INSURER_FILE: "taux transmis par l'assureur, grille du produit en secours",
}


def amount_out(value: Decimal) -> AmountOut:
    return AmountOut(value=value, display=format_eur(value))


def line_out(line: CommissionLine) -> CommissionLineOut:
    return CommissionLineOut(
        contract_id=line.contract_id,
        product=line.product,
        commission_type=line.commission_type.value,
        commission_label=COMMISSION_LABELS[line.commission_type],
        amount=line.amount,
        amount_display=format_eur(line.amount),
        rule_id=line.rule_id,
        rule_label=RULE_LABELS.get(line.rule_id, line.rule_id),
        formula=line.formula,
        rate_source=line.rate_source,
    )


def exclusion_out(exclusion: Exclusion) -> ExclusionOut:
    return ExclusionOut(contract_id=exclusion.contract_id, code=exclusion.reason.value, label=exclusion.label,
                        detail=exclusion.detail)


def calculation_out(result: MonthlyResult) -> CalculationOut:
    return CalculationOut(
        perimeter=result.perimeter,
        month=result.month,
        lines=[line_out(line) for line in result.lines],
        exclusions=[exclusion_out(exclusion) for exclusion in result.exclusions],
        totals=TotalsOut(
            precompte=amount_out(result.total(CommissionType.P)),
            reprises=amount_out(result.total(CommissionType.RP)),
            lineaire=amount_out(result.total(CommissionType.L)),
            net=amount_out(result.total()),
        ),
    )


def perimeter_summary(catalog: Catalog, perimeter: Perimeter) -> PerimeterSummaryOut:
    return PerimeterSummaryOut(
        code=perimeter.code,
        label=perimeter.label,
        description=perimeter.description,
        insurer=catalog.insurers.get(normalize_token(perimeter.insurer), perimeter.insurer),
        line_of_business=perimeter.line_of_business,
        active=perimeter.active,
    )


def perimeter_details(catalog: Catalog, perimeter: Perimeter) -> PerimeterDetailsOut:
    products = [p for p in catalog.products.values() if normalize_token(p.perimeter) == normalize_token(perimeter.code)]
    return PerimeterDetailsOut(
        **perimeter_summary(catalog, perimeter).model_dump(),
        key_strategy=perimeter.key_strategy.value,
        key_strategy_label=KEY_STRATEGY_LABELS[perimeter.key_strategy],
        exposure_base=perimeter.exposure_base.value,
        exposure_base_label=EXPOSURE_LABELS[perimeter.exposure_base],
        rate_source=perimeter.rate_source.value,
        rate_source_label=RATE_SOURCE_LABELS[perimeter.rate_source],
        tariff_regularisation=perimeter.tariff_regularisation,
        seniority_months=perimeter.seniority_months,
        old_contract_threshold_years=perimeter.old_contract_threshold_years,
        max_future_effect_months=perimeter.max_future_effect_months,
        rate_overrides=[
            RateOverrideOut(rate=o.rate_year_1, display=format_rate(o.rate_year_1), reason=o.reason,
                            product=o.product, guarantee=o.guarantee, segment=o.segment)
            for o in perimeter.rate_overrides
        ],
        product_rules=[ProductRuleOut(contract_prefix=r.contract_prefix, product=r.product, reason=r.reason)
                       for r in perimeter.product_rules],
        linear=LinearPolicyOut(
            excluded_movement_prefixes=list(perimeter.linear.excluded_movement_prefixes),
            excluded_premium_types=list(perimeter.linear.excluded_premium_types),
            excluded_products=list(perimeter.linear.excluded_products),
            first_year_filter=perimeter.linear.first_year_filter,
        ),
        products=[_product_out(p) for p in products],
    )


def _product_out(product: Product) -> ProductOut:
    return ProductOut(code=product.code, label=product.label, year_1=[_window_out(w) for w in product.year_1],
                      year_2_plus=[_window_out(w) for w in product.year_2_plus])


def _window_out(window: RateWindow) -> RateWindowOut:
    return RateWindowOut(rate=window.rate, display=format_rate(window.rate), start=window.start, end=window.end)
