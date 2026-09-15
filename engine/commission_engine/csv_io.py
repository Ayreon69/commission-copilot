"""Lecture et écriture des bordereaux au format CSV (dates ISO, montants décimaux avec un point)."""

from __future__ import annotations

import csv
from dataclasses import MISSING, fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

from .models import CommissionLine, ContractRecord, PremiumRecord

_DATE_FIELDS = {"subscription_date", "effective_date", "end_date", "period_start"}
_DECIMAL_FIELDS = {"annual_premium", "file_rate_year_1", "amount_excl_tax", "amount"}

T = TypeVar("T")


def read_contracts(path: str | Path) -> list[ContractRecord]:
    return _read(Path(path), ContractRecord)


def read_premiums(path: str | Path) -> list[PremiumRecord]:
    return _read(Path(path), PremiumRecord)


def write_contracts(path: str | Path, records: list[ContractRecord]) -> None:
    _write(Path(path), ContractRecord, records)


def write_premiums(path: str | Path, records: list[PremiumRecord]) -> None:
    _write(Path(path), PremiumRecord, records)


def write_lines(path: str | Path, lines: list[CommissionLine]) -> None:
    _write(Path(path), CommissionLine, lines)


def _parse(name: str, raw: str) -> Any:
    raw = raw.strip()
    if name in _DATE_FIELDS:
        return date.fromisoformat(raw) if raw else None
    if name in _DECIMAL_FIELDS:
        return Decimal(raw) if raw else None
    return raw


def _serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _read(path: Path, cls: type[T]) -> list[T]:
    names = [f.name for f in fields(cls)]
    required = {f.name for f in fields(cls) if f.default is MISSING}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} : colonnes obligatoires absentes : {', '.join(sorted(missing))}")
        return [cls(**{n: _parse(n, row[n]) for n in names if n in row}) for row in reader]


def _write(path: Path, cls: type, records: list) -> None:
    names = [f.name for f in fields(cls)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(names)
        for record in records:
            writer.writerow(_serialize(getattr(record, n)) for n in names)
