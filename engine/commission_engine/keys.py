"""Clés de rapprochement entre le mois M et le mois M-1.

Deux notions distinctes :
- la clé métier identifie une ligne *dans un état donné* : si l'état change, la clé change ;
- la clé de lignée suit la même ligne d'un mois à l'autre, quel que soit son état.

Les clés sont des tuples (et non des chaînes concaténées) pour éviter les collisions du type "AB"+"C" == "A"+"BC".
"""

from __future__ import annotations

from enum import StrEnum

from .models import ContractRecord, normalize_token

Key = tuple[str, ...]


class KeyStrategy(StrEnum):
    CONTRACT = "CONTRACT"  # contrat + état + date de souscription
    GUARANTEE = "GUARANTEE"  # souscripteur + bénéficiaire + contrat + état + garantie
    CONTRACT_GUARANTEE = "CONTRACT_GUARANTEE"  # contrat + état + garantie
    PERSON_GUARANTEE = "PERSON_GUARANTEE"  # personne + état + garantie


def business_key(record: ContractRecord, strategy: KeyStrategy) -> Key:
    r = record
    match strategy:
        case KeyStrategy.CONTRACT:
            parts = (r.contract_id, r.state, r.subscription_date.isoformat())
        case KeyStrategy.GUARANTEE:
            parts = (r.subscriber_id, r.beneficiary_code, r.contract_id, r.state, r.guarantee)
        case KeyStrategy.CONTRACT_GUARANTEE:
            parts = (r.contract_id, r.state, r.guarantee)
        case KeyStrategy.PERSON_GUARANTEE:
            parts = (r.person_id, r.state, r.guarantee)
    return tuple(normalize_token(part) for part in parts)


def lineage_key(record: ContractRecord, strategy: KeyStrategy) -> Key:
    r = record
    match strategy:
        case KeyStrategy.CONTRACT:
            parts = (r.contract_id, r.guarantee, r.subscription_date.isoformat())
        case KeyStrategy.GUARANTEE:
            parts = (r.subscriber_id, r.beneficiary_code, r.contract_id, r.guarantee)
        case KeyStrategy.CONTRACT_GUARANTEE:
            parts = (r.contract_id, r.guarantee)
        case KeyStrategy.PERSON_GUARANTEE:
            parts = (r.person_id, r.effective_date.isoformat(), r.guarantee)
    return tuple(normalize_token(part) for part in parts)
