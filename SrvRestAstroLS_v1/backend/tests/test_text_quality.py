import pytest

from modules.library.investigative_qa_v1 import classify
from modules.library.editorial_source_layer import LiteralContext
from modules.library.text_quality import (
    analyze_text_quality,
    build_summary,
    sanitize_evidence_snippet,
)


FOCAL = "servir a HaShem por la noche"


@pytest.mark.parametrize(
    ("case", "text", "phrase", "sanitized"),
    [
        ("c1_start", "\x80\x81\x82\nTexto que permite " + FOCAL, FOCAL, True),
        ("c1_end", "Texto que permite " + FOCAL + "\x80\x81\x82", FOCAL, True),
        ("pdf_marker", "<#>\nTexto que permite " + FOCAL, FOCAL, True),
        ("replacement", "\ufffd Texto que permite " + FOCAL, FOCAL, True),
        ("latin1_mojibake", "InformaciÃ³n editorial sobre " + FOCAL, FOCAL, True),
        ("hebrew", "תפילה בלילה", "תפילה", False),
        ("hebrew_niqqud", "תְּפִלָּה בַּלַּיְלָה", "תְּפִלָּה", False),
        ("bidi_control", "\u202eTexto seguro\u202c", "Texto seguro", True),
        ("spanish", "Oración, emuná y corazón.", "emuná", False),
        ("english", "Serving HaShem during the night.", "HaShem", False),
        ("quotes", "«Texto citado» y “otra cita”.", "Texto citado", False),
        ("ligature", "La ﬁnalidad del estudio.", "ﬁnalidad", False),
        ("nbsp", "Texto\u00a0con espacio.", "con espacio", False),
        ("newline", "Primera línea.\nSegunda línea con plegaria.", "plegaria", False),
        ("hyphenation", "La ora-\nción preservada.", "preservada", False),
        ("inside_match", "servir a\x80 HaShem por la noche", FOCAL, True),
        ("mostly_corrupt", "\x80\x81\x82<#>\ufffd\nTexto válido con plegaria", "plegaria", True),
        ("clean", "Texto completamente limpio.", "limpio", False),
        ("note", "62. Nota editorial comprobable.", "Nota editorial", False),
        ("heading", "LEYES DEL SHULJAN ARUJ", "SHULJAN ARUJ", False),
    ],
)
def test_corrupted_text_batch_preserves_valid_content(
    case: str,
    text: str,
    phrase: str,
    sanitized: bool,
) -> None:
    result = sanitize_evidence_snippet(text, matched_phrase=phrase)
    assert result["raw_snippet"] == text, case
    assert result["sanitization_applied"] is sanitized, case
    assert phrase.casefold() in result["display_snippet"].casefold(), case
    assert not any(0x80 <= ord(char) <= 0x9F for char in result["display_snippet"]), case
    assert "<#>" not in result["display_snippet"], case
    assert "\ufffd" not in result["display_snippet"], case


def test_quality_analysis_distinguishes_controls_markers_and_valid_hebrew() -> None:
    corrupt = analyze_text_quality("\x80\x81\x82<#>texto")
    assert corrupt["has_control_chars"] and corrupt["has_pdf_artifacts"] and corrupt["has_mojibake"]
    hebrew = analyze_text_quality("תְּפִלָּה בַּלַּיְלָה")
    assert not hebrew["has_mojibake"]
    assert not hebrew["reason_codes"]


def test_sanitizer_centers_focal_match_and_preserves_raw_audit_text() -> None:
    raw = "\x80\x81\x82<#>\n" + ("contexto anterior " * 100) + FOCAL + (" contexto posterior" * 100)
    result = sanitize_evidence_snippet(raw, matched_phrase=FOCAL, max_length=240)
    assert result["raw_snippet"] == raw
    assert result["matched_phrase_preserved"]
    assert FOCAL in result["display_snippet"]
    assert len(result["display_snippet"]) <= 242
    assert result["sanitization_reason_codes"]


def test_clean_text_is_not_changed() -> None:
    clean = "Texto completamente limpio con tildes: oración y emuná."
    result = sanitize_evidence_snippet(clean, matched_phrase="oración")
    assert result["display_snippet"] == clean
    assert not result["sanitization_applied"]


def test_summary_uses_correct_singular_and_plural() -> None:
    assert build_summary(1, 1, 0) == (
        "1 evidencia principal · 1 relación contextual · 0 coincidencias literales adicionales"
    )
    assert build_summary(2, 2, 1) == (
        "2 evidencias principales · 2 relaciones contextuales · 1 coincidencia literal adicional"
    )


def test_focal_hit_keeps_literal_strength_separate_from_unknown_source_layer() -> None:
    raw = "\x80\x81\x82\n<#>\nTexto de la edición: " + FOCAL
    hit = classify(
        "lh",
        {
            "record": "page_literal",
            "surface": None,
            "note": None,
            "quote": raw,
            "pdf_page": 137,
            "printed_page": None,
            "zone": None,
            "document_id": "37b5842d-517d-49d1-bab0-3584f409f355",
            "section": "Hashkamat HaBoker — Levantarse por la Mañana",
            "document_part": "main_text",
            "final_page_status": "page_literal_only",
            "match_context": LiteralContext(
                match_text=FOCAL,
                sentence_text=raw,
                paragraph_text=raw,
                context_before="",
                context_after="",
                match_kind="exact_phrase",
            ),
        },
        [FOCAL],
        [FOCAL],
        "library_likutey_halajot_investigative_search_v1",
    )
    assert hit.literal_match_kind == "exact_phrase"
    assert hit.source_layer == "unknown"
    assert hit.source_layer_confidence == "low"
    assert hit.source_layer_rationale == "page_literal_only_without_validated_zone"
    assert hit.author_quote_status == "not_confirmed"
    assert hit.snippet_sanitized
    assert FOCAL in (hit.display_snippet or "")
    assert hit.raw_snippet == raw
