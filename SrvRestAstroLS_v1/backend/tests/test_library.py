"""Tests for library domain, extractors, repository, service, and CLI."""

from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.library.domain import (
    DocumentLanguage,
    DocumentSourceType,
    DocumentStatus,
    ExtractionMethod,
    LibraryCollection,
    LibraryDocument,
    LibraryDocumentReference,
    LibraryDocumentText,
    TextFormat,
)
from modules.library.errors import (
    DuplicateDocumentError,
    ExtractionError,
    UnsupportedFileTypeError,
)
from modules.library.extractors import (
    compute_file_sha256,
    compute_sha256,
    detect_text_format,
    extract_text,
)
from modules.library.schemas import IngestDocumentRequest, IngestDocumentResult


# ── Domain ────────────────────────────────────────────────────────────────────


class TestDomain:
    def test_library_collection_create(self):
        c = LibraryCollection.create(code="test-coll", name="Test Collection", default_language="es")
        assert c.code == "test-coll"
        assert c.name == "Test Collection"
        assert c.default_language == "es"
        assert c.is_active is True
        assert c.metadata == {}

    def test_library_collection_create_lowercases_code(self):
        c = LibraryCollection.create(code="TEST-Coll", name="Test")
        assert c.code == "test-coll"

    def test_library_document_create(self):
        from uuid import UUID
        coll_id = UUID("00000000-0000-0000-0000-000000000001")
        d = LibraryDocument.create(
            collection_id=coll_id,
            title="Test Doc",
            language="en",
            source_type="markdown",
            source_sha256="abc123",
            author="Author",
        )
        assert d.collection_id == coll_id
        assert d.title == "Test Doc"
        assert d.language == "en"
        assert d.source_type == "markdown"
        assert d.source_sha256 == "abc123"
        assert d.status == DocumentStatus.READY.value
        assert d.author == "Author"

    def test_library_document_text_create(self):
        from uuid import UUID
        doc_id = UUID("00000000-0000-0000-0000-000000000002")
        t = LibraryDocumentText.create(
            document_id=doc_id,
            text_format="markdown",
            content="# Hello",
            content_sha256="def456",
            extraction_method="raw_markdown",
        )
        assert t.document_id == doc_id
        assert t.text_format == "markdown"
        assert t.content == "# Hello"
        assert t.content_length == 7
        assert t.extraction_method == "raw_markdown"


# ── Extractors ────────────────────────────────────────────────────────────────


class TestExtractors:
    def test_compute_sha256(self):
        h = compute_sha256(b"hello")
        assert len(h) == 64
        assert h == compute_sha256(b"hello")

    def test_compute_file_sha256(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            p = f.name
        try:
            h = compute_file_sha256(p)
            assert len(h) == 64
        finally:
            pathlib.Path(p).unlink()

    def test_detect_text_format_md(self):
        fmt, method = detect_text_format(".md")
        assert fmt == TextFormat.MARKDOWN
        assert method == ExtractionMethod.RAW_MARKDOWN

    def test_detect_text_format_txt(self):
        fmt, method = detect_text_format(".txt")
        assert fmt == TextFormat.PLAIN_TEXT
        assert method == ExtractionMethod.RAW_TEXT

    def test_detect_text_format_unsupported(self):
        with pytest.raises(UnsupportedFileTypeError):
            detect_text_format(".docx")

    def test_extract_markdown(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nBody text")
            p = f.name
        try:
            content, fmt, method, meta = extract_text(p)
            assert content == "# Title\n\nBody text"
            assert fmt == TextFormat.MARKDOWN
            assert meta["extension"] == ".md"
        finally:
            pathlib.Path(p).unlink()

    def test_extract_txt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Plain text content")
            p = f.name
        try:
            content, fmt, method, meta = extract_text(p)
            assert content == "Plain text content"
            assert fmt == TextFormat.PLAIN_TEXT
            assert method == ExtractionMethod.RAW_TEXT
        finally:
            pathlib.Path(p).unlink()

    def test_extract_file_not_found(self):
        with pytest.raises(ExtractionError, match="File not found"):
            extract_text("/tmp/nonexistent_file_12345.md")


# ── Schemas ───────────────────────────────────────────────────────────────────


class TestSchemas:
    def test_ingest_request_valid(self):
        req = IngestDocumentRequest(
            file_path="/tmp/test.md",
            title="Test",
            language="es",
            collection="general",
            source_type="markdown",
        )
        assert req.dry_run is False

    def test_ingest_request_dry_run(self):
        req = IngestDocumentRequest(
            file_path="/tmp/test.md",
            title="Test",
            language="es",
            collection="general",
            source_type="markdown",
            dry_run=True,
        )
        assert req.dry_run is True

    def test_ingest_result(self):
        from uuid import UUID
        result = IngestDocumentResult(
            document_id=UUID("00000000-0000-0000-0000-000000000001"),
            collection_code="general",
            title="Test",
            language="es",
            source_sha256="abc",
            content_sha256="def",
            content_length=100,
            status="ready",
            is_new=True,
        )
        assert result.collection_code == "general"


# ── Repository (mocked at function level) ──────────────────────────────────────


class TestRepository:
    async def test_get_or_create_collection_new(self):
        with (
            patch("modules.library.repository.fetch_one", return_value=None),
            patch("modules.library.repository.execute", return_value=None),
        ):
            from modules.library.repository import get_or_create_collection

            conn = AsyncMock()
            col, created = await get_or_create_collection(conn, "test", "Test")
            assert created is True
            assert col.code == "test"

    async def test_get_or_create_collection_existing(self):
        existing_row = {
            "id": "11111111-1111-1111-1111-111111111111",
            "code": "test",
            "name": "Test",
            "description": None,
            "default_language": None,
            "metadata": {},
            "is_active": True,
            "created_at": None,
            "updated_at": None,
        }
        with patch("modules.library.repository.fetch_one", return_value=existing_row):
            from modules.library.repository import get_or_create_collection

            conn = AsyncMock()
            col, created = await get_or_create_collection(conn, "test", "Test")
            assert created is False
            assert col.code == "test"


# ── Service (mocked) ──────────────────────────────────────────────────────────


class TestService:
    async def test_ingest_document_dry_run(self):
        from modules.library.domain import LibraryCollection as Lc

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Dry run test")
            p = f.name

        try:
            from modules.library.service import ingest_document

            req = IngestDocumentRequest(
                file_path=p,
                title="Dry Run",
                language="en",
                collection="general",
                source_type="markdown",
                dry_run=True,
            )
            conn = AsyncMock()
            with (
                patch("modules.library.service.get_or_create_collection") as mock_gcc,
                patch("modules.library.service.get_document_by_sha256", return_value=None),
            ):
                mock_gcc.return_value = (Lc.create("general", "General"), True)
                result = await ingest_document(conn, req)
            assert result.dry_run is True
            assert result.title == "Dry Run"
        finally:
            pathlib.Path(p).unlink()

    async def test_ingest_duplicate_raises(self):
        from modules.library.domain import LibraryDocument

        conn = AsyncMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Duplicate test")
            p = f.name

        try:
            from modules.library.service import ingest_document

            # Mock get_or_create_collection so dry_run ingestion doesn't exercise repository
            with (
                patch("modules.library.service.get_or_create_collection") as mock_gcc,
                patch("modules.library.service.get_document_by_sha256", return_value=None),
                patch("modules.library.service.create_document"),
                patch("modules.library.service.create_document_text"),
            ):
                mock_gcc.return_value = (
                    LibraryCollection.create("dup-coll", "Dup"),
                    True,
                )
                req1 = IngestDocumentRequest(
                    file_path=p, title="First", language="en",
                    collection="dup-coll", source_type="markdown",
                )
                result = await ingest_document(conn, req1)
                assert result.is_new is True

            # Second call - existing doc found
            existing = LibraryDocument.create(
                collection_id=result.document_id,
                title="Existing",
                language="en",
                source_type="markdown",
                source_sha256=result.source_sha256,
            )

            with (
                patch("modules.library.service.get_or_create_collection") as mock_gcc2,
                patch("modules.library.service.get_document_by_sha256", return_value=existing),
                pytest.raises(DuplicateDocumentError),
            ):
                mock_gcc2.return_value = (
                    LibraryCollection.create("dup-coll", "Dup"),
                    False,
                )
                req2 = IngestDocumentRequest(
                    file_path=p, title="Second", language="en",
                    collection="dup-coll", source_type="markdown",
                )
                await ingest_document(conn, req2)
        finally:
            pathlib.Path(p).unlink()

    async def test_file_not_found(self):
        from modules.library.service import ingest_document

        req = IngestDocumentRequest(
            file_path="/tmp/nonexistent_file_99999.md",
            title="Missing",
            language="es",
            collection="general",
            source_type="markdown",
        )
        with pytest.raises(FileNotFoundError):
            await ingest_document(AsyncMock(), req)


# ── CLI ───────────────────────────────────────────────────────────────────────


class TestCLI:
    def test_parse_args_required(self):
        from scripts.ingest_document import _parse_args

        args = _parse_args([
            "--file", "/tmp/test.md",
            "--title", "Test",
            "--language", "es",
            "--collection", "general",
            "--source-type", "markdown",
        ])
        assert args.file == "/tmp/test.md"
        assert args.title == "Test"
        assert args.dry_run is False

    def test_parse_args_dry_run(self):
        from scripts.ingest_document import _parse_args

        args = _parse_args([
            "--file", "/tmp/test.md",
            "--title", "Test",
            "--language", "en",
            "--collection", "test",
            "--source-type", "text",
            "--dry-run",
        ])
        assert args.dry_run is True

    def test_parse_args_missing_required(self):
        from scripts.ingest_document import _parse_args

        with pytest.raises(SystemExit):
            _parse_args(["--file", "/tmp/test.md"])

    def test_parse_args_all_optional(self):
        from scripts.ingest_document import _parse_args

        args = _parse_args([
            "--file", "/tmp/doc.md",
            "--title", "Full",
            "--language", "he",
            "--collection", "special",
            "--source-type", "book",
            "--collection-name", "Special Collection",
            "--subtitle", "A Subtitle",
            "--author", "Author Name",
            "--publisher", "Publisher",
            "--publication-year", "2024",
            "--bibliographic-ref", "Ref123",
            "--version-label", "1.0",
            "--metadata-json", '{"key": "val"}',
            "--created-by-email", "admin@tebaai.ai",
            "--dry-run",
        ])
        assert args.author == "Author Name"
        assert args.publication_year == 2024
        assert args.dry_run is True
