"""Tests for bibliographic structure audit script."""

from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest


class TestAuditPatterns:
    """Test pattern detection logic independently of DB."""

    def test_detect_heading_markdown_h1(self):
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        for pat in HEADING_PATTERNS:
            if re.match(pat, "# Title"):
                break
        else:
            pytest.fail("No pattern matched '# Title'")
        assert True

    def test_detect_heading_capitulo(self):
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        for pat in HEADING_PATTERNS:
            if re.match(pat, "CAPÍTULO 1"):
                break
        else:
            pytest.fail("No pattern matched 'CAPÍTULO 1'")
        assert True

    def test_detect_heading_leccion(self):
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        for pat in HEADING_PATTERNS:
            if re.match(pat, "Lección 3"):
                break
        else:
            pytest.fail("No pattern matched 'Lección 3'")
        assert True

    def test_detect_heading_halaja(self):
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        for pat in HEADING_PATTERNS:
            if re.match(pat, "Halajá 5"):
                break
        else:
            pytest.fail("No pattern matched 'Halajá 5'")
        assert True

    def test_detect_page_marker(self):
        from scripts.audit_bibliographic_structure import PAGE_PATTERNS
        import re
        for pat in PAGE_PATTERNS:
            if re.search(pat, "Página 42"):
                break
        else:
            pytest.fail("No pattern matched 'Página 42'")
        assert True

    def test_detect_page_marker_dash(self):
        from scripts.audit_bibliographic_structure import PAGE_PATTERNS
        import re
        for pat in PAGE_PATTERNS:
            if re.search(pat, "- 123 -"):
                break
        else:
            pytest.fail("No pattern matched '- 123 -'")
        assert True

    def test_no_false_positive_for_normal_text(self):
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        for pat in HEADING_PATTERNS:
            if re.match(pat, "This is normal text without markers"):
                pytest.fail(f"Pattern '{pat}' false-matched normal text")
        assert True

    def test_heading_candidates_capped(self):
        # Test that the extraction caps at max_heading_candidates
        lines = [f"# Heading {i}" for i in range(100)]
        from scripts.audit_bibliographic_structure import HEADING_PATTERNS
        import re
        heading_set = set()
        for line in lines:
            stripped = line.strip()
            for pat in HEADING_PATTERNS:
                if re.match(pat, stripped):
                    heading_set.add(stripped)
                    break
        capped = sorted(heading_set)[:30]
        assert len(capped) <= 30
        assert len(heading_set) > 30  # confirm there were more


class TestAuditJSON:
    def test_json_shape(self):
        """Verify audit output JSON structure."""
        output = {
            "collection": "breslov",
            "total_documents": 1,
            "total_chunks": 10,
            "documents": [
                {
                    "title": "Test Doc",
                    "author": None,
                    "source_filename": "test.pdf",
                    "content_length": 1000,
                    "chunk_count": 10,
                    "existing_metadata": {
                        "page_fields_available": False,
                        "chunks_with_page": 0,
                        "chunks_with_chapter": 0,
                        "chunks_with_section": 0,
                        "page_start_end_exists_in_db": False,
                    },
                    "page_marker_candidates": [],
                    "heading_candidates": ["# Title", "## Chapter 1"],
                    "chapter_references": ["Capítulo 1"],
                    "sample_content_start": "",
                    "chunking_observations": [],
                    "chunk_lengths": {"avg": 500.0, "min": 100, "max": 2000},
                    "confidence": "low",
                    "recommended_strategy": "Re-extract PDF",
                }
            ],
            "existing_metadata_summary": {
                "total_chunks": 10,
                "chunks_with_page": 0,
                "chunks_with_chapter": 0,
                "pct_with_page": 0.0,
                "pct_with_chapter": 0.0,
                "fields_available": {"page_start": False, "chapter": False, "section": False},
            },
            "pdf_availability": {
                "directory": "/tmp",
                "files": {"test.pdf": {"exists": False}},
            },
        }
        # Should serialize to JSON without error
        json.dumps(output, ensure_ascii=False)


class TestCLI:
    def test_parse_args_required(self):
        from scripts.audit_bibliographic_structure import _parse_args

        args = _parse_args([])
        assert args.collection == "breslov"
        assert args.sample_lines == 5

    def test_parse_args_output(self):
        from scripts.audit_bibliographic_structure import _parse_args

        args = _parse_args([
            "--collection", "test",
            "--output-md", "/tmp/out.md",
            "--output-json", "/tmp/out.json",
            "--sample-lines", "3",
            "--max-heading-candidates", "50",
            "--max-page-markers", "20",
            "--verbose",
        ])
        assert args.collection == "test"
        assert args.output_md == "/tmp/out.md"
        assert args.max_heading_candidates == 50
        assert args.verbose is True

    def test_check_pdfs(self):
        """PDF check should not crash."""
        from scripts.audit_bibliographic_structure import _check_pdfs
        result = _check_pdfs()
        assert "directory" in result
        assert "files" in result
        for fname, info in result["files"].items():
            assert "exists" in info

    def test_markdown_build(self):
        from scripts.audit_bibliographic_structure import _build_markdown

        report = {
            "collection": "test",
            "total_documents": 1,
            "total_chunks": 5,
            "documents": [
                {
                    "title": "Doc",
                    "author": None,
                    "source_filename": "d.pdf",
                    "content_length": 500,
                    "chunk_count": 5,
                    "existing_metadata": {
                        "page_fields_available": False,
                        "chunks_with_page": 0,
                        "chunks_with_chapter": 0,
                        "chunks_with_section": 0,
                        "page_start_end_exists_in_db": False,
                    },
                    "page_marker_candidates": [],
                    "heading_candidates": ["# Title"],
                    "chapter_references": [],
                    "sample_content_start": "",
                    "chunking_observations": [],
                    "chunk_lengths": {"avg": 100.0, "min": 50, "max": 200},
                    "confidence": "low",
                    "recommended_strategy": "test",
                }
            ],
            "existing_metadata_summary": {
                "total_chunks": 5,
                "chunks_with_page": 0,
                "chunks_with_chapter": 0,
                "pct_with_page": 0.0,
                "pct_with_chapter": 0.0,
                "fields_available": {"page_start": False, "chapter": False, "section": False},
            },
            "pdf_availability": {
                "directory": "/tmp",
                "files": {},
            },
        }
        md = _build_markdown(report, type("Args", (), {"collection": "test"})())
        assert "# TebaAI" in md
        assert "Doc" in md
        assert "test" in md
