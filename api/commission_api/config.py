"""Configuration lue dans l'environnement (ou dans un fichier .env à la racine du dépôt)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mistral_api_key: str | None = None
    mistral_model: str = "mistral-large-latest"
    data_dir: Path = REPO_ROOT / "data"
    knowledge_path: Path = REPO_ROOT / "knowledge" / "regles-metier.md"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    max_tool_rounds: int = 4

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.json"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "samples"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(REPO_ROOT / ".env")
        defaults = cls()
        origins = os.environ.get("CORS_ORIGINS", ",".join(defaults.cors_origins))
        return cls(
            mistral_api_key=os.environ.get("MISTRAL_API_KEY") or None,
            mistral_model=os.environ.get("MISTRAL_MODEL") or defaults.mistral_model,
            data_dir=Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else defaults.data_dir,
            knowledge_path=(Path(os.environ["KNOWLEDGE_PATH"]) if os.environ.get("KNOWLEDGE_PATH")
                            else defaults.knowledge_path),
            cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        )
