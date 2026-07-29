"""Simple, failure-tolerant, PostgreSQL-grounded RAG for research."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import defaultdict
from typing import Any

import httpx

from globalVar import (
    BRESLOV_PRODUCTIVE_COLLECTION,
    EMBEDDINGS_DIMENSION,
    EMBEDDINGS_MODEL_ALIAS,
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
)
from infrastructure.milvus.client import (
    create_connection,
    ensure_collection,
    search_vectors,
)
from modules.embeddings.client import embed_text
from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope
from modules.library.investigative_model import detect_language
from modules.library.simple_research_repository import (
    fetch_canonical_chunks,
    resolve_ready_documents,
    search_literal_candidates,
)

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = "breslov_primary"
DEFAULT_WORKS = {"kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"}
SEMANTIC_TOP_K = 30
LITERAL_TOP_K = 30
CONTEXT_MIN = 8
CONTEXT_MAX = 12

CONTROLLED_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "azamra": ("Azamra", "Azamrá", "אזמרה", "אֲזַמְּרָה", "I will sing", "cantaré"),
    "escorpion": ("escorpión", "escorpion", "escorpiones", "scorpion", "scorpions", "עקרב", "עקרבים"),
    "habla": ("habla", "palabra", "decir", "voz", "speech", "speaking", "דיבור"),
    "sangre": ("sangre", "blood", "דם"),
    "alegria": ("alegría", "alegria", "simjá", "simcha", "joy", "שמחה"),
    "emuna": ("emuná", "emuna", "emunah", "fe", "faith", "אמונה"),
    "miedo": ("miedo", "temor", "fear", "awe", "פחד", "יראה"),
    "tristeza": ("tristeza", "melancolía", "sadness", "atzvut", "עצבות"),
    "hitbodedut": ("hitbodedut", "התבודדות", "plegaria personal", "secluded prayer"),
    "salmo 19": ("Salmo 19", "Salmos 19", "Psalm 19", "Psalms 19", "תהלים יט"),
}


def _fold(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(char)
    )


def build_query_variants(original_query: str) -> list[str]:
    """Keep the complete query first and add only bounded, controlled aliases."""
    folded = _fold(original_query)
    variants = [original_query]
    for key, aliases in CONTROLLED_EXPANSIONS.items():
        if key in folded:
            variants.extend(aliases)
    if "sangre" in folded and "habla" in folded:
        variants.extend((
            "impurezas en la sangre",
            "elevar la voz",
            "recitación del Shemá",
            "recitar esos dos versículos",
            "Reinado del Cielo",
        ))
    return list(dict.fromkeys(item.strip() for item in variants if item.strip()))[:24]


def build_explicit_filters(data: Any) -> dict[str, Any]:
    works = list(data.works)
    explicit_works = works if set(works) != DEFAULT_WORKS else []
    languages = list(dict.fromkeys(data.languages)) or [detect_language(data.question)]
    return {
        "scope": DEFAULT_SCOPE,
        "works": explicit_works,
        "languages": languages,
        "include_parallels": bool(data.include_thematic),
        "result_limit": min(max(int(data.max_hits_per_work), 1), 20),
    }


def _milvus_expression(
    *,
    scope_code: str,
    languages: list[str],
    document_ids: list[str],
) -> str:
    clauses = [
        f'collection_code == "{resolve_milvus_collection_code_for_scope(scope_code)}"'
    ]
    if languages:
        quoted = ", ".join(json.dumps(item) for item in languages)
        clauses.append(f"language in [{quoted}]")
    if document_ids:
        quoted = ", ".join(json.dumps(item) for item in document_ids)
        clauses.append(f"document_id in [{quoted}]")
    return " and ".join(clauses)


def _semantic_search(
    original_query: str,
    *,
    scope_code: str,
    languages: list[str],
    document_ids: list[str],
    simulate_failure: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    if simulate_failure:
        raise RuntimeError("simulated_milvus_failure")
    vector = embed_text(original_query)
    if len(vector) != EMBEDDINGS_DIMENSION:
        raise ValueError("embedding_dimension_mismatch")
    create_connection()
    ensure_collection(BRESLOV_PRODUCTIVE_COLLECTION, dimension=len(vector))
    hits = search_vectors(
        collection_name=BRESLOV_PRODUCTIVE_COLLECTION,
        query_embedding=vector,
        top_k=SEMANTIC_TOP_K,
        expr=_milvus_expression(
            scope_code=scope_code,
            languages=languages,
            document_ids=document_ids,
        ),
        output_fields=["chunk_id", "document_id", "language"],
    )
    return (
        [
            {
                "chunk_id": str(hit.get("chunk_id") or ""),
                "semantic_score": float(hit.get("distance") or 0.0),
                "semantic_rank": index + 1,
            }
            for index, hit in enumerate(hits)
            if hit.get("chunk_id")
        ],
        {
            "model": EMBEDDINGS_MODEL_ALIAS,
            "dimension": len(vector),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )


def merge_results(
    semantic: list[dict[str, Any]],
    literal: list[dict[str, Any]],
    *,
    query_language: str,
) -> list[dict[str, Any]]:
    """Fuse ranks without allowing either retrieval branch to erase the other."""
    merged: dict[str, dict[str, Any]] = {}
    for item in semantic:
        merged[item["chunk_id"]] = {
            **item,
            "literal_score": 0.0,
            "literal_rank": None,
            "exact_match": False,
            "retrieval_sources": ["milvus"],
        }
    for rank, item in enumerate(literal, 1):
        chunk_id = str(item["chunk_id"])
        target = merged.setdefault(chunk_id, {
            "chunk_id": chunk_id,
            "semantic_score": 0.0,
            "semantic_rank": None,
            "retrieval_sources": [],
        })
        target.update({
            "literal_score": float(item.get("literal_score") or 0.0),
            "literal_rank": rank,
            "exact_match": bool(item.get("exact_match")),
            "exact_variant_count": int(item.get("exact_variant_count") or 0),
        })
        target["retrieval_sources"].append("literal")
    for item in merged.values():
        semantic_rrf = 1 / (50 + item["semantic_rank"]) if item.get("semantic_rank") else 0.0
        literal_rrf = 1 / (50 + item["literal_rank"]) if item.get("literal_rank") else 0.0
        overlap_bonus = 0.008 if len(item["retrieval_sources"]) == 2 else 0.0
        exact_bonus = 0.006 if item.get("exact_match") else 0.0
        controlled_coverage_bonus = min(
            int(item.get("exact_variant_count") or 0),
            8,
        ) * 0.002
        item["combined_score"] = (
            semantic_rrf
            + literal_rrf
            + overlap_bonus
            + exact_bonus
            + controlled_coverage_bonus
        )
        item["query_language"] = query_language
    return sorted(
        merged.values(),
        key=lambda item: (item["combined_score"], item["semantic_score"]),
        reverse=True,
    )


def _source_layer(chunk: dict[str, Any]) -> str:
    role = str(chunk.get("evidence_role") or "")
    block = str(chunk.get("block_type") or "")
    if block == "footnote":
        return "footnote"
    if "source" in role:
        return "rebbe_lesson_text"
    if "comment" in role:
        return "editorial_commentary"
    return "editorial_translation" if chunk.get("language") == "es" else "unknown"


def _work_code(chunk: dict[str, Any]) -> str:
    title = _fold(str(chunk.get("work") or ""))
    if "kitzur" in title:
        return "kitzur"
    if "potencia de la plegaria" in title:
        return "potencia_plegaria"
    if "likutey halajot" in title:
        return "lh"
    if "likutey moharan ii" in title:
        return "lmii"
    if "likutey moharan" in title:
        return "lmi"
    return str(chunk.get("document_code") or "breslov")


def select_context(
    ranked: list[dict[str, Any]],
    canonical_by_id: dict[str, dict[str, Any]],
    *,
    explicit_work_filter: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_work: defaultdict[str, int] = defaultdict(int)
    seen_content: set[str] = set()
    max_per_work = CONTEXT_MAX if explicit_work_filter else 4
    for item in ranked:
        chunk = canonical_by_id.get(item["chunk_id"])
        if not chunk:
            continue
        content_key = str(chunk.get("content_sha256") or "")
        if not content_key:
            content_key = hashlib.sha256(str(chunk.get("markdown") or "").encode()).hexdigest()
        if content_key in seen_content:
            continue
        work = str(chunk.get("work") or "")
        if per_work[work] >= max_per_work:
            continue
        selected.append({**chunk, **item})
        seen_content.add(content_key)
        per_work[work] += 1
        if len(selected) >= CONTEXT_MAX:
            break
    return selected


def _evidence_id(chunk_id: str) -> str:
    return f"ev-{hashlib.sha256(chunk_id.encode()).hexdigest()[:16]}"


def _context_pack(original_query: str, filters: dict[str, Any], chunks: list[dict[str, Any]]) -> str:
    lines = [
        "PREGUNTA ORIGINAL",
        original_query,
        "",
        "FILTROS EXPLÍCITOS",
        json.dumps(filters, ensure_ascii=False),
        "",
        "INSTRUCCIONES DE RESPUESTA",
        "Usá exclusivamente las fuentes siguientes. Citá evidence_ids.",
    ]
    for index, chunk in enumerate(chunks, 1):
        lines.extend([
            "",
            f"FUENTE {index}",
            f"Evidence ID: {chunk['evidence_id']}",
            f"Obra: {chunk['work']}",
            f"Página PDF: {chunk.get('pdf_page')}",
            f"Página impresa: {chunk.get('printed_page')}",
            f"Idioma: {chunk.get('language')}",
            "Markdown:",
            str(chunk.get("markdown") or ""),
        ])
    return "\n".join(lines)


def validate_grounded_answer(
    value: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    allowed = {chunk["evidence_id"]: chunk for chunk in chunks}
    markdown = str(value.get("answer_markdown") or "").strip()
    claims = value.get("claims")
    if not markdown or not isinstance(claims, list) or not claims:
        raise ValueError("missing_grounded_answer")
    cited_in_markdown = set(re.findall(r"\bev-[0-9a-f]{16}\b", markdown))
    if not cited_in_markdown.issubset(allowed):
        raise ValueError("invented_markdown_evidence_id")
    normalized_claims = []
    for index, claim in enumerate(claims, 1):
        ids = list(dict.fromkeys(
            str(item).strip().strip("[]`")
            for item in claim.get("evidence_ids", [])
        ))
        if not ids or not set(ids).issubset(allowed):
            raise ValueError(f"invalid_evidence_id:{ids}")
        relation_type = str(claim.get("relation_type") or "thematic")
        if relation_type not in {"direct", "mediated", "thematic", "none"}:
            raise ValueError("invalid_relation_type")
        confidence = str(claim.get("confidence") or "low")
        if confidence not in {"high", "medium", "low"}:
            raise ValueError("invalid_confidence")
        normalized_claims.append({
            "claim_id": str(claim.get("claim_id") or f"claim_{index}"),
            "text": str(claim.get("text") or "").strip(),
            "strength": {"high": "strong", "medium": "medium", "low": "weak"}[confidence],
            "confidence": confidence,
            "relation_type": relation_type,
            "evidence_ids": ids,
            "primary_evidence_id": ids[0],
        })
        if not normalized_claims[-1]["text"]:
            raise ValueError("empty_claim")
    allowed_pages = {
        str(chunk["pdf_page"])
        for chunk in chunks
        if chunk.get("pdf_page") is not None
    }
    mentioned_pages = re.findall(r"(?i)(?:página|pdf p\.)\s*(\d+)", markdown)
    if any(page not in allowed_pages for page in mentioned_pages):
        raise ValueError("invented_page")
    return markdown, normalized_claims


async def render_grounded_answer(
    original_query: str,
    filters: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    simulate_failure: bool,
) -> tuple[str, list[dict[str, Any]], bool]:
    if simulate_failure:
        raise RuntimeError("simulated_ai_render_failure")
    if not LITELLM_API_KEY:
        raise RuntimeError("litellm_key_missing")
    prompt = (
        "Respondé únicamente usando las fuentes proporcionadas. Conservá la pregunta "
        "original. Si la relación es directa, decilo; si es mediada, explicá la cadena; "
        "si es temática, marcala como temática. No inventes citas, páginas, obras ni "
        "referencias. Cada afirmación importante debe incluir evidence_ids. Diferenciá "
        "cita literal de interpretación. No copies citas textuales en la respuesta: "
        "parafraseá y remití al evidence_id para que el backend muestre el Markdown "
        "canónico. Si las fuentes no alcanzan, decilo claramente. Respondé en el idioma "
        "del usuario. No uses conocimiento externo. Devolvé JSON con answer_markdown y "
        "claims. Cada claim: claim_id, text, "
        "evidence_ids, relation_type (direct|mediated|thematic|none), confidence "
        "(high|medium|low). Escribí como máximo 350 palabras y 3 claims. Todos los "
        "claims deben tener al menos un evidence_id exacto del paquete."
    )
    context_pack = _context_pack(original_query, filters, chunks)
    allowed_ids = [chunk["evidence_id"] for chunk in chunks]
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
        for attempt in range(2):
            repair = (
                ""
                if attempt == 0
                else (
                    "\nREINTENTO DE VALIDACIÓN: la salida anterior fue rechazada. "
                    "Usá solamente estos IDs exactos y no dejes evidence_ids vacío: "
                    + ", ".join(allowed_ids)
                )
            )
            try:
                response = await client.post(
                    f"{LITELLM_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                    json={
                        "model": RESEARCH_CONVERSATION_MODEL,
                        "messages": [
                            {"role": "system", "content": prompt + repair},
                            {"role": "user", "content": context_pack},
                        ],
                        "temperature": 0,
                        "max_tokens": 1200,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                value = json.loads(
                    response.json()["choices"][0]["message"]["content"]
                )
                markdown, claims = validate_grounded_answer(value, chunks)
                return markdown, claims, True
            except Exception as exc:
                last_error = exc
    assert last_error is not None
    raise last_error


def _fallback_answer(chunks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    lines = [
        "## Fuentes recuperadas",
        "",
        "La redacción automática no estuvo disponible. Se muestran las fuentes recuperadas.",
    ]
    for chunk in chunks[:5]:
        location = f"PDF p. {chunk['pdf_page']}" if chunk.get("pdf_page") is not None else "página no disponible"
        excerpt = " ".join(str(chunk.get("markdown") or "").split())[:500]
        lines.extend([
            "",
            f"### {chunk['work']} — {location}",
            f"> {excerpt}",
            f"Evidence ID: `{chunk['evidence_id']}`",
        ])
    ids = [chunk["evidence_id"] for chunk in chunks[:3]]
    claims = [{
        "claim_id": "sources_recovered",
        "text": "Se recuperaron fuentes canónicas relevantes; no se generó una interpretación automática.",
        "strength": "weak",
        "confidence": "low",
        "relation_type": "none",
        "evidence_ids": ids,
        "primary_evidence_id": ids[0],
    }] if ids else []
    return "\n".join(lines), claims


def _frontend_hit(chunk: dict[str, Any], primary_ids: set[str]) -> dict[str, Any]:
    evidence_id = chunk["evidence_id"]
    markdown = str(chunk.get("markdown") or "")
    language = chunk.get("language") if chunk.get("language") in {"es", "en", "he"} else "es"
    literal = float(chunk.get("literal_score") or 0.0) > 0
    return {
        "hit_id": evidence_id,
        "evidence_id": evidence_id,
        "chunk_id": str(chunk["chunk_id"]),
        "document_id": str(chunk["document_id"]),
        "work_code": _work_code(chunk),
        "work_title": str(chunk.get("work") or ""),
        "pdf_page": chunk.get("pdf_page"),
        "physical_pdf_page": chunk.get("pdf_page"),
        "printed_page": (
            int(chunk["printed_page"])
            if str(chunk.get("printed_page") or "").isdigit()
            else None
        ),
        "section": chunk.get("section"),
        "quote": markdown,
        "snippet": " ".join(markdown.split())[:900],
        "display_snippet": " ".join(markdown.split())[:900],
        "match_text": "",
        "sentence_text": "",
        "paragraph_text": markdown,
        "context_before": "",
        "context_after": "",
        "language": language,
        "direction": "rtl" if language == "he" else "ltr",
        "evidence_type": "canonical_markdown",
        "literal_strength": "strong" if literal else "weak",
        "evidence_strength": "strong" if evidence_id in primary_ids else "medium",
        "relation_relevance": "direct_relation" if literal else "thematic_parallel",
        "relation_type": "direct_literal" if literal else "thematic_parallel",
        "relation_strength": "high" if literal else "medium",
        "literal_relation": literal,
        "inference_required": not literal,
        "matched_terms": [],
        "matched_concepts": [],
        "is_primary": evidence_id in primary_ids,
        "source_layer": _source_layer(chunk),
        "source_layer_confidence": "medium",
        "source_layer_rationale": "canonical_chunk_metadata",
        "is_original_language": True,
        "is_primary_language_match": language == chunk.get("query_language"),
        "is_translation": False,
        "is_editorial_commentary": _source_layer(chunk) == "editorial_commentary",
        "parallel_texts": [],
        "language_match": "exact" if language == chunk.get("query_language") else "secondary",
        "literal_match_kind": "exact_phrase" if chunk.get("exact_match") else "semantic",
        "retrieval_tier": 0 if literal else 1,
        "retrieval_sources": chunk.get("retrieval_sources", []),
        "semantic_score": chunk.get("semantic_score"),
        "literal_score": chunk.get("literal_score"),
        "combined_score": chunk.get("combined_score"),
        "warnings": [],
        "physical_file_name": chunk.get("physical_file_name"),
        "source_sha256": chunk.get("source_sha256"),
        "author_quote_status": "not_confirmed",
        "attribution_label": "Markdown canónico recuperado desde PostgreSQL",
        "raw_snippet": markdown,
        "snippet_sanitized": False,
        "sanitization_reason_codes": [],
    }


async def run_simple_rag(
    conn: Any,
    data: Any,
    *,
    simulations: dict[str, bool] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    simulations = simulations or {}
    original_query = data.question
    filters = build_explicit_filters(data)
    query_language = detect_language(original_query)
    variants = build_query_variants(original_query)
    warnings: list[str] = []
    latency: dict[str, float] = {}

    documents = await resolve_ready_documents(
        conn,
        knowledge_scope_code=filters["scope"],
        work_codes=filters["works"] or None,
    )
    document_ids = [str(item["document_id"]) for item in documents]
    semantic_task = asyncio.create_task(asyncio.to_thread(
        _semantic_search,
        original_query,
        scope_code=filters["scope"],
        languages=filters["languages"],
        document_ids=document_ids if filters["works"] else [],
        simulate_failure=bool(simulations.get("milvus")),
    ))

    literal_started = time.perf_counter()
    literal_status = "ok"
    try:
        if simulations.get("literal"):
            raise RuntimeError("simulated_literal_failure")
        literal = await search_literal_candidates(
            conn,
            knowledge_scope_code=filters["scope"],
            variants=variants,
            languages=filters["languages"],
            document_ids=document_ids if filters["works"] else None,
            top_k=LITERAL_TOP_K,
        )
    except Exception:
        literal = []
        literal_status = "failed"
        warnings.append("La búsqueda literal no estuvo disponible; se utilizó recuperación semántica.")
    latency["literal_ms"] = round((time.perf_counter() - literal_started) * 1000, 2)

    semantic_status = "ok"
    embedding_metadata: dict[str, Any] = {}
    try:
        semantic, embedding_metadata = await semantic_task
    except Exception:
        semantic = []
        semantic_status = "failed"
        warnings.append("La búsqueda semántica no estuvo disponible; se utilizó búsqueda literal.")
    latency["embedding_and_milvus_ms"] = float(embedding_metadata.get("latency_ms") or 0.0)

    ranked = merge_results(semantic, literal, query_language=query_language)
    fetch_started = time.perf_counter()
    canonical = await fetch_canonical_chunks(
        conn,
        knowledge_scope_code=filters["scope"],
        chunk_ids=[item["chunk_id"] for item in ranked],
    )
    latency["fetch_chunks_ms"] = round((time.perf_counter() - fetch_started) * 1000, 2)
    canonical_by_id = {str(item["chunk_id"]): item for item in canonical}
    selected = select_context(
        ranked,
        canonical_by_id,
        explicit_work_filter=bool(filters["works"]),
    )
    for chunk in selected:
        chunk["evidence_id"] = _evidence_id(str(chunk["chunk_id"]))

    retrieval_failed = semantic_status == "failed" and literal_status == "failed"
    if not selected:
        if retrieval_failed:
            research_status = "degraded"
            answer = (
                "No fue posible completar la búsqueda por un problema técnico. "
                "No se concluye que el corpus carezca de evidencia."
            )
        else:
            research_status = "no_evidence"
            answer = "No se encontró evidencia suficiente en el corpus consultado."
        claims: list[dict[str, Any]] = []
        ai_status = "not_run"
        ai_used = False
    else:
        ai_started = time.perf_counter()
        try:
            answer, claims, ai_used = await render_grounded_answer(
                original_query,
                filters,
                selected,
                simulate_failure=bool(simulations.get("ai_render")),
            )
            ai_status = "ok"
        except Exception as exc:
            logger.warning(
                "simple_rag grounded render rejected: %s",
                type(exc).__name__,
                exc_info=True,
            )
            answer, claims = _fallback_answer(selected)
            ai_status = "failed"
            ai_used = False
            warnings.append(
                "La redacción automática no estuvo disponible. Se muestran las fuentes recuperadas."
            )
            warnings.append(f"ai_render_failed:{type(exc).__name__}")
        latency["ai_ms"] = round((time.perf_counter() - ai_started) * 1000, 2)
        research_status = (
            "complete"
            if semantic_status == literal_status == ai_status == "ok"
            else "degraded"
        )
        if research_status == "complete" and len(selected) < CONTEXT_MIN:
            research_status = "partial"

    primary_ids = list(dict.fromkeys(
        claim["primary_evidence_id"]
        for claim in claims
        if claim.get("primary_evidence_id")
    ))
    if not primary_ids and selected:
        primary_ids = [selected[0]["evidence_id"]]
    hits = [_frontend_hit(chunk, set(primary_ids)) for chunk in selected]
    evidence = [{
        "evidence_id": chunk["evidence_id"],
        "chunk_id": str(chunk["chunk_id"]),
        "document_id": str(chunk["document_id"]),
        "work": chunk["work"],
        "title": chunk["work"],
        "pdf_page": chunk.get("pdf_page"),
        "printed_page": chunk.get("printed_page"),
        "section": chunk.get("section"),
        "language": chunk.get("language"),
        "markdown": chunk.get("markdown"),
        "source_layer": _source_layer(chunk),
        "attribution_status": "not_confirmed",
        "semantic_score": chunk.get("semantic_score"),
        "literal_score": chunk.get("literal_score"),
        "combined_score": chunk.get("combined_score"),
        "retrieval_sources": chunk.get("retrieval_sources"),
    } for chunk in selected]
    compatibility_status = {
        "complete": "ok",
        "partial": "partial",
        "degraded": "partial",
        "no_evidence": "no_evidence",
    }[research_status]
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    latency["total_ms"] = duration_ms
    request_id = hashlib.sha256(f"{time.time_ns()}:{original_query}".encode()).hexdigest()[:16]
    logger.info(
        "simple_rag request_id=%s original_query_hash=%s query_language=%s "
        "filters=%s milvus_status=%s literal_status=%s milvus_hits=%s "
        "literal_hits=%s selected_chunks=%s ai_status=%s fallback=%s latency_ms=%s",
        request_id,
        hashlib.sha256(original_query.encode()).hexdigest(),
        query_language,
        filters,
        semantic_status,
        literal_status,
        len(semantic),
        len(literal),
        len(selected),
        ai_status,
        research_status == "degraded",
        latency,
    )
    matrix = [
        {
            "work_code": work,
            "hits": sum(hit["work_code"] == work for hit in hits),
            "primary_hits": sum(
                hit["work_code"] == work and hit["is_primary"] for hit in hits
            ),
            "contextual_hits": sum(
                hit["work_code"] == work and not hit["is_primary"] for hit in hits
            ),
            "additional_literal_hits": 0,
        }
        for work in dict.fromkeys(hit["work_code"] for hit in hits)
    ]
    return {
        "pipeline": "simple_rag",
        "status": compatibility_status,
        "research_status": research_status,
        "original_query": original_query,
        "question": original_query,
        "answer_text": answer,
        "answer_markdown": answer,
        "summary": (
            f"{len(primary_ids)} fuentes principales y {max(0, len(hits) - len(primary_ids))} contextuales."
            if hits else ""
        ),
        "claims": claims,
        "evidence": evidence,
        "hits": hits,
        "primary_evidence_ids": primary_ids,
        "evidence_counts": {
            "primary": len(primary_ids),
            "contextual": max(0, len(hits) - len(primary_ids)),
            "additional_literal": 0,
        },
        "retrieval": {
            "semantic_used": bool(semantic),
            "literal_used": bool(literal),
            "semantic_status": semantic_status,
            "literal_status": literal_status,
            "semantic_hits": len(semantic),
            "literal_hits": len(literal),
            "selected_chunks": len(selected),
            "query_variants": variants,
        },
        "processing": {
            "ai_interpretation_used": False,
            "ai_render_used": ai_used,
            "fallback_used": research_status == "degraded",
        },
        "execution": {
            "pipeline_version": "simple_grounded_rag_v1",
            "model": RESEARCH_CONVERSATION_MODEL,
            "embedding_model": EMBEDDINGS_MODEL_ALIAS,
            "embedding_dimension": embedding_metadata.get("dimension"),
            "used_ai_interpretation": False,
            "used_ai_rendering": ai_used,
            "used_deterministic_fallback": not ai_used and bool(selected),
            "used_vector": bool(semantic),
            "retrieval_modes": ["milvus", "literal", "fts", "trigram"],
            "duration_ms": duration_ms,
            "latency_ms": latency,
            "request_id": request_id,
        },
        "conversation": {
            "conversation_id": data.conversation.get("conversation_id"),
            "turn_id": data.conversation.get("turn_id"),
            "resolved_context": [],
        },
        "works_consulted": list(dict.fromkeys(hit["work_code"] for hit in hits)),
        "evidence_matrix": matrix,
        "cross_corpus_matrix": [],
        "relations": [],
        "not_found": [] if selected else [original_query],
        "warnings": list(dict.fromkeys(warnings)),
        "query_understanding": {
            "original_query": original_query,
            "intent": "unknown",
            "operation": "simple_grounded_retrieval",
            "subject_type": "query",
            "subject_raw": original_query,
            "subject_canonical": original_query,
            "ai_used": False,
            "ai_accepted": False,
            "fallback_used": False,
            "requires_clarification": False,
        },
    }
