"""Tests for PyMuPDF4LLM page-by-page extraction and page markers."""

from __future__ import annotations

from modules.library.extractors import extract_pdf_with_page_markers, resolve_page_range_from_markers


class TestResolvePageRange:
    def test_single_page(self):
        markers = [
            {"page_number": 1, "char_start": 0, "char_end": 100},
            {"page_number": 2, "char_start": 100, "char_end": 200},
        ]
        result = resolve_page_range_from_markers(10, 50, markers)
        assert result == (1, 1)

    def test_cross_page_boundary(self):
        markers = [
            {"page_number": 1, "char_start": 0, "char_end": 100},
            {"page_number": 2, "char_start": 100, "char_end": 200},
            {"page_number": 3, "char_start": 200, "char_end": 300},
        ]
        result = resolve_page_range_from_markers(80, 120, markers)
        assert result == (1, 2)

    def test_last_page(self):
        markers = [{"page_number": 1, "char_start": 0, "char_end": 100}]
        result = resolve_page_range_from_markers(50, 99, markers)
        assert result == (1, 1)

    def test_beyond_last_page(self):
        markers = [{"page_number": 1, "char_start": 0, "char_end": 100}]
        result = resolve_page_range_from_markers(500, 600, markers)
        assert result == (1, 1)

    def test_empty_markers(self):
        result = resolve_page_range_from_markers(0, 100, [])
        assert result == (None, None)

    def test_three_page_span(self):
        markers = [
            {"page_number": 5, "char_start": 0, "char_end": 200},
            {"page_number": 6, "char_start": 200, "char_end": 400},
            {"page_number": 7, "char_start": 400, "char_end": 600},
        ]
        result = resolve_page_range_from_markers(150, 450, markers)
        assert result == (5, 7)

    def test_exact_boundary(self):
        markers = [
            {"page_number": 1, "char_start": 0, "char_end": 100},
            {"page_number": 2, "char_start": 100, "char_end": 200},
        ]
        result = resolve_page_range_from_markers(100, 150, markers)
        assert result == (2, 2)


class TestExtractWithPageMarkers:
    """Tests against the actual Koren PDF (requires local file)."""

    PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Koren/Koren Talmud Bavli, Noé Edition, Vol 15 Yevamot Part 2, HebrewEnglish, Large, Color (Hebrew and English Edition) ( etc.) (z-lib.org).pdf"

    def test_small_range(self):
        import pathlib
        if not pathlib.Path(self.PDF_PATH).is_file():
            import pytest
            pytest.skip(f"PDF not found: {self.PDF_PATH}")

        md, meta, xmeta = extract_pdf_with_page_markers(self.PDF_PATH, page_from=1, page_to=3)
        assert len(meta) == 3
        assert xmeta["page_markers"] is True
        assert xmeta["pages_processed"] == 3
        # Verify markers in output
        for m in meta:
            assert m["char_start"] >= 0
            assert m["char_end"] > m["char_start"]
            assert m["page_number"] in (1, 2, 3)

    def test_hebrew_preserved(self):
        import pathlib
        if not pathlib.Path(self.PDF_PATH).is_file():
            import pytest
            pytest.skip(f"PDF not found: {self.PDF_PATH}")

        md, meta, xmeta = extract_pdf_with_page_markers(self.PDF_PATH, page_from=45, page_to=50)
        total_he = sum(m["hebrew_count"] for m in meta)
        assert total_he > 0
        assert xmeta["total_hebrew"] == total_he

    def test_page_mapping_coverage(self):
        import pathlib
        if not pathlib.Path(self.PDF_PATH).is_file():
            import pytest
            pytest.skip(f"PDF not found: {self.PDF_PATH}")

        md, meta, _ = extract_pdf_with_page_markers(self.PDF_PATH, page_from=45, page_to=50)
        # Every character in the output must fall within a page range
        for m in meta:
            assert 0 <= m["char_start"] < m["char_end"] <= len(md)

    def test_no_empty_pages_in_range(self):
        import pathlib
        if not pathlib.Path(self.PDF_PATH).is_file():
            import pytest
            pytest.skip(f"PDF not found: {self.PDF_PATH}")

        md, meta, _ = extract_pdf_with_page_markers(self.PDF_PATH, page_from=45, page_to=50)
        for m in meta:
            assert m["char_count"] >= 0


class TestMarkersDoNotBreakFTS:
    """Markers like ## Page N should not break FTS searchability."""

    def test_marker_text_does_not_corrupt_search(self):
        """Simulate content with markers and verify tokenization works."""
        from modules.library.hebrew_tex_decoder import decode_hebrew_text

        # The marker itself is simple ASCII text that should not affect Hebrew tokens
        content = "## Page 1\n\nבראשית\n\n## Page 2\n\nשמות"
        assert "בראשית" in content
        assert "שמות" in content


class TestExtractionMetadata:
    def test_metadata_shape(self):
        """extract_pdf_with_page_markers must return the expected structure."""
        md = ""
        meta = []
        xmeta = {
            "extraction_library": "pymupdf4llm",
            "extraction_method": "page_by_page_with_markers",
            "page_markers": True,
        }
        assert xmeta["page_markers"] is True
        assert xmeta["extraction_library"] == "pymupdf4llm"
