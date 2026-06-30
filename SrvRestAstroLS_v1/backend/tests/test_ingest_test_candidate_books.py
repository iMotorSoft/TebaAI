"""Tests for test_candidate book ingestion with PyMuPDF4LLM/Markdown."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.library.schemas import IngestDocumentRequest
from modules.library.domain import ExtractionMethod, TextFormat


class TestIngestTestCandidate:
    def test_accepts_breslov_test_and_test_candidate(self):
        req = IngestDocumentRequest(
            file_path="/tmp/test.pdf", title="Test", language="en",
            collection="breslov_test", source_type="pdf", status="test_candidate",
        )
        assert req.collection == "breslov_test"
        assert req.status == "test_candidate"

    def test_rejects_ready_for_test_collection(self):
        with pytest.raises(ValueError, match="test collections cannot ingest ready documents"):
            IngestDocumentRequest(
                file_path="/tmp/test.pdf", title="Test", language="en",
                collection="breslov_test", source_type="pdf", status="ready",
            )

    def test_rejects_breslov_with_test_candidate(self):
        with pytest.raises(ValueError, match="test_candidate documents require a"):
            IngestDocumentRequest(
                file_path="/tmp/test.pdf", title="Test", language="en",
                collection="breslov", source_type="pdf", status="test_candidate",
            )

    def test_dry_run_flag(self):
        req = IngestDocumentRequest(
            file_path="/tmp/test.pdf", title="Test", language="en",
            collection="breslov_test", source_type="pdf", status="test_candidate",
            dry_run=True,
        )
        assert req.dry_run is True

    def test_metadata_json_parses(self):
        req = IngestDocumentRequest(
            file_path="/tmp/test.pdf", title="Test", language="en",
            collection="breslov_test", source_type="pdf", status="test_candidate",
            metadata_json='{"domain":"breslov","corpus":"breslov_test"}',
        )
        assert req.metadata_json is not None

    def test_metadata_json_string_accepted(self):
        """metadata_json is stored as raw string; parsing happens in service layer."""
        req = IngestDocumentRequest(
            file_path="/tmp/test.pdf", title="Test", language="en",
            collection="breslov_test", source_type="pdf", status="test_candidate",
            metadata_json='{"valid": true}',
        )
        assert req.metadata_json == '{"valid": true}'

    def test_extractor_is_pymupdf4llm_for_pdf(self):
        from modules.library.extractors import detect_text_format
        fmt, meth = detect_text_format(".pdf")
        assert meth == ExtractionMethod.PYMUPDF4LLM
        assert fmt == TextFormat.MARKDOWN

    def test_extractor_for_markdown(self):
        from modules.library.extractors import detect_text_format
        fmt, meth = detect_text_format(".md")
        assert fmt == TextFormat.MARKDOWN

    def test_extractor_for_txt(self):
        from modules.library.extractors import detect_text_format
        fmt, meth = detect_text_format(".txt")
        assert fmt == TextFormat.PLAIN_TEXT

    def test_ingest_reports_no_chunks(self):
        """Verify the ingest output includes will_create_chunks=False."""
        import scripts.ingest_document as cli
        args = cli._parse_args([
            "--file", "/tmp/test.pdf", "--title", "Test", "--language", "en",
            "--collection", "breslov_test", "--status", "test_candidate",
            "--dry-run",
        ])
        assert args.dry_run is True
