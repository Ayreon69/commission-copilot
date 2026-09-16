import json

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


def parse_sse(body):
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_chat_stream_emits_progress_then_final_answer(settings):
    llm = FakeLLM(
        LLMReply("", (ToolCall("call00001", "lookup_sample_contract",
                               {"perimeter": "SANTE_INDIV", "contract_id": "SI-RESILIE"}),)),
        LLMReply("Reprise partielle (R-RP2) de −1 044,50 €."),
    )
    client = TestClient(create_app(settings, llm=llm))

    with client.stream("POST", "/api/chat/stream", json=QUESTION) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(response.read().decode("utf-8"))

    assert [name for name, _ in events] == ["tool_call", "tool_result", "delta", "done"]
    assert events[0][1] == {"name": "lookup_sample_contract",
                            "arguments": {"perimeter": "SANTE_INDIV", "contract_id": "SI-RESILIE"}}
    assert events[2][1] == {"text": "Reprise partielle (R-RP2) de −1 044,50 €."}
    done = events[-1][1]
    assert done["citations"] == [{"rule_id": "R-RP2", "label": "Reprise partielle d'un contrat résilié",
                                  "in_answer": True, "from_calculation": True}]
    assert (done["unverified_amounts"], done["unknown_rules"], done["unknown_products"]) == ([], [], [])


def test_chat_stream_reports_model_failure_as_event(settings):
    client = TestClient(create_app(settings, llm=FailingLLM(QuotaExceededError("tous les modèles"))))
    with client.stream("POST", "/api/chat/stream", json=QUESTION) as response:
        events = parse_sse(response.read().decode("utf-8"))
    assert events == [("error", {"status": 429, "detail": events[0][1]["detail"]})]
    assert "quota gratuit" in events[0][1]["detail"]


def test_chat_stream_requires_key(settings):
    response = TestClient(create_app(settings)).post("/api/chat/stream", json=QUESTION)
    assert response.status_code == 503


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
