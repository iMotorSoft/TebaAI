"""Read-only orchestration for the investigative Breslov relation QA API."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from typing import Any

from psycopg import AsyncConnection

from globalVar import (
    BRESLOV_PRODUCTIVE_COLLECTION,
    RESEARCH_CONVERSATION_MODEL,
    RESEARCH_EMBEDDING_MODEL_ALIAS,
)
from infrastructure.milvus.client import (
    close_connection,
    create_connection,
    search_vectors,
)
from modules.embeddings.client import embed_text
from modules.library.domain import KnowledgeScope
from modules.library.relation_qa_ai import (
    RelationQAAIError,
    build_editorial_answer_with_ai,
)
from modules.library.relation_qa_evidence import (
    build_relation_patterns,
    build_source_map,
    expand_concept_variants,
    extract_concepts_from_question,
    merge_candidate_rows,
    validate_sources_resolve_to_pg,
)
from modules.library.relation_qa_repository import (
    get_chunks_by_ids,
    search_cooccurrence_chunks,
    search_fts_chunks,
    search_ilike_chunks,
    search_relation_pattern_chunks,
)
from modules.library.relation_qa_schemas import (
    ConceptVariants,
    EvidenceSummary,
    EvidenceType,
    RelationQAAnswer,
    RelationQAConcepts,
    RelationQAMethod,
    RelationQARequest,
    RelationQAResponse,
    RelationQASource,
)


def _detect_language(question: str) -> str:
    if any("\u0590" <= char <= "\u05ff" for char in question):
        return "he"
    lower = question.casefold()
    if any(word in lower for word in ("where", "what", "between", "speech", "blood")):
        return "en"
    return "es"


def _resolve_concepts(data: RelationQARequest) -> tuple[str, str]:
    extracted_a, extracted_b = extract_concepts_from_question(data.question)
    return (data.concept_a or extracted_a, data.concept_b or extracted_b)


def _vector_search_sync(queries: list[str], top_k: int) -> list[dict[str, Any]]:
    """Search an existing collection; this code has no collection creation path."""
    results: dict[str, dict[str, Any]] = {}
    create_connection()
    try:
        for query in queries:
            vector = embed_text(query, model=RESEARCH_EMBEDDING_MODEL_ALIAS)
            hits = search_vectors(
                collection_name=BRESLOV_PRODUCTIVE_COLLECTION,
                query_embedding=vector,
                top_k=top_k,
                expr='collection_code == "breslov"',
                output_fields=["chunk_id", "document_id"],
            )
            for hit in hits:
                chunk_id = str(hit.get("chunk_id") or "")
                if not chunk_id:
                    continue
                score = float(hit.get("distance") or 0.0)
                current = results.get(chunk_id)
                if current is None or score > current["score"]:
                    results[chunk_id] = {"chunk_id": chunk_id, "score": score}
    finally:
        close_connection()
    return list(results.values())


async def retrieve_relation_evidence(
    conn: AsyncConnection,
    *,
    scope: KnowledgeScope,
    data: RelationQARequest,
    language: str,
    concept_a_variants: list[str],
    concept_b_variants: list[str],
) -> tuple[list[dict[str, Any]], list[str], list[str], bool]:
    """Execute the ordered lexical, relational and vector retrieval pipeline."""
    warnings: list[str] = []
    methods: list[str] = []
    variants = list(dict.fromkeys([*concept_a_variants, *concept_b_variants]))
    candidate_limit = max(data.top_k * 3, 30)

    fts_rows = await search_fts_chunks(
        conn,
        knowledge_scope_id=scope.id,
        variants=variants,
        language=language,
        include_test_candidates=data.include_test_candidates,
        limit=candidate_limit,
    )
    if fts_rows:
        methods.append("postgresql_fts_websearch")

    ilike_rows = await search_ilike_chunks(
        conn,
        knowledge_scope_id=scope.id,
        variants=variants,
        include_test_candidates=data.include_test_candidates,
        limit=candidate_limit,
    )
    if ilike_rows:
        methods.append("postgresql_ilike_fallback")

    relation_rows = await search_relation_pattern_chunks(
        conn,
        knowledge_scope_id=scope.id,
        patterns=build_relation_patterns(concept_a_variants, concept_b_variants),
        include_test_candidates=data.include_test_candidates,
        limit=candidate_limit,
    )
    if relation_rows:
        methods.append("postgresql_relation_patterns")

    cooccurrence_rows = await search_cooccurrence_chunks(
        conn,
        knowledge_scope_id=scope.id,
        concept_a_variants=concept_a_variants,
        concept_b_variants=concept_b_variants,
        include_test_candidates=data.include_test_candidates,
        limit=candidate_limit,
    )
    if cooccurrence_rows:
        methods.append("postgresql_cooccurrence")

    vector_rows: list[dict[str, Any]] = []
    used_milvus = False
    if scope.knowledge_scope_code == "breslov_primary":
        queries = list(
            dict.fromkeys(
                [
                    data.question,
                    f"{concept_a_variants[0]} {concept_b_variants[0]}",
                    f"conexión entre {concept_a_variants[0]} y {concept_b_variants[0]}",
                ]
            )
        )
        try:
            vector_hits = await asyncio.to_thread(_vector_search_sync, queries, data.top_k)
            used_milvus = True
            if vector_hits:
                pg_rows = await get_chunks_by_ids(
                    conn,
                    knowledge_scope_id=scope.id,
                    chunk_ids=[hit["chunk_id"] for hit in vector_hits],
                    include_test_candidates=data.include_test_candidates,
                )
                hit_by_id = {hit["chunk_id"]: hit for hit in vector_hits}
                for row in pg_rows:
                    hit = hit_by_id[row["chunk_id"]]
                    row["retrieval_methods"] = ["vector"]
                    row["score"] = hit["score"]
                    vector_rows.append(row)
                missing = len(vector_hits) - len(pg_rows)
                if missing:
                    warnings.append(f"milvus_candidates_without_authorized_pg:{missing}")
                methods.append("milvus_dense_cosine")
        except Exception:
            warnings.append("milvus_unavailable: lexical retrieval used")
    else:
        warnings.append("milvus_not_routed_for_requested_scope")

    rows = merge_candidate_rows(
        relation_rows,
        cooccurrence_rows,
        fts_rows,
        ilike_rows,
        vector_rows,
    )
    return rows, methods, warnings, used_milvus


def _contains_variant(text: str, variants: list[str]) -> bool:
    lower = text.casefold()
    return any(value.casefold() in lower for value in variants if len(value) >= 2)


def _add_cross_chunk_relations(
    sources: list[RelationQASource],
    concept_a_variants: list[str],
    concept_b_variants: list[str],
) -> None:
    pages: dict[tuple[str, int], list[RelationQASource]] = defaultdict(list)
    sections: dict[tuple[str, str], list[RelationQASource]] = defaultdict(list)
    for source in sources:
        if source.page_number is not None:
            pages[(source.document_id, source.page_number)].append(source)
        if source.section:
            sections[(source.document_id, source.section)].append(source)

    for group, evidence_type in (
        (pages.values(), EvidenceType.cooccurrence_same_page),
        (sections.values(), EvidenceType.cooccurrence_same_section),
    ):
        for items in group:
            has_a = any(_contains_variant(item.snippet, concept_a_variants) for item in items)
            has_b = any(_contains_variant(item.snippet, concept_b_variants) for item in items)
            if has_a and has_b:
                for item in items:
                    if evidence_type not in item.evidence_types:
                        item.evidence_types.append(evidence_type)


def _evidence_summary(sources: list[RelationQASource]) -> EvidenceSummary:
    counts: Counter[str] = Counter()
    for source in sources:
        counts.update(value.value for value in source.evidence_types)
    if not sources:
        counts[EvidenceType.not_found.value] = 1
    values = {name: counts.get(name, 0) for name in EvidenceSummary.model_fields}
    return EvidenceSummary(**values)


def _deterministic_answer(
    sources: list[RelationQASource],
    literal_relation_found: bool,
) -> RelationQAAnswer:
    has_cooccurrence = any(
        EvidenceType.cooccurrence_same_chunk in source.evidence_types
        for source in sources
    )
    if literal_relation_found:
        conclusion = "Se encontró una relación literal explícita en el corpus recuperado."
        certainty = "high"
    elif has_cooccurrence:
        conclusion = (
            "No se encontró una relación literal directa; sí hay coocurrencia de "
            "los conceptos y requiere lectura editorial."
        )
        certainty = "low"
    elif sources:
        conclusion = (
            "No se encontró una relación literal ni coocurrencia concluyente; "
            "los resultados son temáticos o referencias separadas."
        )
        certainty = "low"
    else:
        conclusion = "No se encontró evidencia suficiente en el corpus autorizado."
        certainty = "low"

    lines = [conclusion, "", "Fuentes recuperadas:"]
    for source in [value for value in sources if value.is_final_citation][:8]:
        page = f", p. {source.page_number}" if source.page_number is not None else ""
        lines.append(
            f"- [{source.source_id}] {source.document_title}{page} "
            f"({source.evidence_type.value})."
        )
    return RelationQAAnswer(
        short_conclusion=conclusion,
        editorial_answer_markdown="\n".join(lines),
        literal_relation_found=literal_relation_found,
        ai_inference_used=False,
        editorial_certainty=certainty,
    )


def _editorial_warnings(
    sources: list[RelationQASource],
    *,
    literal_relation_found: bool,
    ai_inference_used: bool,
    include_test_candidates: bool,
) -> list[str]:
    warnings: list[str] = []
    has_cooccurrence = any(
        EvidenceType.cooccurrence_same_chunk in source.evidence_types
        for source in sources
    )
    if not literal_relation_found:
        warnings.append("no_literal_relation: no citar como doctrina literal")
    if has_cooccurrence and not literal_relation_found:
        warnings.append("cooccurrence_only: coocurrencia no equivale a relación explícita")
    if ai_inference_used:
        warnings.append("ai_inference: INFERIDA_POR_IA")
    if any(EvidenceType.ambiguous in source.evidence_types for source in sources):
        warnings.append("ambiguous_hebrew_davar: דבר requiere desambiguación editorial")
    if include_test_candidates and any(
        source.document_status != "ready" for source in sources
    ):
        warnings.append("test_candidate_read_only: no constituye promoción productiva")
    if any(not source.is_final_citation for source in sources):
        warnings.append("non_final_context_excluded_from_citations")
    return warnings


async def run_relation_qa(
    conn: AsyncConnection,
    data: RelationQARequest,
    scope: KnowledgeScope,
    *,
    allow_debug: bool = False,
) -> RelationQAResponse:
    """Run relation QA over an already authorized knowledge scope."""
    language = _detect_language(data.question) if data.language == "auto" else data.language
    concept_a, concept_b = _resolve_concepts(data)
    concept_a_variants = expand_concept_variants(concept_a, language)
    concept_b_variants = expand_concept_variants(concept_b, language)

    rows, methods, retrieval_warnings, used_milvus = await retrieve_relation_evidence(
        conn,
        scope=scope,
        data=data,
        language=language,
        concept_a_variants=concept_a_variants,
        concept_b_variants=concept_b_variants,
    )
    sources = build_source_map(
        rows,
        concept_a_variants,
        concept_b_variants,
        data.evidence_depth,
        data.top_k,
    )
    _add_cross_chunk_relations(sources, concept_a_variants, concept_b_variants)
    validate_sources_resolve_to_pg(sources)
    summary = _evidence_summary(sources)
    literal_relation_found = summary.literal_relation > 0
    answer = _deterministic_answer(sources, literal_relation_found)
    ai_warning: str | None = None
    used_ai = False

    if data.use_ai and sources:
        try:
            ai_result = await build_editorial_answer_with_ai(
                question=data.question,
                concept_a=concept_a,
                concept_b=concept_b,
                sources=sources,
                literal_relation_found=literal_relation_found,
            )
            answer.short_conclusion = ai_result.short_conclusion
            answer.editorial_answer_markdown = ai_result.editorial_answer_markdown
            answer.editorial_certainty = ai_result.editorial_certainty
            answer.ai_inference_used = ai_result.ai_inference_used
            used_ai = True
        except RelationQAAIError:
            ai_warning = "ai_response_parse_failed: deterministic editorial fallback used"

    if not data.return_markdown:
        answer.editorial_answer_markdown = ""
    summary.ai_inference = 1 if answer.ai_inference_used else 0
    warnings = [
        *retrieval_warnings,
        *_editorial_warnings(
            sources,
            literal_relation_found=literal_relation_found,
            ai_inference_used=answer.ai_inference_used,
            include_test_candidates=data.include_test_candidates,
        ),
    ]
    if ai_warning:
        warnings.append(ai_warning)
    if data.debug and not allow_debug:
        warnings.append("debug_omitted: requires admin role")

    debug: dict[str, Any] | None = None
    if data.debug and allow_debug:
        debug = {
            "candidate_rows": len(rows),
            "source_rows": len(sources),
            "final_citations": sum(source.is_final_citation for source in sources),
            "document_statuses": dict(Counter(source.document_status for source in sources)),
        }

    method = RelationQAMethod(
        retrieval=list(dict.fromkeys(methods)),
        llm_model=RESEARCH_CONVERSATION_MODEL if used_ai else "",
        embedding_model=RESEARCH_EMBEDDING_MODEL_ALIAS,
        used_pg_as_canonical=True,
        used_milvus=used_milvus,
        used_ai=used_ai,
    )
    concepts = RelationQAConcepts(
        concept_a=ConceptVariants(label=concept_a, variants=concept_a_variants),
        concept_b=ConceptVariants(label=concept_b, variants=concept_b_variants),
    )
    return RelationQAResponse(
        question=data.question,
        language=language,
        knowledge_scope_code=scope.knowledge_scope_code,
        concepts=concepts,
        answer=answer,
        evidence_summary=summary,
        sources=sources,
        source_map=sources,
        warnings=list(dict.fromkeys(warnings)),
        method=method,
        debug=debug,
    )
