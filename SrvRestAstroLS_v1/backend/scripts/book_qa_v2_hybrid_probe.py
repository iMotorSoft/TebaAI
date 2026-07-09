#!/usr/bin/env python3
"""Hybrid Book QA V2 probe: PostgreSQL + Milvus semantic search."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys
from pathlib import Path
from typing import Any

import psycopg
from pymilvus import Collection, connections

PG_CONF = {
    "user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
    "host": os.environ.get("DB_PG_IP", "localhost"),
    "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai",
}
SNIPPET_CHARS = 400
MILVUS_HOST = "127.0.0.1"


def _v(row, idx=0):
    if row is None: return None
    if isinstance(row, dict): return row[list(row.keys())[idx]]
    return row[idx]


async def embed_text(text: str) -> list[float]:
    import httpx
    from globalVar import LITELLM_BASE_URL, LITELLM_API_KEY
    r = await httpx.AsyncClient(timeout=60).post(
        f"{LITELLM_BASE_URL}/v1/embeddings",
        headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
        json={"input": text[:3000], "model": "openai_text_embedding_3_small"},
    )
    return r.json()["data"][0]["embedding"]


async def probe(question: str, run_id: str, collection: str, top_k: int = 10, sql_top_k: int = 10, milvus_top_k: int = 10) -> dict[str, Any]:
    q = question.strip().rstrip("¿?!.")
    q_lower = q.lower()
    conn = await psycopg.AsyncConnection.connect(**PG_CONF)
    sources: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    warnings: list[str] = []

    async with conn.cursor() as cur:
        # ── SQL candidates ──
        # Concept lookup by ILIKE
        await cur.execute(
            "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) AS snippet "
            "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
            "ORDER BY p.page_number LIMIT %s",
            (q_lower, SNIPPET_CHARS, run_id, f"%{q_lower}%", sql_top_k),
        )
        sql_rows = await cur.fetchall()

        # If no direct match, try first meaningful word
        if not sql_rows:
            tokens = [t for t in re.findall(r"\w{4,}", q_lower) if t not in ("que", "para", "con", "por", "las", "los")]
            for token in tokens[:3]:
                await cur.execute(
                    "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), 300) "
                    "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                    "ORDER BY p.page_number LIMIT 5",
                    (token, run_id, f"%{token}%"),
                )
                sql_rows.extend(await cur.fetchall())

        for r in sql_rows:
            pg = _v(r, 0)
            if pg not in seen_pages:
                seen_pages.add(pg)
                sources.append({
                    "page_number": pg, "evidence_type": "literal", "score": 0.8,
                    "sql_score": 0.8, "milvus_score": 0.0,
                    "snippet": (_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                    "matched_terms": [], "source_refs_nearby": [],
                    "grounded_in_postgres": True,
                })

    # ── Milvus semantic candidates ──
    connections.connect(alias="default", host=MILVUS_HOST, port=19530, timeout=30)
    col = Collection(collection)
    col.load()
    query_vec = await embed_text(q)

    milvus_results = col.search(
        data=[query_vec], anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        limit=milvus_top_k, output_fields=["page_number", "text_preview"],
    )
    col.release()
    connections.disconnect("default")

    for hits in milvus_results:
        for hit in hits:
            pg = int(hit.entity.get("page_number", 0))
            if pg == 0:
                continue
            if pg not in seen_pages:
                seen_pages.add(pg)
                # Ground in PostgreSQL
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT substring(text, 1, %s) FROM library_pages_v2 WHERE run_id = %s AND page_number = %s",
                        (SNIPPET_CHARS, run_id, pg),
                    )
                    row = await cur.fetchone()
                    snippet = (_v(row) or "")[:SNIPPET_CHARS].replace("\n", " ").strip() if row else "(no pg grounding)"
                    if not row:
                        warnings.append(f"milvus_candidate_discarded_no_postgres_grounding: page {pg}")
                        continue
                sources.append({
                    "page_number": pg, "evidence_type": "semantic_candidate", "score": hit.distance,
                    "sql_score": 0.0, "milvus_score": hit.distance,
                    "snippet": snippet, "matched_terms": [],
                    "source_refs_nearby": [], "grounded_in_postgres": True,
                })
            else:
                # Found by both: boost score
                for s in sources:
                    if s["page_number"] == pg:
                        s["milvus_score"] = hit.distance
                        s["score"] = s.get("sql_score", 0.5) * 0.55 + hit.distance * 0.45 + 0.1
                        s["evidence_type"] = "hybrid"

    await conn.close()

    # Sort by score desc, limit top_k
    sources.sort(key=lambda s: -s.get("score", s.get("sql_score", 0)))
    sources = sources[:top_k]
    pages = sorted(set(s.get("page_number") for s in sources))

    result = {
        "question": question, "route": "book_qa_v2_hybrid",
        "run_id": run_id, "answer_type": "hybrid",
        "short_conclusion": f"Se encontraron {len(sources)} fuente(s) en {len(pages)} página(s). "
                           f"SQL: {sum(1 for s in sources if s.get('sql_score', 0) > 0)}, "
                           f"Milvus: {sum(1 for s in sources if s.get('milvus_score', 0) > 0)}.",
        "evidence_summary": {
            "sql_candidates": len(sql_rows),
            "milvus_candidates": len(milvus_results[0]) if milvus_results else 0,
            "merged_sources": len(sources), "pages": pages,
        },
        "sources": sources, "warnings": warnings,
        "method": {
            "retrieval": "postgres_v2_sql_plus_milvus_test",
            "used_milvus": True, "used_embeddings": True, "used_ai": False,
            "milvus_collection": collection,
        },
    }
    return result


def fmt_md(r: dict[str, Any]) -> str:
    lines = ["# Book QA V2 Hybrid Probe", "", f"## Pregunta\n{r.get('question','')}", "", f"## Conclusión\n{r.get('short_conclusion','')}",
             "", "## Método", f"- retrieval: postgres_v2_sql_plus_milvus_test", f"- Milvus: sí ({r.get('method',{}).get('milvus_collection','?')})",
             f"- Embeddings: sí", f"- IA: no", ""]
    for i, s in enumerate(r.get("sources", [])[:8], 1):
        snip = (s.get("snippet") or "—")[:250].replace("\n", " ")
        ev = s.get("evidence_type", "?")
        sc = round(s.get("score", 0), 4)
        lines += [f"### {i}. Página {s.get('page_number','?')} — {ev} (score={sc})", "", f"{snip}", ""]
    es = r.get("evidence_summary", {})
    lines += ["## Resumen", f"- SQL: {es.get('sql_candidates',0)} | Milvus: {es.get('milvus_candidates',0)} | Merged: {es.get('merged_sources',0)}",
              f"- Páginas: {es.get('pages',[])}", ""]
    if r.get("warnings"):
        lines += ["## Advertencias"] + [f"- {w}" for w in r["warnings"]] + [""]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Book QA V2 Hybrid Probe (SQL + Milvus)")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--collection", default="tebaai_breslov_bookqa_v2_kitzur_test_pages_v1")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--sql-top-k", type=int, default=10)
    parser.add_argument("--milvus-top-k", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("question", nargs="*")
    args = parser.parse_args()
    if not args.question: print("ERROR: question required"); return 1

    question = " ".join(args.question)
    result = await probe(question, args.run_id, args.collection, args.top_k, args.sql_top_k, args.milvus_top_k)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(fmt_md(result))

    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", question.lower())[:40].strip("-")
        (args.report_dir / f"hybrid_{slug}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
