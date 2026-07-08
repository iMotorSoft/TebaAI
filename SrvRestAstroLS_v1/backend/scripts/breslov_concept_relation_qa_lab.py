#!/usr/bin/env python3
"""
Breslov Concept Relation QA Lab — Sangre / Habla (Blood / Speech).

Investigative tool for cross-concept research queries in the Breslov corpus.
Answers questions like "¿Dónde está la conexión entre sangre y habla?"
with traceable evidence: literal → cooccurrence → thematic → AI inference.

Usage:
  # No-AI mode (PG + Milvus only)
  uv run python -m scripts.breslov_concept_relation_qa_lab \\
    --concept-a "sangre" --concept-b "habla" \\
    --question "¿Dónde está la conexión entre sangre y habla?" \\
    --top-k 20 --no-ai

  # With AI interpretation via LiteLLM
  uv run python -m scripts.breslov_concept_relation_qa_lab \\
    --concept-a "sangre" --concept-b "habla" \\
    --question "¿Dónde está la conexión entre sangre y habla?" \\
    --top-k 20 --use-ai

  # English
  uv run python -m scripts.breslov_concept_relation_qa_lab \\
    --concept-a "blood" --concept-b "speech" \\
    --question "Where is the connection between blood and speech?" \\
    --top-k 20 --use-ai

  # Hebrew
  uv run python -m scripts.breslov_concept_relation_qa_lab \\
    --concept-a "דם" --concept-b "דיבור" \\
    --question "מה הקשר בין דם ודיבור?" \\
    --top-k 20 --no-ai

Requirements:
  LITELLM_MASTER_KEY in environment (for embeddings + optional AI interpretation).
  PostgreSQL, Milvus, LiteLLM running.
  No OpenAI key directa.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

SCOPE_CODE = "breslov_primary"
MILVUS_PROD_COLL = "tebaai_breslov_chunks_v1"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
PROD_MILVUS_COLLECTION = "tebaai_breslov_chunks_v1"

# ── Concept expansion tables ──────────────────────────────────────────────

CONCEPT_EXPANSIONS: dict[str, list[str]] = {
    "sangre": [
        "sangre", "blood", "דם", "dam", "sangre",
    ],
    "blood": [
        "blood", "sangre", "דם", "dam",
    ],
    "דם": [
        "דם", "dam", "blood", "sangre",
    ],
    "habla": [
        "habla", "hablar", "palabra", "palabras",
        "speech", "speaking", "word", "words",
        "dibur", "dibbur", "דיבור", "דבור",
        "דבר", "פה", "boca", "mouth",
    ],
    "speech": [
        "speech", "speaking", "word", "words",
        "habla", "hablar", "palabra",
        "dibur", "dibbur", "דיבור",
        "פה", "mouth", "boca",
    ],
    "דיבור": [
        "דיבור", "דבור", "דבר", "פה",
        "dibur", "dibbur", "speech", "word",
        "habla", "palabra", "mouth", "boca",
    ],
}

NORMALIZED_NO_ACCENT: dict[str, str] = {
    "sangre": "sangre",
    "habla": "habla",
    "palabra": "palabra",
}


# ── Evidence types ─────────────────────────────────────────────────────────

LITERAL = "literal_relation"
CONCEPT_A = "literal_concept_a"
CONCEPT_B = "literal_concept_b"
COOCCUR_SAME_CHUNK = "cooccurrence_same_chunk"
COOCCUR_SAME_PAGE = "cooccurrence_same_page"
COOCCUR_SAME_SECTION = "cooccurrence_same_section"
THEMATIC = "thematic_relation"
AI_INFERENCE = "ai_inference_candidate"
NOT_FOUND = "not_found"


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class EvidenceItem:
    evidence_id: str = ""
    document_id: str = ""
    document_title: str = ""
    page_number: int | None = None
    chapter: str | None = None
    section: str | None = None
    subtitle: str | None = None
    node_path: str | None = None
    block_type: str | None = None
    language: str | None = None
    chunk_id: str = ""
    text: str = ""
    source_refs: list[str] = field(default_factory=list)
    internal_cross_refs: list[str] = field(default_factory=list)
    citable: bool = True
    evidence_type: str = NOT_FOUND
    signal: str = ""  # fts, vector, both
    distance: float | None = None
    score: float | None = None


@dataclass
class SourceMapEntry:
    document_id: str
    document_title: str
    page_number: int | None
    chapter: str | None
    section: str | None
    block_type: str | None
    evidence_type: str
    text_excerpt: str
    citable: bool


# ── Module imports (lazy, after preflight) ─────────────────────────────────

async def _get_pool():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool
    pool = create_pool_from_settings()
    await open_pool(pool)
    return pool


async def _close_pool(pool):
    from infrastructure.postgres.pool import close_pool
    await close_pool(pool)


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 0 — PREFLIGHT
# ══════════════════════════════════════════════════════════════════════════

async def preflight() -> dict[str, Any]:
    results: dict[str, Any] = {
        "status": "PASS",
        "checks": {},
        "scope_id": None,
        "blocker": None,
    }

    # 1. PostgreSQL
    try:
        pool = await _get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT current_database() AS db")
                row = await cur.fetchone()
                results["checks"]["pg_connect"] = f"OK ({row['db']})"

                await cur.execute(
                    "SELECT id::text, knowledge_scope_code, status "
                    "FROM knowledge_scopes "
                    "WHERE knowledge_scope_code = %s",
                    (SCOPE_CODE,),
                )
                scope = await cur.fetchone()
                if scope:
                    results["scope_id"] = scope["id"]
                    results["checks"]["scope_resolve"] = (
                        f"OK ({scope['knowledge_scope_code']}, {scope['status']})"
                    )
                else:
                    results["checks"]["scope_resolve"] = "FAIL (not found)"
                    results["status"] = "BLOCKED"

                await cur.execute(
                    "SELECT count(*) AS cnt FROM library_documents WHERE status = 'ready'"
                )
                results["checks"]["ready_docs"] = str((await cur.fetchone())["cnt"])

                await cur.execute(
                    "SELECT count(*) AS cnt FROM library_document_chunks ch "
                    "JOIN library_documents d ON d.id = ch.document_id "
                    "WHERE d.status = 'ready'"
                )
                results["checks"]["ready_chunks"] = str((await cur.fetchone())["cnt"])

                await cur.execute(
                    "SELECT id::text, status FROM library_documents "
                    "WHERE id::text LIKE '47768aac%'"
                )
                likutey = await cur.fetchone()
                if likutey:
                    results["checks"]["likutey_layout_doc"] = (
                        f"OK ({likutey['id'][:8]}, {likutey['status']})"
                    )
                else:
                    results["checks"]["likutey_layout_doc"] = "FAIL (not found)"
        await _close_pool(pool)
    except Exception as exc:
        results["checks"]["pg_connect"] = f"FAIL ({exc})"
        results["status"] = "BLOCKED"
        results["blocker"] = f"PostgreSQL: {exc}"
        return results

    # 2. Milvus
    try:
        from pymilvus import utility, Collection
        from infrastructure.milvus.client import create_connection, close_connection
        create_connection()
        cols = utility.list_collections()
        test_ok = MILVUS_TEST_COLL in cols
        prod_ok = MILVUS_PROD_COLL in cols
        results["checks"]["milvus_test"] = (
            f"{'OK' if test_ok else 'NOT FOUND'} ({MILVUS_TEST_COLL})"
        )
        results["checks"]["milvus_prod"] = (
            f"{'OK' if prod_ok else 'NOT FOUND'} ({MILVUS_PROD_COLL})"
        )
        if test_ok:
            c = Collection(MILVUS_TEST_COLL)
            c.load()
            results["checks"]["milvus_test_entities"] = str(c.num_entities)
            c.release()
        if prod_ok:
            c = Collection(MILVUS_PROD_COLL)
            c.load()
            results["checks"]["milvus_prod_entities"] = str(c.num_entities)
            c.release()
        close_connection()
    except Exception as exc:
        results["checks"]["milvus_test"] = f"FAIL ({exc})"
        results["status"] = "BLOCKED"
        results["blocker"] = results.get("blocker", "") + f" Milvus: {exc}"

    # 3. LiteLLM
    try:
        import httpx
        from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL
        if not LITELLM_API_KEY:
            results["checks"]["litellm_health"] = "FAIL (no API key)"
            results["checks"]["gpt5_nano"] = "SKIPPED (no key)"
        else:
            headers = {"Authorization": f"Bearer {LITELLM_API_KEY}"}
            r = httpx.get(f"{LITELLM_BASE_URL}/health", headers=headers, timeout=10)
            results["checks"]["litellm_health"] = (
                f"OK ({r.status_code})" if r.status_code == 200
                else f"WARN ({r.status_code})"
            )
            r2 = httpx.get(
                f"{LITELLM_BASE_URL}/model/info", headers=headers, timeout=10
            )
            nano_available = False
            if r2.status_code == 200:
                data = r2.json()
                models = []
                if isinstance(data, list):
                    models = [m.get("model_name", "") for m in data]
                elif isinstance(data, dict):
                    ml = data.get("data") or data.get("models") or []
                    if isinstance(ml, list):
                        models = [m.get("model_name", "") for m in ml]
                nano_available = any(
                    "openai_gpt-5.4-nano" in str(m) for m in models
                )
            results["checks"]["gpt5_nano"] = (
                "available" if nano_available else "NOT FOUND"
            )
    except Exception as exc:
        results["checks"]["litellm_health"] = f"FAIL ({exc})"

    # Block if critical fails
    fails = [
        k for k, v in results["checks"].items()
        if v.startswith("FAIL") and k
        in ("pg_connect", "scope_resolve", "milvus_test", "milvus_prod")
    ]
    if fails:
        results["status"] = "BLOCKED"
        results["blocker"] = f"Critical failures: {', '.join(fails)}"

    return results


def print_preflight(results: dict[str, Any]) -> None:
    print(f"\n{'='*60}")
    print("  PRECHECK — Breslov Concept Relation QA Lab")
    print(f"{'='*60}")
    print(f"\n  Status: {results['status']}")
    if results.get("blocker"):
        print(f"  Blocker: {results['blocker']}")
    print(f"\n  {'Check':<30} {'Result':<30}")
    print(f"  {'-'*30} {'-'*30}")
    for check, val in results["checks"].items():
        icon = "✅" if val.startswith("OK") else "⚠️" if val.startswith("WARN") else "❌"
        print(f"  {icon} {check:<28} {val:<30}")
    print(f"{'='*60}\n")


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — CONCEPT EXPANSION
# ══════════════════════════════════════════════════════════════════════════

def expand_concepts(concept_a: str, concept_b: str) -> dict[str, Any]:
    a_variants = CONCEPT_EXPANSIONS.get(concept_a.lower(), [concept_a])
    b_variants = CONCEPT_EXPANSIONS.get(concept_b.lower(), [concept_b])

    if not a_variants or a_variants == [concept_a]:
        a_variants = [concept_a]
        for key, vals in CONCEPT_EXPANSIONS.items():
            if concept_a.lower() in vals:
                a_variants = list(dict.fromkeys(vals + [concept_a]))
                break

    if not b_variants or b_variants == [concept_b]:
        b_variants = [concept_b]
        for key, vals in CONCEPT_EXPANSIONS.items():
            if concept_b.lower() in vals:
                b_variants = list(dict.fromkeys(vals + [concept_b]))
                break

    return {
        "concept_a": concept_a,
        "concept_b": concept_b,
        "a_variants": a_variants,
        "b_variants": b_variants,
    }


def print_expansion(expansion: dict[str, Any]) -> None:
    print(f"\n{'─'*60}")
    print("  CONCEPT EXPANSION")
    print(f"{'─'*60}")
    print(f"\n  Concept A: {expansion['concept_a']}")
    for v in expansion["a_variants"]:
        print(f"    • {v}")
    print(f"\n  Concept B: {expansion['concept_b']}")
    for v in expansion["b_variants"]:
        print(f"    • {v}")
    print()


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 3 — FTS LITERAL SEARCH
# ══════════════════════════════════════════════════════════════════════════

def _detect_lang(variant: str) -> tuple[str, str]:
    """Return (pg_fts_config, pg_vector_column) for a variant."""
    import re
    hebrew = bool(re.search(r'[\u0590-\u05FF]', variant))
    if hebrew:
        return ('simple', 'simple')
    has_spanish = any(c in 'áéíóúüñÁÉÍÓÚÜÑ' for c in variant)
    if has_spanish:
        return ('spanish', 'es')
    return ('english', 'simple')


async def search_literal_fts(
    pool, concept_variants: list[str], top_k: int, concept_label: str
) -> list[EvidenceItem]:
    results: list[EvidenceItem] = []
    seen_chunks: set[str] = set()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SAVEPOINT fts_search")
            for variant in concept_variants[:5]:
                if len(variant) < 2:
                    continue
                fts_config, fts_column = _detect_lang(variant)
                try:
                    await cur.execute(
                        f"""
                        SELECT ch.id AS chunk_id, ch.content,
                               ch.page_start, ch.page_end,
                               ch.chapter, ch.section,
                               ch.node_path, ch.block_type, ch.language,
                               ch.citable,
                               d.id AS document_id, d.title AS document_title,
                               d.status,
                               ts_rank(ch.search_vector_{fts_column}, websearch_to_tsquery('{fts_config}', %s)) AS rank
                        FROM library_document_chunks ch
                        JOIN library_documents d ON d.id = ch.document_id
                        WHERE d.knowledge_scope_id = (
                            SELECT id FROM knowledge_scopes
                            WHERE knowledge_scope_code = %s
                            LIMIT 1
                        )
                        AND d.status IN ('ready', 'test_candidate')
                        AND (
                            ch.search_vector_{fts_column} @@ websearch_to_tsquery('{fts_config}', %s)
                            OR ch.content ILIKE %s
                        )
                        ORDER BY rank DESC NULLS LAST, ch.page_start NULLS LAST
                        LIMIT %s
                        """,
                        (variant, SCOPE_CODE, variant, f"%{variant}%", top_k),
                    )
                    rows = await cur.fetchall()
                    for row in rows:
                        cid = str(row["chunk_id"])
                        if cid in seen_chunks:
                            continue
                        seen_chunks.add(cid)
                        results.append(EvidenceItem(
                            evidence_id=f"fts_{concept_label}_{cid[:12]}",
                            document_id=str(row["document_id"]),
                            document_title=row["document_title"],
                            page_number=row["page_start"],
                            chapter=row["chapter"],
                            section=row["section"],
                            node_path=row["node_path"],
                            block_type=row["block_type"],
                            language=row["language"],
                            chunk_id=cid,
                            text=row["content"],
                            citable=row.get("citable", True),
                            evidence_type=CONCEPT_A if concept_label == "a" else CONCEPT_B,
                            signal="fts",
                            score=1.0,
                        ))
                except Exception as exc:
                    print(f"  [WARN] FTS search for '{variant}' failed: {exc}", file=sys.stderr)
                    try:
                        await cur.execute("ROLLBACK TO SAVEPOINT fts_search")
                    except Exception:
                        pass
    return results


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 4 — COOCCURRENCE SEARCH
# ══════════════════════════════════════════════════════════════════════════

async def search_exact_cooccurrence(
    pool,
    concept_a_variants: list[str],
    concept_b_variants: list[str],
) -> list[EvidenceItem]:
    results: list[EvidenceItem] = []
    seen_chunks: set[str] = set()

    a_patterns = [f"%{v}%" for v in concept_a_variants[:3] if len(v) >= 2]
    b_patterns = [f"%{v}%" for v in concept_b_variants[:3] if len(v) >= 2]

    if not a_patterns or not b_patterns:
        return results

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SAVEPOINT cooc_search")
            for ap in a_patterns:
                for bp in b_patterns:
                    try:
                        await cur.execute(
                            """
                            SELECT ch.id AS chunk_id, ch.content,
                                   ch.page_start, ch.page_end,
                                   ch.chapter, ch.section,
                                   ch.node_path, ch.block_type, ch.language,
                                   ch.citable,
                                   d.id AS document_id, d.title AS document_title,
                                   d.status
                            FROM library_document_chunks ch
                            JOIN library_documents d ON d.id = ch.document_id
                            WHERE d.knowledge_scope_id = (
                                SELECT id FROM knowledge_scopes
                                WHERE knowledge_scope_code = %s
                                LIMIT 1
                            )
                            AND d.status IN ('ready', 'test_candidate')
                            AND ch.content ILIKE %s
                            AND ch.content ILIKE %s
                            LIMIT 50
                            """,
                            (SCOPE_CODE, ap, bp),
                        )
                        rows = await cur.fetchall()
                        for row in rows:
                            cid = str(row["chunk_id"])
                            if cid in seen_chunks:
                                continue
                            seen_chunks.add(cid)
                            results.append(EvidenceItem(
                                evidence_id=f"cooc_chunk_{cid[:12]}",
                                document_id=str(row["document_id"]),
                                document_title=row["document_title"],
                                page_number=row["page_start"],
                                chapter=row["chapter"],
                                section=row["section"],
                                node_path=row["node_path"],
                                block_type=row["block_type"],
                                language=row["language"],
                                chunk_id=cid,
                                text=row["content"],
                                citable=row.get("citable", True),
                                evidence_type=COOCCUR_SAME_CHUNK,
                                signal="fts_cooccurrence",
                                score=1.0,
                            ))
                    except Exception as exc:
                        print(f"  [WARN] Cooccurrence search failed: {exc}", file=sys.stderr)
                        try:
                            await cur.execute("ROLLBACK TO SAVEPOINT cooc_search")
                        except Exception:
                            pass

    return results


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 5 — VECTOR SEARCH (MILVUS)
# ══════════════════════════════════════════════════════════════════════════

def generate_vector_queries(
    concept_a: str, concept_b: str, expansion: dict[str, Any]
) -> list[str]:
    a_primary = expansion["a_variants"][0] if expansion["a_variants"] else concept_a
    b_primary = expansion["b_variants"][0] if expansion["b_variants"] else concept_b
    queries = [
        f"conexión entre {a_primary} y {b_primary}",
        f"{a_primary} y {b_primary}",
        f"connection between {a_primary} and {b_primary}",
        f"{a_primary} {b_primary} related",
    ]
    if concept_a.lower() in ("דם", "sangre", "blood") or concept_b.lower() in ("דם", "sangre", "blood"):
        queries.extend([
            "sangre y palabra",
            "sangre y boca",
            "blood and speech",
            "blood and speaking",
        ])
    if concept_a.lower() in ("דם",) or concept_b.lower() in ("דיבור", "דבור", "דבר"):
        queries.extend([
            "דם דיבור",
            "דם פה",
        ])
    return list(dict.fromkeys(queries))


def search_vector_relation(
    queries: list[str],
    top_k: int,
    scope_code: str = SCOPE_CODE,
    milvus_collection: str = "",
) -> list[EvidenceItem]:
    from modules.embeddings.client import embed_text
    from infrastructure.milvus.client import create_connection, search_vectors, close_connection

    results: list[EvidenceItem] = []
    seen_chunks: set[str] = set()

    coll = milvus_collection or MILVUS_PROD_COLL

    try:
        create_connection()
    except Exception as exc:
        print(f"  [ERROR] Milvus connection failed: {exc}", file=sys.stderr)
        return results

    try:
        for query in queries:
            vec = embed_text(query)
            if not vec:
                continue

            hits = search_vectors(
                collection_name=coll,
                query_embedding=vec,
                top_k=top_k,
                expr='collection_code == "breslov"' if scope_code else None,
                output_fields=[
                    "chunk_id", "document_id", "title", "content_preview",
                    "chunk_index", "content_sha256", "page_start", "page_end",
                    "language",
                ],
            )

            for hit in hits:
                cid = hit.get("chunk_id", "")
                if not cid or cid in seen_chunks:
                    continue
                seen_chunks.add(cid)
                results.append(EvidenceItem(
                    evidence_id=f"vector_{cid[:12]}",
                    document_id=hit.get("document_id", ""),
                    document_title=hit.get("title", ""),
                    page_number=hit.get("page_start"),
                    chunk_id=cid,
                    text=hit.get("content_preview", ""),
                    language=hit.get("language"),
                    evidence_type=THEMATIC,
                    signal=f"vector:{query[:30]}",
                    distance=hit.get("distance"),
                ))
    except Exception as exc:
        print(f"  [WARN] Vector search failed: {exc}", file=sys.stderr)

    try:
        close_connection()
    except Exception:
        pass

    return results


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 6 — PG ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════

async def enrich_evidence_from_pg(pool, items: list[EvidenceItem]) -> list[EvidenceItem]:
    enriched: list[EvidenceItem] = []
    seen: set[str] = set()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for item in items:
                if item.chunk_id in seen:
                    continue
                seen.add(item.chunk_id)

                try:
                    await cur.execute(
                        """
                        SELECT ch.content, ch.page_start, ch.page_end,
                               ch.chapter, ch.section,
                               ch.node_path, ch.block_type, ch.language,
                               ch.citable,
                               d.id AS document_id, d.title AS document_title,
                               d.status
                        FROM library_document_chunks ch
                        JOIN library_documents d ON d.id = ch.document_id
                        WHERE ch.id = %s
                        """,
                        (item.chunk_id,),
                    )
                    row = await cur.fetchone()
                except Exception:
                    row = None

                if row:
                    item.text = row["content"]
                    item.document_id = str(row["document_id"])
                    item.document_title = row["document_title"]
                    item.page_number = item.page_number or row["page_start"]
                    item.chapter = item.chapter or row["chapter"]
                    item.section = item.section or row["section"]
                    item.node_path = item.node_path or row["node_path"]
                    item.block_type = item.block_type or row["block_type"]
                    item.language = item.language or row["language"]
                    item.citable = row.get("citable", True) if item.citable else False
                else:
                    print(f"  [WARN] No PG record for chunk {item.chunk_id[:12]}", file=sys.stderr)

                enriched.append(item)

    return enriched


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 7 — MERGE + CLASSIFY
# ══════════════════════════════════════════════════════════════════════════

def classify_evidence(
    items: list[EvidenceItem],
    concept_a_variants: list[str],
    concept_b_variants: list[str],
) -> list[EvidenceItem]:
    classified: list[EvidenceItem] = []

    for item in items:
        text_lower = item.text.lower()

        has_a = any(v.lower() in text_lower for v in concept_a_variants if len(v) >= 2)
        has_b = any(v.lower() in text_lower for v in concept_b_variants if len(v) >= 2)

        if has_a and has_b:
            item.evidence_type = COOCCUR_SAME_CHUNK

            av = concept_a_variants[0] if concept_a_variants else ""
            bv = concept_b_variants[0] if concept_b_variants else ""
            escaped_a = re.escape(av) if av else ""
            escaped_b = re.escape(bv) if bv else ""

            explicit_patterns = [
                r"conectad[oa]\s+(con|a)\s+" + escaped_a,
                r"relaci[óo]n\s+(entre|con)\s+" + escaped_a,
                r"vinculad[oa]\s+(con|a)\s+" + escaped_a,
                r"corresponden\s+(entre|con|a)\s+" + escaped_a,
                r"connection\s+(between|of)\s+" + escaped_a,
                r"related\s+to\s+" + escaped_a,
                r"linked\s+(to|with)\s+" + escaped_a,
                r"associated\s+with\s+" + escaped_a,
                r"קשר\s+(בין|של)\s+" + escaped_a,
                r"חיבור\s+(בין|של)\s+" + escaped_a,
            ]
            is_a_to_b = any(re.search(p, text_lower) for p in explicit_patterns)

            # Also check b-to-a direction
            b_to_a_patterns = [
                r"conectad[oa]\s+(con|a)\s+" + escaped_b,
                r"relaci[óo]n\s+(entre|con)\s+" + escaped_b,
                r"vinculad[oa]\s+(con|a)\s+" + escaped_b,
                r"connection\s+(between|of)\s+" + escaped_b,
                r"related\s+to\s+" + escaped_b,
            ]
            is_b_to_a = any(re.search(p, text_lower) for p in b_to_a_patterns) if escaped_b else False

            if is_a_to_b or is_b_to_a:
                item.evidence_type = LITERAL
        elif has_a:
            item.evidence_type = CONCEPT_A
        elif has_b:
            item.evidence_type = CONCEPT_B
        else:
            item.evidence_type = THEMATIC

        classified.append(item)

    return classified


def merge_results(
    fts_a: list[EvidenceItem],
    fts_b: list[EvidenceItem],
    cooc: list[EvidenceItem],
    vector: list[EvidenceItem],
    concept_a_variants: list[str],
    concept_b_variants: list[str],
) -> list[EvidenceItem]:
    seen: dict[str, EvidenceItem] = {}

    for item in fts_a + fts_b + cooc + vector:
        cid = item.chunk_id
        if not cid:
            continue
        if cid in seen:
            existing = seen[cid]
            if item.signal and item.signal not in existing.signal:
                existing.signal = f"{existing.signal}+{item.signal.split(':')[0]}"
            if item.evidence_type != NOT_FOUND and existing.evidence_type == NOT_FOUND:
                existing.evidence_type = item.evidence_type
            if item.evidence_type == LITERAL:
                existing.evidence_type = LITERAL
            if item.text and not existing.text:
                existing.text = item.text
            if item.distance is not None and existing.distance is None:
                existing.distance = item.distance
            continue
        seen[cid] = item

    merged = list(seen.values())
    merged = classify_evidence(merged, concept_a_variants, concept_b_variants)

    return merged


def build_source_map(items: list[EvidenceItem]) -> list[SourceMapEntry]:
    seen: set[str] = set()
    entries: list[SourceMapEntry] = []
    for item in items:
        key = f"{item.document_id}:{item.chunk_id}"
        if key in seen:
            continue
        seen.add(key)
        entries.append(SourceMapEntry(
            document_id=item.document_id,
            document_title=item.document_title,
            page_number=item.page_number,
            chapter=item.chapter,
            section=item.section,
            block_type=item.block_type,
            evidence_type=item.evidence_type,
            text_excerpt=item.text[:300] if item.text else "",
            citable=item.citable,
        ))
    return entries


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 8 — AI INTERPRETATION (LiteLLM)
# ══════════════════════════════════════════════════════════════════════════

def call_interpretation_model(
    question: str,
    concept_a: str,
    concept_b: str,
    source_map: list[SourceMapEntry],
    items: list[EvidenceItem],
) -> dict[str, Any]:
    from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL
    import httpx

    if not LITELLM_API_KEY:
        return {"error": "No LiteLLM API key available", "raw": ""}

    serializable_map = []
    for entry in source_map:
        serializable_map.append({
            "evidence_id": f"src_{entry.document_id[:8]}_{entry.page_number or 'np'}",
            "document_title": entry.document_title,
            "page_number": entry.page_number,
            "chapter": entry.chapter,
            "section": entry.section,
            "block_type": entry.block_type,
            "evidence_type": entry.evidence_type,
            "text": entry.text_excerpt[:500],
            "citable": entry.citable,
        })

    source_payload = json.dumps(
        {
            "question": question,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "source_map": serializable_map,
        },
        ensure_ascii=False,
    )

    system_prompt = (
        "Sos un asistente bibliográfico-investigativo de Breslov.\n\n"
        f"Tu tarea es responder la pregunta de un editor/investigador:\n\"{question}\"\n\n"
        "REGLAS:\n"
        "- Usá únicamente la evidencia recuperada provista.\n"
        "- No inventes fuentes.\n"
        "- No agregues conocimiento externo.\n"
        "- No conviertas inferencias en citas literales.\n\n"
        "Estructurá tu respuesta en estas secciones:\n\n"
        "### 1. Respuesta breve\n"
        "Una oración clara: conexión literal sí/no, o inferida.\n\n"
        "### 2. Apariciones de concepto A ({concept_a})\n"
        "Listar fuentes con página y fragmento.\n\n"
        "### 3. Apariciones de concepto B ({concept_b})\n"
        "Listar fuentes con página y fragmento.\n\n"
        "### 4. Conexión literal\n"
        "Si existe, citar el texto exacto. Si no: \"No encontré una conexión literal directa en el corpus recuperado.\"\n\n"
        "### 5. Coocurrencias\n"
        "Fragmentos donde ambos conceptos aparecen en el mismo pasaje.\n\n"
        "### 6. Interpretación\n"
        "Solo si no hay conexión literal. Indicar: \"Esta conexión es inferida por IA a partir de las fuentes recuperadas.\"\n\n"
        "### 7. Nivel de certeza\n"
        "Alta / Media / Baja, según el tipo de evidencia.\n\n"
        "### 8. Fuentes exactas\n"
        "Lista de {documento, página, tipo de evidencia}.\n\n"
        "FORMATO:\n"
        "- Usar **negritas** para conceptos.\n"
        "- Usar comillas para fragmentos textuales.\n"
        "- Separar claramente qué es cita literal vs interpretación.\n"
    )

    try:
        headers = {
            "Authorization": f"Bearer {LITELLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openai_gpt-5.4-nano",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Evidence:\n\n{source_payload}"},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                json=payload,
                headers=headers,
            )

        if resp.status_code != 200:
            return {
                "error": f"LiteLLM returned {resp.status_code}: {resp.text[:300]}",
                "raw": "",
            }

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        return {
            "error": None,
            "raw": content,
            "model": data.get("model", "openai_gpt-5.4-nano"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }
    except Exception as exc:
        return {"error": str(exc), "raw": ""}


# ══════════════════════════════════════════════════════════════════════════
#  PHASE 9 — REPORT
# ══════════════════════════════════════════════════════════════════════════

def render_report(
    question: str,
    concept_a: str,
    concept_b: str,
    expansion: dict[str, Any],
    all_items: list[EvidenceItem],
    source_map: list[SourceMapEntry],
    ai_response: dict[str, Any] | None,
    use_ai: bool,
    no_pg_count: int,
    preflight_result: dict[str, Any],
) -> None:
    print(f"\n{'='*70}")
    print("  BRESLOV CONCEPT RELATION QA LAB — REPORT")
    print(f"{'='*70}")
    print(f"\n  Question: {question}")
    print(f"  Concept A: {concept_a}")
    print(f"  Concept B: {concept_b}")

    # 1. Brief answer
    print(f"\n{'─'*60}")
    print("  1. RESPUESTA BREVE")
    print(f"{'─'*60}")

    literal_count = sum(1 for i in all_items if i.evidence_type == LITERAL)
    cooc_count = sum(1 for i in all_items if i.evidence_type == COOCCUR_SAME_CHUNK)
    a_count = sum(1 for i in all_items if i.evidence_type == CONCEPT_A)
    b_count = sum(1 for i in all_items if i.evidence_type == CONCEPT_B)
    thematic_count = sum(1 for i in all_items if i.evidence_type == THEMATIC)

    if literal_count > 0:
        print(f"\n  ✅ Sí, encontré una conexión LITERAL entre {concept_a} y {concept_b}.")
        print(f"     {literal_count} fragmento(s) conectan ambos conceptos explícitamente.")
    else:
        print(f"\n  ❌ No encontré una conexión literal directa entre {concept_a} y {concept_b}.")
    if cooc_count > 0:
        print(f"     {cooc_count} fragmento(s) contienen ambos conceptos (coocurrencia).")
    if thematic_count > 0:
        print(f"     {thematic_count} fragmento(s) tienen relación temática.")

    if a_count == 0 and b_count == 0 and cooc_count == 0 and literal_count == 0:
        print("  ⚠️  No se encontraron apariciones de ningún concepto en el corpus recuperado.")

    # 2. Source map
    print(f"\n{'─'*60}")
    print("  2. MAPA DE FUENTES")
    print(f"{'─'*60}")
    if source_map:
        print(f"\n  {'ID':<8} {'Libro':<35} {'Pág':<5} {'Tipo':<25}")
        print(f"  {'-'*8} {'-'*35} {'-'*5} {'-'*25}")
        for i, entry in enumerate(source_map[:15], 1):
            title = entry.document_title[:34] if entry.document_title else "?"
            pg = str(entry.page_number) if entry.page_number else "?"
            etype = entry.evidence_type.replace("_", " ")
            print(f"  {i:<8} {title:<35} {pg:<5} {etype:<25}")
        if len(source_map) > 15:
            print(f"  ... y {len(source_map) - 15} fuente(s) más.")
    else:
        print("  No se encontraron fuentes.")

    # 3. Concept A appearances
    print(f"\n{'─'*60}")
    print(f"  3. APARICIONES DE {concept_a.upper()}")
    print(f"{'─'*60}")
    a_items = [i for i in all_items if i.evidence_type == CONCEPT_A]
    if a_items:
        print(f"\n  {'Libro':<35} {'Pág':<5} {'Fragmento':<60}")
        print(f"  {'-'*35} {'-'*5} {'-'*60}")
        for item in a_items[:10]:
            title = item.document_title[:34] if item.document_title else "?"
            pg = str(item.page_number) if item.page_number else "?"
            snippet = _snippet(item.text, expansion["a_variants"], 80)
            print(f"  {title:<35} {pg:<5} {snippet:<60}")
    else:
        print(f"  Sin apariciones literales de '{concept_a}' en el corpus recuperado.")

    # 4. Concept B appearances
    print(f"\n{'─'*60}")
    print(f"  4. APARICIONES DE {concept_b.upper()}")
    print(f"{'─'*60}")
    b_items = [i for i in all_items if i.evidence_type == CONCEPT_B]
    if b_items:
        print(f"\n  {'Libro':<35} {'Pág':<5} {'Fragmento':<60}")
        print(f"  {'-'*35} {'-'*5} {'-'*60}")
        for item in b_items[:10]:
            title = item.document_title[:34] if item.document_title else "?"
            pg = str(item.page_number) if item.page_number else "?"
            snippet = _snippet(item.text, expansion["b_variants"], 80)
            print(f"  {title:<35} {pg:<5} {snippet:<60}")
    else:
        print(f"  Sin apariciones literales de '{concept_b}' en el corpus recuperado.")

    # 5. Literal connection
    print(f"\n{'─'*60}")
    print("  5. CONEXIÓN LITERAL")
    print(f"{'─'*60}")
    if literal_count > 0:
        print(f"  Sí — {literal_count} fragmento(s) conectan {concept_a} y {concept_b} explícitamente.")
        for item in all_items:
            if item.evidence_type == LITERAL:
                print(f"\n  📖 {item.document_title}")
                if item.page_number:
                    print(f"     Página: {item.page_number}")
                if item.chapter:
                    print(f"     Capítulo: {item.chapter}")
                if item.section:
                    print(f"     Sección: {item.section}")
                print(f"     Fragmento: {item.text[:300]}")
    else:
        print(f"  No. No hay conexión literal directa en el corpus recuperado.")

    # 6. Cooccurrences
    print(f"\n{'─'*60}")
    print("  6. COOCURRENCIAS")
    print(f"{'─'*60}")
    print(f"\n  Nivel              Resultado")
    print(f"  {'-'*20} {'-'*20}")
    print(f"  same_chunk         {'Sí (' + str(cooc_count) + ')' if cooc_count > 0 else 'No'}")
    print(f"  same_page          {'Sí' if _has_same_page(all_items) else 'No'}")
    print(f"  same_section       {'Sí' if _has_same_section(all_items) else 'No'}")
    print(f"  same_document      {'Sí' if _has_same_document(all_items) else 'No'}")
    print(f"  thematic           {'Sí (' + str(thematic_count) + ')' if thematic_count > 0 else 'No'}")

    # 7. AI interpretation
    if use_ai and ai_response:
        print(f"\n{'─'*60}")
        print("  7. INTERPRETACIÓN IA")
        print(f"{'─'*60}")
        if ai_response.get("error"):
            print(f"\n  ⚠️  Error: {ai_response['error']}")
        else:
            print(f"\n  Modelo: {ai_response.get('model', '?')}")
            print(f"  Tokens: {ai_response.get('usage', {})}")
            print(f"\n  Respuesta:")
            for line in ai_response["raw"].split("\n"):
                print(f"    {line}")

        ai_literal = literal_count > 0
        print(f"\n  Tipo: {'LITERAL' if ai_literal else 'INFERIDA_POR_IA'}")
        print(f"  Confianza: {'alta' if ai_literal else 'media' if cooc_count > 0 else 'baja'}")
        if not ai_literal:
            print(f"  Limitación: La conexión entre {concept_a} y {concept_b} no aparece literalmente en el corpus. La interpretación IA es inferida.")

    # 8. Audit
    print(f"\n{'─'*60}")
    print("  8. AUDITORÍA")
    print(f"{'─'*60}")
    print(f"\n  PG OK                   {'✅' if preflight_result['checks'].get('pg_connect', '').startswith('OK') else '❌'}")
    print(f"  Milvus OK               {'✅' if preflight_result['checks'].get('milvus_prod', '').startswith('OK') else '❌'}")
    print(f"  LiteLLM OK              {'✅' if preflight_result['checks'].get('litellm_health', '').startswith('OK') else '⚠️'}")
    print(f"  Sin PG                  {no_pg_count}")
    print(f"  Total resultados        {len(all_items)}")
    print(f"  OpenAI directo          no")

    print(f"\n{'='*70}")
    print("  END OF REPORT")
    print(f"{'='*70}\n")


def _snippet(text: str, variants: list[str], width: int = 80) -> str:
    if not text:
        return ""
    text_lower = text.lower()
    for v in variants:
        if len(v) < 2:
            continue
        idx = text_lower.find(v.lower())
        if idx >= 0:
            start = max(0, idx - 20)
            end = min(len(text), idx + len(v) + 40)
            snip = text[start:end].replace("\n", " ")
            if start > 0:
                snip = "..." + snip
            if end < len(text):
                snip = snip + "..."
            return snip[:width]
    return text[:width].replace("\n", " ")


def _has_same_page(items: list[EvidenceItem]) -> bool:
    pages: dict[str, set[int]] = {}
    for item in items:
        if item.page_number is not None and item.document_id:
            key = item.document_id
            if key not in pages:
                pages[key] = set()
            pages[key].add(item.page_number)
    return any(len(pg_set) > 1 and len(pg_set) < len([i for i in items if i.document_id == doc_id]) for doc_id, pg_set in pages.items())


def _has_same_section(items: list[EvidenceItem]) -> bool:
    sections: dict[str, set[str]] = {}
    for item in items:
        if item.section and item.document_id:
            key = f"{item.document_id}:{item.section}"
            sections[key] = sections.get(key, set())
            sections[key].add(item.chunk_id)
    return any(len(chunks) > 1 for chunks in sections.values())


def _has_same_document(items: list[EvidenceItem]) -> bool:
    return len(set(item.document_id for item in items if item.document_id)) < len(items)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(
        description="Breslov Concept Relation QA Lab"
    )
    parser.add_argument("--concept-a", required=True, help="Primer concepto")
    parser.add_argument("--concept-b", required=True, help="Segundo concepto")
    parser.add_argument("--question", "-q", required=True, help="Pregunta de investigación")
    parser.add_argument("--top-k", type=int, default=20, help="Resultados por búsqueda")
    parser.add_argument("--no-ai", action="store_true", help="Modo sin IA (solo PG + Milvus)")
    parser.add_argument("--use-ai", action="store_true", help="Modo con IA (LiteLLM)")
    parser.add_argument("--skip-preflight", action="store_true", help="Saltar preflight check")
    args = parser.parse_args()

    if args.no_ai and args.use_ai:
        print("ERROR: --no-ai y --use-ai son mutuamente excluyentes.", file=sys.stderr)
        return 1

    if not args.no_ai and not args.use_ai:
        args.no_ai = True  # default

    report = {
        "question": args.question,
        "concept_a": args.concept_a,
        "concept_b": args.concept_b,
        "use_ai": args.use_ai,
        "ai_response": None,
        "evidence_count": 0,
        "literal_count": 0,
        "cooc_count": 0,
        "no_pg_count": 0,
    }

    # ── Phase 0: Preflight ──────────────────────────────────────────
    pf_result: dict[str, Any] | None = None
    if not args.skip_preflight:
        pf_result = await preflight()
        print_preflight(pf_result)
        if pf_result["status"] == "BLOCKED":
            print(f"\n{'❌'*5} BLOQUEADO_PRECHECK")
            print(f"  Causa: {pf_result.get('blocker', 'Unknown')}")
            print("  No se ejecutó retrieval ni interpretación.")
            return 1
        if pf_result["status"] == "WARN":
            print("  ⚠️  Preflight con advertencias. Continuando...\n")
    else:
        pf_result = {"status": "SKIPPED", "checks": {}}

    # ── Phase 2: Concept expansion ──────────────────────────────────
    expansion = expand_concepts(args.concept_a, args.concept_b)
    print_expansion(expansion)

    # ── Phase 3-5: Search ───────────────────────────────────────────
    pool = await _get_pool()
    all_items: list[EvidenceItem] = []

    try:
        # FTS for concept A
        print(f"[1/5] FTS literal para '{args.concept_a}'...")
        fts_a = await search_literal_fts(pool, expansion["a_variants"], args.top_k, "a")
        print(f"  → {len(fts_a)} resultado(s)")

        # FTS for concept B
        print(f"[2/5] FTS literal para '{args.concept_b}'...")
        fts_b = await search_literal_fts(pool, expansion["b_variants"], args.top_k, "b")
        print(f"  → {len(fts_b)} resultado(s)")

        # Cooccurrence
        print(f"[3/5] Coocurrencia exacta...")
        cooc = await search_exact_cooccurrence(pool, expansion["a_variants"], expansion["b_variants"])
        print(f"  → {len(cooc)} resultado(s)")

        # Vector search
        print(f"[4/5] Búsqueda vectorial (Milvus)...")
        vec_queries = generate_vector_queries(args.concept_a, args.concept_b, expansion)
        print(f"  Queries: {vec_queries}")
        vec_results = search_vector_relation(vec_queries, args.top_k)
        print(f"  → {len(vec_results)} hit(s) crudos de Milvus")

        # Enrich vector results from PG
        if vec_results:
            vec_results = await enrich_evidence_from_pg(pool, vec_results)
            no_vec_pg = sum(1 for v in vec_results if not v.text)
            print(f"  → {len(vec_results)} enriquecidos desde PG ({no_vec_pg} sin PG)")
            report["no_pg_count"] += no_vec_pg
        else:
            print(f"  → Sin resultados vectoriales")

        # Merge all
        print(f"[5/5] Merge y clasificación...")
        all_items = merge_results(
            fts_a, fts_b, cooc, vec_results,
            expansion["a_variants"], expansion["b_variants"],
        )
        print(f"  → {len(all_items)} fragmento(s) únicos tras merge")

    finally:
        await _close_pool(pool)

    # Build source map
    source_map = build_source_map(all_items)

    # Stats
    report["evidence_count"] = len(all_items)
    report["literal_count"] = sum(1 for i in all_items if i.evidence_type == LITERAL)
    report["cooc_count"] = sum(1 for i in all_items if i.evidence_type == COOCCUR_SAME_CHUNK)

    # ── Phase 8: AI interpretation ──────────────────────────────────
    ai_response = None
    if args.use_ai:
        print(f"\n{'─'*60}")
        print("  [IA] Llamando a modelo interpretativo LiteLLM...")
        print(f"{'─'*60}")
        if not all_items:
            print("  ⚠️  No hay evidencia recuperada. No se llamará al modelo.")
        else:
            ai_response = call_interpretation_model(
                args.question,
                args.concept_a,
                args.concept_b,
                source_map,
                all_items,
            )
            if ai_response.get("error"):
                print(f"  ⚠️  Error IA: {ai_response['error']}")
            else:
                print(f"  ✅ Modelo: {ai_response.get('model', '?')}")
                print(f"     Tokens: {ai_response.get('usage', {})}")
                report["ai_response"] = ai_response

    # ── Render report ───────────────────────────────────────────────
    render_report(
        args.question,
        args.concept_a,
        args.concept_b,
        expansion,
        all_items,
        source_map,
        ai_response,
        args.use_ai,
        report["no_pg_count"],
        pf_result,
    )

    # ── Final verdict ───────────────────────────────────────────────
    if report["literal_count"] > 0:
        print(f"\n{'✅'*3} CONEXIÓN LITERAL ENCONTRADA")
    elif report["cooc_count"] > 0:
        print(f"\n{'🔗'*3} COOCURRENCIA ENCONTRADA (sin conexión literal)")
    elif any(i.evidence_type == THEMATIC for i in all_items):
        print(f"\n{'🔍'*3} SOLO RELACIÓN TEMÁTICA (ni literal ni coocurrencia)")
    else:
        print(f"\n{'❌'*3} SIN RESULTADOS RELEVANTES")

    if not args.use_ai:
        print("  Modo: --no-ai (solo recuperación, sin interpretación IA)")
    else:
        print(f"  Modo: --use-ai (con interpretación LiteLLM)")

    if report["no_pg_count"] > 0:
        print(f"  ⚠️  {report['no_pg_count']} resultado(s) sin texto PostgreSQL")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
