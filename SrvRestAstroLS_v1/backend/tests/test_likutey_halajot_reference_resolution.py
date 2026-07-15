from scripts.likutey_halajot_reference_resolution_investigative import resolve


def row(surface_form: str) -> dict:
    return {"surface_form": surface_form, "text_quote": f"Ver {surface_form}.", "cross_mappings": [], "cross_kind": None}


def test_internal_locator_is_rejected_not_normalized() -> None:
    decision, kind, name, _, method, _, confidence, _ = resolve(row("más arriba, p. 86"))
    assert (decision, kind, name, method, confidence) == ("rejected_false_positive", None, None, "false_positive_rule", .98)


def test_talmudic_literal_is_resolved_for_search_only() -> None:
    decision, kind, name, _, method, _, confidence, _ = resolve(row("Berajot 4a, donde se explica"))
    assert (decision, kind, name, method, confidence) == ("resolved_canonical_reference", "talmudic_tractate", "Berajot", "deterministic_pattern", .92)


def test_unclassified_literal_remains_valid_generic_source() -> None:
    decision, kind, name, _, method, _, confidence, _ = resolve(row("Una obra sin patrón seguro"))
    assert (decision, kind, name, method, confidence) == ("keep_generic_source", "generic_source", None, "fallback_keep_generic", .72)
