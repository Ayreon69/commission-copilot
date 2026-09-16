"""Tests hors ligne de l'évaluation : cohérence du jeu de référence avec le moteur, vérifications, exécution."""

import pytest
from conftest import FakeLLM
from evals.checks import EvalCase, contains, evaluate, load_dataset
from evals.report import render
from evals.run import PatientLLM, run_model, summarize

from commission_api.assistant.agent import AssistantAnswer, ToolTrace
from commission_api.assistant.llm import LLMError, LLMReply, ModelUnavailableError, ToolCall
from commission_api.config import Settings

DATASET = load_dataset()


def test_dataset_covers_every_category():
    assert {case.category for case in DATASET.cases} == {
        "explication", "simulation", "regles", "info_manquante", "limites", "conversation"}


@pytest.mark.parametrize("case", [c for c in DATASET.cases if c.ground_truth], ids=lambda c: c.id)
def test_expectations_match_the_engine(case, service):
    truth = case.ground_truth
    if truth.lookup:
        result, tool, arguments = (service.sample_contract(truth.lookup.perimeter, truth.lookup.contract_id),
                                   "lookup_sample_contract", truth.lookup.model_dump())
    else:
        result, tool, arguments = (service.simulate(truth.simulation), "simulate_contract",
                                   truth.simulation.model_dump(mode="json"))

    amounts = {abs(line.amount) for line in result.lines}
    assert set(case.expect.amounts) <= amounts
    assert not set(case.expect.forbidden_amounts) & amounts
    assert set(case.expect.rule_ids) <= {line.rule_id for line in result.lines}
    if tool in case.expect.tool_arguments:
        assert contains(arguments, case.expect.tool_arguments[tool])
    assert not case.expect.tools or case.expect.tools == [tool]


def make_case(**expect):
    return EvalCase(id="cas", category="simulation", question="?", expect=expect)


def make_answer(content, tool_calls=(), unverified=()):
    return AssistantAnswer(content, tuple(tool_calls), tuple(unverified), "fake-model")


def failed_checks(case, answer):
    return [check.name for check in evaluate(case, answer) if not check.passed]


def test_complete_answer_passes_every_check():
    case = make_case(tools=["simulate_contract"],
                     tool_arguments={"simulate_contract": {"contract": {"product": "ns-confort"}}},
                     amounts=["1800.00"], rule_ids=["R-P1"], mentions=[["précompte", "precompte"]])
    arguments = {"perimeter": "SANTE_INDIV", "contract": {"product": "NS-CONFORT"}}
    trace = ToolTrace("simulate_contract", arguments, {}, True)
    answer = make_answer("Précompte de 1 800,00 € (r-p1).", [trace])
    assert failed_checks(case, answer) == []


def test_failures_are_reported_individually():
    case = make_case(tools=["simulate_contract"], amounts=["1800.00"], forbidden_amounts=["1440"],
                     asks_question=True, no_amounts=True)
    failed_tool = ToolTrace("simulate_contract", {}, {"error": "Paramètres invalides"}, False)
    answer = make_answer("Environ 1 440 €.", [failed_tool], unverified=["1 440 €"])
    assert failed_checks(case, answer) == [
        "appelle simulate_contract", "cite 1800.00 €", "ne cite pas 1440 €", "ne cite aucun montant",
        "demande les informations manquantes", "tous les montants ont une source"]


def test_request_for_information_without_question_mark_counts():
    case = make_case(asks_question=True, any_tools=["lookup_sample_contract", "get_perimeter_details"])
    trace = ToolTrace("get_perimeter_details", {"perimeter": "ANIMAUX"}, {}, True)
    answer = make_answer("J'ai besoin de la date de résiliation et de la prime annuelle.", [trace])
    assert failed_checks(case, answer) == []


def test_mentions_ignore_case_and_accents():
    case = make_case(mentions=[["régularisation"], ["mois précédent", "déjà"]])
    assert failed_checks(case, make_answer("Aucune REGULARISATION : deja commissionné.")) == []


def sef_case():
    return next(case for case in DATASET.cases if case.id == "simulation-sans-effet")


def test_run_case_scores_an_answer(service):
    arguments = sef_case().ground_truth.simulation.model_dump(mode="json")
    llm = FakeLLM(LLMReply("", (ToolCall("call00001", "simulate_contract", arguments),)),
                  LLMReply("Reprise totale (R-RP1) de −950,00 €."))
    run = run_model(Settings(), service, "fake-model", [sef_case()], 1, delay_s=0, sleep=lambda s: None, client=llm)

    assert run["summary"]["passed"] == 1
    assert run["cases"][0]["status"] == "passed"
    assert run["llm_calls"] == 2


def test_infrastructure_errors_are_not_counted_as_failures(service):
    class DownLLM:
        model = "down"

        def complete(self, messages, tools):
            raise LLMError("clé invalide")

    cases = DATASET.cases[:5]
    run = run_model(Settings(), service, "down", cases, 1, delay_s=0, sleep=lambda s: None, client=DownLLM())

    assert run["complete"] is False  # arrêt après 3 erreurs consécutives
    assert run["summary"]["errors"] == 3 and run["summary"]["pass_rate"] is None


def test_patient_llm_waits_then_gives_up():
    waits = []

    class OverloadedLLM:
        model = "overloaded"

        def complete(self, messages, tools):
            raise ModelUnavailableError("surcharge")

    with pytest.raises(ModelUnavailableError):
        PatientLLM(OverloadedLLM(), waits=(1, 2), sleep=waits.append).complete([], [])
    assert waits == [1, 2]


def test_summary_and_report():
    results = [
        {"id": "a", "category": "simulation", "status": "passed",
         "checks": [{"name": "x", "passed": True, "detail": ""}], "unverified_amounts": [], "latency_s": 2.0},
        {"id": "b", "category": "limites", "status": "failed",
         "checks": [{"name": "ne cite pas 150.00 €", "passed": False, "detail": "montants cités : 150.00"}],
         "unverified_amounts": ["150 €"], "latency_s": 4.0},
        {"id": "c", "category": "limites", "status": "error", "error": "quota", "latency_s": 0.1},
    ]
    summary = summarize(results)
    assert (summary["passed"], summary["evaluated"], summary["errors"], summary["unverified_amounts"]) == (1, 2, 1, 1)
    assert summary["median_latency_s"] == 3.0

    report = render([{"model": "gemini-test", "complete": True, "llm_calls": 5, "date": "2026-09-16T10:00:00+00:00",
                      "summary": summary, "cases": results}])
    assert "| `gemini-test` | 50 % (1/2) |" in report
    assert "- **b** : ne cite pas 150.00 € (montants cités : 150.00)" in report
    assert "- **c** : erreur d'infrastructure (quota)" in report
