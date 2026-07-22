import pytest

from modules.library.editorial_source_layer import (
    SOURCE_LAYERS,
    classify_source_layer,
    literal_context,
    match_hebrew_literal,
)


def test_golden_phrase_returns_confirmed_pdf_form_and_full_paragraph() -> None:
    text = (
        ")מלכים א' ט, ג(: \"וְהָיָה עֵינַי וְלִבִּי שָׁם\".\n"
        "וְאוֹר הָעֵינִין מְעוֹרְרִין הַגְּאֻלָּה.\n"
        "וּשְׂאוֹר וְחָמֵץ שֶׁבְּלֵב הָאָדָם"
    )
    result = literal_context(text, "וְהָיוּ עֵינַי וְלִבִּי שָׁם")
    assert result is not None
    assert result.match_text == "וְהָיָה עֵינַי וְלִבִּי שָׁם"
    assert result.match_kind == "normalized"
    assert "וְאוֹר הָעֵינִין" in result.paragraph_text
    assert result.context_after.startswith("וּשְׂאוֹר")


@pytest.mark.parametrize("query", [
    "וְהָיָה עֵינַי וְלִבִּי שָׁם",
    "והיה עיני ולבי שם",
    "עיני ולבי שם",
    "ולבי שם",
])
def test_confirmed_variants_match_without_rewriting_source(query: str) -> None:
    text = "(מלכים א' ט, ג): וְהָיָה עֵינַי וְלִבִּי שָׁם"
    assert match_hebrew_literal(text, query)


@pytest.mark.parametrize(("text", "zone", "role", "part", "matched", "expected"), [
    ('(מלכים א ט ג) "והיה עיני ולבי שם"', "main_text_hebrew", "primary", "body", "והיה עיני ולבי שם", "biblical_quote_in_lesson"),
    ('(זוהר) "תא חזי"', "main_text_hebrew", "primary", "body", "תא חזי", "rabbinic_quote_in_lesson"),
    ("וזה בחינת תפילה", "main_text_hebrew", "primary", "body", "תפילה", "rebbe_lesson_text"),
    ("Texto traducido", "main_text_spanish", "primary", "body", None, "editorial_translation"),
    ("Explicación editorial", "commentary", "satellite", "body", None, "editorial_commentary"),
    ("Observación del editor", "note_or_source_candidate", "satellite", "body", None, "editorial_note"),
    ("62. Nota numerada", "main_text_spanish", "primary", "body", None, "footnote"),
    ("(Reyes 1, 9:3)", "reference", "satellite", "body", None, "source_reference"),
    ("LIKUTEY MOHARÁN II #83:8", "section_heading", "navigational", "body", None, "section_heading"),
    ("215\nLIKUTEY MOHARÁN II #83:8", "header", "navigational", "body", None, "page_heading"),
    ("Introducción del editor", "main_text_spanish", "primary", "front_matter", None, "introduction"),
    ("Fragmento ambiguo", "ambiguous", "primary", "body", None, "unknown"),
    ("Número de página", "page_number", "navigational", "body", None, "page_heading"),
    ("Encabezado corriente", "header", "navigational", "body", None, "page_heading"),
    ("Índice alfabético", "index", "navigational", "back_matter", None, "unknown"),
    ("Glosario editorial", "glossary", "satellite", "back_matter", None, "editorial_commentary"),
    ("Texto principal sin zona validada", None, None, "main_text", None, "unknown"),
    ("7) Nota conectada", "note_or_source_candidate", "satellite", "body", None, "footnote"),
    ("Explicación secundaria", "translator_note", "satellite", "body", None, "editorial_commentary"),
    ("Referencia breve (Salmos 119:62)", "reference", "satellite", "body", None, "source_reference"),
])
def test_source_layer_batch(text, zone, role, part, matched, expected) -> None:
    decision = classify_source_layer(
        text, zone_type=zone, zone_role=role, document_part=part, matched_text=matched
    )
    assert decision.source_layer == expected
    assert decision.source_layer in SOURCE_LAYERS


def test_unknown_layer_is_prudent() -> None:
    decision = classify_source_layer("sin estructura suficiente", zone_type=None)
    assert (decision.source_layer, decision.confidence) == ("unknown", "low")
