"""Structured API contract for investigative relation QA."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceType(StrEnum):
    literal_phrase = "literal_phrase"
    literal_relation = "literal_relation"
    explicit_reference = "explicit_reference"
    biblical_citation = "biblical_citation"
    rabbinic_source = "rabbinic_source"
    breslov_text = "breslov_text"
    editorial_explanation = "editorial_explanation"
    footnote_reference = "footnote_reference"
    marginal_source = "marginal_source"
    internal_cross_reference = "internal_cross_reference"
    source_hebrew = "source_hebrew"
    cooccurrence_same_chunk = "cooccurrence_same_chunk"
    cooccurrence_same_page = "cooccurrence_same_page"
    cooccurrence_same_section = "cooccurrence_same_section"
    paraphrase = "paraphrase"
    thematic_relation = "thematic_relation"
    derash_interpretation = "derash_interpretation"
    remez_hint = "remez_hint"
    ai_inference = "ai_inference"
    ambiguous = "ambiguous"
    not_found = "not_found"
    excluded_false_positive = "excluded_false_positive"


class RelationQARequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    concept_a: str | None = Field(default=None, min_length=1, max_length=120)
    concept_b: str | None = Field(default=None, min_length=1, max_length=120)
    language: Literal["es", "en", "he", "auto"] = "auto"
    top_k: int = Field(default=20, ge=1, le=50)
    use_ai: bool = True
    include_test_candidates: bool = False
    knowledge_scope_code: str = Field(
        default="breslov_primary", min_length=1, max_length=100
    )
    evidence_depth: Literal["compact", "standard", "full"] = "standard"
    return_markdown: bool = True
    debug: bool = False


class ConceptVariants(BaseModel):
    label: str
    variants: list[str] = Field(default_factory=list)


class RelationQAConcepts(BaseModel):
    concept_a: ConceptVariants
    concept_b: ConceptVariants


class RelationQAAnswer(BaseModel):
    short_conclusion: str
    editorial_answer_markdown: str = ""
    literal_relation_found: bool = False
    ai_inference_used: bool = False
    editorial_certainty: Literal["low", "medium", "high"] = "low"


class EvidenceSummary(BaseModel):
    literal_phrase: int = 0
    literal_relation: int = 0
    explicit_reference: int = 0
    biblical_citation: int = 0
    rabbinic_source: int = 0
    breslov_text: int = 0
    editorial_explanation: int = 0
    footnote_reference: int = 0
    marginal_source: int = 0
    internal_cross_reference: int = 0
    source_hebrew: int = 0
    cooccurrence_same_chunk: int = 0
    cooccurrence_same_page: int = 0
    cooccurrence_same_section: int = 0
    paraphrase: int = 0
    thematic_relation: int = 0
    derash_interpretation: int = 0
    remez_hint: int = 0
    ai_inference: int = 0
    ambiguous: int = 0
    not_found: int = 0
    excluded_false_positive: int = 0


class RelationQASource(BaseModel):
    source_id: str
    document_id: str
    document_title: str
    document_status: str
    page_number: int | None = None
    section: str = ""
    chapter: str = ""
    subtitle: str = ""
    node_path: str = ""
    block_type: str = ""
    language: str = ""
    chunk_id: str
    evidence_type: EvidenceType
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    editorial_role: str = ""
    retrieval_method: str
    score: float = 0.0
    citable: bool = True
    is_final_citation: bool = True
    snippet: str
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    internal_cross_refs: list[dict[str, Any]] = Field(default_factory=list)


class RelationQAMethod(BaseModel):
    retrieval: list[str] = Field(default_factory=list)
    llm_model: str = ""
    embedding_model: str = ""
    used_pg_as_canonical: bool = True
    used_milvus: bool = False
    used_ai: bool = False
    ai_synthesis_status: str = "skipped"
    ai_synthesis_attempts: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    synthesis_mode: str = "deterministic_fallback"


class RelationQAResponse(BaseModel):
    question: str
    language: str
    knowledge_scope_code: str
    concepts: RelationQAConcepts
    answer: RelationQAAnswer
    evidence_summary: EvidenceSummary
    sources: list[RelationQASource] = Field(default_factory=list)
    source_map: list[RelationQASource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    method: RelationQAMethod
    debug: dict[str, Any] | None = None
