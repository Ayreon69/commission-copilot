"""Schémas d'entrée et de sortie de l'API, partagés avec les outils de l'assistant.

Les modèles de sortie alimentent le schéma OpenAPI, dont seront générés les types TypeScript de l'interface.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from commission_engine import ContractRecord
from commission_engine.models import normalize_state
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _check_state(value: str) -> str:
    if normalize_state(value) is None:
        raise ValueError("état inconnu : utiliser AFN (actif), SEF (sans effet) ou RES (résilié)")
    return value


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Entrées ------------------------------------------------------------------------------------------------------


class ContractInput(_Input):
    product: str = Field(min_length=1, max_length=60, description="Code produit, ex. NS-CONFORT")
    state: str = Field(min_length=1, max_length=40, description="AFN, SEF ou RES (libellés des assureurs acceptés)")
    subscription_date: date
    effective_date: date
    annual_premium: Decimal = Field(ge=0, le=10_000_000, description="Prime annuelle hors taxes, en euros")
    end_date: date | None = None
    guarantee: str = Field(default="", max_length=60)
    segment: str = Field(default="", max_length=60)
    file_rate_year_1: Decimal | None = Field(default=None, ge=0, le=10, description="Taux transmis par l'assureur")
    contract_id: str = Field(default="SIMULATION", min_length=1, max_length=60)

    @field_validator("state")
    @classmethod
    def _valid_state(cls, value: str) -> str:
        return _check_state(value)

    @model_validator(mode="after")
    def _consistent_dates(self) -> ContractInput:
        if self.end_date is not None and self.end_date < self.effective_date:
            raise ValueError("la date de fin ne peut pas précéder la date d'effet")
        return self

    def to_record(self) -> ContractRecord:
        return ContractRecord(
            contract_id=self.contract_id,
            product=self.product,
            state=self.state,
            subscription_date=self.subscription_date,
            effective_date=self.effective_date,
            annual_premium=self.annual_premium,
            end_date=self.end_date,
            guarantee=self.guarantee,
            segment=self.segment,
            file_rate_year_1=self.file_rate_year_1,
        )


class PreviousMonthInput(_Input):
    """Situation du même contrat le mois précédent : seuls l'état, la prime et la date de fin peuvent différer."""

    state: str = Field(min_length=1, max_length=40)
    annual_premium: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    end_date: date | None = None

    @field_validator("state")
    @classmethod
    def _valid_state(cls, value: str) -> str:
        return _check_state(value)


class SimulationRequest(_Input):
    perimeter: str = Field(min_length=1, max_length=40)
    month: str = Field(pattern=MONTH_PATTERN, description="Mois de calcul, AAAA-MM")
    contract: ContractInput
    previous_month: PreviousMonthInput | None = None

    def records(self) -> tuple[ContractRecord, ContractRecord | None]:
        current = self.contract.to_record()
        if self.previous_month is None:
            return current, None
        before = self.previous_month
        previous = replace(
            current,
            state=before.state,
            annual_premium=before.annual_premium if before.annual_premium is not None else current.annual_premium,
            end_date=before.end_date,
        )
        return current, previous


class PerimeterRequest(_Input):
    perimeter: str = Field(min_length=1, max_length=40)


class LookupRequest(_Input):
    perimeter: str = Field(min_length=1, max_length=40)
    contract_id: str = Field(min_length=1, max_length=60)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _ends_with_user(self) -> ChatRequest:
        if self.messages[-1].role != "user":
            raise ValueError("le dernier message doit venir de l'utilisateur")
        return self


# --- Sorties ------------------------------------------------------------------------------------------------------


class AmountOut(BaseModel):
    value: Decimal
    display: str


class CommissionLineOut(BaseModel):
    contract_id: str
    product: str
    commission_type: Literal["P", "RP", "L"]
    commission_label: str
    amount: Decimal
    amount_display: str
    rule_id: str
    rule_label: str
    formula: str
    rate_source: str


class ExclusionOut(BaseModel):
    contract_id: str
    code: str
    label: str
    detail: str


class TotalsOut(BaseModel):
    precompte: AmountOut
    reprises: AmountOut
    lineaire: AmountOut
    net: AmountOut


class CalculationOut(BaseModel):
    perimeter: str
    month: str
    lines: list[CommissionLineOut]
    exclusions: list[ExclusionOut]
    totals: TotalsOut


class RateWindowOut(BaseModel):
    rate: Decimal
    display: str
    start: date
    end: date | None


class ProductOut(BaseModel):
    code: str
    label: str
    year_1: list[RateWindowOut]
    year_2_plus: list[RateWindowOut]


class RateOverrideOut(BaseModel):
    rate: Decimal
    display: str
    reason: str
    product: str | None
    guarantee: str | None
    segment: str | None


class ProductRuleOut(BaseModel):
    contract_prefix: str
    product: str
    reason: str


class LinearPolicyOut(BaseModel):
    excluded_movement_prefixes: list[str]
    excluded_premium_types: list[str]
    excluded_products: list[str]
    first_year_filter: bool


class PerimeterSummaryOut(BaseModel):
    code: str
    label: str
    description: str
    insurer: str
    line_of_business: str
    active: bool


class PerimeterDetailsOut(PerimeterSummaryOut):
    key_strategy: str
    key_strategy_label: str
    exposure_base: str
    exposure_base_label: str
    rate_source: str
    rate_source_label: str
    tariff_regularisation: bool
    seniority_months: int | None
    old_contract_threshold_years: Decimal
    max_future_effect_months: int | None
    rate_overrides: list[RateOverrideOut]
    product_rules: list[ProductRuleOut]
    linear: LinearPolicyOut
    products: list[ProductOut]


class ContractRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_id: str
    product: str
    state: str
    subscription_date: date
    effective_date: date
    annual_premium: Decimal
    end_date: date | None
    guarantee: str
    segment: str
    file_rate_year_1: Decimal | None


class PremiumRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_id: str
    product: str
    subscription_date: date
    effective_date: date
    period_start: date
    amount_excl_tax: Decimal
    movement: str
    premium_type: str


class SampleContractOut(BaseModel):
    perimeter: str
    month: str
    previous_month: str
    contract_id: str
    previous_records: list[ContractRecordOut]
    current_records: list[ContractRecordOut]
    premiums: list[PremiumRecordOut]
    lines: list[CommissionLineOut]
    exclusions: list[ExclusionOut]


class ToolCallTrace(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    ok: bool


class CitationOut(BaseModel):
    rule_id: str
    label: str
    in_answer: bool = Field(description="L'identifiant de la règle figure dans le texte de la réponse")
    from_calculation: bool = Field(description="La règle a été appliquée par le moteur dans un résultat d'outil")


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallTrace]
    citations: list[CitationOut] = Field(description="Règles citées dans la réponse ou appliquées par le moteur")
    unverified_amounts: list[str] = Field(
        description="Montants cités par l'assistant qui ne proviennent d'aucune source (outil, règles, question)"
    )
    unknown_rules: list[str] = Field(description="Identifiants de règle cités qui n'existent pas")
    unknown_products: list[str] = Field(description="Noms de produits cités qui n'existent pas dans le catalogue")
    model: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    chat_enabled: bool
    model: str | None
