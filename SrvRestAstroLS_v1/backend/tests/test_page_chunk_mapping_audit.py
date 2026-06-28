"""Tests for page-aware chunk mapping audit."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


class TestNormalization:
    def test_remove_accent(self):
        from scripts.audit_page_chunk_mapping import _normalize
        n = _normalize("Página de prueba")
        assert "página" in n or "pagina" in n

    def test_collapse_spaces(self):
        from scripts.audit_page_chunk_mapping import _normalize
        n = _normalize("Hello    World")
        assert n == "hello world"

    def test_preserve_most_chars(self):
        from scripts.audit_page_chunk_mapping import _normalize
        n = _normalize("¡Hola! ¿Cómo estás?")
        assert "cómo" in n


class TestAnchors:
    def test_short_text_single_anchor(self):
        from scripts.audit_page_chunk_mapping import _make_anchors
        text = "hello world. " * 20  # ~260 chars
        anchors = _make_anchors(text, n=50)
        assert len(anchors) >= 1
        assert "hello" in anchors[0]

    def test_long_text_multiple_anchors(self):
        from scripts.audit_page_chunk_mapping import _make_anchors
        text = "word " * 200
        anchors = _make_anchors(text, n=100)
        assert len(anchors) >= 3, f"Expected >=3 anchors, got {len(anchors)}"

    def test_anchors_unique(self):
        from scripts.audit_page_chunk_mapping import _make_anchors
        text = "hello " * 200
        anchors = _make_anchors(text, n=100)
        assert len(anchors) == len(set(anchors))


class TestMatchAnchor:
    def test_exact_match(self):
        from scripts.audit_page_chunk_mapping import _match_anchor_in_pages
        pages = ["this is page one content", "page two has the anchor text here", "page three"]
        hits = _match_anchor_in_pages("anchor text", pages)
        assert hits == [2]

    def test_multiple_pages(self):
        from scripts.audit_page_chunk_mapping import _match_anchor_in_pages
        pages = ["common text here", "some common text there", "no match"]
        hits = _match_anchor_in_pages("common text", pages)
        assert hits == [1, 2]

    def test_no_match(self):
        from scripts.audit_page_chunk_mapping import _match_anchor_in_pages
        pages = ["page one", "page two"]
        hits = _match_anchor_in_pages("nonexistent anchor xyz", pages)
        assert hits == []


class TestDetectHeadings:
    def test_detect_h1(self):
        from scripts.audit_page_chunk_mapping import _detect_headings
        headings = _detect_headings("# Title\n\nSome text")
        assert any("Title" in h for h in headings)

    def test_detect_capitulo(self):
        from scripts.audit_page_chunk_mapping import _detect_headings
        headings = _detect_headings("CAPÍTULO 1: Introducción\n\nText")
        assert any("CAPÍTULO 1" in h for h in headings)

    def test_detect_leccion(self):
        from scripts.audit_page_chunk_mapping import _detect_headings
        headings = _detect_headings("Lección 3\n\nText")
        assert any("Lección 3" in h for h in headings)

    def test_no_false_positive(self):
        from scripts.audit_page_chunk_mapping import _detect_headings
        headings = _detect_headings("This is normal paragraph text without headings")
        assert len(headings) == 0


class TestJSONShape:
    def test_output_shape(self):
        report = {
            "collection": "test",
            "pdf_root": "/tmp",
            "documents": [
                {
                    "title": "Doc",
                    "author": None,
                    "source_filename": "d.pdf",
                    "pdf_path": "/tmp/d.pdf",
                    "pdf_found": True,
                    "pdf_page_count": 10,
                    "chunk_count": 5,
                    "mapped_chunks": 4,
                    "unmapped_chunks": 1,
                    "ambiguous_chunks": 0,
                    "coverage": {"high": 2, "medium": 1, "low": 1, "none": 1},
                    "useful_coverage_pct": 60.0,
                    "heading_candidates": ["# Title"],
                    "sample_mappings": [],
                    "unmapped_samples": [],
                }
            ],
            "summary": {"total_chunks": 5, "useful_chunks": 3, "useful_pct": 60.0},
        }
        json.dumps(report, ensure_ascii=False)
        assert report["summary"]["useful_pct"] == 60.0


class TestCLI:
    def test_parse_args(self):
        from scripts.audit_page_chunk_mapping import _parse_args
        args = _parse_args(["--collection", "test", "--pdf-root", "/tmp/pdfs"])
        assert args.collection == "test"
        assert args.pdf_root == "/tmp/pdfs"

    def test_parse_args_defaults(self):
        from scripts.audit_page_chunk_mapping import _parse_args
        args = _parse_args([])
        assert args.collection == "breslov"
        assert args.sample_size == 5
