"""Tests for SI-960 TeX Hebrew decoder."""

from __future__ import annotations

import pytest

from modules.library.hebrew_tex_decoder import (
    decode_hebrew_text,
    decode_hebrew_text_selective,
    is_likely_si960_encoded,
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
