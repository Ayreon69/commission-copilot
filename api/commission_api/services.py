"""Services métier appelés à la fois par les routes HTTP et par les outils de l'assistant."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TypeVar

from commission_engine import Catalog, compute_month, simulate_contract
from commission_engine.catalog import Perimeter
from commission_engine.csv_io import read_contracts, read_premiums
from commission_engine.models import normalize_token
from commission_engine.periods import add_months, format_month, parse_month

from . import presenters
from .schemas import (
    CalculationOut,
    ContractRecordOut,
    PerimeterDetailsOut,
    PerimeterSummaryOut,
    PremiumRecordOut,
    SampleContractOut,
    SimulationRequest,
)

T = TypeVar("T")
_CONTRACTS_FILE = re.compile(r"^contracts_(\d{4}-\d{2})\.csv$")
_RANDOM_CONTRACT = re.compile(r"-\d{4}$")


class ServiceError(Exception):
    """Erreur dont le message peut être montré tel quel à l'utilisateur ou au modèle de langage."""


class NotFoundError(ServiceError):
    pass


class InvalidRequestError(ServiceError):
    pass


class CommissionService:
    def __init__(self, catalog: Catalog, samples_dir: Path):
        self.catalog = catalog
        self.samples_dir = samples_dir

    def perimeters(self) -> list[PerimeterSummaryOut]:
        return [presenters.perimeter_summary(self.catalog, p) for p in self.catalog.perimeters.values()]

    def perimeter_details(self, code: str) -> PerimeterDetailsOut:
        return presenters.perimeter_details(self.catalog, self._perimeter(code))

    def simulate(self, request: SimulationRequest) -> CalculationOut:
        perimeter = self._active_perimeter(request.perimeter)
        _check_segment(perimeter, request.contract.segment)
        current, previous = request.records()
        return presenters.calculation_out(
            simulate_contract(self.catalog, perimeter.code, request.month, current, previous)
        )

    def sample_contract(self, perimeter_code: str, contract_id: str) -> SampleContractOut:
        perimeter = self._active_perimeter(perimeter_code)
        folder = self.samples_dir / perimeter.code
        month = self._latest_month(folder, perimeter.code)
        previous_month = format_month(add_months(parse_month(month), -1))
        current = read_contracts(folder / f"contracts_{month}.csv")
        previous = _read_if_exists(read_contracts, folder / f"contracts_{previous_month}.csv")
        premiums = _read_if_exists(read_premiums, folder / f"premiums_{month}.csv")

        wanted = normalize_token(contract_id)
        if not any(normalize_token(r.contract_id) == wanted for r in [*current, *previous, *premiums]):
            scenarios = sorted({r.contract_id for r in current if not _RANDOM_CONTRACT.search(r.contract_id)})
            raise NotFoundError(
                f"Contrat « {contract_id} » absent des bordereaux d'exemple {perimeter.code} de {month}. "
                f"Contrats scénarios disponibles : {', '.join(scenarios)}"
            )

        result = presenters.calculation_out(
            compute_month(self.catalog, perimeter.code, month, current, previous, premiums)
        )

        def mine(items):
            return [item for item in items if normalize_token(item.contract_id) == wanted]

        return SampleContractOut(
            perimeter=perimeter.code,
            month=month,
            previous_month=previous_month,
            contract_id=contract_id.strip().upper(),
            previous_records=[ContractRecordOut.model_validate(r) for r in mine(previous)],
            current_records=[ContractRecordOut.model_validate(r) for r in mine(current)],
            premiums=[PremiumRecordOut.model_validate(p) for p in mine(premiums)],
            lines=mine(result.lines),
            exclusions=mine(result.exclusions),
        )

    def default_month(self) -> str:
        """Mois le plus récent des bordereaux d'exemple, proposé par défaut à l'assistant."""
        folders = [f for f in self.samples_dir.iterdir() if f.is_dir()] if self.samples_dir.is_dir() else []
        months = [month for folder in folders for month in _months_in(folder)]
        return max(months) if months else format_month(date.today())

    def _perimeter(self, code: str) -> Perimeter:
        try:
            return self.catalog.perimeter(code)
        except KeyError as exc:
            raise NotFoundError(exc.args[0]) from None

    def _active_perimeter(self, code: str) -> Perimeter:
        perimeter = self._perimeter(code)
        if not perimeter.active:
            raise InvalidRequestError(f"Le périmètre {perimeter.code} est arrêté : aucun calcul n'est possible.")
        return perimeter

    @staticmethod
    def _latest_month(folder: Path, code: str) -> str:
        months = _months_in(folder) if folder.is_dir() else []
        if not months:
            raise NotFoundError(f"Aucun bordereau d'exemple pour le périmètre {code}.")
        return max(months)


def _check_segment(perimeter: Perimeter, segment: str) -> None:
    """Refuse un segment inconnu : sinon le taux standard s'appliquerait sans que personne ne s'en aperçoive."""
    if not segment:
        return
    allowed = sorted({o.segment for o in perimeter.rate_overrides if o.segment})
    if normalize_token(segment) not in {normalize_token(s) for s in allowed}:
        accepted = ", ".join(allowed) if allowed else "aucun"
        raise InvalidRequestError(
            f"Segment « {segment} » inconnu pour le périmètre {perimeter.code}. Segments à taux négocié : {accepted}. "
            "Laisser le segment vide pour un client sans taux négocié."
        )


def _months_in(folder: Path) -> list[str]:
    return [match.group(1) for path in folder.glob("contracts_*.csv") if (match := _CONTRACTS_FILE.match(path.name))]


def _read_if_exists(reader: Callable[[Path], list[T]], path: Path) -> list[T]:
    return reader(path) if path.exists() else []
