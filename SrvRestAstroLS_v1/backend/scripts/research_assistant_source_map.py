#!/usr/bin/env python3
"""
Breslov Research Assistant — Source Map Prototype MVP.

For a given query, this script:
  1. Expands the query with controlled term tables
  2. Runs FTS + vector search (Milvus test)
  3. Recovers canonical text from PostgreSQL
  4. Classifies evidence (literal, direct_quote, paraphrase, thematic, remez)
  5. Groups by document → page → chunk
  6. Produces an investigative response with source map

Usage:
  uv run python -m scripts.research_assistant_source_map --query "¿Qué es un Tzadik?"
  uv run python -m scripts.research_assistant_source_map --query "tristeza" --scope breslov_primary
  uv run python -m scripts.research_assistant_source_map --query "miedo" --document-id 0bad063c

Environment:
  LITELLM_MASTER_KEY must be set (global convention).
  No OpenAI key directa. No Milvus productivo.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
from typing import Any

# ── Query expansion tables ──────────────────────────────────────────────

QUERY_EXPANSIONS: dict[str, list[str]] = {
    "tristeza": [
        "tristeza", "triste", "depresión", "melancolía", "desánimo",
        "caída", "abatimiento", "amargura", "desesperación", "falta de alegría",
        "alegría", "simjá", "no estar triste",
    ],
    "miedo": [
        "miedo", "temor", "temores", "angustia", "ansiedad", "pavor",
        "confianza", "fe", "emuna", "no tener miedo", "desesperación",
        "puente angosto", "valentía", "fortaleza",
    ],
    "tzadik": [
        "tzadik", "tzaddik", "justo", "Rebe Najmán", "rabí Najmán",
        "maestro", "guía espiritual", "verdadero tzadik", "tzadik verdadero",
        "rebe", "rabino",
    ],
    "oracion": [
        "oración", "plegaria", "hitbodedut", "oración personal",
        "hablar con Dios", "súplica", "rezo", "tefilá", "meditación",
        "aislamiento", "hitbodedut",
    ],
    "alegria": [
        "alegría", "felicidad", "gozo", "regocijo", "simjá",
        "contento", "dicha", "júbilo",
    ],
    "fe": [
        "fe", "emuna", "creencia", "confianza", "certeza",
        "creer", "confiar",
    ],
    "desesperacion": [
        "desesperación", "desesperar", "desánimo", "desaliento",
        "no desesperar", "esperanza", "tikvá",
    ],
    "puente_angosto": [
        "puente angosto", "puente muy angosto", "angosto",
        "el puente", "angostura",
    ],
}

# Topical map: map generic queries to expansion keys
TOPIC_MAP: dict[str, str] = {
    "tristeza": "tristeza",
    "miedo": "miedo",
    "tzadik": "tzadik",
    "oración": "oracion",
    "oracion": "oracion",
    "alegría": "alegria",
    "alegria": "alegria",
    "fe": "fe",
    "desesperación": "desesperacion",
    "desesperacion": "desesperacion",
    "puente": "puente_angosto",
    "hitbodedut": "oracion",
}


MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
PROD_COLL = "tebaai_breslov_chunks_v1"


# ── Evidence classification ─────────────────────────────────────────────

DIRECT_QUOTE_PATTERNS = re.compile(
    r"(Likutei|Likutey|Likutei Moharán|Likutei Moharan|Likutey Halajot|"
    r"Sijot Haran|Sefer HaMidot|"
    r"Rebe Najmán (dice|dijo|enseña|escribe|afirma|explica)|"
    r"Rabí Natán (dice|dijo|escribe|explica)|"
    r"enseña el Rebe Najmán|"
    r"dice el Rebe|"
    r"como dice|"
    r"como está escrito|"
    r"dijo el Rebe)",
    re.IGNORECASE,
)


def classify_evidence(
    content: str,
    query_terms: list[str],
    vector_score: float | None = None,
    fts_rank: float | None = None,
) -> dict[str, Any]:
    """Classify a chunk's evidence level.

    Returns dict with evidence_type, confidence, notes.
    """
    content_lower = content.lower()

    # 1. Check for direct quote patterns
    if DIRECT_QUOTE_PATTERNS.search(content):
        # Check if query terms also appear
        if _any_term_in(content_lower, query_terms):
            return {
                "evidence_type": "direct_quote",
                "confidence": "high",
                "notes": "Contiene cita directa de fuente Breslov con términos de búsqueda.",
            }
        return {
            "evidence_type": "direct_quote",
            "confidence": "medium",
            "notes": "Contiene cita directa de fuente Breslov. Los términos de búsqueda no aparecen literalmente en el mismo fragmento.",
        }

    # 2. Check for literal term match
    matching_terms = [t for t in query_terms if t.lower() in content_lower]
    if matching_terms:
        return {
            "evidence_type": "literal",
            "confidence": "high",
            "notes": f"Términos literales encontrados: {', '.join(matching_terms[:5])}.",
        }

    # 3. Vector score heuristic for strong thematic
    if vector_score is not None and vector_score > 0.65:
        return {
            "evidence_type": "strong_thematic",
            "confidence": "medium",
            "notes": f"Similitud vectorial alta ({vector_score:.2f}). El tema se aborda sin usar los términos exactos de búsqueda.",
        }

    # 4. FTS rank heuristic
    if fts_rank is not None and fts_rank > 0.5:
        return {
            "evidence_type": "strong_thematic",
            "confidence": "medium",
            "notes": "Coincidencia textual sin términos exactos. Relación temática.",
        }

    # 5. Vector score moderate → remez/derash
    if vector_score is not None and vector_score > 0.45:
        return {
            "evidence_type": "remez_derash_inference",
            "confidence": "low",
            "notes": "Similitud vectorial moderada. Puede haber relación conceptual, pero no es explícita.",
        }

    # 6. Weak match
    if vector_score is not None and vector_score > 0.35:
        return {
            "evidence_type": "remez_derash_inference",
            "confidence": "low",
            "notes": "Similitud vectorial baja. Posible relación remota. No considerar cita.",
        }

    return {
        "evidence_type": "not_enough_evidence",
        "confidence": "none",
        "notes": "No hay evidencia suficiente en este fragmento.",
    }


def _any_term_in(text: str, terms: list[str]) -> bool:
    return any(t.lower() in text for t in terms)


# ── Query expansion ──────────────────────────────────────────────────────

def expand_query(query: str) -> dict[str, Any]:
    """Expand a query using controlled term tables.

    Returns dict with original, expanded_terms, expansion_source.
    """
    query_lower = query.lower().strip()
    expansion_source = None
    expanded_terms = [query]

    # Direct topic match
    for topic_key, terms in QUERY_EXPANSIONS.items():
        if topic_key in query_lower or any(t in query_lower for t in terms[:3]):
            expansion_source = topic_key
            expanded_terms = terms
            break

    # Word-level match
    if not expansion_source:
        for word in query_lower.split():
            word_clean = word.strip("¿?¡!,.;:")
            for topic_key, terms in QUERY_EXPANSIONS.items():
                if word_clean == topic_key or word_clean in terms:
                    expansion_source = topic_key
                    expanded_terms = terms
                    break
            if expansion_source:
                break

    return {
        "original": query,
        "expanded_terms": expanded_terms,
        "expansion_source": expansion_source,
    }


# ── FTS search ────────────────────────────────────────────────────────────

async def search_fts(
    conn,
    knowledge_scope_code: str,
    query: str,
    top_k: int = 30,
    language: str = "es",
) -> list[dict]:
    from modules.library.text_search import search_chunks_text
    return await search_chunks_text(
        conn,
        knowledge_scope_code=knowledge_scope_code,
        query=query,
        top_k=top_k,
        mode="auto",
        language=language,
    )


# ── Vector search (Milvus test) ──────────────────────────────────────────

def search_vector(
    query: str,
    top_k: int = 30,
    knowledge_scope_code: str = "breslov_primary",
    milvus_collection: str = MILVUS_TEST_COLL,
) -> list[dict[str, Any]]:
    """Vector search against Milvus test collection.
    
    Uses real embedding via LiteLLM. Recovers chunk_id, document_id,
    page_start, page_end from Milvus metadata.
    """
    from modules.embeddings.client import embed_text
    from infrastructure.milvus.client import create_connection, ensure_collection, search_vectors

    try:
        create_connection()
        query_vec = embed_text(query)
        if not query_vec:
            return []
        ensure_collection(milvus_collection, dimension=len(query_vec))
        hits = search_vectors(
            collection_name=milvus_collection,
            query_embedding=query_vec,
            top_k=top_k,
            expr=f'collection_code == "{knowledge_scope_code}"',
            output_fields=[
                "chunk_id", "document_id", "title", "content_preview",
                "chunk_index", "content_sha256", "page_start", "page_end",
                "language",
            ],
        )
        return hits
    except Exception as exc:
        print(f"  [WARN] Vector search failed: {exc}", file=sys.stderr)
        return []


# ── PG enrichment ──────────────────────────────────────────────────────

async def enrich_chunk(conn, chunk_id: str) -> dict[str, Any]:
    from infrastructure.postgres.transaction import fetch_one
    row = await fetch_one(
        conn,
        """
        SELECT d.id AS document_id, d.title AS document_title, d.author,
               d.language, d.status, d.knowledge_scope_id,
               ch.chunk_index, ch.content, ch.content_length,
               ch.page_start, ch.page_end, ch.chapter, ch.section,
               ch.reference_label, ch.chunk_uid
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        WHERE ch.id = %(chunk_id)s
        """,
        {"chunk_id": chunk_id},
    )
    if row:
        return dict(row)
    return {}


async def get_chunk_by_id(conn, chunk_id: str) -> dict[str, Any] | None:
    from infrastructure.postgres.transaction import fetch_one
    row = await fetch_one(
        conn,
        """
        SELECT ch.*, d.title AS document_title, d.author,
               d.language AS doc_language, d.status
        FROM library_document_chunks ch
        JOIN library_documents d ON d.id = ch.document_id
        WHERE ch.id = %(chunk_id)s
        """,
        {"chunk_id": chunk_id},
    )
    return dict(row) if row else None


# ── Source grouping ────────────────────────────────────────────────────

def group_by_source(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group results by document → page → chunk."""
    sources: dict[str, Any] = {}
    for r in results:
        doc_id = r.get("document_id", r.get("id", ""))
        if not doc_id:
            continue
        if doc_id not in sources:
            sources[doc_id] = {
                "document_id": doc_id,
                "title": r.get("document_title", r.get("title", "Desconocido")),
                "author": r.get("author"),
                "language": r.get("language", "es"),
                "status": r.get("status", "unknown"),
                "pages": {},
            }
        pg = r.get("page_start", r.get("page", None))
        pg_key = str(pg) if pg is not None else "unknown"
        if pg_key not in sources[doc_id]["pages"]:
            sources[doc_id]["pages"][pg_key] = {
                "page": pg,
                "chunks": [],
            }
        sources[doc_id]["pages"][pg_key]["chunks"].append(r)
    return sources


# ── Build response ────────────────────────────────────────────────────

def build_response(
    query_info: dict[str, Any],
    fts_results: list[dict],
    vec_results: list[dict],
    scope_code: str,
    doc_id_filter: str | None = None,
) -> dict[str, Any]:
    """Build an investigative response with source map."""
    query = query_info["original"]
    expanded_terms = query_info["expanded_terms"]

    # Merge FTS + vector results, deduplicate by chunk_id
    seen: set[str] = set()
    merged: list[dict] = []
    for r in fts_results:
        cid = str(r.get("chunk_id", ""))
        if cid and cid not in seen:
            seen.add(cid)
            r["_source_signal"] = "fts"
            r["_vector_score"] = None
            merged.append(r)
    for r in vec_results:
        cid = r.get("chunk_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            r["_source_signal"] = "vector"
            r["_vector_score"] = r.get("distance", 0.0)
            merged.append(r)
        elif cid:
            # Mark as also found by vector
            for existing in merged:
                if str(existing.get("chunk_id", "")) == cid:
                    existing["_source_signal"] = "fts+vector"
                    existing["_vector_score"] = r.get("distance", 0.0)
                    break

    # Classify evidence for each merged result
    for r in merged:
        content = r.get("content", r.get("content_preview", ""))
        vec_score = r.get("_vector_score", r.get("distance"))
        fts_rank = r.get("rank", r.get("_fts_rank"))
        ev = classify_evidence(
            content,
            expanded_terms,
            vector_score=float(vec_score) if vec_score else None,
            fts_rank=float(fts_rank) if fts_rank else None,
        )
        r["evidence"] = ev

    # Group by source
    sources = group_by_source(merged)

    # Filter by document_id if requested
    if doc_id_filter:
        sources = {k: v for k, v in sources.items() if k == doc_id_filter}

    # Summary stats
    evidence_counts: dict[str, int] = {}
    for r in merged:
        et = r.get("evidence", {}).get("evidence_type", "unknown")
        evidence_counts[et] = evidence_counts.get(et, 0) + 1

    return {
        "query": query,
        "query_expansion": expanded_terms,
        "expansion_source": query_info["expansion_source"],
        "scope": scope_code,
        "total_unique_results": len(merged),
        "evidence_counts": evidence_counts,
        "sources": sources,
        "results": merged[:10],  # Top 10 detail
        "notes": _generate_notes(query, merged, sources, scope_code),
    }


def _generate_notes(
    query: str,
    results: list[dict],
    sources: dict,
    scope_code: str,
) -> list[str]:
    notes = []
    if not results:
        notes.append("No se encontraron resultados en el corpus consultado.")
        return notes

    doc_count = len(sources)
    notes.append(f"Se encontraron {len(results)} fragmentos relevantes en {doc_count} documento(s).")

    # Check for direct quotes
    dq = sum(1 for r in results if r.get("evidence", {}).get("evidence_type") == "direct_quote")
    if dq > 0:
        notes.append(f"{dq} fragmento(s) contienen citas directas de fuentes Breslov.")

    # Check for literal matches
    lit = sum(1 for r in results if r.get("evidence", {}).get("evidence_type") == "literal")
    if lit > 0:
        notes.append(f"{lit} fragmento(s) contienen términos literales de búsqueda.")

    # Thematic
    th = sum(1 for r in results if r.get("evidence", {}).get("evidence_type") == "strong_thematic")
    if th > 0:
        notes.append(f"{th} fragmento(s) abordan el tema sin usar los términos exactos.")

    # Remez
    rz = sum(1 for r in results if r.get("evidence", {}).get("evidence_type") == "remez_derash_inference")
    if rz > 0:
        notes.append(f"{rz} fragmento(s) tienen relación conceptual remota (remez/derash).")

    # Cross-scope
    if doc_count <= 1:
        notes.append(
            f"La búsqueda se limitó al documento principal. "
            "Para búsqueda transversal en todo el corpus, otros documentos pueden no tener embeddings completos."
        )
    else:
        notes.append(f"Resultados distribuidos en {doc_count} documentos del scope '{scope_code}'.")

    return notes


# ── Print functions ───────────────────────────────────────────────────

def print_response(response: dict[str, Any], verbose: bool = False) -> None:
    """Print the investigative response."""
    print(f"\n{'='*70}")
    print(f"  BRESLOV RESEARCH ASSISTANT — SOURCE MAP")
    print(f"{'='*70}")

    # Query section
    print(f"\n🔍 Query: {response['query']}")
    if response["expansion_source"]:
        print(f"   Expansión temática: {response['expansion_source']}")
        print(f"   Términos expandidos: {', '.join(response['query_expansion'][:8])}")
    print(f"   Scope: {response['scope']}")
    print(f"   Fragmentos únicos: {response['total_unique_results']}")

    # Evidence summary
    print(f"\n📊 Clasificación de evidencia:")
    for etype, count in sorted(
        response["evidence_counts"].items(), key=lambda x: -x[1]
    ):
        label = etype.replace("_", " ").title()
        print(f"   {label}: {count}")

    # Per-document results
    print(f"\n📚 Fuentes por documento:")
    for doc_id, src in response["sources"].items():
        print(f"\n   📖 {src['title'][:70]}")
        if src["author"]:
            print(f"      Autor: {src['author']}")
        print(f"      ID: {doc_id[:8]} | Idioma: {src['language']} | Status: {src['status']}")
        pages = src["pages"]
        print(f"      Páginas con resultados: {len(pages)}")
        for pg_key in sorted(pages.keys(), key=lambda k: int(k) if k != "unknown" else 0):
            pg_data = pages[pg_key]
            if pg_key == "unknown":
                print(f"      [página desconocida]: {len(pg_data['chunks'])} fragmento(s)")
            else:
                # Evidence types on this page
                ev_types = set(
                    c.get("evidence", {}).get("evidence_type", "?")
                    for c in pg_data["chunks"]
                )
                ev_str = ", ".join(t.replace("_", " ") for t in ev_types)
                print(f"      Pág. {pg_key}: {len(pg_data['chunks'])} fragmento(s) [{ev_str}]")
            if verbose:
                for ch in pg_data["chunks"][:2]:
                    snippet = ch.get("content", ch.get("content_preview", ""))[:200]
                    ev = ch.get("evidence", {})
                    ev_type = ev.get("evidence_type", "?").replace("_", " ")
                    print(f"        [{ev_type}] {snippet[:150]}...")

    # Top results detail
    print(f"\n📋 Top resultados:")
    for i, r in enumerate(response["results"][:8]):
        ev = r.get("evidence", {})
        ev_type = ev.get("evidence_type", "?").replace("_", " ")
        ev_note = ev.get("notes", "")
        title = r.get("document_title", r.get("title", "?"))
        pg = r.get("page_start", r.get("page", "?"))
        cid = str(r.get("chunk_id", ""))[:8]
        signal = r.get("_source_signal", "?")
        snippet = r.get("content", r.get("content_preview", ""))[:180]
        print(f"\n   {i+1}. [{ev_type}] {title[:50]}")
        print(f"      Pág: {pg} | Chunk: {cid} | Señal: {signal}")
        print(f"      {ev_note[:120]}")
        print(f"      \"{snippet}...\"")

    # Notes
    print(f"\n📝 Notas:")
    for note in response["notes"]:
        print(f"   • {note}")

    print(f"\n{'='*70}")
    print(f"  FIN DEL REPORTE")
    print(f"{'='*70}")


# ── Main ─────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Breslov Research Assistant — Source Map")
    parser.add_argument("--query", "-q", required=True, help="Pregunta de investigación")
    parser.add_argument("--scope", default="breslov_primary", help="Knowledge scope code")
    parser.add_argument("--document-id", "-d", help="Filtrar por document_id")
    parser.add_argument("--top-k", type=int, default=30, help="Resultados por búsqueda")
    parser.add_argument("--verbose", "-v", action="store_true", help="Output detallado")
    parser.add_argument("--json", action="store_true", help="Output como JSON")
    parser.add_argument("--analyze", action="store_true",
                        help="Usar ResearchConversationAnalyzer para análisis de intención")
    parser.add_argument("--research-answer", action="store_true",
                        help="Usar BreslovResearchService completo (answer + source map estructurado)")
    args = parser.parse_args()

    # ── Mode: Full research answer via BreslovResearchService ─────────
    if args.research_answer:
        return await _run_research_answer(args)

    # ── Legacy mode with optional conversation analysis ────────────────
    print(f"\n{'='*70}")
    print(f"  BRESLOV RESEARCH ASSISTANT — SOURCE MAP")
    print(f"  Query: {args.query}")
    print(f"  Scope: {args.scope}")
    print(f"{'='*70}")

    # 0. Optional conversation analysis
    if args.analyze:
        print(f"\n[0/4] Análisis conversacional...")
        from modules.library.conversation_analyzer import ResearchConversationAnalyzer
        ca = ResearchConversationAnalyzer()
        analysis = ca.analyze(args.query)
        print(f"  Idioma: {analysis.language}")
        print(f"  Intención: {analysis.intent.value}")
        print(f"  Modo: {analysis.research_mode.value}")
        print(f"  Términos: {', '.join(analysis.topic_terms)}")
        if analysis.expanded_terms:
            print(f"  Términos expandidos: {', '.join(analysis.expanded_terms[:8])}")
        if analysis.requested_documents:
            print(f"  Documentos solicitados: {', '.join(analysis.requested_documents)}")
        if analysis.analysis_fallback:
            print(f"  ⚠️ Análisis determinístico (fallback)")
        else:
            print(f"  ✅ Análisis vía {analysis.model_used}")

    # 1. Query expansion
    query_info = expand_query(args.query)
    if query_info["expansion_source"]:
        print(f"\n[1/4] Expansión de query: {query_info['expansion_source']}")
        print(f"  Términos: {', '.join(query_info['expanded_terms'][:8])}")
    else:
        print(f"\n[1/4] Sin expansión temática disponible.")
        query_info["expanded_terms"] = [args.query]

    # 2. FTS search
    print(f"\n[2/4] Búsqueda FTS...")
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

    pool = create_pool_from_settings()
    await open_pool(pool)

    fts_results = []
    try:
        async with pool.connection() as conn:
            for term in query_info["expanded_terms"][:5]:
                r = await search_fts(conn, args.scope, term, top_k=args.top_k)
                fts_results.extend(r)
            r_orig = await search_fts(conn, args.scope, args.query, top_k=args.top_k)
            fts_results.extend(r_orig)
        print(f"  FTS: {len(fts_results)} resultados crudos")
    except Exception as exc:
        print(f"  [WARN] FTS search failed: {exc}")

    # 3. Vector search (Milvus productivo)
    print(f"\n[3/4] Búsqueda vectorial (Milvus)...")
    vec_results = []
    for term in query_info["expanded_terms"][:5]:
        hits = search_vector(
            term,
            top_k=args.top_k,
            knowledge_scope_code=args.scope,
        )
        vec_results.extend(hits)
    hits_orig = search_vector(
        args.query,
        top_k=args.top_k,
        knowledge_scope_code=args.scope,
    )
    vec_results.extend(hits_orig)
    print(f"  Vector: {len(vec_results)} hits crudos")

    # 4. Enrich with PG canonical text
    print(f"\n[4/4] Enriqueciendo desde PostgreSQL...")
    enriched_vec = []
    async with pool.connection() as conn:
        for hit in vec_results:
            cid = hit.get("chunk_id", "")
            if not cid:
                continue
            pg_data = await enrich_chunk(conn, cid)
            if pg_data:
                hit["content"] = pg_data["content"]
                hit["document_title"] = pg_data["document_title"]
                hit["author"] = pg_data["author"]
                hit["status"] = pg_data["status"]
                hit["page_start"] = hit.get("page_start") or pg_data.get("page_start")
                hit["page_end"] = hit.get("page_end") or pg_data.get("page_end")
                hit["chapter"] = pg_data.get("chapter")
                hit["section"] = pg_data.get("section")
                enriched_vec.append(hit)

        for r in fts_results:
            cid = r.get("chunk_id", "")
            if cid:
                pg_data = await enrich_chunk(conn, cid)
                if pg_data:
                    r["status"] = pg_data.get("status")

    await close_pool(pool)

    # 5. Build response
    response = build_response(
        query_info,
        fts_results,
        enriched_vec,
        args.scope,
        doc_id_filter=args.document_id,
    )

    # 6. Output
    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False, default=str))
    else:
        print_response(response, verbose=args.verbose)

    # 7. Acceptance check
    total = len(response["results"])
    has_literal = any(
        r.get("evidence", {}).get("evidence_type") == "literal"
        for r in response["results"]
    )
    has_thematic = any(
        r.get("evidence", {}).get("evidence_type") in ("strong_thematic", "direct_quote")
        for r in response["results"]
    )
    if total == 0:
        print(f"\n{'❌'*3} SIN RESULTADOS")
        return 1
    if not has_literal and not has_thematic:
        print(f"\n{'⚠️'*3} Solo evidencia remota (remez/inferencia)")
    else:
        print(f"\n{'✅'*3} Respuesta útil: {total} resultados, "
              f"{'literal' if has_literal else 'temático'}")

    return 0


async def _run_research_answer(args) -> int:
    """Run full research answer via BreslovResearchService."""
    from modules.library.research_service import BreslovResearchService
    service = BreslovResearchService(scope_code=args.scope)
    answer = await service.research(
        query=args.query,
        top_k=args.top_k,
        document_id=args.document_id,
    )

    if args.json:
        print(answer.model_dump_json(indent=2))
        return 0

    print(f"\n{'='*70}")
    print(f"  BRESLOV RESEARCH ANSWER")
    print(f"{'='*70}")
    print(f"\n🔍 Query: {answer.query}")
    print(f"\n📋 Análisis conversacional:")
    ca = answer.conversation_analysis
    print(f"   Idioma: {ca.language}")
    print(f"   Intención: {ca.intent}")
    print(f"   Modo: {ca.research_mode}")
    if ca.topic_terms:
        print(f"   Términos: {', '.join(ca.topic_terms[:8])}")
    if ca.model_used:
        print(f"   Modelo: {ca.model_used}")
    if ca.analysis_fallback:
        print(f"   ⚠️ Fallback determinístico activo")

    print(f"\n📝 Respuesta:")
    print(f"   {answer.answer_summary}")

    print(f"\n📊 Evidencia:")
    for etype, count in sorted(
        answer.evidence_counts.items(), key=lambda x: -x[1]
    ):
        label = etype.replace("_", " ").title()
        print(f"   {label}: {count}")

    print(f"\n📚 Mapa de fuentes:")
    for i, entry in enumerate(answer.source_map[:10], 1):
        ev = entry.evidence
        ev_type = ev.evidence_type.value.replace("_", " ")
        pages = f"pág. {entry.page_start}" if entry.page_start else "s/p"
        print(f"\n   {i}. {entry.document_title[:60]}")
        print(f"      {pages} | {ev_type.upper()} | chunk: {entry.chunk_id[:8]}")
        if entry.canonical_excerpt:
            print(f"      “{entry.canonical_excerpt[:180]}...”")
        if ev.notes:
            print(f"      Nota: {ev.notes[:120]}")

    if len(answer.source_map) > 10:
        print(f"\n   ... y {len(answer.source_map) - 10} fuente(s) más.")

    print(f"\n⚠️ Limitaciones:")
    for lim in answer.limitations:
        print(f"   • {lim}")

    print(f"\n{'='*70}")
    print(f"  FIN DEL REPORTE")
    print(f"{'='*70}")

    total = sum(answer.evidence_counts.values())
    if total == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
