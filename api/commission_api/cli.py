"""Pose une question à l'assistant depuis le terminal et affiche le flux de réponse de l'API en direct.

    python -m commission_api.cli "Pourquoi le contrat SI-RESILIE donne-t-il une reprise ?"
    python -m commission_api.cli --url http://localhost:8000 "Quel est le taux du produit Nordale Santé Confort ?"

L'API doit être lancée (uvicorn commission_api.main:create_app --factory).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from typing import Any

import httpx


def iter_events(chunks: Iterable[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Découpe un flux Server-Sent Events en couples (événement, données)."""
    buffer = ""
    for chunk in chunks:
        buffer += chunk.replace("\r\n", "\n")
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
            if "event" in fields:
                yield fields["event"], json.loads(fields.get("data", "{}"))


def render_summary(done: dict[str, Any]) -> str:
    lines = [f"--- Modèle : {done['model']}"]
    for citation in done["citations"]:
        cited = "citée" if citation["in_answer"] else "non citée dans le texte"
        applied = "appliquée par le moteur" if citation["from_calculation"] else "non appliquée par le moteur"
        lines.append(f"Règle {citation['rule_id']} ({citation['label']}) : {cited}, {applied}")
    for label, key in (("Montants sans source", "unverified_amounts"), ("Règles inexistantes", "unknown_rules"),
                       ("Produits inexistants", "unknown_products")):
        lines.append(f"{label} : {', '.join(done[key]) or 'aucun'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="commission_api.cli", description="Pose une question à l'assistant.")
    parser.add_argument("question")
    parser.add_argument("--url", default="http://localhost:8000", help="adresse de l'API")
    args = parser.parse_args(argv)

    body = {"messages": [{"role": "user", "content": args.question}]}
    try:
        with httpx.stream("POST", f"{args.url}/api/chat/stream", json=body, timeout=120) as response:
            if response.status_code != 200:
                response.read()
                print(f"Erreur {response.status_code} : {response.json().get('detail')}", file=sys.stderr)
                return 1
            for event, data in iter_events(response.iter_text()):
                if event == "tool_call":
                    print(f"\n→ outil {data['name']} {json.dumps(data['arguments'], ensure_ascii=False)}")
                elif event == "tool_result":
                    print("← succès\n" if data["ok"] else f"← erreur : {data['result'].get('error')}\n")
                elif event == "delta":
                    print(data["text"], end="", flush=True)
                elif event == "done":
                    print(f"\n\n{render_summary(data)}")
                elif event == "error":
                    print(f"\nErreur {data['status']} : {data['detail']}", file=sys.stderr)
                    return 1
    except httpx.ConnectError:
        print(f"API injoignable sur {args.url} : lancez-la d'abord avec uvicorn.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
