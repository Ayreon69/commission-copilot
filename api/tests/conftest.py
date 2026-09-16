from __future__ import annotations

import copy
from typing import Any

import pytest
from commission_engine import Catalog
from fastapi.testclient import TestClient

from commission_api.assistant.llm import LLMReply
from commission_api.config import Settings
from commission_api.main import create_app
from commission_api.services import CommissionService


class FakeLLM:
    """Modèle de langage scripté : renvoie les réponses prévues et enregistre ce qu'il a reçu."""

    model = "fake-model"

    def __init__(self, *replies: LLMReply, repeat_last: bool = False):
        self._replies = list(replies)
        self.repeat_last = repeat_last
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self._replies:
            raise AssertionError("Appel au modèle non prévu par le test")
        if self.repeat_last and len(self._replies) == 1:
            return self._replies[0]
        return self._replies.pop(0)


SEF_SIMULATION: dict[str, Any] = {
    "perimeter": "SANTE_INDIV",
    "month": "2026-03",
    "contract": {
        "product": "NS-CONFORT",
        "state": "SEF",
        "subscription_date": "2026-01-20",
        "effective_date": "2026-02-01",
        "annual_premium": 1000,
    },
    "previous_month": {"state": "AFN"},
}


@pytest.fixture
def settings() -> Settings:
    return Settings()  # aucune clé : l'assistant est désactivé


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture(scope="session")
def service() -> CommissionService:
    defaults = Settings()
    return CommissionService(Catalog.load(defaults.catalog_path), defaults.samples_dir)
