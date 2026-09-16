import copy

import pytest
from conftest import SEF_SIMULATION


def test_home_redirects_to_interactive_documentation(client):
    response = client.get("/", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (307, "/docs")


def test_health_reports_chat_disabled_without_key(client):
    assert client.get("/api/health").json() == {"status": "ok", "chat_enabled": False, "model": None}


def test_list_perimeters(client):
    perimeters = {p["code"]: p for p in client.get("/api/perimeters").json()}
    assert perimeters["SANTE_INDIV"]["active"] is True
    assert perimeters["SANTE_INDIV"]["insurer"] == "Nordale Assurances"
    assert perimeters["OBSEQUES"]["active"] is False


def test_perimeter_details(client):
    data = client.get("/api/perimeters/sante_indiv").json()
    assert data["key_strategy_label"] == "n° de contrat + état + date de souscription"
    essentiel = next(p for p in data["products"] if p["code"] == "NS-ESSENTIEL")
    assert [w["display"] for w in essentiel["year_1"]] == ["80 %", "95 %"]
    assert data["rate_overrides"][0]["display"] == "20 %"


def test_unknown_perimeter_returns_404(client):
    response = client.get("/api/perimeters/AUTO")
    assert response.status_code == 404
    assert "Périmètre inconnu" in response.json()["detail"]


def test_simulate_clawback_of_contract_without_effect(client):
    data = client.post("/api/simulate", json=SEF_SIMULATION).json()
    line = data["lines"][0]
    assert line["amount_display"] == "−1 200,00 €"
    assert (line["rule_id"], line["rule_label"], line["commission_label"]) == (
        "R-RP1", "Reprise totale d'un contrat sans effet", "Reprise")
    assert data["totals"]["net"]["display"] == "−1 200,00 €"


def test_simulate_new_contract(client):
    body = copy.deepcopy(SEF_SIMULATION)
    body.pop("previous_month")
    body["contract"] |= {"state": "AFN", "effective_date": "2026-03-01"}
    line = client.post("/api/simulate", json=body).json()["lines"][0]
    assert (line["commission_type"], line["amount_display"]) == ("P", "1 200,00 €")


def test_simulate_rejects_stopped_perimeter(client):
    body = copy.deepcopy(SEF_SIMULATION)
    body["perimeter"] = "OBSEQUES"
    body["contract"]["product"] = "VO-OBSEQUES"
    response = client.post("/api/simulate", json=body)
    assert response.status_code == 422
    assert "arrêté" in response.json()["detail"]


def test_simulate_rejects_unknown_segment_instead_of_applying_standard_rate(client):
    body = copy.deepcopy(SEF_SIMULATION)
    body["perimeter"] = "EMPRUNTEUR"
    body["contract"] |= {"product": "NE-EMPRUNT-CLASSIQUE", "segment": "RACHAT_CREDIT"}
    response = client.post("/api/simulate", json=body)
    assert response.status_code == 422
    assert "PRIMO, RACHAT" in response.json()["detail"]

    body["contract"]["segment"] = "rachat"
    assert client.post("/api/simulate", json=body).status_code == 200


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("month", "2026-13"),
        ("contract.state", "EN ATTENTE"),
        ("contract.end_date", "2026-01-01"),
        ("contract.unexpected", "x"),
    ],
)
def test_simulate_rejects_invalid_input(client, path, value):
    body = copy.deepcopy(SEF_SIMULATION)
    *parents, leaf = path.split(".")
    target = body
    for key in parents:
        target = target[key]
    target[leaf] = value
    assert client.post("/api/simulate", json=body).status_code == 422


def test_sample_contract_lookup(client):
    data = client.get("/api/samples/SANTE_INDIV/contracts/si-resilie").json()
    assert (data["month"], data["previous_month"], data["contract_id"]) == ("2026-03", "2026-02", "SI-RESILIE")
    assert data["previous_records"][0]["state"] == "En cours"
    assert data["current_records"][0]["state"] == "Résilié"
    assert data["lines"][0]["rule_id"] == "R-RP2"


def test_unknown_sample_contract_lists_scenarios(client):
    response = client.get("/api/samples/SANTE_INDIV/contracts/SI-999")
    assert response.status_code == 404
    assert "SI-NOUVEAU" in response.json()["detail"]
    assert "SI-0001" not in response.json()["detail"]


def test_chat_is_unavailable_without_key(client):
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Bonjour"}]})
    assert response.status_code == 503


def test_openapi_schema_is_generated(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/chat", "/api/simulate", "/api/perimeters/{code}"} <= set(paths)
