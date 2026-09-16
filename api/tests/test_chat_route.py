from conftest import FakeLLM
from fastapi.testclient import TestClient

from commission_api.assistant.llm import LLMError, LLMReply, QuotaExceededError, ToolCall
from commission_api.main import create_app

QUESTION = {"messages": [{"role": "user", "content": "Pourquoi SI-RESILIE donne-t-il une reprise ?"}]}


def test_chat_returns_answer_and_tool_trace(settings):
    llm = FakeLLM(
        LLMReply("", (ToolCall("call00001", "lookup_sample_contract",
                               {"perimeter": "SANTE_INDIV", "contract_id": "SI-RESILIE"}),)),
        LLMReply("Le contrat a été résilié après 7 mois : reprise partielle (R-RP2) de −1 044,50 €."),
    )
    client = TestClient(create_app(settings, llm=llm))

    assert client.get("/api/health").json() == {"status": "ok", "chat_enabled": True, "model": "fake-model"}
    body = client.post("/api/chat", json=QUESTION).json()
    assert body["model"] == "fake-model"
    assert body["answer"].endswith("−1 044,50 €.")
    assert body["tool_calls"][0]["name"] == "lookup_sample_contract"
    assert body["tool_calls"][0]["result"]["lines"][0]["rule_id"] == "R-RP2"
    assert body["unverified_amounts"] == []
    assert "Commission Copilot" in llm.calls[0]["messages"][0]["content"]


def test_chat_requires_last_message_from_user(settings):
    client = TestClient(create_app(settings, llm=FakeLLM()))
    messages = QUESTION["messages"] + [{"role": "assistant", "content": "Réponse"}]
    assert client.post("/api/chat", json={"messages": messages}).status_code == 422


class FailingLLM:
    model = "failing-model"

    def __init__(self, error):
        self.error = error

    def complete(self, messages, tools):
        raise self.error


def test_llm_failure_returns_502(settings):
    client = TestClient(create_app(settings, llm=FailingLLM(LLMError("service indisponible"))))
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 502
    assert "indisponible" in response.json()["detail"]


def test_exhausted_quota_returns_429(settings):
    client = TestClient(create_app(settings, llm=FailingLLM(QuotaExceededError("tous les modèles"))))
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 429
    assert "quota gratuit" in response.json()["detail"]
