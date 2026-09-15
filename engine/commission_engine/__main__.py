"""Calcule les commissions d'un périmètre sur un mois à partir des bordereaux d'exemple.

    python -m commission_engine SANTE_INDIV 2026-03
    python -m commission_engine ANIMAUX 2026-03 --exclusions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import Catalog
from .csv_io import read_contracts, read_premiums
from .engine import compute_month
from .formatting import format_eur
from .models import EXCLUSION_LABELS, CommissionType
from .periods import add_months, format_month, parse_month

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="commission_engine", description=__doc__.splitlines()[0])
    parser.add_argument("perimeter", help="code du périmètre, ex. SANTE_INDIV")
    parser.add_argument("month", help="mois de calcul, format AAAA-MM")
    parser.add_argument("--catalog", type=Path, default=DATA_DIR / "catalog.json")
    parser.add_argument("--samples", type=Path, default=DATA_DIR / "samples")
    parser.add_argument("--exclusions", action="store_true", help="détaille chaque ligne exclue")
    args = parser.parse_args(argv)

    catalog = Catalog.load(args.catalog)
    month = format_month(parse_month(args.month))
    previous_month = format_month(add_months(parse_month(month), -1))
    folder = args.samples / catalog.perimeter(args.perimeter).code

    current = read_contracts(folder / f"contracts_{month}.csv")
    previous_path = folder / f"contracts_{previous_month}.csv"
    premiums_path = folder / f"premiums_{month}.csv"
    previous = read_contracts(previous_path) if previous_path.exists() else []
    premiums = read_premiums(premiums_path) if premiums_path.exists() else []

    result = compute_month(catalog, args.perimeter, month, current, previous, premiums)

    print(f"\n{result.perimeter} — {result.month}\n")
    for line in result.lines:
        print(f"  {line.commission_type:<2}  {line.contract_id:<32} {format_eur(line.amount):>14}  "
              f"[{line.rule_id}] {line.formula}")
    print()
    for kind in CommissionType:
        print(f"  Total {kind:<2} : {format_eur(result.total(kind)):>14}")
    print(f"  Net      : {format_eur(result.total()):>14}\n")

    print("  Lignes exclues :")
    for reason, count in result.exclusion_counts().most_common():
        print(f"    {count:>4}  {EXCLUSION_LABELS[reason]}")
    if args.exclusions:
        print()
        for exclusion in result.exclusions:
            print(f"    {exclusion.contract_id:<32} {exclusion.reason:<20} {exclusion.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
