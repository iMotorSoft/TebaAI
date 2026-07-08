"""Tests for SI-960 TeX Hebrew decoder."""

from __future__ import annotations

import pytest

from modules.library.hebrew_tex_decoder import (
    decode_hebrew_text,
    decode_hebrew_text_selective,
    is_likely_si960_encoded,
    scan_unknown_characters,
    SI960_TO_HEBREW,
)


class TestAyinMapping:
    def test_ayin_double_quote_mapped(self):
        assert '"' in SI960_TO_HEBREW
        assert SI960_TO_HEBREW['"'] == "\u05e2"

    def test_ayin_decodes_correctly(self):
        result = decode_hebrew_text('w"d')
        assert "\u05e2" in result

    def test_ayin_in_page704_context(self):
        line = ".'\"ydw w\"d ,b\"d Nkw yrqw bytk h'"
        result = decode_hebrew_text(line)
        assert any("\u0590" <= c <= "\u05ff" for c in result)
        assert "\u05e2" in result


class TestKnownDecodings:
    def test_title_page_decode(self):
        result = decode_hebrew_text("Mybwtk My'ybn hrwt")
        assert "\u05db\u05ea\u05d5\u05d1\u05d9\u05dd" in result

    def test_tehillim_decode(self):
        result = decode_hebrew_text("Mylht")
        assert "\u05ea\u05d4\u05dc\u05d9\u05dd" in result

    def test_yirmeyahu_decode(self):
        result = decode_hebrew_text("hymry")
        assert "\u05d9\u05e8\u05de\u05d9\u05d4" in result

    def test_no_empty_chunks(self):
        samples = ["Mybwtk", "Mylht", "hymry", "Nkw", "yrqw", "bytk"]
        for s in samples:
            result = decode_hebrew_text(s)
            assert len(result) > 0


class TestSelectiveDecoding:
    def test_english_preserved(self):
        text = "Introduction to the Massoretico-Critical edition"
        result = decode_hebrew_text_selective(text)
        assert result == text

    def test_english_with_punctuation_preserved(self):
        text = "This edition, prepared by C.D. Ginsburg, contains 4438 notes."
        result = decode_hebrew_text_selective(text)
        assert result == text

    def test_hebrew_decoded(self):
        text = "Mybwtk My'ybn hrwt"
        result = decode_hebrew_text_selective(text)
        assert any("\u0590" <= c <= "\u05ff" for c in result)
        assert "\u05db\u05ea\u05d5\u05d1\u05d9\u05dd" in result

    def test_hebrew_page_decoded(self):
        text = ".'\"ydw w\"d ,b\"d Nkw yrqw bytk h'"
        result = decode_hebrew_text_selective(text)
        assert any("\u0590" <= c <= "\u05ff" for c in result)

    def test_technical_english_not_decoded(self):
        text = "Typeset with pdfLATEX under Linux"
        result = decode_hebrew_text_selective(text)
        assert result == text

    def test_mixed_page_english_preserved(self):
        text = "And its peseqot are 23. The years of the book"
        result = decode_hebrew_text_selective(text)
        assert result == text

    def test_empty_text(self):
        assert decode_hebrew_text_selective("") == ""
        assert decode_hebrew_text_selective("   ") == "   "


class TestSi960Detection:
    def test_detect_title_hebrew(self):
        assert is_likely_si960_encoded("Mybwtk My'ybn hrwt")

    def test_not_detect_english_intro(self):
        assert not is_likely_si960_encoded(
            "Introduction to the Massoretico-Critical edition of the Hebrew Bible"
        )

    def test_not_detect_technical_english(self):
        assert not is_likely_si960_encoded(
            "Typeset with pdfLATEX under Linux: Sun 31st Jul, 2005 at 04:39"
        )

    def test_not_detect_english_with_proper_nouns(self):
        assert not is_likely_si960_encoded(
            "New corrected text, notes and typesetting copyright Bibles.org.uk."
        )

    def test_detect_hebrew_page_with_numbers(self):
        assert is_likely_si960_encoded(
            "23. 29-24. 3\nhymry\n751\nrB¡Ď hČ =tŇ 'Ć NbĆŇ"
        )

    def test_not_detect_english_notes(self):
        assert not is_likely_si960_encoded(
            "[Exod 2:2]. And its peseqot are 23. The years of the book"
        )

    def test_detect_long_hebrew_page(self):
        text = "33. 22-34. 13\nCnylĳĄ'Ď hoăĎhyĘ ìăŇDĘsĘ xČ =yhĲĂ yĘ"
        assert is_likely_si960_encoded(text)

    def test_hebrew_unicode_already_present(self):
        assert not is_likely_si960_encoded('\u05db\u05ea\u05d5\u05d1\u05d9\u05dd \u05e0\u05d1\u05d9\u05d0\u05d9\u05dd')

    def test_short_text_not_false_positive(self):
        assert not is_likely_si960_encoded("A")
        assert not is_likely_si960_encoded("")


class TestHebrewPreservation:
    def test_utf8_preserved_after_decode(self):
        samples = [
            "Mybwtk My'ybn hrwt",
            "hymry",
            "Mylht",
        ]
        for s in samples:
            result = decode_hebrew_text(s)
            encoded = result.encode("utf-8")
            decoded_back = encoded.decode("utf-8")
            assert decoded_back == result

    def test_no_corrupted_surrogates(self):
        result = decode_hebrew_text("Mybwtk My'ybn hrwt")
        for c in result:
            cp = ord(c)
            assert not (0xD800 <= cp <= 0xDFFF)

    def test_only_valid_unicode(self):
        result = decode_hebrew_text("Mybwtk My'ybn hrwt")
        for c in result:
            cp = ord(c)
            assert cp <= 0x10FFFF


class TestSi960Reversals:
    def test_word_reversal_correct(self):
        result = decode_hebrew_text("Mybwtk")
        assert result == "\u05db\u05ea\u05d5\u05d1\u05d9\u05dd"

    def test_multi_word_reversal(self):
        result = decode_hebrew_text("Mybwtk My'ybn hrwt")
        words = result.split()
        assert len(words) >= 3


class TestNewMappings:
    """Tests for newly added SI-960 character mappings."""

    def test_inverted_exclamation_maps_to_meteg(self):
        """¡ (U+00A1) should decode to meteg (U+05BD)."""
        result = decode_hebrew_text("word\xa1word")
        assert "\u05bd" in result

    def test_meteg_in_context(self):
        """Actual Tiqwah content with ¡ should produce meteg."""
        # Sample from page 29 raw text containing ¡
        raw = "MyĂU¡ČhČ"
        result = decode_hebrew_text(raw)
        assert "\u05bd" in result
        assert any("\u0590" <= c <= "\u05ff" for c in result)

    def test_grave_i_maps_to_qamats_qatan(self):
        """Ì (U+00CC) should decode to qamats qatan (U+05C7)."""
        result = decode_hebrew_text("word\xccword")
        assert "\u05c7" in result

    def test_question_mark_preserved(self):
        """¿ (U+00BF) should be preserved as-is (not yet mapped)."""
        result = decode_hebrew_text("word\xbfword")
        assert "\u00bf" in result
        assert "¿" in result

    def test_i_acute_preserved(self):
        """Í (U+00CD) should be preserved as-is (not yet mapped)."""
        result = decode_hebrew_text("word\xcdword")
        assert "\u00cd" in result


class TestArtifactDetection:
    """Tests for scan_unknown_characters utility."""

    def test_clean_hebrew_no_artifacts(self):
        result = scan_unknown_characters("\u05d0\u05d1\u05d2 \u05d3\u05d4\u05d5")
        assert len(result) == 0

    def test_detects_unknown_characters(self):
        result = scan_unknown_characters("\u05d0\xbf\u05d1\xcd\u05d2")
        # ¿ and Í are outside Hebrew block and should be detected
        assert len(result) >= 1

    def test_detects_count(self):
        result = scan_unknown_characters("\u05d0\xbf\u05d1\xbf\u05d2")
        assert result.get("\u00bf", 0) == 2

    def test_meteg_not_counted_as_artifact(self):
        """Meteg (U+05BD) is a valid Hebrew mark, not an artifact."""
        result = scan_unknown_characters("word\u05bdword")
        assert "\u05bd" not in result

    def test_qamats_qatan_not_counted(self):
        """Qamats qatan (U+05C7) is a valid Hebrew mark."""
        result = scan_unknown_characters("word\u05c7word")
        assert "\u05c7" not in result

    def test_english_not_counted(self):
        result = scan_unknown_characters("Hello World 123!")
        assert len(result) == 0

    def test_final_letters_preserved(self):
        """Final forms (sofit) must be preserved (C=final tsadi, not S)."""
        result = decode_hebrew_text("KMNPC")
        assert "\u05da" in result  # final kaf
        assert "\u05dd" in result  # final mem
        assert "\u05df" in result  # final nun
        assert "\u05e3" in result  # final pe
        assert "\u05e5" in result  # final tsadi

    def test_dagesh_preserved(self):
        """Dagesh marks must be present after decoding."""
        result = decode_hebrew_text("BGD")
        assert "\u05bc" in result  # dagesh


class TestNiqqudPreservation:
    """Niqqud (vowel marks) must survive decoding."""

    def test_he8_niqqud_mapped(self):
        """HE8 niqqud range (U+00C0-U+00CB) must map to Hebrew niqqud."""
        for cp in range(0xC0, 0xCC):
            result = decode_hebrew_text(chr(cp))
            assert any(0x05B0 <= ord(c) <= 0x05BB for c in result), \
                f"Position U+{cp:04X} did not produce niqqud"

    def test_niqqud_in_full_word(self):
        """A word with niqqud must preserve vowel marks."""
        raw = "rBĎ hČ"  # Words with niqqud
        result = decode_hebrew_text(raw)
        # Should contain Hebrew consonants and at least one niqqud mark
        he_chars = sum(1 for c in result if 0x0590 <= ord(c) <= 0x05FF)
        niqqud_chars = sum(1 for c in result if 0x05B0 <= ord(c) <= 0x05BB)
        assert he_chars > 0
        assert niqqud_chars > 0


class TestOrderPreservation:
    """The decoder must not reverse logical RTL order."""

    def test_hebrew_word_not_empty_after_reversal(self):
        result = decode_hebrew_text("Mybwtk")
        assert len(result) > 0
        # The word should be the correct Hebrew, not just reversed garbage
        assert result == "\u05db\u05ea\u05d5\u05d1\u05d9\u05dd"

    def test_english_word_not_reversed(self):
        """English words must remain in reading order."""
        result = decode_hebrew_text_selective("Hello word")
        assert result == "Hello word"

    def test_mixed_content_not_corrupted(self):
        """Numbers and punctuation in Hebrew context must survive."""
        raw = "23. 29-24. 3"
        result = decode_hebrew_text_selective(raw)
        assert "23" in result
        assert "29" in result
