"""Exposition : part de la période de référence réellement couverte par un contrat."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from enum import StrEnum


class ExposureBase(StrEnum):
    MONTHS_12 = "MONTHS_12"  # mois entamés / 12
    MONTHS_24 = "MONTHS_24"  # mois entamés / 24
    DAYS_365 = "DAYS_365"
    DAYS_365_25 = "DAYS_365_25"
    DAYS_730 = "DAYS_730"
    ANNIVERSARY = "ANNIVERSARY"  # jours / durée réelle jusqu'à la date anniversaire du contrat


_MONTH_DIVISORS = {ExposureBase.MONTHS_12: 12, ExposureBase.MONTHS_24: 24}
_DAY_DIVISORS = {
    ExposureBase.DAYS_365: Decimal("365"),
    ExposureBase.DAYS_365_25: Decimal("365.25"),
    ExposureBase.DAYS_730: Decimal("730"),
}


def exposure(start: date, end: date, base: ExposureBase) -> Decimal:
    """Exposition entre `start` et `end`, bornes incluses. Vaut 0 pour un contrat qui finit le jour où il commence."""
    if start == end:
        return Decimal(0)
    numerator, denominator = _fraction(start, end, base)
    return Decimal(numerator) / denominator


def describe_exposure(start: date, end: date, base: ExposureBase) -> str:
    """Fraction exacte affichée dans les formules (« 7/12 », « 196/365,25 ») pour que le calcul reste vérifiable."""
    if start == end:
        return "0"
    numerator, denominator = _fraction(start, end, base)
    return f"{numerator}/{str(denominator).replace('.', ',')}"


def _fraction(start: date, end: date, base: ExposureBase) -> tuple[int, Decimal]:
    if base in _MONTH_DIVISORS:
        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        return months, Decimal(_MONTH_DIVISORS[base])
    days = (end - start).days + 1
    if base in _DAY_DIVISORS:
        return days, _DAY_DIVISORS[base]
    return days, Decimal(_days_to_anniversary(start))


def _days_to_anniversary(start: date) -> int:
    # Un contrat démarré un 29 février fête son anniversaire le 28 février les années non bissextiles.
    year = start.year + 1
    day = min(start.day, calendar.monthrange(year, start.month)[1])
    return (date(year, start.month, day) - start).days
