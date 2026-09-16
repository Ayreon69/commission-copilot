"""Traduction des réponses du SDK Mistral, sans appel réseau."""

from types import SimpleNamespace

import pytest
from mistralai.client.errors import NoResponseError

from commission_api.assistant.llm import LLMError, MistralClient


def client_returning(response=None, error=None):
    received = {}

    def complete(**kwargs):
        received.update(kwargs)
        if error:
            raise error
        return response

    client = MistralClient(api_key="test", model="mistral-test")
    client._client = SimpleNamespace(chat=SimpleNamespace(complete=complete))
    return client, received


def response_with(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


def test_tool_calls_are_parsed():
    call = SimpleNamespace(id="abc123XYZ", function=SimpleNamespace(
        name="simulate_contract", arguments='{"perimeter": "SANTE_INDIV"}'))
    client, received = client_returning(response_with(SimpleNamespace(content="", tool_calls=[call])))

    reply = client.complete([{"role": "user", "content": "?"}], [{"type": "function"}])

    assert reply.tool_calls[0].id == "abc123XYZ"
    assert reply.tool_calls[0].arguments == {"perimeter": "SANTE_INDIV"}
    assert received["tool_choice"] == "auto"


def test_text_chunks_are_joined_and_tools_omitted_when_empty():
    chunks = [SimpleNamespace(text="Bonjour "), SimpleNamespace(text="à vous")]
    client, received = client_returning(response_with(SimpleNamespace(content=chunks, tool_calls=None)))

    assert client.complete([], []).content == "Bonjour à vous"
    assert "tools" not in received and "tool_choice" not in received


def test_unreadable_arguments_become_empty():
    call = SimpleNamespace(id=None, function=SimpleNamespace(name="simulate_contract", arguments="{pas du json"))
    client, _ = client_returning(response_with(SimpleNamespace(content="", tool_calls=[call])))

    reply = client.complete([], [])
    assert (reply.tool_calls[0].id, reply.tool_calls[0].arguments) == ("call00000", {})


def test_provider_errors_become_llm_errors():
    client, _ = client_returning(error=NoResponseError("délai dépassé"))
    with pytest.raises(LLMError):
        client.complete([], [])
