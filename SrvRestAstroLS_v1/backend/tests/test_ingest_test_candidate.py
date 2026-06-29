"""Tests for isolated test-candidate document ingestion."""

from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from modules.library.domain import DocumentStatus, LibraryCollection, LibraryDocument
from modules.library.schemas import IngestDocumentRequest


def _request(path: str, **overrides) -> IngestDocumentRequest:
    values = {
        "file_path": path,
        "title": "El Alma del Rebe Najmán",
        "language": "es",
        "collection": "breslov_test",
        "source_type": "pdf",
        "status": "test_candidate",
        "metadata_json": '{"corpus":"breslov_test"}',
        "dry_run": True,
    }
    values.update(overrides)
    return IngestDocumentRequest(**values)


@pytest.fixture
def source_file(tmp_path: pathlib.Path) -> str:
    path = tmp_path / "candidate.txt"
    path.write_text("Texto de prueba para ingesta controlada.", encoding="utf-8")
    return str(path)


def test_status_test_candidate_accepted(source_file: str):
    request = _request(source_file, source_type="text")
    assert request.status == DocumentStatus.TEST_CANDIDATE.value


def test_invalid_status_rejected(source_file: str):
    with pytest.raises(ValidationError):
        _request(source_file, source_type="text", status="published")


def test_test_candidate_rejected_in_product_collection(source_file: str):
    with pytest.raises(ValidationError, match="require a \\*_test collection"):
        _request(source_file, source_type="text", collection="breslov")


def test_ready_rejected_in_test_collection(source_file: str):
    with pytest.raises(ValidationError, match="cannot ingest ready"):
        _request(source_file, source_type="text", status="ready")


async def test_metadata_json_parses_and_is_persisted(source_file: str):
    from modules.library.service import ingest_document

    collection = LibraryCollection.create("breslov_test", "Breslov Test Corpus", "es")
    request = _request(source_file, source_type="text", dry_run=False)
    create_document = AsyncMock()
    with (
        patch("modules.library.service.get_or_create_collection", return_value=(collection, True)),
        patch("modules.library.service.get_document_by_sha256", return_value=None),
        patch("modules.library.service.create_document", create_document),
        patch("modules.library.service.create_document_text", new_callable=AsyncMock),
    ):
        result = await ingest_document(AsyncMock(), request)

    document = create_document.await_args.args[1]
    assert result.status == "test_candidate"
    assert document.bibliographic_metadata == {"corpus": "breslov_test"}
    assert document.metadata == {}


async def test_repository_serializes_bibliographic_metadata():
    from modules.library.repository import create_document

    document = LibraryDocument.create(
        collection_id=LibraryCollection.create("breslov_test", "Breslov Test Corpus").id,
        title="Candidate",
        language="es",
        source_type="pdf",
        source_sha256="candidate-sha",
        status="test_candidate",
        bibliographic_metadata={"corpus": "breslov_test"},
    )
    execute = AsyncMock()
    with patch("modules.library.repository.execute", execute):
        await create_document(AsyncMock(), document)

    sql = execute.await_args.args[1]
    params = execute.await_args.args[2]
    assert "bibliographic_metadata" in sql
    assert params["bibliographic_metadata"] == '{"corpus": "breslov_test"}'


async def test_dry_run_does_not_write_or_create_collection(source_file: str):
    from modules.library.service import ingest_document

    request = _request(source_file, source_type="text")
    create_collection = AsyncMock()
    create_document = AsyncMock()
    create_text = AsyncMock()
    with (
        patch("modules.library.service.get_collection_by_code", return_value=None),
        patch("modules.library.service.get_or_create_collection", create_collection),
        patch("modules.library.service.create_document", create_document),
        patch("modules.library.service.create_document_text", create_text),
    ):
        result = await ingest_document(AsyncMock(), request)

    assert result.dry_run is True
    create_collection.assert_not_awaited()
    create_document.assert_not_awaited()
    create_text.assert_not_awaited()


async def test_breslov_test_never_falls_back_to_breslov(source_file: str):
    from modules.library.service import ingest_document

    request = _request(source_file, source_type="text")
    lookup = AsyncMock(return_value=None)
    with patch("modules.library.service.get_collection_by_code", lookup):
        result = await ingest_document(AsyncMock(), request)

    assert result.collection_code == "breslov_test"
    assert result.status == "test_candidate"
    lookup.assert_awaited_once()
    assert lookup.await_args.args[1] == "breslov_test"


async def test_existing_ready_document_is_not_changed(source_file: str):
    from modules.library.service import ingest_document

    collection = LibraryCollection.create("breslov_test", "Breslov Test Corpus", "es")
    existing = LibraryDocument.create(
        collection_id=collection.id,
        title="Existing",
        language="es",
        source_type="text",
        source_sha256="existing-sha",
    )
    request = _request(source_file, source_type="text")
    with (
        patch("modules.library.service.get_collection_by_code", return_value=collection),
        patch("modules.library.service.get_document_by_sha256", return_value=existing),
    ):
        result = await ingest_document(AsyncMock(), request)

    assert existing.status == "ready"
    assert result.is_new is False
    assert result.status == "test_candidate"


def test_cli_accepts_source_path_status_and_infers_pdf():
    from scripts.ingest_document import _parse_args

    args = _parse_args([
        "--source-path", "/tmp/candidate.pdf",
        "--title", "Candidate",
        "--language", "es",
        "--collection", "breslov_test",
        "--status", "test_candidate",
        "--dry-run",
    ])
    assert args.file == "/tmp/candidate.pdf"
    assert args.source_type == "pdf"
    assert args.status == "test_candidate"


def test_test_collection_default_name_is_isolated():
    from modules.library.service import _default_collection_name

    assert _default_collection_name("breslov_test") == "Breslov Test Corpus"
    assert _default_collection_name("breslov") == "breslov"


async def test_apply_creates_test_collection_with_test_metadata(source_file: str):
    from modules.library.service import ingest_document

    collection = LibraryCollection.create(
        "breslov_test",
        "Breslov Test Corpus",
        "es",
        metadata={"status": "test"},
    )
    create_collection = AsyncMock(return_value=(collection, True))
    with (
        patch("modules.library.service.get_or_create_collection", create_collection),
        patch("modules.library.service.get_document_by_sha256", return_value=None),
        patch("modules.library.service.create_document", new_callable=AsyncMock),
        patch("modules.library.service.create_document_text", new_callable=AsyncMock),
    ):
        await ingest_document(
            AsyncMock(),
            _request(source_file, source_type="text", dry_run=False),
        )

    assert create_collection.await_args.kwargs["metadata"] == {"status": "test"}
