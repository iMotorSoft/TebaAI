"""Tests for applying structural Markdown chunking."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from scripts.chunk_documents import (
    _detect_sections,
    _chunk_markdown_structure,
    _build_db_chunks,
)


SAMPLE_MD = """# Title

Intro text.

## Chapter 1

Content of chapter one.

## Chapter 2

Content of chapter two.

## Lección 1

Spanish lesson one content.

## Lección 2

Spanish lesson two content.
"""


class TestSectionDetection:
    def test_heading_aware(self):
        s = _detect_sections(SAMPLE_MD, "heading-aware")
        assert len(s) >= 4

    def test_lesson_aware(self):
        s = _detect_sections(SAMPLE_MD, "lesson-aware")
        assert len(s) == 2


class TestChunkMarkdownStructure:
    def test_heading_aware_creates_chunks(self):
        chunks = _chunk_markdown_structure(SAMPLE_MD, "heading-aware", 1800, 250, 200)
        assert len(chunks) > 0
        for c in chunks:
            assert "content" in c

    def test_lesson_aware_creates_chunks(self):
        chunks = _chunk_markdown_structure(SAMPLE_MD, "lesson-aware", 1800, 250, 200)
        assert len(chunks) > 0

    def test_fallback_to_generic(self):
        md = "Plain.\n\nText.\n\nWithout headings.\n\nMore.\n\nEven more.\n"
        chunks = _chunk_markdown_structure(md, "heading-aware", 100, 20, 10)
        assert len(chunks) > 0

    def test_lesson_chunks_have_numbers(self):
        md = "Pre.\n\n## Lección 1\nContent 1.\n\n## Lección 2\nContent 2.\n"
        chunks = _chunk_markdown_structure(md, "lesson-aware", 100, 20, 10)
        lesson_chunks = [c for c in chunks if c.get("section_number") is not None]
        assert len(lesson_chunks) >= 2


class TestBuildDbChunks:
    def test_metadata_structure(self):
        doc_id = uuid4()
        text_id = uuid4()
        raw = [
            {"content": "Chapter text", "chunk_index": 0,
             "section_type": "heading", "section_number": None,
             "section_label": "Chapter 1", "section_title": "Chapter 1",
             "source_strategy": "heading-aware"},
        ]
        db = _build_db_chunks(raw, doc_id, text_id, "Test", "en", uuid4())
        assert len(db) == 1
        r = db[0]
        assert r["metadata"]["chunking"]["strategy"] == "heading-aware"
        assert r["metadata"]["chunking"]["source"] == "persisted_markdown"
        assert r["metadata"]["section"]["section_type"] == "heading"
        assert r["section"] == "Chapter 1"

    def test_lesson_section_metadata(self):
        raw = [
            {"content": "Lesson text", "chunk_index": 0,
             "section_type": "lesson", "section_number": 5,
             "section_label": "Lección 5", "section_title": "Lección 5",
             "source_strategy": "lesson-aware"},
        ]
        db = _build_db_chunks(raw, uuid4(), uuid4(), "Test", "es", uuid4())
        meta = db[0]["metadata"]["section"]
        assert meta["section_type"] == "lesson"
        assert meta["section_number"] == 5

    def test_chunk_uid_deterministic(self):
        doc_id = uuid4()
        text_id = uuid4()
        raw = [{"content": "Content", "chunk_index": 0, "source_strategy": "heading-aware"}]
        db1 = _build_db_chunks(raw, doc_id, text_id, "Test", "en", uuid4())
        db2 = _build_db_chunks(raw, doc_id, text_id, "Test", "en", uuid4())
        assert db1[0]["chunk_uid"] == db2[0]["chunk_uid"]

    def test_content_fields(self):
        raw = [{"content": "Test content here", "chunk_index": 0, "source_strategy": "generic"}]
        db = _build_db_chunks(raw, uuid4(), uuid4(), "Test", "en", uuid4())
        r = db[0]
        assert r["content"] == "Test content here"
        assert r["content_length"] == 17
        assert r["token_count_estimate"] > 0

    def test_no_empty_chunks(self):
        doc_id = uuid4()
        raw = _chunk_markdown_structure(SAMPLE_MD, "heading-aware", 100, 20, 10)
        db = _build_db_chunks(raw, doc_id, uuid4(), "Test", "en", uuid4())
        assert all(c["content_length"] > 0 for c in db)
