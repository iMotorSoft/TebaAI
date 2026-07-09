"""Book QA V2 SQL-only schemas — PostgreSQL V2 grounded answers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BookQAOptions(BaseModel):
    include_sources_nearby: bool = True
    include_page_text: bool = False
    allow_ai_synthesis: bool = False
    allow_milvus: bool = False


class BookQARequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    run_id: str = Field(..., min_length=1, max_length=64)
    scope_code: str = "breslov_test"
    top_k: int = Field(default=8, ge=1, le=20)
    language: Literal["es", "en", "he"] = "es"
    options: BookQAOptions = Field(default_factory=BookQAOptions)


class BookQASource(BaseModel):
    page_number: int
    evidence_type: Literal[
        "literal", "partial_phrase", "concept", "relation_candidate",
        "cooccurrence_same_page", "cooccurrence_nearby_pages",
        "source_reference", "semantic_disabled", "no_evidence",
    ]
    score: float = 0.0
    snippet: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    source_refs_nearby: list[dict[str, str]] = Field(default_factory=list)
    grounded_in_postgres: bool = True


class BookQAEvidenceSummary(BaseModel):
    literal_matches: int = 0
    concept_matches: int = 0
    relation_matches: int = 0
    source_references: int = 0
    pages: list[int] = Field(default_factory=list)


class BookQAMethod(BaseModel):
    retrieval: str = "postgres_v2_sql_only"
    used_milvus: bool = False
    used_embeddings: bool = False
    used_ai: bool = False
    milvus_disabled: bool = True
    ai_synthesis_enabled: bool = False
    run_id: str = ""
    scope_code: str = ""


class BookQAResponse(BaseModel):
    question: str
    route: str = "book_qa_v2_sql"
    run_id: str
    document_id: str = ""
    scope_code: str = ""
    answer_type: Literal[
        "concept_lookup", "phrase_lookup", "relation_lookup", "mixed", "no_evidence"
    ] = "no_evidence"
    short_conclusion: str = ""
    evidence_summary: BookQAEvidenceSummary = Field(default_factory=BookQAEvidenceSummary)
    sources: list[BookQASource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    method: BookQAMethod = Field(default_factory=BookQAMethod)
