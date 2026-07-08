"""Tests for Breslov Research Conversation Analyzer (deterministic fallback)."""

from __future__ import annotations

from modules.library.conversation_analyzer import ResearchConversationAnalyzer
from modules.library.research_schemas import (
    ResearchIntent,
    ResearchMode,
    RetrievalMode,
)


class TestDeterministicAnalysis:
    def setup_method(self):
        self.analyzer = ResearchConversationAnalyzer()

    def test_spanish_query_detection(self):
        r = self.analyzer._analyze_deterministic("¿Qué es un Tzadik según Breslov?")
        assert r.language == "es"

    def test_english_query_detection(self):
        r = self.analyzer._analyze_deterministic("What is a Tzadik in Breslov?")
        assert r.language == "en"

    def test_find_sources_intent(self):
        r = self.analyzer._analyze_deterministic("¿Dónde aparece el miedo en los libros?")
        assert r.intent == ResearchIntent.find_sources

    def test_locate_literal_intent(self):
        r = self.analyzer._analyze_deterministic("¿Dónde aparece literalmente puente angosto?")
        assert r.intent == ResearchIntent.locate_literal

    def test_explain_concept_intent(self):
        r = self.analyzer._analyze_deterministic("¿Qué significa la fe en Breslov?")
        assert r.intent == ResearchIntent.explain_concept

    def test_evidence_check_intent(self):
        r = self.analyzer._analyze_deterministic("¿Eso es cita directa o interpretación?")
        assert r.intent == ResearchIntent.evidence_check

    def test_compare_sources_intent(self):
        r = self.analyzer._analyze_deterministic("¿Qué relación hay entre miedo, fe y alegría?")
        assert r.intent == ResearchIntent.compare_sources

    def test_list_books_intent(self):
        r = self.analyzer._analyze_deterministic("¿En qué libros se toca la tristeza?")
        assert r.intent == ResearchIntent.list_books

    def test_literal_mode(self):
        r = self.analyzer._analyze_deterministic("¿Dónde aparece literalmente?")
        assert r.research_mode == ResearchMode.literal

    def test_comparative_mode(self):
        r = self.analyzer._analyze_deterministic("Compara miedo y fe")
        assert r.research_mode == ResearchMode.comparative

    def test_literal_retrieval_mode(self):
        r = self.analyzer._analyze_deterministic("¿Dónde dice exactamente?")
        assert r.retrieval_strategy.mode == RetrievalMode.literal

    def test_hybrid_retrieval_default(self):
        r = self.analyzer._analyze_deterministic("¿Qué es un Tzadik?")
        assert r.retrieval_strategy.mode == RetrievalMode.hybrid

    def test_topic_term_extraction(self):
        r = self.analyzer._analyze_deterministic("¿Qué es la alegría en Breslov?")
        assert len(r.topic_terms) > 0
        assert "alegría" in r.topic_terms or "alegria" in r.topic_terms

    def test_expanded_terms_for_miedo(self):
        r = self.analyzer._analyze_deterministic("¿Dónde habla del miedo?")
        assert "miedo" in r.expanded_terms
        assert "temor" in r.expanded_terms

    def test_expanded_terms_for_tristeza(self):
        r = self.analyzer._analyze_deterministic("tristeza")
        assert "tristeza" in r.expanded_terms
        assert "depresión" in r.expanded_terms

    def test_requested_document_detection(self):
        r = self.analyzer._analyze_deterministic("¿Qué dice Likutey Halajot sobre plegaria?")
        assert "likutey halajot" in r.requested_documents

    def test_cross_book_search_flag(self):
        r = self.analyzer._analyze_deterministic("¿En qué libros se toca?")
        assert r.requires_cross_book_search is True

    def test_literal_check_flag(self):
        r = self.analyzer._analyze_deterministic("¿Dónde aparece literalmente?")
        assert r.requires_literal_check is True

    def test_fallback_flag(self):
        r = self.analyzer._analyze_deterministic("test")
        assert r.analysis_fallback is True

    def test_empty_query_base_case(self):
        r = self.analyzer._analyze_deterministic("¿Qué es?")
        assert r.user_query == "¿Qué es?"
        assert r.language == "es"

    def test_query_with_document_filter(self):
        r = self.analyzer._analyze_deterministic("¿Qué dice KITZUR sobre alegría?")
        assert "kitzur" in r.requested_documents

    def test_query_with_cruzando_detection(self):
        r = self.analyzer._analyze_deterministic("¿Dónde aparece en Cruzando el Puente?")
        assert "cruzando el puente" in r.requested_documents

    def test_requires_evidence_levels_default(self):
        r = self.analyzer._analyze_deterministic("¿Qué es fe?")
        assert r.requires_evidence_levels is True

    def test_requires_limitations_default(self):
        r = self.analyzer._analyze_deterministic("¿Qué es fe?")
        assert r.requires_limitations is True

    def test_safety_flags_default(self):
        r = self.analyzer._analyze_deterministic("¿Qué es un Tzadik?")
        assert r.safety_flags.risk_of_false_quote is False
        assert r.safety_flags.may_need_interpretive_label is False

    def test_analyze_method_returns_valid(self):
        r = self.analyzer.analyze("¿Dónde encontrar tristeza en Breslov?")
        assert r.user_query == "¿Dónde encontrar tristeza en Breslov?"
        assert r.language == "es"

    def test_analyze_english_method(self):
        r = self.analyzer.analyze("Where can I find sadness in Breslov?")
        assert r.language == "en"
