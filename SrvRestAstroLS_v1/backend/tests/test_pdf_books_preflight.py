"""Tests for PDF books preflight script."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest


SAMPLE_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\n"
    b"BT /F1 12 Tf 100 700 Td (Hello World this is a test PDF) Tj ET\n"
    b"endstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n"
    b"0000000360 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n441\n%%EOF"
)


@pytest.fixture
def sample_pdf_path() -> pathlib.Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(SAMPLE_PDF)
        return pathlib.Path(f.name)


class TestPreflightScript:
    def test_accepts_multiple_pdfs(self, sample_pdf_path):
        from scripts.preflight_pdf_books import _preflight_pdf
        r1 = _preflight_pdf(sample_pdf_path)
        assert r1["page_count"] == 1
        assert r1["total_chars"] > 0

    def test_parse_args_accepts_multiple_pdfs(self):
        from scripts.preflight_pdf_books import _parse_args
        args = _parse_args(["--pdf", "/a.pdf", "--pdf", "/b.pdf"])
        assert len(args.pdf) == 2

    def test_preflight_returns_required_fields(self, sample_pdf_path):
        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(sample_pdf_path)
        for field in ["filename", "page_count", "total_chars", "total_words",
                       "empty_pages", "detected_language", "needs_ocr",
                       "toc_detected"]:
            assert field in r, f"Missing field: {field}"

    def test_preflight_detects_language(self):
        from scripts.preflight_pdf_books import _detect_language
        assert _detect_language("hello world this is english") == "en"
        assert _detect_language("áéíóú español con acentos") == "es"
        assert _detect_language("\u05d0\u05d1\u05d2 \u05d4\u05d5\u05d6") == "he"

    def test_preflight_no_litellm_imported(self, sample_pdf_path):
        import sys
        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(sample_pdf_path)
        # Only check litellm, not psycopg (which may be imported by other modules)
        assert "litellm" not in sys.modules

    def test_sample_length_limited(self, sample_pdf_path):
        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(sample_pdf_path, sample_chars=50)
        for s in r["samples"]:
            assert len(s["text"]) <= 50

    def test_preflight_calculates_page_count(self, sample_pdf_path):
        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(sample_pdf_path)
        assert r["page_count"] == 1

    def test_empty_page_detection(self, tmp_path):
        """Create a PDF with an empty page and verify detection."""
        import pymupdf as fitz
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        doc.new_page(width=612, height=792)
        path = tmp_path / "empty_test.pdf"
        doc.save(str(path))
        doc.close()

        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(path)
        assert r["page_count"] == 2
        assert r["empty_pages"] >= 1

    def test_structure_detection(self):
        from scripts.preflight_pdf_books import _detect_structure
        text = "Chapter 1\nIntroduction\nSome text\nChapter 2\nMore text\n"
        s = _detect_structure(text, "en")
        assert s["chapter_count"] >= 1

    def test_json_output_valid(self, sample_pdf_path, tmp_path):
        from scripts.preflight_pdf_books import _preflight_pdf
        r = _preflight_pdf(sample_pdf_path)
        report = {"books": [r], "total_books": 1}
        json_str = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["total_books"] == 1
        assert "filename" in parsed["books"][0]


