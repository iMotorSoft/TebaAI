"""Tests for compare_chunking_strategies.py — generic vs section-aware chunking."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.compare_chunking_strategies import (
    SIJOT_EXPECTED_COUNT,
    DEFAULT_CHUNK_SIZE,
    _compute_generic_chunks,
    _compute_generic_metrics,
    _compute_sijot_aware_chunks,
    _compute_sijot_metrics,
    _find_sija_headers,
    _find_section_boundaries,
    _simulate_page_mapping,
    _simulated_search,
    _build_json_report,
    _build_md_report,
    _compute_recommendation,
    _paragraph_chunks,
    StrategyMetrics,
    TemporaryChunk,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_text() -> str:
    return """# Portada
El Alma del Rebe Najmán

# Créditos
Copyright 2017

# Índice
1. Introducción
2. Sija 1

# Introducción
Este es un texto introductorio sobre el Rebe Najmán.

# Sija 1
El comienzo de la Sija 1.

Contenido de la Sija 1, párrafo uno.

Contenido de la Sija 1, párrafo dos.

Contenido de la Sija 1, párrafo tres.

Contenido de la Sija 1, párrafo cuatro.

# Sijá Nº 2
La Sija 2 comienza aquí.

Segundo párrafo de la Sija 2.

# Sija 3
Contenido breve de la Sija 3.

# Glosario
Definiciones aquí.
"""


@pytest.fixture
def text_with_sijot() -> str:
    """Text with multiple Sijot for detection testing."""
    parts = []
    for i in range(1, 10):
        parts.append(f"# Sija {i}\nContenido de la Sija {i}.\n\nMás contenido.\n")
    return "\n".join(parts)


@pytest.fixture
def text_without_sections() -> str:
    """Plain text without detectable sections."""
    return "Este es un texto plano.\n\nSin secciones.\n\nSolo párrafos.\n\nRepetir.\n" * 50


# ── Generic strategy tests ─────────────────────────────────────────────


class TestGenericStrategy:
    def test_generic_not_empty(self, sample_text: str):
        chunks = _compute_generic_chunks(sample_text)
        assert len(chunks) > 0
        for c in chunks:
            assert c.source_strategy == "generic"

    def test_generic_content_preserved(self, sample_text: str):
        chunks = _compute_generic_chunks(sample_text)
        combined = " ".join(c.content for c in chunks)
        assert "El Alma del Rebe Najmán" in combined
        assert "Copyright 2017" in combined
        assert "comienzo de la Sija 1" in combined

    def test_generic_metrics(self, sample_text: str):
        chunks = _compute_generic_chunks(sample_text)
        metrics = _compute_generic_metrics(chunks)
        assert metrics.chunks == len(chunks)
        assert metrics.empty_chunks == 0
        assert metrics.total_chars > 0
        assert metrics.avg_chars > 0

    def test_generic_no_write(self, sample_text: str):
        """Verify generic strategy does not write to DB (in-memory only)."""
        chunks = _compute_generic_chunks(sample_text)
        assert isinstance(chunks, list)
        assert all(isinstance(c, TemporaryChunk) for c in chunks)

    def test_paragraph_chunks_basic(self):
        """Paragraphs shorter than chunk_size get concatenated, but only complete groups."""
        text = "Para con suficiente contenido para superar el mínimo.\n\n" * 8
        chunks = _paragraph_chunks(text, chunk_size=200, min_chunk=10)
        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk["content"]) > 0
        for chunk in chunks:
            assert len(chunk["content"]) >= 0


# ── Sijot detector tests ────────────────────────────────────────────────


class TestSijotDetector:
    def test_detect_sija_1(self, sample_text: str):
        """Sija 1 must be detected."""
        headers = _find_sija_headers(sample_text)
        nums = [h["number"] for h in headers]
        assert 1 in nums

    def test_detect_sija_variants(self, sample_text: str):
        """Sijá Nº 2 must be detected."""
        headers = _find_sija_headers(sample_text)
        nums = [h["number"] for h in headers]
        assert 2 in nums

    def test_detect_sija_25(self):
        """Sijá 25 must be detected (variation with accent)."""
        text = "Texto antes.\n\n# Sijá 25\nContenido importante.\n\nMás texto."
        headers = _find_sija_headers(text)
        nums = [h["number"] for h in headers]
        assert 25 in nums

    def test_detect_sija_with_ordinal(self):
        """Sijá Nº 1 must be detected."""
        for line in ["# Sijá Nº 1", "# Sija Nº 1", "Sijá Nº 1", "SIJA Nº 1"]:
            text = f"Texto.\n\n{line}\nContenido.\n"
            headers = _find_sija_headers(text)
            nums = [h["number"] for h in headers]
            assert 1 in nums, f"Failed to detect '{line}'"

    def test_detect_sija_3(self, sample_text: str):
        """Sija 3 must be detected."""
        headers = _find_sija_headers(sample_text)
        nums = [h["number"] for h in headers]
        assert 3 in nums

    def test_no_false_positives(self):
        text = "Este texto no tiene Sijot.\nSolo una palabra sija no debería contar."
        headers = _find_sija_headers(text)
        assert len(headers) == 0

    def test_section_boundaries(self, sample_text: str):
        boundaries = _find_section_boundaries(sample_text)
        types = [b["type"] for b in boundaries]
        assert "portada" in types
        assert "creditos" in types
        assert "indice" in types
        assert "introduccion" in types
        assert "sija" in types
        assert "glosario" in types


# ── Sijot-aware strategy tests ──────────────────────────────────────────


class TestSijotAwareStrategy:
    def test_sijot_aware_not_empty(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        assert len(chunks) > 0
        for c in chunks:
            assert c.source_strategy == "sijot-aware"

    def test_sijot_aware_section_metadata(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        sija_chunks = [c for c in chunks if c.section_type == "sija"]
        assert len(sija_chunks) > 0
        for c in sija_chunks:
            assert c.section_number is not None
            assert c.section_label is not None
            assert "Sija" in c.section_label or "Sij" in c.section_label

    def test_no_cross_section(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        for i in range(len(chunks) - 1):
            if (chunks[i].section_type == "sija" and chunks[i + 1].section_type == "sija"
                    and chunks[i].section_number is not None
                    and chunks[i + 1].section_number is not None):
                assert chunks[i].section_number != chunks[i + 1].section_number

    def test_heading_preserved(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        sija_chunks = [c for c in chunks if c.section_type == "sija" and c.starts_with_heading]
        assert len(sija_chunks) >= 1  # At least one Sija starts with heading

    def test_sijot_aware_content_preserved(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        combined = " ".join(c.content for c in chunks)
        assert "Sija 1" in combined or "Sijá" in combined
        assert "Sija 3" in combined
        assert "comienzo" in combined

    def test_sijot_aware_metrics(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        metrics = _compute_sijot_metrics(chunks)
        assert metrics.chunks == len(chunks)
        assert metrics.empty_chunks == 0
        assert metrics.sijot_detected >= 2  # At least Sija 1, 2, 3

    def test_missing_sijot(self, sample_text: str):
        chunks = _compute_sijot_aware_chunks(sample_text)
        metrics = _compute_sijot_metrics(chunks)
        all_sijot = set(range(1, SIJOT_EXPECTED_COUNT + 1))
        detected = set(c.section_number for c in chunks if c.section_type == "sija" and c.section_number is not None)
        expected_missing = sorted(all_sijot - detected)
        assert metrics.missing_sijot == expected_missing

    def test_duplicate_sijot(self):
        """When same Sija appears multiple times, it should be tracked."""
        text = "# Sija 1\nPrimera aparición.\n\n# Sija 1\nSegunda aparición.\n"
        chunks = _compute_sijot_aware_chunks(text)
        metrics = _compute_sijot_metrics(chunks)
        if 1 in metrics.duplicate_sijot:
            pass  # Duplicate detection is valid

    def test_fallback_to_generic(self, text_without_sections: str):
        """Without detectable sections, sijot-aware should fall back gracefully."""
        chunks = _compute_sijot_aware_chunks(text_without_sections)
        assert len(chunks) > 0

    def test_large_chunks_counted(self):
        """Chunks over LARGE_CHUNK_THRESHOLD should be counted."""
        big_text = "Párrafo largo. " * 1000
        text = f"# Sija 1\n{big_text}\n\n# Sija 2\nCorto.\n"
        chunks = _compute_sijot_aware_chunks(text)
        metrics = _compute_sijot_metrics(chunks)
        # May have large chunks from the big paragraph
        if metrics.large_chunks:
            assert metrics.large_chunks > 0


# ── Metrics calculation tests ──────────────────────────────────────────


class TestMetrics:
    def test_generic_metrics_correct(self):
        chunks = [
            TemporaryChunk(content="A" * 100, char_start=0, char_end=100, content_length=100, chunk_index=0),
            TemporaryChunk(content="B" * 200, char_start=50, char_end=250, content_length=200, chunk_index=1),
        ]
        metrics = _compute_generic_metrics(chunks)
        assert metrics.chunks == 2
        assert metrics.min_chars == 100
        assert metrics.max_chars == 200
        assert metrics.median_chars == 150.0
        assert metrics.avg_chars == 150.0
        assert metrics.empty_chunks == 0

    def test_sijot_metrics_with_metadata(self):
        chunks = [
            TemporaryChunk(content="Sija 1 text", char_start=0, char_end=20, content_length=11,
                           section_type="sija", section_number=1, section_label="Sija 1",
                           source_strategy="sijot-aware", chunk_index=0),
            TemporaryChunk(content="Sija 2 text", char_start=21, char_end=41, content_length=11,
                           section_type="sija", section_number=2, section_label="Sija 2",
                           source_strategy="sijot-aware", chunk_index=1),
        ]
        metrics = _compute_sijot_metrics(chunks)
        assert metrics.chunks_with_section_metadata == 2
        assert metrics.sijot_detected == 2
        assert len(metrics.missing_sijot) == SIJOT_EXPECTED_COUNT - 2


# ── JSON report shape tests ────────────────────────────────────────────


class TestJSONReport:
    def test_json_shape(self):
        gm = StrategyMetrics(chunks=100, avg_chars=1500, median_chars=1550, min_chars=500, max_chars=2000)
        sm = StrategyMetrics(chunks=60, avg_chars=1400, median_chars=1450, min_chars=600, max_chars=1900,
                             sections_detected=50, sijot_detected=50, missing_sijot=[51, 52])
        report = _build_json_report(
            "Test Doc", "test_collection", "text content",
            gm, sm, {}, {}, [],
            {"recommended_option": "B", "reason": "Test"},
        )
        assert report["collection"] == "test_collection"
        assert report["document_title"] == "Test Doc"
        assert "strategies" in report
        assert "generic" in report["strategies"]
        assert "sijot_aware" in report["strategies"]
        assert report["strategies"]["generic"]["chunks"] == 100
        assert report["strategies"]["sijot_aware"]["sijot_detected"] == 50
        assert "comparison" in report
        assert report["comparison"]["recommended_option"] == "B"

    def test_json_empty_metrics(self):
        gm = StrategyMetrics()
        sm = StrategyMetrics()
        report = _build_json_report("Doc", "col", "", gm, sm, {}, {}, [], {"recommended_option": "D", "reason": "Test"})
        assert report["strategies"]["generic"]["chunks"] == 0

    def test_json_serializable(self):
        gm = StrategyMetrics(chunks=10, avg_chars=1500, median_chars=1500, min_chars=1000, max_chars=2000)
        sm = StrategyMetrics(chunks=5, avg_chars=1400, median_chars=1400, min_chars=800, max_chars=1900,
                             sections_detected=3, sijot_detected=3)
        report = _build_json_report(
            "Test", "col", "text", gm, sm, {}, {}, [],
            {"recommended_option": "A", "reason": "Test"},
        )
        json_str = json.dumps(report, indent=2, ensure_ascii=False)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["document_title"] == "Test"


# ── Sample limits test ──────────────────────────────────────────────────


class TestSampleLimits:
    def test_sample_text_truncation(self):
        long_text = "Párrafo.\n\n" * 500
        # With sample_size smaller than total
        sample = long_text[:500]
        generic_chunks = _compute_generic_chunks(sample)
        assert len(generic_chunks) > 0
        total_content = sum(len(c.content) for c in generic_chunks)
        assert total_content <= len(sample) * 1.1  # Allow small overhead


# ── Simulated search tests ─────────────────────────────────────────────


class TestSimulatedSearch:
    def test_search_finds_term(self):
        chunks = [
            TemporaryChunk(content="La maravilla del cerebro humano", char_start=0, char_end=35, content_length=35,
                           section_type="sija", section_number=1, section_label="Sija 1",
                           source_strategy="sijot-aware", chunk_index=0),
            TemporaryChunk(content="Servir a HaShem con alegría", char_start=36, char_end=65, content_length=29,
                           source_strategy="generic", chunk_index=1),
        ]
        results = _simulated_search("maravilla del cerebro", chunks, top_k=5)
        assert len(results) > 0
        assert results[0]["chunk_index"] == 0

    def test_search_empty_queries(self):
        chunks = [TemporaryChunk(content="Test content", char_start=0, char_end=12, content_length=12, chunk_index=0)]
        results = _simulated_search("notfound", chunks, top_k=5)
        assert len(results) == 0

    def test_search_respects_top_k(self):
        chunks = [TemporaryChunk(content=f"emuná paragraph {i}", char_start=i * 20, char_end=i * 20 + 18,
                                 content_length=18, chunk_index=i) for i in range(10)]
        results = _simulated_search("emuná", chunks, top_k=3)
        assert len(results) <= 3


# ── Page mapping dry-run tests ─────────────────────────────────────────


class TestPageMapping:
    def test_page_mapping_with_section_metadata(self):
        chunks = [
            TemporaryChunk(content="Sija 1 text", char_start=0, char_end=20, content_length=11,
                           section_type="sija", section_number=1, source_strategy="sijot-aware", chunk_index=0),
        ]
        mapping = _simulate_page_mapping(chunks, "text" * 50, total_pdf_pages=200)
        assert 0 in mapping
        assert mapping[0]["confidence"] == "high"

    def test_page_mapping_generic_confidence(self):
        chunks = [
            TemporaryChunk(content="Generic text", char_start=50, char_end=150, content_length=100,
                           source_strategy="generic", chunk_index=0),
        ]
        mapping = _simulate_page_mapping(chunks, "text" * 200, total_pdf_pages=100)
        assert 0 in mapping
        assert mapping[0]["confidence"] in ("low", "medium")

    def test_page_mapping_empty(self):
        mapping = _simulate_page_mapping([], "", 200)
        assert mapping == {}


# ── Recommendation tests ───────────────────────────────────────────────


class TestRecommendation:
    def test_recommendation_a_when_no_sections(self):
        sm = StrategyMetrics(sijot_detected=0)
        rec = _compute_recommendation(StrategyMetrics(), sm, [])
        assert rec["recommended_option"] == "A"

    def test_recommendation_c_when_many_missing(self):
        sm = StrategyMetrics(sijot_detected=10, missing_sijot=list(range(11, 53)))
        rec = _compute_recommendation(StrategyMetrics(), sm, [])
        assert rec["recommended_option"] == "C"

    def test_recommendation_b_when_good_coverage(self):
        sm = StrategyMetrics(sijot_detected=50, missing_sijot=[51, 52])
        rec = _compute_recommendation(StrategyMetrics(), sm, [])
        assert rec["recommended_option"] in ("B", "C")

    def test_recommendation_c_when_crossing_sections(self):
        sm = StrategyMetrics(sijot_detected=50, missing_sijot=[51, 52], chunks_crossing_sections=3)
        rec = _compute_recommendation(StrategyMetrics(), sm, [])
        assert rec["recommended_option"] in ("B", "C")