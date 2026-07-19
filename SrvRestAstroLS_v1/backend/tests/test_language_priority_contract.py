import pytest
from pydantic import ValidationError

from modules.library.editorial_source_layer import LiteralContext
from modules.library.investigative_qa_v1 import (
    Hit,
    _compute_retrieval_tier,
    _lm_xv_location,
    _scripture_reference,
    _sort_key,
    classify,
)
from modules.library.multilingual_query import deterministic_interpret, preprocess_query


@pytest.mark.parametrize(("question", "instruction"), [
    ("¿Dónde aparece והיה עיני ולבי שם?", "es"),
    ("where does והיה עיני ולבי שם appear", "en"),
    ("איפה מופיע הפסוק והיו עיני ולבי שם", "he"),
])
def test_instruction_language_is_independent_from_hebrew_subject(question: str, instruction: str) -> None:
    result = deterministic_interpret(preprocess_query(question))
    assert result.instruction_language == instruction
    assert result.literal_phrases[0].language == "he"


def test_followups_reuse_the_literal_context() -> None:
    history = [{"question": "איפה מופיע הפסוק והיו עיני ולבי שם"}]
    for question in ("¿Es texto de la lección o comentario?", "Mostrame el párrafo completo en hebreo.", "¿Existe traducción al español?", "¿En qué página física está?"):
        result = deterministic_interpret(preprocess_query(question), history)
        assert result.intent == "follow_up"
        assert result.resolved_context == history[0]["question"]
        assert result.literal_phrases[0].normalized == "והיו עיני ולבי שם"


def test_lm_xv_header_contract() -> None:
    assert _lm_xv_location("215\nLIKUTEY MOHARÁN II #83:8") == (215, "LIKUTEY MOHARÁN II #83:8")


def test_parallel_translation_requires_same_scripture_key() -> None:
    assert _scripture_reference("(מלכים א' ט, ג)") == ("1_kings", 9, 3)
    assert _scripture_reference("(Reyes 1, 9:3)") == ("1_kings", 9, 3)
    assert _scripture_reference("texto adyacente") is None


def test_hit_rejects_arbitrary_source_layer() -> None:
    with pytest.raises(ValidationError):
        Hit(
            hit_id="x", work_code="lm_xv", work_title="LM XV", quote="x",
            source_view="view", search_record_type="zone", source_layer="invented",
            matched_terms=[], evidence_type="literal_same_page", literal_strength="strong",
            evidence_strength="strong",
        )


def test_classify_emits_structured_hebrew_paragraph_contract() -> None:
    context = LiteralContext(
        match_text="וְהָיָה עֵינַי וְלִבִּי שָׁם", sentence_text="sentence",
        paragraph_text="paragraph", context_before="before", context_after="after",
        match_kind="normalized",
    )
    row = {
        "record": "main_text_hebrew", "surface": None, "note": None,
        "quote": "והיה עיני ולבי שם", "pdf_page": 229, "printed_page": 215,
        "zone": "main_text_hebrew", "source_layer": "biblical_quote_in_lesson",
        "source_layer_confidence": "high", "source_layer_rationale": "reference",
        "match_context": context, "physical_pdf_page": 229, "section": "LIKUTEY MOHARÁN II #83:8",
        "content_node_id": "block", "parent_zone_id": "zone", "page_anchor_id": "page",
    }
    hit = classify("lm_xv", row, ["והיו עיני ולבי שם"], ["והיו עיני ולבי שם"], "view", "he", ["es", "en"])
    assert hit.paragraph_text == "paragraph"
    assert hit.match_text == "וְהָיָה עֵינַי וְלִבִּי שָׁם"
    assert hit.direction == "rtl"
    assert hit.is_original_language and hit.is_primary_language_match
    assert hit.evidence_id == hit.hit_id


def test_original_layer_ranks_before_translation_at_same_language_tier() -> None:
    base = dict(
        work_code="lm_xv", work_title="LM XV", quote="texto", source_view="view",
        search_record_type="zone", matched_terms=["texto"], evidence_type="literal_same_page",
        literal_strength="strong", evidence_strength="strong", retrieval_tier=0,
    )
    original = Hit(hit_id="original", source_layer="rebbe_lesson_text", **base)
    translation = Hit(hit_id="translation", source_layer="editorial_translation", **base)
    assert _sort_key(original) < _sort_key(translation)


def test_secondary_language_never_uses_primary_retrieval_tier() -> None:
    assert _compute_retrieval_tier("secondary", "exact_phrase") > _compute_retrieval_tier("exact", "normalized")
