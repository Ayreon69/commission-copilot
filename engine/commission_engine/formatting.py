"""Mise en forme française des montants, taux et dates utilisés dans les formules expliquées."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def format_eur(amount: Decimal) -> str:
    text = f"{abs(amount):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if amount < 0 else ''}{text} €"


def format_rate(rate: Decimal) -> str:
    text = f"{(rate * 100).quantize(Decimal('0.01')):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text.replace('.', ',')} %"


def format_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")
