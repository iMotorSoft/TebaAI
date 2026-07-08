"""Tests for research schemas (Pydantic models)."""

from __future__ import annotations

from modules.library.research_schemas import (
    ConversationAnalysisResult,
    EvidenceClassification,
    EvidenceLevel,
    ResearchIntent,
    ResearchMode,
    ResearchAnswer,
    RetrievalMode,
    RetrievalStrategy,
    SafetyFlags,
    SourceMapEntry,
)


class TestEvidenceLevel:
    def test_values(self):
        assert EvidenceLevel.literal.value == "literal"
        assert EvidenceLevel.direct_quote.value == "direct_quote"
        assert EvidenceLevel.not_found.value == "not_found"

    def test_all_levels_present(self):
        expected = {
            "literal", "direct_quote", "paraphrase",
            "strong_thematic_reference", "remez_derash_inference", "not_found",
        }
        actual = {e.value for e in EvidenceLevel}
        assert actual == expected


class TestResearchIntent:
    def test_values(self):
        assert ResearchIntent.find_sources.value == "find_sources"
        assert ResearchIntent.out_of_scope.value == "out_of_scope"

    def test_all_intents_present(self):
        expected = {
            "find_sources", "explain_concept", "compare_sources",
            "locate_literal", "list_books", "evidence_check",
            "out_of_scope", "unclear",
        }
        actual = {i.value for i in ResearchIntent}
        assert actual == expected


class TestResearchMode:
    def test_values(self):
        assert ResearchMode.bibliographic.value == "bibliographic"
        assert ResearchMode.interpretive.value == "interpretive"


class TestRetrievalStrategy:
    def test_defaults(self):
        s = RetrievalStrategy()
        assert s.mode == RetrievalMode.hybrid
        assert s.top_k == 20
        assert s.filters == {}
        assert s.expanded_terms == []

    def test_custom(self):
        s = RetrievalStrategy(
            mode=RetrievalMode.fts,
            top_k=50,
            filters={"document_id": "abc"},
            expanded_terms=["fe", "emuna"],
        )
        assert s.mode == RetrievalMode.fts
        assert s.top_k == 50
        assert s.filters == {"document_id": "abc"}
        assert s.expanded_terms == ["fe", "emuna"]


class TestSafetyFlags:
    def test_defaults(self):
        f = SafetyFlags()
        assert f.may_need_interpretive_label is False
        assert f.risk_of_false_quote is False

    def test_custom(self):
        f = SafetyFlags(may_need_interpretive_label=True, risk_of_false_quote=True)
        assert f.may_need_interpretive_label is True
        assert f.risk_of_false_quote is True


class TestEvidenceClassification:
    def test_defaults(self):
        e = EvidenceClassification()
        assert e.evidence_type == EvidenceLevel.not_found
        assert e.confidence == "none"
        assert e.notes == ""

    def test_literal(self):
        e = EvidenceClassification(
            evidence_type=EvidenceLevel.literal,
            confidence="high",
            notes="Término encontrado literalmente.",
        )
        assert e.evidence_type == EvidenceLevel.literal
        assert e.confidence == "high"

    def test_confidence_literals(self):
        for c in ("high", "medium", "low", "none"):
            e = EvidenceClassification(evidence_type=EvidenceLevel.literal, confidence=c)
            assert e.confidence == c


class TestSourceMapEntry:
    def test_defaults(self):
        s = SourceMapEntry(document_title="Test", document_id="abc", chunk_id="chunk1")
        assert s.document_title == "Test"
        assert s.document_id == "abc"
        assert s.chunk_id == "chunk1"
        assert s.page_start is None
        assert s.evidence.evidence_type == EvidenceLevel.not_found
        assert s.canonical_excerpt == ""

    def test_full(self):
        ev = EvidenceClassification(evidence_type=EvidenceLevel.literal, confidence="high")
        s = SourceMapEntry(
            document_title="KITZUR",
            document_id="doc123",
            page_start=45,
            page_end=46,
            chunk_id="chunk_abc",
            chunk_index=3,
            evidence=ev,
            canonical_excerpt="El Tzadik es...",
            explanation="Término encontrado",
            limitations=["Sin página específica"],
        )
        assert s.document_title == "KITZUR"
        assert s.page_start == 45
        assert s.chunk_index == 3
        assert s.evidence.evidence_type == EvidenceLevel.literal


class TestConversationAnalysisResult:
    def test_defaults(self):
        r = ConversationAnalysisResult(user_query="¿Qué es un Tzadik?")
        assert r.user_query == "¿Qué es un Tzadik?"
        assert r.language == "unknown"
        assert r.intent == ResearchIntent.unclear
        assert r.research_mode == ResearchMode.bibliographic
        assert r.topic_terms == []
        assert r.retrieval_strategy.mode == RetrievalMode.hybrid
        assert r.analysis_fallback is False

    def test_full(self):
        r = ConversationAnalysisResult(
            user_query="¿Dónde aparece el miedo?",
            language="es",
            intent=ResearchIntent.find_sources,
            research_mode=ResearchMode.thematic,
            topic_terms=["miedo", "temor"],
            expanded_terms=["miedo", "temor", "angustia"],
            requires_literal_check=True,
            requires_cross_book_search=True,
            retrieval_strategy=RetrievalStrategy(
                mode=RetrievalMode.hybrid, top_k=30
            ),
            safety_flags=SafetyFlags(risk_of_false_quote=True),
            model_used="gpt5.5-nano",
        )
        assert r.language == "es"
        assert r.intent == ResearchIntent.find_sources
        assert r.topic_terms == ["miedo", "temor"]
        assert r.safety_flags.risk_of_false_quote is True


class TestResearchAnswer:
    def test_defaults(self):
        a = ResearchAnswer(query="test")
        assert a.query == "test"
        assert a.answer_summary == ""
        assert a.source_map == []
        assert a.limitations == []

    def test_with_source_map(self):
        ev = EvidenceClassification(evidence_type=EvidenceLevel.literal)
        entry = SourceMapEntry(
            document_title="KITZUR", document_id="d1", chunk_id="c1",
            evidence=ev, canonical_excerpt="texto...",
        )
        a = ResearchAnswer(
            query="tzadik",
            answer_summary="Se encontraron resultados.",
            source_map=[entry],
            evidence_counts={"literal": 1},
            documents_found=1,
            chunks_found=1,
            limitations=["Solo corpus ES/EN"],
        )
        assert len(a.source_map) == 1
        assert a.evidence_counts["literal"] == 1
        assert "Solo corpus ES/EN" in a.limitations
