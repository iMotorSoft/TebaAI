"""Unit tests for PDF ligature literal normalization (TEBAAI_..._V1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.library.pdf_ligature_normalization import (
    PDF_FRAGMENT_DIGRAPHS,
    PDF_LIGATURE_EXPANSIONS,
    build_pdf_literal_match_variants,
    expand_pdf_compatibility_characters,
    has_pdf_fragmentation_signal,
    normalize_pdf_search_text,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "pdf_ligature_literal_normalization_v1.json").read_text(
        encoding="utf-8"
    )
)


def test_explicit_ligature_table_matches_fixture() -> None:
    for entry in FIXTURE["ligature_mappings"]:
        assert PDF_LIGATURE_EXPANSIONS[entry["character"]] == entry["nfkc"]


def test_expansion_cases() -> None:
    for case in FIXTURE["positive_examples"]:
        assert (
            expand_pdf_compatibility_characters(case["original"])
            == case["normalized_search"]
        )


def test_expansion_is_mechanical_not_orthographic() -> None:
    # aﬀecto (U+FB00) expands to "affecto"; the normalizer is not a spelling
    # corrector, so it must never produce "afecto".
    assert expand_pdf_compatibility_characters("aﬀecto") == "affecto"
    # oﬃcina (U+FB03 = ffi) expands to "officina"; oﬁcina (U+FB01 = fi) to "oficina".
    assert expand_pdf_compatibility_characters("oﬃcina") == "officina"
    assert expand_pdf_compatibility_characters("oﬁcina") == "oficina"


def test_search_normalization_preserves_internal_space() -> None:
    # The extraction space stays in the canonical search form; joining is a
    # separate, controlled matching variant.
    assert normalize_pdf_search_text("reﬁ namiento") == "refi namiento"
    assert normalize_pdf_search_text("  extracción   y  reﬁ namiento  ") == "extracción y refi namiento"


def test_fragmentation_variants_match_fixture() -> None:
    for case in FIXTURE["fragmentation_variants"]:
        assert build_pdf_literal_match_variants(case["query"]) == case["variants"]


def test_real_words_are_never_joined() -> None:
    for case in FIXTURE["negative_examples"]:
        variants = build_pdf_literal_match_variants(case["query"])
        if "forbidden" in case:
            assert case["forbidden"] not in variants
        if "forbidden_join" in case:
            assert case["forbidden_join"] not in variants


def test_fi_nal_not_joined_without_signal() -> None:
    # "fi nal" keeps its space; the digraph is at the start of the run and
    # there is no extraction signal, so no variant collapses it.
    assert build_pdf_literal_match_variants("fi nal") == ["fi nal"]
    assert build_pdf_literal_match_variants("final") == ["final"]


def test_idempotence() -> None:
    texts = [
        "reﬁnamiento",
        "reﬁ namiento",
        "oﬁ cina",
        "ﬂor",
        "aﬀecto",
        "oﬃcina",
        "וּמִצְרַיִם נָסִים לִקְרָאתוֹ",
        "refinamiento",
    ]
    for text in texts:
        once = normalize_pdf_search_text(text)
        assert normalize_pdf_search_text(once) == once
        assert expand_pdf_compatibility_characters(once) == once


def test_deterministic() -> None:
    text = "Birur hace referencia a la extracción y refinamiento de las chispas"
    assert build_pdf_literal_match_variants(text) == build_pdf_literal_match_variants(text)


def test_hebrew_untouched() -> None:
    for text in FIXTURE["hebrew_regressions"].values():
        assert normalize_pdf_search_text(text) == text
        assert expand_pdf_compatibility_characters(text) == text


def test_spanish_accents_preserved() -> None:
    for word in ["acción", "oración", "Najmán", "Mishkán", "Gedalia of Linitz", "Reb Noson"]:
        assert normalize_pdf_search_text(word) == word


def test_fragmentation_signal() -> None:
    assert has_pdf_fragmentation_signal("refinamiento")
    assert has_pdf_fragmentation_signal("oficina")
    assert not has_pdf_fragmentation_signal("la flor")
    assert not has_pdf_fragmentation_signal("por fin")
    assert not has_pdf_fragmentation_signal("flor")
    assert not has_pdf_fragmentation_signal("Bondad")


def test_note36_query_generates_split_variant() -> None:
    query = FIXTURE["note_36"]["query"]
    variants = build_pdf_literal_match_variants(query)
    assert "refi namiento" in variants[0] or any("refi namiento" in v for v in variants)
    # The canonical form must be first.
    assert variants[0] == normalize_pdf_search_text(query)


def test_digraphs_are_bounded() -> None:
    assert set(PDF_FRAGMENT_DIGRAPHS) == {"ffi", "ffl", "ff", "fi", "fl", "st"}
    assert len(PDF_LIGATURE_EXPANSIONS) == 7
