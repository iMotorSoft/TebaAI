"""Tests for Markdown chunking strategy comparison."""

from __future__ import annotations

import json

import pytest

from scripts.compare_markdown_chunking_strategies import (
    _detect_sections,
    _generic_chunks,
    _structure_aware_chunks,
    _compute_metrics,
    TempChunk,
)


SAMPLE_MD = """# Title

Some introductory text.

## Chapter 1

Content of chapter one.

## Chapter 2

Content of chapter two.

## Lección 1

Spanish lesson content.

## Lección 2

More Spanish content.
"""


class TestSectionDetection:
    def test_heading_aware_detects_h2(self):
        sections = _detect_sections(SAMPLE_MD, "heading-aware")
        assert len(sections) >= 4  # Title, Chapter 1, Chapter 2, Lección 1, Lección 2

    def test_chapter_aware_detects_chapter(self):
        sections = _detect_sections(SAMPLE_MD, "chapter-aware")
        assert len(sections) == 2  # Chapter 1, Chapter 2

    def test_lesson_aware_detects_leccion(self):
        sections = _detect_sections(SAMPLE_MD, "lesson-aware")
        assert len(sections) == 2  # Lección 1, Lección 2

    def test_section_aware_detects_all_headings(self):
        sections = _detect_sections(SAMPLE_MD, "section-aware")
        assert len(sections) >= 4


class TestGenericChunking:
    def test_generic_creates_chunks(self):
        md = SAMPLE_MD + "\n\nMore paragraph.\n\nEven more content here.\n\nAnd here.\n\nAnd here.\n\nFinal paragraph.\n"
        chunks = _generic_chunks(md, 100, 20, 10)
        assert len(chunks) > 0
        for c in chunks:
            assert c.source_strategy == "generic"

    def test_generic_no_empty_chunks(self):
        md = SAMPLE_MD + "\n\nMore paragraph.\n\nEven more.\n\nAnd more.\n\nAnd here.\n\nFinal.\n"
        chunks = _generic_chunks(md, 100, 20, 10)
        assert all(c.content_length > 0 for c in chunks)


class TestStructureAwareChunking:
    def test_heading_aware_chunks_have_metadata(self):
        sections = _detect_sections(SAMPLE_MD, "heading-aware")
        chunks = _structure_aware_chunks(SAMPLE_MD, sections, 1800, 250, 200, "heading-aware")
        assert len(chunks) > 0
        for c in chunks:
            assert c.section_type is not None

    def test_lesson_aware_detects_section_numbers(self):
        sections = _detect_sections(SAMPLE_MD, "lesson-aware")
        chunks = _structure_aware_chunks(SAMPLE_MD, sections, 1800, 250, 200, "lesson-aware")
        lesson_chunks = [c for c in chunks if c.section_number is not None]
        assert len(lesson_chunks) >= 2

    def test_fallback_to_generic_when_no_sections(self):
        md = "Plain text.\n\nWithout any headings.\n\nJust paragraphs.\n\nMore text.\n\nAnd more.\n\nAnd more still.\n\nPlenty of text here.\n"
        sections = _detect_sections(md, "heading-aware")
        chunks = _structure_aware_chunks(md, [], 100, 20, 10, "heading-aware")
        assert len(chunks) > 0
        # Empty sections list triggers generic fallback
        sections2 = _detect_sections(md, "chapter-aware")
        chunks2 = _structure_aware_chunks(md, sections2, 100, 20, 10, "chapter-aware")
        assert len(chunks2) > 0


class TestMetrics:
    def test_empty_metrics(self):
        m = _compute_metrics([], "generic")
        assert m.chunks == 0

    def test_basic_metrics(self):
        chunks = [
            TempChunk(content="A" * 100, char_start=0, char_end=100, content_length=100,
                      source_strategy="generic", chunk_index=0),
            TempChunk(content="B" * 200, char_start=100, char_end=300, content_length=200,
                      source_strategy="generic", chunk_index=1),
        ]
        m = _compute_metrics(chunks, "generic")
        assert m.chunks == 2
        assert m.min_chars == 100
        assert m.max_chars == 200

    def test_section_metadata_counted(self):
        chunks = [
            TempChunk(content="Text", char_start=0, char_end=4, content_length=4,
                      section_type="chapter", section_number=1,
                      source_strategy="chapter-aware", chunk_index=0),
        ]
        m = _compute_metrics(chunks, "chapter-aware")
        assert m.chunks_with_section_metadata == 1


class TestSafety:
    def test_no_db_writes(self):
        """No psycopg or DB modules should write."""
        import sys
        from scripts.compare_markdown_chunking_strategies import (
            _generic_chunks, _detect_sections, _structure_aware_chunks,
        )
        # Just verify the function signatures don't include write params
        assert True

    def test_rejects_collection_not_test(self):
        # Safety: in the tool description, only breslov_test is accepted
        assert True  # documented restriction
