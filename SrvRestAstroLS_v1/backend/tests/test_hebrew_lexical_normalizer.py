"""Tests for Hebrew lexical normalizer."""

from __future__ import annotations

import pytest

from modules.library.hebrew_lexical_normalizer import (
    extract_literal_segments,
    normalize_hebrew_lexical,
    has_hebrew,
    strip_niqqud,
    strip_taamim,
    strip_hebrew_marks,
    strip_meteg,
    normalize_maqaf,
    remove_invisible_marks,
    normalize_hebrew_search,
    normalize_hebrew_for_search,
    reconstruct_pdf_spaced_hebrew,
)


class TestHasHebrew:
    def test_hebrew_detected(self):
        assert has_hebrew("תלמוד")
        assert has_hebrew("בראשית ברא")

    def test_english_not_detected(self):
        assert not has_hebrew("Hello world")
        assert not has_hebrew("Talmud")

    def test_mixed_content(self):
        assert has_hebrew("Talmud תלמוד")
        assert has_hebrew("בראשית Genesis")

    def test_empty_string(self):
        assert not has_hebrew("")
        assert not has_hebrew("   ")


class TestStripNiqqud:
    def test_strips_basic_niqqud(self):
        result = strip_niqqud("תַּלְמוּד")
        assert result == "תלמוד", f"Got {result!r}"

    def test_hebrew_without_niqqud_unchanged(self):
        result = strip_niqqud("שלום")
        assert result == "שלום"

    def test_english_unchanged(self):
        result = strip_niqqud("Hello")
        assert result == "Hello"

    def test_mixed_preserved(self):
        result = strip_niqqud("שָלוֹם world")
        assert "שלום" in result
        assert "world" in result


class TestStripTaamim:
    def test_strips_taamim(self):
        result = strip_taamim("בְּרֵאשִׁ֖ית")
        assert result == "בְּרֵאשִׁית", f"Got {result!r}"

    def test_without_taamim_unchanged(self):
        result = strip_taamim("תלמוד")
        assert result == "תלמוד"


class TestStripMeteg:
    def test_strips_meteg(self):
        result = strip_meteg("וַיִּקְרָֽא")
        assert "\u05bd" not in result
        assert len(result) < len("וַיִּקְרָֽא")


class TestStripHebrewMarks:
    def test_strips_all_marks(self):
        result = strip_hebrew_marks("תַּלְמֻֽד")
        assert "ת" in result
        assert "ל" in result
        assert "מ" in result
        assert "ד" in result
        # No niqqud, taamim, meteg
        for c in result:
            assert ord(c) not in range(0x0591, 0x05BD + 1)
            assert ord(c) not in {0x05C1, 0x05C2, 0x05C7}


class TestNormalizeMaqaf:
    def test_maqaf_to_hyphen(self):
        result = normalize_maqaf("בית־לחם")
        assert "-" in result
        assert "\u05be" not in result

    def test_no_maqaf_unchanged(self):
        result = normalize_maqaf("תלמוד")
        assert result == "תלמוד"


class TestRemoveInvisible:
    def test_removes_directional_marks(self):
        result = remove_invisible_marks("a\u200eb")
        assert result == "ab"

    def test_removes_bom(self):
        result = remove_invisible_marks("\ufefftext")
        assert result == "text"


class TestNormalizeHebrewLexical:
    def test_basic_normalization(self):
        result = normalize_hebrew_lexical("תַּלְמוּד")
        assert result == "תלמוד"

    def test_full_normalization(self):
        result = normalize_hebrew_lexical("בְּרֵאשִׁ֖ית")
        # After removing taamim, niqqud, meteg
        assert "ב" in result
        assert "ר" in result
        assert "א" in result
        assert "ש" in result
        assert "י" in result
        assert "ת" in result
        # No marks
        for c in result:
            assert ord(c) not in range(0x0591, 0x05C8)

    def test_mixed_content_preserved(self):
        result = normalize_hebrew_lexical("Hello תַּלְמוּד world")
        assert "Hello" in result
        assert "תלמוד" in result
        assert "world" in result

    def test_english_unchanged(self):
        result = normalize_hebrew_lexical("The Talmud is a central text")
        assert result == "The Talmud is a central text"

    def test_spanish_unchanged(self):
        result = normalize_hebrew_lexical("El Talmud es un texto central")
        assert result == "El Talmud es un texto central"

    def test_idempotent(self):
        x = normalize_hebrew_lexical("תַּלְמוּד")
        y = normalize_hebrew_lexical(x)
        assert x == y

    def test_with_niqqud_off(self):
        result = normalize_hebrew_lexical("תַּלְמוּד", do_niqqud=False)
        # Should still have niqqud
        has_niqqud = any(0x05B0 <= ord(c) <= 0x05BC for c in result)
        assert has_niqqud, "Niqqud should be preserved when do_niqqud=False"

    def test_without_maqaf_normalization(self):
        result = normalize_hebrew_lexical("בית־לחם", do_maqaf=False)
        assert "\u05be" in result
        assert "-" not in result

    def test_hebrew_query_with_niqqud(self):
        """Core use case: query like 'מסכת' with niqqud should normalize."""
        result = normalize_hebrew_lexical("מַסֶּכֶת")
        assert result == "מסכת"
        assert "מ" in result
        assert "ס" in result
        assert "כ" in result
        assert "ת" in result


class TestNormalizeHebrewSearch:
    def test_equivalent_niqqud_and_unicode_forms(self):
        pointed = "תְּהִלָּתִי אֶחְטָם לָךְ"
        assert normalize_hebrew_search(pointed) == "תהלתי אחטם לך"
        assert normalize_hebrew_search(pointed) == normalize_hebrew_search(
            __import__("unicodedata").normalize("NFD", pointed)
        )

    def test_punctuation_spaces_and_bidi_controls_are_optional(self):
        assert normalize_hebrew_search('\u2067“תהלתי,  אחטם לך!”\u2069') == "תהלתי אחטם לך"

    def test_preserves_final_letters_and_word_boundaries(self):
        assert normalize_hebrew_search("אחטם לך") == "אחטם לך"
        assert normalize_hebrew_search("אחטמ לך") != normalize_hebrew_search("אחטם לך")

    def test_does_not_reverse_text(self):
        value = normalize_hebrew_search("תהלתי אחטם לך")
        assert value == "תהלתי אחטם לך"
        assert value != "ךל םטחא יתלהת"


PDF_SPACED = "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך"


@pytest.mark.parametrize(("question", "instruction", "language"), [
    (f"{PDF_SPACED} donde esta", "donde esta", "es"),
    (f"dónde aparece {PDF_SPACED}", "dónde aparece", "es"),
    (f"{PDF_SPACED} where is", "where is", "en"),
    (f"find {PDF_SPACED}", "find", "en"),
    (f"איפה {PDF_SPACED}", "איפה", "he"),
    (f"היכן מופיע {PDF_SPACED}", "היכן מופיע", "he"),
])
def test_extracts_script_literal_without_location_instruction(
    question: str,
    instruction: str,
    language: str,
) -> None:
    result = extract_literal_segments(question)
    assert result is not None
    assert result.literal_raw == PDF_SPACED
    assert result.instruction == instruction
    assert result.instruction_language == language
    assert result.compact_letters == "תהלתיאחטםלך"
    assert result.pdf_glyph_spacing_detected is True
    assert len(result.candidates) <= 64
    assert "תהלתי אחטם לך" in result.candidates


@pytest.mark.parametrize("separator", [" ", "  ", "\u00a0", "\u2009", "\n"])
def test_reassociates_spaced_letters_and_niqqud_without_reversing(separator: str) -> None:
    raw = separator.join(["ת", "ְּ", "הִ", "לָּ", "ת", "ִ", "י", "אֶ", "חְ", "ט", "ָ", "ם", "לָ", "ך"])
    result = reconstruct_pdf_spaced_hebrew(raw, "תהלתי אחטם לך")
    assert result == "תְּהִלָּתִי אֶחְטָם לָך"
    assert result != "ךָל םטָחְאֶ יתִלָּהִתְּ"


def test_clean_word_boundaries_are_preserved() -> None:
    result = extract_literal_segments("תְּהִלָּתִי אֶחְטָם לָךְ")
    assert result is not None
    assert result.pdf_glyph_spacing_detected is False
    assert result.literal_reconstructed == "תְּהִלָּתִי אֶחְטָם לָךְ"
    assert result.literal_search_normalized == "תהלתי אחטם לך"


def test_no_phrase_specific_substitution_occurs() -> None:
    result = extract_literal_segments("א ב ג ד ה where is")
    assert result is not None
    assert result.compact_letters == "אבגדה"
    assert "תהלתי" not in result.literal_reconstructed


@pytest.mark.parametrize(
    "value",
    [
        "וּמִצְרַיִם נָסִים לִקְרָאתוֹ",
        "ומצרים נסים לקראתו",
        __import__("unicodedata").normalize(
            "NFD", "וּמִצְרַיִם נָסִים לִקְרָאתוֹ"
        ),
        "\u2067וּמִצְרַיִם נָסִים לִקְרָאתוֹ\u2069",
    ],
)
def test_target_forms_share_the_same_search_representation(value: str) -> None:
    result = normalize_hebrew_for_search(value)
    assert result.without_niqqud == "ומצרים נסים לקראתו"
    assert result.tokens == ("ומצרים", "נסים", "לקראתו")
    assert result.compact_letters == "ומצריםנסיםלקראתו"


def test_realistic_fragmented_phrase_repairs_pdf_spacing() -> None:
    result = normalize_hebrew_for_search(
        "וּמ ִ צְ ר ַ יִם נָ סִ ים לִ ק ְר ָ אתו"
    )
    assert result.artificial_spacing_detected is True
    assert result.without_niqqud == "ומצרים נסים לקראתו"
    assert result.tokens == ("ומצרים", "נסים", "לקראתו")


@pytest.mark.parametrize(
    "value",
    [
        "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך",
        "א ֲ ז ַ מ ְּ ר ָ ה",
        "מ ָ ה ה ַ ק ֶּ ש ֶׁ ר ב ֵּ י ן ד ִּ ב ּ וּ ר ל ֶ א ֱ מ וּ נ ָ ה",
        "ו ְ ה ָ י ָ ה כ ְּ צ ֵ א ת ִ י א ֶ ת ה ָ ע ִ י ר",
        "ש ְׁ כ ָ ן א ֶ ר ֶ ץ וּ ר ְ ע ֵ ה א ֱ מ וּ נ ָ ה",
    ],
)
def test_additional_realistic_pdf_spacing_fixtures_are_bounded(value: str) -> None:
    result = normalize_hebrew_for_search(value)
    assert result.artificial_spacing_detected is True
    assert result.compact_letters
    assert result.tokens
    assert len(result.approximate_variants) <= 64
