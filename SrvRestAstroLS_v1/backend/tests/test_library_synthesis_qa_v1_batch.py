from scripts.library_synthesis_qa_v1_batch import deterministic, quote


def test_quote_returns_a_grounded_window_for_a_variant() -> None:
    text = "Antes. La vergüenza es la esencia del arrepentimiento mediante la cual hay perdón. Después."
    result = quote(text, ["vergüenza"])
    assert "vergüenza es la esencia" in result


def test_deterministic_marks_missing_claims_without_inventing_evidence() -> None:
    answer = deterministic("Pregunta", [
        {"claim": "confirmado", "accepted": [{"quote": "Texto", "page": 20}]},
        {"claim": "ausente", "accepted": []},
    ])
    assert "Texto [p. 20]" in answer
    assert "ausente: NO_CONFIRMADO" in answer
