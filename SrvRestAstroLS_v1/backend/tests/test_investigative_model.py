from modules.library.investigative_model import expand_query, relation_strength, stable_hash

def test_span_hash_is_normalization_stable():
    assert stable_hash("Alegría  del Rebe") == stable_hash("Alegría del Rebe")

def test_spanish_query_expands_to_hebrew_english_and_transliteration():
    expanded = expand_query("¿Dónde habla de la alegría?")
    assert expanded.language == "es"
    assert {"שמחה", "simcha", "joy"}.issubset(expanded.variants)

def test_hebrew_query_expands_across_languages():
    expanded = expand_query("תפילה")
    assert expanded.language == "he"
    assert {"plegaria", "tefilah", "prayer"}.issubset(expanded.variants)

def test_same_page_cross_role_is_never_strong():
    assert relation_strength("same_page", "same_page", "primary", "satellite") == "weak_contextual"

def test_translation_and_literal_spans_are_strong():
    assert relation_strength("parallel_translation", "translation_alignment", "primary", "primary") == "strong"
    assert relation_strength("same_node", "literal_same_span", "primary", "primary") == "strong"
