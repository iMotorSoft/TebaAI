"""Tests for Sijot-aware page mapping enrichment."""

from __future__ import annotations

import json

import pytest

from scripts.enrich_chunk_page_metadata import (
    _normalize,
    _normalization_plus,
    _make_anchors,
)


class TestNormalizationPlus:
    def test_unicode_nfkc(self):
        result = _normalization_plus("café \u2160")
        assert "cafe" in result

    def test_lowercase(self):
        result = _normalization_plus("HELLO WORLD")
        assert result == "hello world"

    def test_unaccent(self):
        result = _normalization_plus("Sijá 25")
        assert "sija" in result
        assert "sijá" not in result

    def test_markdown_headings_stripped(self):
        result = _normalization_plus("## Sija 1\ncontent")
        assert "sija 1" in result
        assert "## " not in result

    def test_markdown_bold_italic_stripped(self):
        result = _normalization_plus("## _**Sija**_ **#25**")
        assert "sija" in result
        assert "*" not in result
        assert "_" not in result

    def test_sija_normalization(self):
        """Sijá #25, Sija #25, Sijá 25 all normalize to 'sija 25'."""
        results = []
        for variant in ["Sijá #25", "Sija #25", "Sijá 25", "Sija 25"]:
            results.append(_normalization_plus(variant))
        assert all(r == "sija 25" for r in results)

    def test_dash_normalization(self):
        result = _normalization_plus("word\u2013word")
        assert "word-word" in result
        assert "\u2013" not in result

    def test_quote_normalization(self):
        result = _normalization_plus("\u201cquoted\u201d")
        assert '"quoted"' in result

    def test_whitespace_collapse(self):
        result = _normalization_plus("many   spaces\tand\nnewlines")
        assert "many spaces and newlines" == result


class TestNormalize:
    def test_basic(self):
        assert _normalize("Hello World") == "hello world"

    def test_whitespace(self):
        assert _normalize("a   b\n\nc") == "a b c"


class TestMakeAnchors:
    def test_short_text_returns_empty(self):
        text = "Short text"
        anchors = _make_anchors(text, n=50)
        assert len(anchors) == 0  # filtered by min length 50

    def test_long_text_multiple_anchors(self):
        text = ("A" * 500 + " " + "B" * 500) * 3
        anchors = _make_anchors(text, n=100)
        assert len(anchors) >= 1
        for a in anchors:
            assert len(a) >= 50

    def test_normalization_plus_strategy(self):
        text = "## _**Sija**_ **#25** content\n\nPage text here"
        anchors = _make_anchors(text, n=50, strategy="normalization_plus")
        for a in anchors:
            assert "##" not in a
            assert "*" not in a
            assert "_" not in a

    def test_anchor_length_filter(self):
        text = "ab"
        anchors = _make_anchors(text, n=50)
        assert len(anchors) == 0

    def test_deduplication(self):
        text = "AAAA" * 100
        anchors = _make_anchors(text, n=100)
        # Check there are no exact duplicates
        assert len(anchors) == len(set(anchors))
