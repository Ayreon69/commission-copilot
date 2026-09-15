"""Moteur déterministe de calcul des commissions de courtage.

Le moteur ne dépend d'aucune bibliothèque externe : chaque ligne de commission produite
porte la règle appliquée et la formule détaillée, pour pouvoir être expliquée à un utilisateur.
"""

from .catalog import Catalog
from .engine import MonthlyResult, compute_month, simulate_contract
from .models import (
    CommissionLine,
    CommissionType,
    ContractRecord,
    Exclusion,
    ExclusionReason,
    PremiumRecord,
    State,
)

__all__ = [
    "Catalog",
    "CommissionLine",
    "CommissionType",
    "ContractRecord",
    "Exclusion",
    "ExclusionReason",
    "MonthlyResult",
    "PremiumRecord",
    "State",
    "compute_month",
    "simulate_contract",
]
