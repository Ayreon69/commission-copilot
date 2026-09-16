from commission_api.assistant.prompt import build_system_prompt


def test_system_prompt_contains_rules_perimeters_and_knowledge(service):
    prompt = build_system_prompt(service.catalog, "## Règles\n\nContenu des règles métier {avec accolades}", "2026-03")
    assert "Opaline Courtage" in prompt
    assert "Tu ne calcules jamais toi-même un montant" in prompt
    assert "| SANTE_INDIV | Santé individuelle | Nordale Assurances | oui |" in prompt
    assert "| OBSEQUES | Obsèques | Mutuelle Verdance | non, périmètre arrêté |" in prompt
    assert "Mois de calcul par défaut : 2026-03" in prompt
    assert prompt.rstrip().endswith("Contenu des règles métier {avec accolades}")
