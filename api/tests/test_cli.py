from commission_api.cli import iter_events, render_summary


def test_events_are_parsed_across_arbitrary_chunk_boundaries():
    stream = ['event: delta\ndata: {"text": "Bon', 'jour"}\n\nevent: done\r\n', 'data: {"model": "m"}\r\n\r\n']
    assert list(iter_events(stream)) == [("delta", {"text": "Bonjour"}), ("done", {"model": "m"})]


def test_summary_lists_citations_and_alerts():
    done = {
        "model": "gemini-3.5-flash-lite",
        "citations": [{"rule_id": "R-RP2", "label": "Reprise partielle", "in_answer": True, "from_calculation": False}],
        "unverified_amounts": ["100 €"], "unknown_rules": [], "unknown_products": ["Verdance Essentiel"],
    }
    assert render_summary(done).splitlines() == [
        "--- Modèle : gemini-3.5-flash-lite",
        "Règle R-RP2 (Reprise partielle) : citée, non appliquée par le moteur",
        "Montants sans source : 100 €",
        "Règles inexistantes : aucun",
        "Produits inexistants : Verdance Essentiel",
    ]
