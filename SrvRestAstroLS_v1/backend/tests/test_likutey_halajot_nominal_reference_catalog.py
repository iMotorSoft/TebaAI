from modules.library.likutey_halajot_nominal_reference_catalog import catalog_matches
from scripts.likutey_halajot_nominal_reference_detector import find_candidates


def test_catalog_preserves_literal_surface_and_normalizes_only_safe_variant() -> None:
    candidates = find_candidates("Ver Zóhar y Likutey Moharán; no inventar nada.")
    assert {(candidate.surface_form, candidate.normalized_reference_name) for candidate in candidates} == {
        ("Zóhar", "Zohar"), ("Likutey Moharán", "Likutey Moharan")
    }


def test_lone_honorific_is_not_a_generic_reference() -> None:
    assert not find_candidates("Ver Rabí.")


def test_generic_literal_marker_stays_ambiguous_and_unnormalized() -> None:
    candidate = find_candidates("Ver Tzadik #367.")[0]
    assert (candidate.reference_kind, candidate.normalized_reference_name, candidate.validation_status) == (
        "generic_source", None, "ambiguous_surface_form"
    )


def test_catalog_does_not_match_inside_larger_latin_word() -> None:
    assert not catalog_matches("Rashbamic is not a nominal reference.")
