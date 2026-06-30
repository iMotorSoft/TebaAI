"""Tests for page mapping on Markdown-sourced structural chunks."""

from __future__ import annotations

import re
from collections import Counter

from scripts.enrich_chunk_page_metadata import (
    _make_anchors,
    _normalize,
    _normalization_plus,
)


MARKDOWN_SAMPLE = """## **REBBE NACHMAN**

REB AVRAHAM CHAZZAN Z"L

Published by Breslov Research Institute

## **Chapter 1**

Content of chapter one.

More text here.

## **Chapter 2**

Different content here.
"""


class TestNormalizationForMarkdown:
    def test_markdown_headings_stripped(self):
        t = _normalization_plus("## **Chapter 1**\ncontent")
        assert "chapter 1" in t

    def test_bold_markers_stripped(self):
        t = _normalization_plus("**REBBE NACHMAN**")
        assert "rebbe nachman" in t
        assert "*" not in t

    def test_italic_markers_stripped(self):
        t = _normalization_plus("_**Kokhavey Ohr**_")
        assert "kokhavey ohr" in t
        assert "_" not in t
        assert "*" not in t

    def test_lesson_heading_preserved(self):
        t = _normalization_plus("## Lección 1\ncontent")
        assert "leccion 1" in t

    def test_mixed_formatting(self):
        t = _normalization_plus("## _**Sichot V'Sippurim**_")
        assert "sichot v'sippurim" in t

    def test_special_chars_handled(self):
        t = _normalization_plus("REB AVRAHAM CHAZZAN Z\"L")
        assert "reb avraham chazzan" in t


class TestAnchorsForMarkdownChunks:
    def test_normalization_plus_anchors(self):
        anchors = _make_anchors(MARKDOWN_SAMPLE, n=50, strategy="normalization_plus")
        assert len(anchors) > 0
        for a in anchors:
            assert "*" not in a
            assert "#" not in a

    def test_anchor_length_filter(self):
        anchors = _make_anchors("short", n=50)
        assert len(anchors) == 0

    def test_standard_normalize(self):
        t = _normalize("Hello World\n\n## Heading")
        assert t == "hello world ## heading"


class TestSafety:
    def test_no_litellm_import(self):
        import sys
        assert "litellm" not in sys.modules
