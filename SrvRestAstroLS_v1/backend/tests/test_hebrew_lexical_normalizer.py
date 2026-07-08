"""Tests for Hebrew lexical normalizer."""

from __future__ import annotations

from modules.library.hebrew_lexical_normalizer import (
    normalize_hebrew_lexical,
    has_hebrew,
    strip_niqqud,
    strip_taamim,
    strip_hebrew_marks,
    strip_meteg,
    normalize_maqaf,
    remove_invisible_marks,
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
