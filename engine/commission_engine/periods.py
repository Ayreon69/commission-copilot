"""Manipulation des mois comptables (représentés par leur premier jour)."""

from __future__ import annotations

import calendar
from datetime import date


def parse_month(value: str) -> date:
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Mois invalide : {value!r} (format attendu AAAA-MM)") from exc


def format_month(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def add_months(day: date, months: int) -> date:
    """Premier jour du mois situé `months` mois après (ou avant) celui de `day`."""
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def month_end(day: date) -> date:
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
