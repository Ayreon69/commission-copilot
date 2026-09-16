"""Client compatible OpenAI et chaîne de repli, sans appel réseau."""

from types import SimpleNamespace

import httpx
import openai
import pytest
from conftest import FakeLLM
from openai.types.chat import ChatCompletion

from commission_api.assistant.llm import (
    FallbackLLM,
    LLMError,
    LLMReply,
    ModelUnavailableError,
    OpenAICompatibleClient,
    QuotaExceededError,
)

REQUEST = httpx.Request("POST", "https://llm.example.test/chat/completions")


def client_returning(response=None, error=None, **options):
    received = {}

    def create(**kwargs):
        received.update(kwargs)
        if error:
            raise error
        return response

    client = OpenAICompatibleClient(base_url="https://llm.example.test", api_key="test", model="gemini-test",
                                    **options)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, received


def completion(message):
    return ChatCompletion.model_validate({
        "id": "reponse-1", "object": "chat.completion", "created": 0, "model": "gemini-test",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", **message}}],
    })


def test_tool_calls_are_parsed_and_provider_fields_kept():
    tool_call = {
        "id": "abc123XYZ", "type": "function",
        "function": {"name": "simulate_contract", "arguments": '{"perimeter": "SANTE_INDIV"}'},
        "extra_content": {"google": {"thought_signature": "c2lnbmF0dXJl"}},
    }
    client, received = client_returning(completion({"content": None, "tool_calls": [tool_call]}))

    reply = client.complete([{"role": "user", "content": "?"}], [{"type": "function"}])

    assert reply.tool_calls[0].id == "abc123XYZ"
    assert reply.tool_calls[0].arguments == {"perimeter": "SANTE_INDIV"}
    assert reply.model == "gemini-test"
    assert reply.raw_message["tool_calls"][0]["extra_content"] == {"google": {"thought_signature": "c2lnbmF0dXJl"}}
    assert received["tool_choice"] == "auto"


def test_missing_call_id_is_generated_in_both_places():
    tool_call = {"id": "", "type": "function", "function": {"name": "simulate_contract", "arguments": "{pas du json"}}
    client, _ = client_returning(completion({"content": None, "tool_calls": [tool_call]}))

    reply = client.complete([], [])

    assert (reply.tool_calls[0].id, reply.tool_calls[0].arguments) == ("call00000", {})
    assert reply.raw_message["tool_calls"][0]["id"] == "call00000"


def test_optional_parameters_are_only_sent_when_needed():
    client, received = client_returning(completion({"content": "Bonjour"}))
    assert client.complete([], []).content == "Bonjour"
    assert not {"tools", "tool_choice", "reasoning_effort", "temperature"} & set(received)

    client, received = client_returning(completion({"content": "Bonjour"}), reasoning_effort="low")
    client.complete([], [])
    assert received["reasoning_effort"] == "low"


def test_rate_limit_becomes_quota_error():
    error = openai.RateLimitError("quota", response=httpx.Response(429, request=REQUEST), body=None)
    client, _ = client_returning(error=error)
    with pytest.raises(QuotaExceededError):
        client.complete([], [])


@pytest.mark.parametrize(
    "error",
    [
        openai.InternalServerError("surcharge", response=httpx.Response(503, request=REQUEST), body=None),
        openai.APIConnectionError(request=REQUEST),
        openai.APITimeoutError(request=REQUEST),
    ],
)
def test_temporary_failures_become_unavailable_errors(error):
    client, _ = client_returning(error=error)
    with pytest.raises(ModelUnavailableError):
        client.complete([], [])


def test_definitive_errors_are_not_retryable():
    error = openai.AuthenticationError("clé invalide", response=httpx.Response(401, request=REQUEST), body=None)
    client, _ = client_returning(error=error)
    with pytest.raises(LLMError) as raised:
        client.complete([], [])
    assert not isinstance(raised.value, QuotaExceededError | ModelUnavailableError)


class ExhaustedLLM:
    def __init__(self, model):
        self.model = model
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        raise QuotaExceededError(f"{self.model} : quota atteint")


def test_fallback_switches_model_when_quota_is_exhausted():
    primary, secondary = ExhaustedLLM("flash"), FakeLLM(LLMReply("Réponse"), LLMReply("Encore"))
    secondary.model = "flash-lite"
    now = [0.0]
    llm = FallbackLLM([primary, secondary], cooldown_s=60, clock=lambda: now[0])

    assert llm.complete([], []).model == "flash-lite"
    now[0] = 30
    llm.complete([], [])
    assert primary.calls == 1  # mis de côté pendant la pause, le modèle principal n'est pas réessayé


def test_fallback_retries_primary_after_cooldown():
    primary = FakeLLM(LLMReply("Réponse du principal"))
    primary.model = "flash"
    exhausted_once = [True]

    def complete(messages, tools):
        if exhausted_once[0]:
            exhausted_once[0] = False
            raise QuotaExceededError("flash : quota atteint")
        return FakeLLM.complete(primary, messages, tools)

    primary.complete = complete
    secondary = FakeLLM(LLMReply("Réponse du secours"))
    now = [0.0]
    llm = FallbackLLM([primary, secondary], cooldown_s=60, clock=lambda: now[0])

    assert llm.complete([], []).content == "Réponse du secours"
    now[0] = 61
    assert llm.complete([], []).content == "Réponse du principal"


class UnavailableLLM(ExhaustedLLM):
    def complete(self, messages, tools):
        self.calls += 1
        raise ModelUnavailableError(f"{self.model} : indisponible")


def test_fallback_switches_model_when_primary_is_overloaded():
    secondary = FakeLLM(LLMReply("Réponse du secours"))
    llm = FallbackLLM([UnavailableLLM("flash"), secondary])
    assert llm.complete([], []).content == "Réponse du secours"


def test_fallback_reports_unavailability_when_not_only_quota():
    llm = FallbackLLM([ExhaustedLLM("flash"), UnavailableLLM("flash-lite")])
    with pytest.raises(ModelUnavailableError):
        llm.complete([], [])


def test_definitive_error_stops_the_fallback():
    class RejectingLLM(ExhaustedLLM):
        def complete(self, messages, tools):
            raise LLMError("requête refusée")

    secondary = FakeLLM()
    with pytest.raises(LLMError, match="refusée"):
        FallbackLLM([RejectingLLM("flash"), secondary]).complete([], [])
    assert secondary.calls == []


def test_fallback_raises_when_every_model_is_exhausted():
    llm = FallbackLLM([ExhaustedLLM("flash"), ExhaustedLLM("flash-lite")])
    with pytest.raises(QuotaExceededError, match="tous les modèles"):
        llm.complete([], [])
    assert llm.models == ["flash", "flash-lite"]
