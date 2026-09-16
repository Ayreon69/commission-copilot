"""Exporte le schéma OpenAPI de l'API, source des types TypeScript de l'interface.

    python scripts/export_openapi.py            (depuis api/, puis `npm run types` dans web/)
"""

from __future__ import annotations

import json
from pathlib import Path

from commission_api.config import Settings
from commission_api.main import create_app

OUTPUT = Path(__file__).resolve().parents[2] / "web" / "openapi.json"


def main() -> None:
    schema = create_app(Settings()).openapi()
    OUTPUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Schéma OpenAPI écrit dans {OUTPUT}")


if __name__ == "__main__":
    main()
