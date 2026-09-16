"""Structures de données du moteur : lignes de bordereaux en entrée, commissions et exclusions en sortie."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENT = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def normalize_token(value: object) -> str:
    """Majuscules, sans accents ni espaces superflus : compare des codes saisis différemment selon les fichiers."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.upper().split())


class State(StrEnum):
    AFN = "AFN"  # affaire nouvelle : contrat actif
    SEF = "SEF"  # sans effet : le contrat n'a jamais pris effet
    RES = "RES"  # résilié


_STATE_LABELS: dict[State, set[str]] = {
    State.AFN: {"AFN", "AFFAIRE NOUVELLE", "EN COURS", "EFFET FUTUR", "SUSPENDU", "SUS", "MIS EN DEMEURE", "MED"},
    State.SEF: {"SEF", "SANS EFFET"},
    State.RES: {"RES", "RESILIE"},
}


def normalize_state(raw: str) -> State | None:
    """Ramène les libellés d'état des assureurs aux trois états utiles au calcul."""
    label = normalize_token(raw)
    for state, labels in _STATE_LABELS.items():
        if label in labels:
            return state
    return None


class CommissionType(StrEnum):
    P = "P"  # précompte : commission de première année versée d'avance
    RP = "RP"  # reprise de précompte : montant à rembourser à l'assureur
    L = "L"  # linéaire : commission des années suivantes, au fil des cotisations


class ExclusionReason(StrEnum):
    UNKNOWN_STATE = "UNKNOWN_STATE"
    SENIORITY = "SENIORITY"
    FUTURE_EFFECT = "FUTURE_EFFECT"
    OLD_CONTRACT = "OLD_CONTRACT"
    ALREADY_KNOWN = "ALREADY_KNOWN"
    STATE_ANOMALY = "STATE_ANOMALY"
    STABLE_TERMINATION = "STABLE_TERMINATION"
    ZERO_DURATION = "ZERO_DURATION"
    FULL_YEAR_SERVED = "FULL_YEAR_SERVED"
    MISSING_RATE = "MISSING_RATE"
    LINEAR_MOVEMENT = "LINEAR_MOVEMENT"
    LINEAR_PREMIUM_TYPE = "LINEAR_PREMIUM_TYPE"
    LINEAR_PRODUCT = "LINEAR_PRODUCT"
    LINEAR_FIRST_YEAR = "LINEAR_FIRST_YEAR"


EXCLUSION_LABELS: dict[ExclusionReason, str] = {
    ExclusionReason.UNKNOWN_STATE: "État du contrat non reconnu",
    ExclusionReason.SENIORITY: "Date d'effet antérieure à la limite d'ancienneté",
    ExclusionReason.FUTURE_EFFECT: "Date d'effet trop éloignée dans le futur",
    ExclusionReason.OLD_CONTRACT: "Contrat ancien : précompte déjà acquis",
    ExclusionReason.ALREADY_KNOWN: "Déjà présent le mois précédent, sans changement",
    ExclusionReason.STATE_ANOMALY: "Anomalie : passage entre sans effet et résilié",
    ExclusionReason.STABLE_TERMINATION: "Contrat terminé sans historique actif",
    ExclusionReason.ZERO_DURATION: "Contrat de durée nulle",
    ExclusionReason.FULL_YEAR_SERVED: "Résiliation après une année complète : pas de reprise",
    ExclusionReason.MISSING_RATE: "Aucun taux applicable",
    ExclusionReason.LINEAR_MOVEMENT: "Mouvement d'annulation ou d'extourne",
    ExclusionReason.LINEAR_PREMIUM_TYPE: "Type de cotisation non commissionné en linéaire",
    ExclusionReason.LINEAR_PRODUCT: "Produit sans commission linéaire",
    ExclusionReason.LINEAR_FIRST_YEAR: "Cotisation de première année (couverte par le précompte)",
}


RULE_LABELS: dict[str, str] = {
    "R-P1": "Précompte d'une affaire nouvelle",
    "R-RP1": "Reprise totale d'un contrat sans effet",
    "R-RP2": "Reprise partielle d'un contrat résilié",
    "R-REG": "Régularisation d'un changement de prime",
    "R-L1": "Commission linéaire",
}


@dataclass(frozen=True)
class ContractRecord:
    """Une ligne du bordereau mensuel de contrats envoyé par l'assureur."""

    contract_id: str
    product: str
    state: str
    subscription_date: date
    effective_date: date
    annual_premium: Decimal  # prime annuelle hors taxes
    end_date: date | None = None
    subscriber_id: str = ""
    beneficiary_code: str = ""
    person_id: str = ""
    guarantee: str = ""
    segment: str = ""
    file_rate_year_1: Decimal | None = None  # taux transmis par l'assureur, pour les périmètres concernés


@dataclass(frozen=True)
class PremiumRecord:
    """Une cotisation encaissée sur le mois, base du calcul linéaire."""

    contract_id: str
    product: str
    subscription_date: date
    effective_date: date
    period_start: date
    amount_excl_tax: Decimal
    movement: str = ""
    premium_type: str = ""


@dataclass(frozen=True)
class CommissionLine:
    contract_id: str
    product: str
    commission_type: CommissionType
    amount: Decimal
    rule_id: str
    formula: str
    rate_source: str


@dataclass(frozen=True)
class Exclusion:
    contract_id: str
    reason: ExclusionReason
    detail: str = ""

    @property
    def label(self) -> str:
        return EXCLUSION_LABELS[self.reason]


@dataclass(frozen=True)
class SectionResult:
    lines: tuple[CommissionLine, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()
