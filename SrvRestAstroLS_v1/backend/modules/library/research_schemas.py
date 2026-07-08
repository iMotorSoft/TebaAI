"""Pydantic schemas for Breslov Research Conversation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceLevel(str, Enum):
    literal = "literal"
    direct_quote = "direct_quote"
    paraphrase = "paraphrase"
    strong_thematic_reference = "strong_thematic_reference"
    remez_derash_inference = "remez_derash_inference"
    not_found = "not_found"


class ResearchIntent(str, Enum):
    find_sources = "find_sources"
    explain_concept = "explain_concept"
    compare_sources = "compare_sources"
    locate_literal = "locate_literal"
    list_books = "list_books"
    evidence_check = "evidence_check"
    out_of_scope = "out_of_scope"
    unclear = "unclear"


class ResearchMode(str, Enum):
    bibliographic = "bibliographic"
    conceptual = "conceptual"
    comparative = "comparative"
    literal = "literal"
    thematic = "thematic"
    interpretive = "interpretive"


class RetrievalMode(str, Enum):
    hybrid = "hybrid"
    vector = "vector"
    fts = "fts"
    literal = "literal"


class SafetyFlags(BaseModel):
    may_need_interpretive_label: bool = False
    risk_of_false_quote: bool = False


class RetrievalStrategy(BaseModel):
    mode: RetrievalMode = RetrievalMode.hybrid
    top_k: int = 20
    filters: dict[str, Any] = Field(default_factory=dict)
    expanded_terms: list[str] = Field(default_factory=list)


class ConversationAnalysisResult(BaseModel):
    user_query: str
    language: str = "unknown"
    intent: ResearchIntent = ResearchIntent.unclear
    research_mode: ResearchMode = ResearchMode.bibliographic
    topic_terms: list[str] = Field(default_factory=list)
    expanded_terms: list[str] = Field(default_factory=list)
    requested_documents: list[str] = Field(default_factory=list)
    requires_literal_check: bool = False
    requires_cross_book_search: bool = False
    requires_evidence_levels: bool = True
    requires_limitations: bool = True
    retrieval_strategy: RetrievalStrategy = Field(default_factory=RetrievalStrategy)
    safety_flags: SafetyFlags = Field(default_factory=SafetyFlags)
    model_used: str = ""
    analysis_fallback: bool = False


class EvidenceClassification(BaseModel):
    evidence_type: EvidenceLevel = EvidenceLevel.not_found
    confidence: Literal["high", "medium", "low", "none"] = "none"
    notes: str = ""


class SourceMapEntry(BaseModel):
    document_title: str
    document_id: str
    page_start: int | None = None
    page_end: int | None = None
    chunk_id: str
    chunk_index: int = 0
    evidence: EvidenceClassification = Field(default_factory=EvidenceClassification)
    canonical_excerpt: str = ""
    explanation: str = ""
    limitations: list[str] = Field(default_factory=list)


class ResearchAnswer(BaseModel):
    query: str
    conversation_analysis: ConversationAnalysisField = Field(
        default_factory=lambda: ConversationAnalysisField()
    )
    answer_summary: str = ""
    source_map: list[SourceMapEntry] = Field(default_factory=list)
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    documents_found: int = 0
    chunks_found: int = 0
    limitations: list[str] = Field(default_factory=list)
    answer_generated_at: str = ""


class ConversationAnalysisField(BaseModel):
    language: str = "unknown"
    intent: str = "unclear"
    research_mode: str = "bibliographic"
    topic_terms: list[str] = Field(default_factory=list)
    model_used: str = ""
    analysis_fallback: bool = False
