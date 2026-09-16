import pytest
from conftest import SEF_SIMULATION

from commission_api.assistant.tools import Toolbox, ToolError
from commission_api.schemas import ContractInput, LookupRequest, PerimeterRequest, PreviousMonthInput, SimulationRequest


@pytest.fixture(scope="module")
def toolbox(service):
    return Toolbox(service)


def _parameters(toolbox):
    return {d["function"]["name"]: d["function"]["parameters"] for d in toolbox.definitions}


def test_tool_schemas_match_validation_models(toolbox):
    parameters = _parameters(toolbox)
    simulate = parameters["simulate_contract"]
    pairs = [
        (parameters["get_perimeter_details"], PerimeterRequest),
        (simulate, SimulationRequest),
        (simulate["properties"]["contract"], ContractInput),
        (simulate["properties"]["previous_month"], PreviousMonthInput),
        (parameters["lookup_sample_contract"], LookupRequest),
    ]
    for schema, model in pairs:
        assert set(schema["properties"]) <= set(model.model_fields), model.__name__
        required = {name for name, field in model.model_fields.items() if field.is_required()}
        assert set(schema["required"]) == required, model.__name__


def test_calculation_tools_only_offer_active_perimeters(toolbox):
    parameters = _parameters(toolbox)
    simulate = parameters["simulate_contract"]["properties"]
    assert "OBSEQUES" not in simulate["perimeter"]["enum"]
    assert "VO-OBSEQUES" not in simulate["contract"]["properties"]["product"]["enum"]
    assert "OBSEQUES" in parameters["get_perimeter_details"]["properties"]["perimeter"]["enum"]


def test_simulate_tool_returns_engine_result(toolbox):
    result = toolbox.execute("simulate_contract", SEF_SIMULATION)
    assert result["lines"][0]["amount_display"] == "−1 200,00 €"


def test_lookup_tool_returns_contract_history(toolbox):
    result = toolbox.execute("lookup_sample_contract", {"perimeter": "ANIMAUX", "contract_id": "AN-ANOMALIE"})
    assert result["exclusions"][0]["code"] == "STATE_ANOMALY"


def test_invalid_arguments_produce_readable_error(toolbox):
    arguments = {"perimeter": "SANTE_INDIV", "month": "2026-03", "contract": {"product": "NS-CONFORT"}}
    with pytest.raises(ToolError, match=r"contract\.annual_premium"):
        toolbox.execute("simulate_contract", arguments)


def test_service_errors_are_reported(toolbox):
    with pytest.raises(ToolError, match="Contrats scénarios disponibles"):
        toolbox.execute("lookup_sample_contract", {"perimeter": "SANTE_INDIV", "contract_id": "SI-999"})


def test_unknown_tool(toolbox):
    with pytest.raises(ToolError, match="inconnu"):
        toolbox.execute("delete_everything", {})
