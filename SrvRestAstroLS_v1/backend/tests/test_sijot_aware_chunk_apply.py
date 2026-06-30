"""Tests for Sijot-aware chunk apply logic."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from modules.library.chunking import (
    convert_temporary_chunks_to_db_format,
    make_chunk_uid,
)


# ── Fake TemporaryChunk ───────────────────────────────────────────────


class FakeTemporaryChunk:
    """Mimics TemporaryChunk dataclass from compare_chunking_strategies."""
    def __init__(self, content: str, section_type: str | None = None,
                 section_number: int | None = None,
                 section_label: str | None = None,
                 section_title: str | None = None,
                 chunk_index: int = 0,
                 char_start: int = 0, char_end: int = 0,
                 content_length: int = 0):
        self.content = content
        self.char_start = char_start
        self.char_end = char_end
        self.content_length = content_length or len(content)
        self.section_type = section_type
        self.section_number = section_number
        self.section_label = section_label
        self.section_title = section_title
        self.chunk_index = chunk_index


# ── Tests ─────────────────────────────────────────────────────────────


class TestConvertTemporaryChunks:
    def test_convert_basic(self):
        doc_id = uuid4()
        text_id = uuid4()
        chunks = [
            FakeTemporaryChunk(
                content="Sija 1 content",
                section_type="sija", section_number=1,
                section_label="Sija 1", section_title="Sija 1",
                chunk_index=0,                 char_start=0, char_end=14,
            ),
        ]
        result = convert_temporary_chunks_to_db_format(chunks, doc_id, text_id)
        assert len(result) == 1
        r = result[0]
        assert r["document_id"] == doc_id
        assert r["document_text_id"] == text_id
        assert r["chunk_index"] == 0
        assert r["content"] == "Sija 1 content"
        assert r["content_length"] == 14
        assert isinstance(r["id"], UUID)
        assert r["chunk_uid"] == make_chunk_uid(doc_id, text_id, 0)
        assert r["metadata"]["chunking"]["strategy"] == "sijot-aware"

    def test_convert_section_metadata(self):
        chunks = [
            FakeTemporaryChunk(
                content="Sija 25 text",
                section_type="sija", section_number=25,
                section_label="## Sija #25", section_title="Sija #25",
                chunk_index=0,                 char_start=0, char_end=14,
            ),
        ]
        result = convert_temporary_chunks_to_db_format(chunks, uuid4(), uuid4())
        meta = result[0]["metadata"]
        assert meta["section"]["section_type"] == "sija"
        assert meta["section"]["section_number"] == 25
        assert meta["section"]["section_label"] == "## Sija #25"
        assert meta["section"]["section_title"] == "Sija #25"

    def test_convert_non_sija_section(self):
        chunks = [
            FakeTemporaryChunk(
                content="Preface content",
                section_type="prefacio", section_number=None,
                section_label="Prefacio", section_title="Prefacio",
                chunk_index=0, char_start=0, char_end=15,
            ),
        ]
        result = convert_temporary_chunks_to_db_format(chunks, uuid4(), uuid4())
        meta = result[0]["metadata"]
        assert meta["section"]["section_type"] == "prefacio"
        assert "section_number" not in meta["section"]

    def test_convert_none_section_metadata(self):
        chunks = [
            FakeTemporaryChunk(
                content="Generic text without section metadata",
                section_type=None, section_number=None,
                section_label=None, section_title=None,
                chunk_index=0, char_start=0, char_end=42,
            ),
        ]
        result = convert_temporary_chunks_to_db_format(chunks, uuid4(), uuid4())
        meta = result[0]["metadata"]
        assert meta["section"] == {}

    def test_convert_multiple_chunks(self):
        chunks = [
            FakeTemporaryChunk(content=f"Chunk {i}", chunk_index=i,
                               char_start=i * 10, char_end=i * 10 + 7,
                               content_length=7)
            for i in range(5)
        ]
        result = convert_temporary_chunks_to_db_format(chunks, uuid4(), uuid4())
        assert len(result) == 5
        for i, r in enumerate(result):
            assert r["chunk_index"] == i
            assert r["content"] == f"Chunk {i}"
            assert r["token_count_estimate"] > 0

    def test_chunk_uid_deterministic(self):
        doc_id = uuid4()
        text_id = uuid4()
        chunks = [FakeTemporaryChunk(content="Same content", chunk_index=0,
                                     char_start=0, char_end=12)]
        result1 = convert_temporary_chunks_to_db_format(chunks, doc_id, text_id)
        result2 = convert_temporary_chunks_to_db_format(chunks, doc_id, text_id)
        assert result1[0]["chunk_uid"] == result2[0]["chunk_uid"]

    def test_language_preserved(self):
        chunks = [FakeTemporaryChunk(content="Text", chunk_index=0,
                                     char_start=0, char_end=4)]
        result = convert_temporary_chunks_to_db_format(
            chunks, uuid4(), uuid4(), language="he",
        )
        assert result[0]["language"] == "he"

    def test_empty_chunks_list(self):
        result = convert_temporary_chunks_to_db_format([], uuid4(), uuid4())
        assert result == []


class TestMakeChunkUid:
    def test_deterministic(self):
        uid1 = make_chunk_uid(UUID(int=1), UUID(int=2), 0)
        uid2 = make_chunk_uid(UUID(int=1), UUID(int=2), 0)
        assert uid1 == uid2

    def test_differs_by_index(self):
        uid1 = make_chunk_uid(UUID(int=1), UUID(int=2), 0)
        uid2 = make_chunk_uid(UUID(int=1), UUID(int=2), 1)
        assert uid1 != uid2

    def test_string_length(self):
        uid = make_chunk_uid(UUID(int=1), UUID(int=2), 42)
        assert len(uid) == 24
