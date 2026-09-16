"""Outils mis à disposition du modèle de langage.

Les schémas JSON sont écrits à la main : descriptions en français et énumérations explicites guident mieux le modèle
qu'un schéma généré. Ils se limitent au sous-ensemble de JSON Schema accepté par tous les fournisseurs (pas de
`format` ni de `pattern`) : les arguments reçus sont validés ensuite par les mêmes modèles pydantic que l'API HTTP,
et un test vérifie que les deux restent alignés.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from ..schemas import LookupRequest, PerimeterRequest, SimulationRequest
from ..services import CommissionService, ServiceError

_STATE = {"type": "string", "enum": ["AFN", "SEF", "RES"],
          "description": "AFN = contrat actif, SEF = sans effet, RES = résilié"}


class ToolError(Exception):
    """Erreur renvoyée au modèle pour qu'il corrige son appel ou l'explique à l'utilisateur."""


def _date(description: str) -> dict[str, str]:
    return {"type": "string", "description": f"{description}, format AAAA-MM-JJ"}


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


class Toolbox:
    def __init__(self, service: CommissionService):
        self.service = service
        catalog = service.catalog
        all_perimeters = [p.code for p in catalog.perimeters.values()]
        active_perimeters = [p.code for p in catalog.perimeters.values() if p.active]
        products = sorted(p.code for p in catalog.products.values() if catalog.perimeter(p.perimeter).active)
        month = service.default_month()

        self.definitions: list[dict[str, Any]] = [
            _function(
                "get_perimeter_details",
                "Renvoie le paramétrage exact d'un périmètre : clé de rapprochement, base d'exposition, limites "
                "d'ancienneté, régularisation, taux spécifiques, exclusions du linéaire et grilles de taux datées de "
                "chaque produit. À utiliser avant de citer un taux, un seuil ou une particularité.",
                {"perimeter": {"type": "string", "enum": all_perimeters, "description": "Code du périmètre"}},
                ["perimeter"],
            ),
            _function(
                "simulate_contract",
                "Calcule avec le moteur officiel la commission d'un contrat au mois de calcul, en tenant compte de sa "
                "situation le mois précédent : précompte, reprise ou régularisation, avec la règle appliquée, la "
                "formule détaillée et la provenance du taux, ou le motif pour lequel rien n'est dû.",
                {
                    "perimeter": {"type": "string", "enum": active_perimeters, "description": "Code du périmètre"},
                    "month": {"type": "string",
                              "description": f"Mois de calcul au format AAAA-MM (par défaut {month})"},
                    "contract": {
                        "type": "object",
                        "description": "Le contrat tel qu'il figure au mois de calcul",
                        "properties": {
                            "product": {"type": "string", "enum": products,
                                        "description": "Code du produit, qui doit appartenir au périmètre"},
                            "state": _STATE,
                            "subscription_date": _date("Date de souscription, qui fixe le taux"),
                            "effective_date": _date("Date d'effet du contrat"),
                            "annual_premium": {"type": "number", "minimum": 0,
                                               "description": "Prime annuelle hors taxes, en euros"},
                            "end_date": _date("Date de fin ou de résiliation, à renseigner pour un contrat résilié"),
                            "guarantee": {"type": "string",
                                          "description": "Garantie, uniquement si elle a un taux spécifique"},
                            "segment": {"type": "string",
                                        "description": "Segment de clientèle, uniquement s'il a un taux négocié"},
                            "file_rate_year_1": {"type": "number", "minimum": 0,
                                                 "description": "Taux transmis par l'assureur, ex. 0.38 pour 38 %"},
                        },
                        "required": ["product", "state", "subscription_date", "effective_date", "annual_premium"],
                    },
                    "previous_month": {
                        "type": "object",
                        "description": "Situation du même contrat le mois précédent. À omettre pour un contrat qui "
                                       "apparaît au mois de calcul.",
                        "properties": {
                            "state": _STATE,
                            "annual_premium": {"type": "number", "minimum": 0,
                                               "description": "Prime annuelle du mois précédent, si elle a changé"},
                            "end_date": _date("Date de fin connue le mois précédent"),
                        },
                        "required": ["state"],
                    },
                },
                ["perimeter", "month", "contract"],
            ),
            _function(
                "lookup_sample_contract",
                f"Retrouve un contrat des bordereaux d'exemple ({month} et mois précédent, cotisations encaissées) et "
                "le résultat calculé par le moteur pour ce contrat. Les numéros de scénarios décrivent le cas "
                "illustré, par exemple SI-RESILIE, AN-ANOMALIE ou EM-TAUX-SPECIFIQUE-1.",
                {
                    "perimeter": {"type": "string", "enum": active_perimeters, "description": "Code du périmètre"},
                    "contract_id": {"type": "string", "description": "Numéro du contrat"},
                },
                ["perimeter", "contract_id"],
            ),
        ]
        self._handlers: dict[str, tuple[type[BaseModel], Callable[[Any], BaseModel]]] = {
            "get_perimeter_details": (PerimeterRequest, lambda a: service.perimeter_details(a.perimeter)),
            "simulate_contract": (SimulationRequest, service.simulate),
            "lookup_sample_contract": (LookupRequest, lambda a: service.sample_contract(a.perimeter, a.contract_id)),
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._handlers:
            raise ToolError(f"Outil inconnu : {name}")
        model, handler = self._handlers[name]
        try:
            return handler(model.model_validate(arguments)).model_dump(mode="json")
        except ValidationError as exc:
            raise ToolError(_describe_validation_error(exc)) from None
        except ServiceError as exc:
            raise ToolError(str(exc)) from None


def _describe_validation_error(exc: ValidationError) -> str:
    problems = [f"{'.'.join(str(part) for part in error['loc']) or 'arguments'} : {error['msg']}"
                for error in exc.errors()]
    return "Paramètres invalides — " + " ; ".join(problems)
