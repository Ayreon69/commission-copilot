import json

import pytest
from conftest import SEF_SIMULATION, FakeLLM

from commission_api.assistant.agent import Assistant
from commission_api.assistant.guard import Citation
from commission_api.assistant.llm import LLMReply, ToolCall
from commission_api.assistant.tools import Toolbox
from commission_api.schemas import ChatMessage

KNOWLEDGE = "Exemple : prime de 1 200 €, taux de 120 % → précompte de 1 440 €."


@pytest.fixture(scope="module")
def toolbox(service):
    return Toolbox(service)


def ask(llm, toolbox, question, rounds=4):
    assistant = Assistant(llm, toolbox, "prompt système", KNOWLEDGE, max_tool_rounds=rounds)
    return assistant.answer([ChatMessage(role="user", content=question)])


def simulate_call():
    return LLMReply("", (ToolCall("call00001", "simulate_contract", SEF_SIMULATION),))


def test_tool_result_is_sent_back_to_the_model(toolbox):
    llm = FakeLLM(simulate_call(), LLMReply("La reprise est de −1 200,00 € : reprise totale (R-RP1)."))
    answer = ask(llm, toolbox, "Combien est repris sur ce contrat sans effet ?")

    assert answer.content.startswith("La reprise")
    assert [(t.name, t.ok) for t in answer.tool_calls] == [("simulate_contract", True)]
    assert answer.unverified_amounts == ()

    second_call = llm.calls[1]["messages"]
    assert second_call[0] == {"role": "system", "content": "prompt système"}
    assert second_call[-2]["tool_calls"][0]["function"]["name"] == "simulate_contract"
    assert json.loads(second_call[-2]["tool_calls"][0]["function"]["arguments"]) == SEF_SIMULATION
    assert second_call[-1]["role"] == "tool"
    assert second_call[-1]["tool_call_id"] == "call00001"
    assert "−1 200,00 €" in second_call[-1]["content"]


def test_provider_message_is_sent_back_unchanged(toolbox):
    raw = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call00001", "type": "function",
            "function": {"name": "simulate_contract", "arguments": json.dumps(SEF_SIMULATION)},
            "extra_content": {"google": {"thought_signature": "c2lnbmF0dXJl"}},
        }],
    }
    first = LLMReply("", (ToolCall("call00001", "simulate_contract", SEF_SIMULATION),), "flash", raw)
    llm = FakeLLM(first, LLMReply("La reprise est de −1 200,00 €.", model="flash-lite"))

    answer = ask(llm, toolbox, "Combien est repris ?")

    assert llm.calls[1]["messages"][-2] == raw
    assert answer.model == "flash-lite"


def test_events_describe_the_whole_exchange(toolbox):
    llm = FakeLLM(simulate_call(), LLMReply("Reprise totale (R-RP1) de −1 200,00 €."))
    assistant = Assistant(llm, toolbox, "prompt système", KNOWLEDGE)

    events = list(assistant.events([ChatMessage(role="user", content="Combien est repris ?")]))

    assert [type(event).__name__ for event in events] == ["ToolStarted", "ToolFinished", "TextDelta", "Completed"]
    assert events[0].name == "simulate_contract" and events[1].trace.ok
    answer = events[-1].answer
    assert answer.citations == (Citation("R-RP1", "Reprise totale d'un contrat sans effet", True, True),)
    assert (answer.unknown_rules, answer.unknown_products) == ((), ())


def test_rule_applied_but_not_cited_is_still_listed(toolbox):
    llm = FakeLLM(simulate_call(), LLMReply("La reprise est de −1 200,00 €."))
    citation = ask(llm, toolbox, "?").citations[0]
    assert (citation.rule_id, citation.in_answer, citation.from_calculation) == ("R-RP1", False, True)


def test_invented_rule_and_product_are_reported(toolbox):
    llm = FakeLLM(LLMReply("Selon la règle R-P9, Verdance Essentiel est traité comme Nordale Santé Confort."))
    answer = ask(llm, toolbox, "?")
    assert answer.unknown_rules == ("R-P9",)
    assert answer.unknown_products == ("Verdance Essentiel",)


def test_amount_without_source_is_flagged(toolbox):
    llm = FakeLLM(LLMReply("Vous toucherez 1 234,56 €, comme les 1 440 € de l'exemple."))
    assert ask(llm, toolbox, "Combien vais-je toucher ?").unverified_amounts == ("1 234,56 €",)


def test_amount_given_by_the_user_is_a_valid_source(toolbox):
    llm = FakeLLM(LLMReply("Pour une prime de 1 500 €, il me manque la date de souscription."))
    assert ask(llm, toolbox, "Mon contrat a une prime de 1 500 €").unverified_amounts == ()


def test_tool_error_is_returned_to_the_model(toolbox):
    incomplete = {"perimeter": "SANTE_INDIV", "month": "2026-03", "contract": {"product": "NS-CONFORT"}}
    llm = FakeLLM(LLMReply("", (ToolCall("call00001", "simulate_contract", incomplete),)),
                  LLMReply("Il me manque la prime annuelle et les dates du contrat."))
    answer = ask(llm, toolbox, "Combien pour un contrat Confort ?")

    assert answer.tool_calls[0].ok is False
    assert "annual_premium" in answer.tool_calls[0].result["error"]
    assert "Paramètres invalides" in llm.calls[1]["messages"][-1]["content"]


def test_tool_loop_is_bounded(toolbox):
    looping = FakeLLM(LLMReply("", (ToolCall("call00001", "get_perimeter_details", {"perimeter": "SANTE_INDIV"}),)),
                      repeat_last=True)
    answer = ask(looping, toolbox, "?", rounds=2)

    assert len(looping.calls) == 3
    assert looping.calls[0]["tools"] and looping.calls[-1]["tools"] == []
    assert "reformuler" in answer.content
    assert len(answer.tool_calls) == 2
