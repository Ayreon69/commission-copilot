"""Configuration lue dans l'environnement (ou dans un fichier .env à la racine du dépôt)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None = None
    llm_base_url: str = GEMINI_BASE_URL
    # Modèles essayés dans l'ordre : le suivant prend le relais quand le quota gratuit du précédent est épuisé.
    llm_models: tuple[str, ...] = ("gemini-3.7-flash", "gemini-3.5-flash-lite")
    llm_reasoning_effort: str | None = None
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
        return cls(
            llm_api_key=os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or None,
            llm_base_url=os.environ.get("LLM_BASE_URL") or defaults.llm_base_url,
            llm_models=_split(os.environ.get("LLM_MODELS")) or defaults.llm_models,
            llm_reasoning_effort=os.environ.get("LLM_REASONING_EFFORT") or None,
            data_dir=Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else defaults.data_dir,
            knowledge_path=(Path(os.environ["KNOWLEDGE_PATH"]) if os.environ.get("KNOWLEDGE_PATH")
                            else defaults.knowledge_path),
            cors_origins=_split(os.environ.get("CORS_ORIGINS")) or defaults.cors_origins,
        )


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())
