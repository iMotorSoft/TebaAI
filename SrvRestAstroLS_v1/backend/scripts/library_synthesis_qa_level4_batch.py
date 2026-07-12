#!/usr/bin/env python3
"""Level 4 synthesis QA — deep interconnection between concepts.

Pipeline:
  1. decompose_question_to_claims  (from level4_decomposition)
  2. retrieve_evidence_per_claim   (SQL/page + Book QA + VectorSearchBackend auto)
  3. retrieve_evidence_for_relations
  4. build_claim_evidence_matrix
  5. build_relation_matrix
  6. verify_page_text
  7. classify_evidence_type
  8. synthesize_integrated_answer   (AI via LiteLLM)
  9. deterministic_fallback_answer
 10. emit_audit_report

Usage:
  uv run python scripts/library_synthesis_qa_level4_batch.py \
    --run-id 492acd8d-06bd-42ac-a511-f3ec52f97bb3 \
    --scope breslov_primary \
    --vector-backend auto \
    --question-id kitzur_level4_interconnection_01 \
    --json-out data/reports/breslov/2026-07-12-kitzur-level4-synthesis-qa-v1/results.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, LITELLM_TIMEOUT_SECONDS, RESEARCH_CONVERSATION_MODEL
from modules.library.book_qa_service import run_book_qa
from modules.library.vector_backends import VectorHit, get_vector_backend
from scripts.library_synthesis_qa_level4_decomposition import (
    DECOMPOSITION,
    EVIDENCE_TYPES,
    LEVEL4_QUESTION,
    LEVEL4_QUESTION_ID,
    RELATIONS,
    all_expected_pages,
    get_claim_by_id,
    get_relations_for_claim,
)

PG = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
      "host": os.environ.get("DB_PG_IP", "localhost"),
      "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}

SNIPPET_CHARS = 600


# ── Helpers ──────────────────────────────────────────────────────────────────


def _quote(text: str, terms: list[str]) -> str:
    lower = text.lower()
    for term in terms:
        pos = lower.find(term.lower())
        if pos >= 0:
            return re.sub(r"\s+", " ", text[max(0, pos - 120):pos + 500]).strip()
    return ""


def _classify_evidence(page_text: str, claim_text: str, terms: list[str]) -> str:
    """Classify evidence type: literal / paraphrase / thematic / cooccurrence."""
    lower_text = page_text.lower()
    lower_claim = claim_text.lower()

    # Literal: claim terms appear verbatim
    term_hits = sum(1 for t in terms if t.lower() in lower_text)
    if term_hits >= 2:
        return "literal"
    if term_hits == 1:
        # Check if text contains characteristic claim fragments
        claim_tokens = [w for w in re.findall(r"\w{4,}", lower_claim) if len(w) > 4]
        frag_hits = sum(1 for t in claim_tokens if t in lower_text)
        if frag_hits >= 2:
            return "paraphrase"
        return "thematic"

    # Cooccurrence: at least one term appears
    if any(t.lower() in lower_text for t in terms):
        return "cooccurrence"

    return "thematic"


async def _page_evidence(conn: psycopg.AsyncConnection, run_id: str,
                         pages: list[int], claim_text: str,
                         terms: list[str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    async with conn.cursor() as cur:
        for page in pages:
            await cur.execute(
                "SELECT text FROM library_pages_v2 WHERE run_id=%s AND page_number=%s",
                (run_id, page),
            )
            row = await cur.fetchone()
            text = row[0] if row else ""
            if not text:
                continue
            snippet = _quote(text, terms)
            if snippet:
                etype = _classify_evidence(text, claim_text, terms)
                found.append({
                    "source_id": f"{claim_text[:4]}_p{page}",
                    "page": page, "language": "es",
                    "method": "page_direct", "evidence_type": etype,
                    "quote": snippet, "score": 1.0,
                })
    return found


# ── Deterministic fallback ───────────────────────────────────────────────────


def _deterministic_answer(claims: list[dict[str, Any]],
                          relations: list[dict[str, Any]]) -> str:
    lines = [
        "## Síntesis determinística (sin IA)",
        "",
        "Basada únicamente en la matriz de evidencia recuperada.",
        "",
    ]
    for item in claims:
        cid = item["claim_id"]
        text = item["claim"]
        acc = item.get("accepted", [])
        if acc:
            best = acc[0]
            lines.append(f"- **{cid}**: {text}")
            lines.append(f"  → p. {best['page']} ({best['evidence_type']}) \"{best['quote'][:200]}...\"")
        else:
            lines.append(f"- **{cid}**: {text} → NO_CONFIRMADO")

    lines.append("")
    lines.append("### Relaciones detectadas")
    for rel in relations:
        if rel.get("status") == "PASS":
            lines.append(f"- {rel['description']} ({rel.get('evidence_type','?')})")
        elif rel.get("status") == "INFERRED":
            lines.append(f"- {rel['description']} (INFERIDA — {rel.get('evidence_type','?')})")
        else:
            lines.append(f"- {rel['description']}: NO_CONFIRMADA")

    lines.append("")
    lines.append("---")
    lines.append("*Fuentes: SQL/page + Book QA + VectorSearchBackend auto. "
                 "La evidencia debe verificarse contra el texto canónico.*")
    return "\n".join(lines)


# ── AI synthesis ─────────────────────────────────────────────────────────────


async def _ai_synthesis(question: str, claims: list[dict[str, Any]],
                        relations: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if not LITELLM_API_KEY:
        return None, "litellm_key_missing"

    # Build source list from accepted evidence
    sources = []
    for c in claims:
        for e in c.get("accepted", [])[:1]:
            sources.append({
                "claim_id": c["claim_id"],
                "claim": c["claim"],
                "page": e["page"],
                "quote": e["quote"][:400],
                "evidence_type": e.get("evidence_type", "?"),
            })

    if not sources:
        return None, "no_verified_evidence"

    # Build relation summary
    relation_summary = []
    for r in relations:
        if r.get("status") in ("PASS", "INFERRED"):
            relation_summary.append({
                "relation_id": r["relation_id"],
                "description": r["description"],
                "evidence_type": r.get("evidence_type", "?"),
            })

    prompt = {
        "question": question,
        "sources": sources,
        "relations": relation_summary,
        "rules": (
            "Eres un investigador académico de Breslov. "
            "Debes construir una respuesta integrada que explique la interconexión "
            "entre humildad, verdad, alegría, daat, pureza sexual y unión con los Tzadikim "
            "como vía para alcanzar el propósito final de la vida. "
            "Usa SOLO las fuentes proporcionadas. "
            "Cada afirmación factual debe citar [claim_id p. N]. "
            "Las conexiones entre conceptos deben explicarse con referencias a las relaciones identificadas. "
            "Si una conexión no tiene evidencia directa, indícalo como [INFERIDA] o [TEMÁTICA]. "
            "No inventes páginas ni citas. "
            "La respuesta debe ser en español, estructurada, con secciones por cualidad espiritual."
        ),
    }

    payload = {
        "model": RESEARCH_CONVERSATION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sos un investigador de Breslov que produce síntesis académicas "
                    "basadas exclusivamente en fuentes verificadas. "
                    "Citas cada afirmación. No inventas evidencia."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                json=payload,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

        # Validate citations
        allowed_ids = {s["claim_id"] for s in sources}
        cited = set(re.findall(r"\[([A-Za-z0-9_]+)", content))
        unknown = cited - allowed_ids
        if not content:
            return None, "empty_ai_response"
        if unknown:
            return content, f"unknown_citations:{','.join(sorted(unknown))}"
        return content, None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        return None, f"ai_error:{type(exc).__name__}"


# ── Oracle page verification ────────────────────────────────────────────────


async def _verify_page_text(conn: psycopg.AsyncConnection, run_id: str,
                            page: int, terms: list[str]) -> dict[str, Any]:
    """Verify that a page actually contains the expected terms."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT text FROM library_pages_v2 WHERE run_id=%s AND page_number=%s",
            (run_id, page),
        )
        row = await cur.fetchone()
        if not row:
            return {"verified": False, "reason": "page_not_found"}
        text = row[0]
        lower = text.lower()
        hits = [t for t in terms if t.lower() in lower]
        return {"verified": len(hits) > 0, "hits": hits, "text_length": len(text)}


# ── Main pipeline ────────────────────────────────────────────────────────────


async def run_level4(args: argparse.Namespace) -> int:
    output_dir = args.json_out.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw_requests").mkdir(exist_ok=True)
    (output_dir / "raw_responses").mkdir(exist_ok=True)

    errors: list[str] = []
    conn = await psycopg.AsyncConnection.connect(**PG)
    await conn.execute("SET search_path TO public")
    vector_backend = get_vector_backend(args.vector_backend)
    run_id = args.run_id

    # ── Step 1: Claim evidence matrix ───────────────────────────────────────
    print("=== Level 4 Pipeline ===")
    print(f"Question: {LEVEL4_QUESTION[:80]}...")
    print(f"Claims: {len(DECOMPOSITION)}")
    print(f"Relations: {len(RELATIONS)}")
    print(f"Vector backend: {args.vector_backend}")
    print()

    claim_results: list[dict[str, Any]] = []
    page_verification: dict[int, dict[str, Any]] = {}

    method_counts: dict[str, int] = {
        "page_direct": 0, "book_qa": 0, "vector": 0, "fts": 0, "relation_qa": 0,
    }
    evidence_accepted = 0
    evidence_discarded = 0

    for claim_def in DECOMPOSITION:
        cid = claim_def["claim_id"]
        ctext = claim_def["claim"]
        pages = claim_def["expected_pages"]
        terms = claim_def["search_terms"]

        # Wrap each claim in a savepoint to isolate transaction errors
        await conn.execute("SAVEPOINT sp_claim_" + cid)

        # Page-direct evidence
        direct: list[dict[str, Any]] = []
        try:
            direct = await _page_evidence(conn, run_id, pages, ctext, terms)
            if direct:
                method_counts["page_direct"] += len(direct)
        except Exception:
            await conn.execute("ROLLBACK TO SAVEPOINT sp_claim_" + cid)

        # Book QA evidence
        book_sources = []
        try:
            book = await run_book_qa(
                conn, f"¿Dónde aparece {ctext}?",
                run_id=run_id, scope_code=args.scope,
                top_k=args.top_k,
            )
            book_sources = book.sources
        except Exception:
            await conn.execute("ROLLBACK TO SAVEPOINT sp_claim_" + cid)

        # Vector evidence
        vector_evidence: list[dict[str, Any]] = []
        vector_error: str | None = None
        try:
            hits = await vector_backend.search(
                ctext, args.scope, top_k=args.top_k,
                filters={"run_id": run_id, "language": "es"},
            )
            for idx, hit in enumerate(hits):
                vector_evidence.append({
                    "source_id": f"vec_{cid}_{idx+1}",
                    "source_method": "vector",
                    "vector_backend_used": hit.backend,
                    "chunk_id": hit.chunk_id,
                    "document_id": hit.document_id,
                    "page": hit.page,
                    "language": hit.language,
                    "distance": hit.distance,
                    "score": hit.score,
                    "quote": hit.evidence_text,
                    "evidence_type": "thematic",
                })
            if hits:
                method_counts["vector"] += len(hits)
        except Exception as exc:
            vector_error = f"{type(exc).__name__}: {exc}"
            if hasattr(vector_backend, "last_error") and vector_backend.last_error:
                vector_error = vector_backend.last_error

        # FTS evidence
        fts_evidence: list[dict[str, Any]] = []
        try:
            async with conn.cursor() as cur:
                for term in terms[:3]:
                    if len(term) < 3:
                        continue
                    await cur.execute(
                        "SELECT p.page_number, substring(p.text, 1, %s) "
                        "FROM library_pages_v2 p WHERE p.run_id = %s "
                        "AND to_tsvector('spanish', p.text) @@ to_tsquery('spanish', %s) "
                        "ORDER BY p.page_number LIMIT 3",
                        (SNIPPET_CHARS, run_id, term),
                    )
                    for row in await cur.fetchall():
                        pg = row[0]
                        snippet = (row[1] or "")[:SNIPPET_CHARS].replace("\n", " ").strip()
                        if snippet:
                            fts_evidence.append({
                                "source_id": f"fts_{cid}_{term[:8]}_p{pg}",
                                "page": pg, "method": "fts",
                                "quote": snippet, "score": 0.8,
                                "evidence_type": "thematic",
                            })
                            method_counts["fts"] += 1
        except Exception:
            await conn.execute("ROLLBACK TO SAVEPOINT sp_claim_" + cid)

        # Accept best evidence
        all_evidence = direct + vector_evidence + fts_evidence
        accepted = all_evidence[:2] if all_evidence else []

        if accepted:
            evidence_accepted += len(accepted)
            for pg in {e.get("page", 0) for e in accepted if e.get("page")}:
                if pg and pg not in page_verification:
                    try:
                        page_verification[pg] = await _verify_page_text(
                            conn, run_id, pg, terms
                        )
                    except Exception:
                        await conn.execute("ROLLBACK TO SAVEPOINT sp_claim_" + cid)
        else:
            evidence_discarded += 1

        await conn.execute("RELEASE SAVEPOINT sp_claim_" + cid)

        claim_results.append({
            "claim_id": cid,
            "claim": ctext,
            "category": claim_def["category"],
            "expected_pages": pages,
            "page_direct": direct,
            "book_qa_hits": len(book_sources),
            "vector_evidence": vector_evidence,
            "fts_evidence": fts_evidence,
            "vector_error": vector_error,
            "accepted": accepted,
            "status": "PASS" if accepted else "FAIL",
            "best_evidence_type": accepted[0].get("evidence_type", "?") if accepted else "none",
        })

    # ── Step 2: Build relation matrix ───────────────────────────────────────
    relation_results: list[dict[str, Any]] = []
    for rel in RELATIONS:
        from_claim = get_claim_by_id(rel["from_claim_id"])
        to_claim = get_claim_by_id(rel["to_claim_id"])

        from_acc = next((c for c in claim_results if c["claim_id"] == rel["from_claim_id"]), None)
        to_acc = next((c for c in claim_results if c["claim_id"] == rel["to_claim_id"]), None)

        from_pages = set()
        to_pages = set()
        if from_acc:
            for e in from_acc.get("accepted", []):
                if e.get("page"):
                    from_pages.add(e["page"])
            for e in from_acc.get("page_direct", []):
                if e.get("page"):
                    from_pages.add(e["page"])
        if to_acc:
            for e in to_acc.get("accepted", []):
                if e.get("page"):
                    to_pages.add(e["page"])
            for e in to_acc.get("page_direct", []):
                if e.get("page"):
                    to_pages.add(e["page"])

        shared_pages = sorted(from_pages & to_pages)
        all_pages = sorted(from_pages | to_pages)

        # Determine evidence type
        evidence_type = "thematic"
        if shared_pages:
            evidence_type = "same_page"
        if rel.get("expected_relation_type") == "literal" and shared_pages:
            evidence_type = "literal"

        if from_acc and to_acc and from_acc["status"] == "PASS" and to_acc["status"] == "PASS":
            if shared_pages:
                status = "PASS"
            else:
                status = "INFERRED"
                evidence_type = "thematic"
        elif from_acc and to_acc:
            status = "INFERRED"
            evidence_type = "thematic"
        else:
            status = "FAIL"

        relation_results.append({
            "relation_id": rel["relation_id"],
            "from_claim_id": rel["from_claim_id"],
            "to_claim_id": rel["to_claim_id"],
            "description": rel["description"],
            "from_label": rel["from_label"],
            "to_label": rel["to_label"],
            "status": status,
            "evidence_type": evidence_type,
            "shared_pages": shared_pages,
            "all_pages": all_pages,
            "confidence": 0.9 if status == "PASS" and shared_pages else (
                0.6 if status == "PASS" else 0.3
            ),
        })

    # ── Step 3: Synthesis ────────────────────────────────────────────────────
    print("=== Synthesis ===")
    ai, ai_error = None, None
    if args.use_ai:
        ai, ai_error = await _ai_synthesis(LEVEL4_QUESTION, claim_results, relation_results)
        if ai:
            print(f"[OK] AI synthesis: {len(ai)} chars")
        else:
            print(f"[WARN] AI synthesis failed: {ai_error}")
    else:
        print("[INFO] AI disabled by --no-ai")

    fallback = _deterministic_answer(claim_results, relation_results)

    # ── Step 4: Build diagnostics ────────────────────────────────────────────
    vector_backend_used = getattr(vector_backend, "backend_used",
                                  getattr(vector_backend, "name", "none"))

    diagnostics = {
        "total_claims": len(DECOMPOSITION),
        "claims_pass": sum(1 for c in claim_results if c["status"] == "PASS"),
        "claims_fail": sum(1 for c in claim_results if c["status"] == "FAIL"),
        "total_relations": len(RELATIONS),
        "relations_pass": sum(1 for r in relation_results if r["status"] == "PASS"),
        "relations_inferred": sum(1 for r in relation_results if r["status"] == "INFERRED"),
        "relations_fail": sum(1 for r in relation_results if r["status"] == "FAIL"),
        "method_hits": method_counts,
        "evidence_accepted": evidence_accepted,
        "evidence_discarded": evidence_discarded,
        "vector_backend_requested": args.vector_backend,
        "vector_backend_used": vector_backend_used,
        "ai_synthesis_used": ai is not None,
        "ai_error": ai_error,
        "fallback_used": ai is None,
        "backend_runtime_model": RESEARCH_CONVERSATION_MODEL,
        "embedding_model": "openai_text_embedding_3_small",
    }

    # ── Step 5: Build result ─────────────────────────────────────────────────
    result = {
        "question_id": LEVEL4_QUESTION_ID,
        "level": 4,
        "question": LEVEL4_QUESTION,
        "scope": args.scope,
        "run_id": run_id,
        "claims": claim_results,
        "relations": relation_results,
        "page_verification": {str(k): v for k, v in page_verification.items()},
        "synthesis": {
            "ai": ai,
            "ai_error": ai_error,
            "fallback": fallback,
            "selected": ai if ai else fallback,
        },
        "diagnostics": diagnostics,
        "final_status": "PASS" if (
            sum(1 for c in claim_results if c["status"] == "PASS") >= len(DECOMPOSITION) * 0.6
            and len(relation_results) > 0
        ) else "PARTIAL",
    }

    # ── Step 6: Write outputs ────────────────────────────────────────────────
    raw_dir = output_dir / "raw_responses"
    (raw_dir / f"{LEVEL4_QUESTION_ID}_claims.json").write_text(
        json.dumps(claim_results, ensure_ascii=False, indent=2))
    (raw_dir / f"{LEVEL4_QUESTION_ID}_relations.json").write_text(
        json.dumps(relation_results, ensure_ascii=False, indent=2))
    (raw_dir / f"{LEVEL4_QUESTION_ID}_full.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2))

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    # Write auxiliary files
    (output_dir / "claim_evidence_matrix.json").write_text(
        json.dumps(claim_results, ensure_ascii=False, indent=2))
    (output_dir / "relation_matrix.json").write_text(
        json.dumps(relation_results, ensure_ascii=False, indent=2))
    (output_dir / "synthesis_output.md").write_text(
        f"# Synthesis Level 4\n\n{ai or fallback}\n")
    (output_dir / "fallback_output.md").write_text(
        f"# Deterministic Fallback\n\n{fallback}\n")

    await conn.close()

    print(f"\n=== Complete ===")
    print(f"Status: {result['final_status']}")
    print(f"Claims: {diagnostics['claims_pass']}/{diagnostics['total_claims']} PASS, "
          f"{diagnostics['claims_fail']} FAIL")
    print(f"Relations: {diagnostics['relations_pass']} PASS, "
          f"{diagnostics['relations_inferred']} INFERRED, "
          f"{diagnostics['relations_fail']} FAIL")
    print(f"Methods: {json.dumps(method_counts)}")
    print(f"Vector backend: {vector_backend_used}")
    print(f"AI synthesis: {'yes' if ai else 'no'}{' (' + ai_error + ')' if ai_error else ''}")
    print(f"Output: {args.json_out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Level 4 Synthesis QA — deep interconnection")
    parser.add_argument("--run-id", required=True, help="Ingestion V2 run ID")
    parser.add_argument("--scope", default="breslov_primary", help="Knowledge scope code")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K for retrieval")
    parser.add_argument("--vector-backend", choices=("milvus", "pgvector", "auto", "disabled"),
                        default="auto", help="Vector search backend")
    parser.add_argument("--question-id", default=LEVEL4_QUESTION_ID)
    parser.add_argument("--json-out", type=Path, required=True, help="Output JSON path")
    parser.add_argument("--use-ai", action="store_true", dest="use_ai", help="Enable AI synthesis")
    parser.add_argument("--no-ai", action="store_false", dest="use_ai", help="Disable AI synthesis")
    parser.set_defaults(use_ai=False)
    raise SystemExit(asyncio.run(run_level4(parser.parse_args())))
