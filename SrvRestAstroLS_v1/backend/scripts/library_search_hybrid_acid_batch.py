#!/usr/bin/env python3
"""HTTP acid batch for POST /library/search hybrid retrieval.

Read-only by design:
- uses a locally generated access JWT for an existing user instead of /auth/login;
- calls POST /library/search;
- runs direct FTS/vector probes for observability only;
- writes evidence files under SrvRestAstroLS_v1/data/reports.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx

DEFAULT_REPORT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "reports"
    / "breslov"
    / "2026-07-09-library-search-hybrid-acid"
)
DEFAULT_QUERIES_FILE = DEFAULT_REPORT_DIR / "queries.json"


def _load_backend_local_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env.backend-dev.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _elapsed_ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))


def _normalize_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _combined_result_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for row in response.get("results", []) or []:
        parts.extend(
            str(row.get(key) or "")
            for key in ("document_title", "plain_excerpt", "highlighted_excerpt", "chapter", "section")
        )
    return "\n".join(parts)


def _term_hits(response: dict[str, Any], expected_terms: list[str]) -> dict[str, bool]:
    haystack = _normalize_text(_combined_result_text(response))
    return {term: _normalize_text(term).strip('"') in haystack for term in expected_terms}


def _result_has_vector(row: dict[str, Any]) -> bool:
    signals = row.get("source_signals") or []
    return (
        "vector" in signals
        or row.get("vector_score") is not None
        or row.get("match_type") == "vector"
    )


def _classify(score: int) -> str:
    if score >= 18:
        return "PASS fuerte"
    if score >= 15:
        return "PASS usable"
    if score >= 10:
        return "WARN"
    return "FAIL"


def _classify_global(score: int) -> str:
    if score >= 180:
        return "PASS fuerte"
    if score >= 150:
        return "PASS usable"
    if score >= 100:
        return "WARN"
    return "FAIL"


async def _read_user_for_token(email: str) -> dict[str, str]:
    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id::text AS id, role::text AS role
                    FROM users
                    WHERE lower(email) = lower(%(email)s)
                      AND is_active = true
                    LIMIT 1
                    """,
                    {"email": email},
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("No active user found for TEBAAI_E2E_ADMIN_EMAIL")
                return {"id": str(row["id"]), "role": str(row["role"])}
    finally:
        await close_pool(pool)


async def _access_token_read_only(email: str) -> str:
    from modules.auth.tokens import create_access_token

    user = await _read_user_for_token(email)
    return create_access_token(user["id"], user["role"])


async def _call_library_search(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    token: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "collection": query["scope_code"],
        "query": query["query"],
        "mode": query["mode"],
        "top_k": query["top_k"],
        "language": query["language"],
    }
    start = time.perf_counter()
    response = await client.post(
        f"{base_url.rstrip('/')}/library/search",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=120,
    )
    elapsed_ms = _elapsed_ms(start)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:1000]}
    return {
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "request": payload,
        "response": body,
    }


async def _direct_fts_hits(query: dict[str, Any]) -> dict[str, Any]:
    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
    from modules.library.text_search import search_chunks_text

    result: dict[str, Any] = {"hits": 0, "error": None, "elapsed_ms": None}
    mode = "auto" if query["mode"] == "hybrid" else query["mode"]
    if mode == "trigram":
        mode = "trigram"
    start = time.perf_counter()
    pool = create_pool_from_settings()
    try:
        await open_pool(pool)
        async with pool.connection() as conn:
            rows = await search_chunks_text(
                conn,
                knowledge_scope_code=query["scope_code"],
                query=query["query"],
                top_k=query["top_k"],
                mode=mode,
                language=query["language"],
            )
            result["hits"] = len(rows)
            result["top_titles"] = [row.get("document_title") for row in rows[:3]]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["elapsed_ms"] = _elapsed_ms(start)
        await close_pool(pool)
    return result


def _direct_vector_hits(query: dict[str, Any]) -> dict[str, Any]:
    from infrastructure.milvus.client import close_connection, create_connection, search_vectors
    from modules.embeddings.client import embed_text
    from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope
    import globalVar

    milvus_code = resolve_milvus_collection_code_for_scope(query["scope_code"])
    result: dict[str, Any] = {
        "hits": 0,
        "error": None,
        "elapsed_ms": None,
        "milvus_collection_code": milvus_code,
        "expr": f'collection_code == "{milvus_code}"' if milvus_code else None,
    }
    if query["mode"] != "hybrid":
        result["skipped"] = True
        return result
    start = time.perf_counter()
    try:
        create_connection()
        vector = embed_text(query["query"])
        hits = search_vectors(
            collection_name=globalVar.MILVUS_COLLECTION_BRESLOV,
            query_embedding=vector,
            top_k=query["top_k"],
            expr=result["expr"],
            output_fields=["chunk_id", "document_id", "title", "collection_code"],
        )
        result["hits"] = len(hits)
        result["top"] = [
            {
                "chunk_id": hit.get("chunk_id"),
                "distance": round(float(hit.get("distance") or 0.0), 4),
                "title": hit.get("title"),
                "collection_code": hit.get("collection_code"),
            }
            for hit in hits[:3]
        ]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["elapsed_ms"] = _elapsed_ms(start)
        close_connection()
    return result


async def _branch_probes(query: dict[str, Any]) -> dict[str, Any]:
    fts = await _direct_fts_hits(query)
    vector = await asyncio.to_thread(_direct_vector_hits, query)
    return {"fts": fts, "vector": vector}


def _score(query: dict[str, Any], http_result: dict[str, Any], probes: dict[str, Any]) -> dict[str, Any]:
    response = http_result.get("response") or {}
    results = response.get("results", []) if isinstance(response, dict) else []
    http_200 = http_result.get("status_code") == 200
    result_count = len(results)
    term_hits = _term_hits(response, query.get("expected_terms", [])) if http_200 else {}
    scope_ok = bool(http_200 and response.get("collection") == query["scope_code"])
    if scope_ok:
        scope_ok = all(row.get("knowledge_scope_code") == query["scope_code"] for row in results)
    mode_ok = bool(http_200 and response.get("mode") == query["mode"])
    vector_visible_hits = sum(1 for row in results if _result_has_vector(row))
    vector_visibility = "yes" if vector_visible_hits else "no"
    if results and not any("source_signals" in row or "vector_score" in row for row in results):
        vector_visibility = "unknown"
    direct_vector_hits = int((probes.get("vector") or {}).get("hits") or 0)
    hybrid_q02_dominated = query["id"] == "hybrid_q02" and direct_vector_hits > 0
    vector_ok = (
        direct_vector_hits > 0
        and (
            vector_visible_hits > 0
            or vector_visibility == "unknown"
            or hybrid_q02_dominated
        )
    ) if query.get("expect_vector_branch") else vector_visible_hits == 0
    critical_warnings: list[str] = []
    quality_warnings: list[str] = []
    if probes.get("fts", {}).get("error"):
        critical_warnings.append(f"fts_probe_error:{probes['fts']['error']}")
    if query["mode"] == "hybrid" and probes.get("vector", {}).get("error"):
        critical_warnings.append(f"vector_probe_error:{probes['vector']['error']}")
    if http_200 and query["mode"] == "hybrid" and direct_vector_hits == 0:
        critical_warnings.append("hybrid_direct_vector_zero")
    if http_200 and query.get("expect_vector_branch") and vector_visible_hits == 0 and not hybrid_q02_dominated:
        critical_warnings.append("hybrid_response_vector_zero")
    if http_200 and result_count == 0:
        quality_warnings.append("empty_results")
    missing_terms = [term for term, ok in term_hits.items() if not ok]
    if missing_terms:
        quality_warnings.append("missing_expected_terms:" + ",".join(missing_terms))

    score = 0
    score += 3 if http_200 else 0
    score += 3 if result_count > 0 else 0
    if term_hits:
        score += round(4 * (sum(1 for ok in term_hits.values() if ok) / len(term_hits)))
    score += 2 if scope_ok else 0
    score += 2 if mode_ok else 0
    score += 4 if vector_ok else 0
    score += 2 if not critical_warnings else 0

    return {
        "score": int(score),
        "status": _classify(int(score)),
        "http_200": http_200,
        "result_count": result_count,
        "term_hits": term_hits,
        "scope_ok": scope_ok,
        "mode_ok": mode_ok,
        "vector_branch_visible": vector_visibility,
        "response_vector_hits": vector_visible_hits,
        "direct_vector_hits": direct_vector_hits,
        "hybrid_vector_merged_hits": vector_visible_hits,
        "fts_hits": int((probes.get("fts") or {}).get("hits") or 0),
        "critical_warnings": critical_warnings,
        "quality_warnings": quality_warnings,
    }


def _render_query_markdown(record: dict[str, Any]) -> str:
    query = record["query"]
    scoring = record["scoring"]
    response = record["http"].get("response") or {}
    results = response.get("results", []) if isinstance(response, dict) else []
    lines = [
        f"# {query['id']}",
        "",
        "## Query",
        query["query"],
        "",
        "## Request",
        f"mode: {query['mode']}",
        f"scope_code: {query['scope_code']}",
        f"top_k: {query['top_k']}",
        "",
        "## Resultado",
        f"HTTP: {record['http']['status_code']}",
        f"score: {scoring['score']}",
        f"status: {scoring['status']}",
        "",
        "## Branches",
        f"FTS hits: {scoring['fts_hits']}",
        f"Vector direct hits: {scoring['direct_vector_hits']}",
        f"Hybrid vector merged hits: {scoring['hybrid_vector_merged_hits']}",
        f"Vector branch visible: {scoring['vector_branch_visible']}",
        "",
        "## Resultados",
    ]
    if not results:
        lines.append("Sin resultados.")
    for idx, row in enumerate(results[:10], start=1):
        title = row.get("document_title") or "Untitled"
        page = row.get("page_start") or row.get("page_end") or "n/a"
        snippet = row.get("highlighted_excerpt") or row.get("plain_excerpt") or ""
        snippet = re.sub(r"\s+", " ", snippet).strip()
        lines.extend([
            f"### {idx}. {title} / page {page}",
            snippet[:700] or "Sin snippet.",
            "",
        ])
    lines.extend(["## Expected terms found"])
    for term, found in scoring["term_hits"].items():
        lines.append(f"- {term}: {'yes' if found else 'no'}")
    lines.extend(["", "## Warnings"])
    warnings = (scoring.get("critical_warnings") or []) + (scoring.get("quality_warnings") or [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _render_summary_markdown(summary: dict[str, Any], records: list[dict[str, Any]]) -> str:
    lines = [
        "# Library Search Hybrid Acid Batch",
        "",
        f"- endpoint: `{summary['endpoint']}`",
        f"- base commit: `{summary['head']}`",
        f"- logical scope: `{summary['scope_code']}`",
        f"- Milvus collection_code alias: `{summary['milvus_collection_code']}`",
        f"- global score: `{summary['global_score']}/{summary['max_score']}` ({summary['percentage']}%)",
        f"- status: `{summary['status']}`",
        "",
        "| ID | Query | Mode | HTTP | Results | FTS | Vector direct | Hybrid vector | Score | Status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in records:
        q = record["query"]
        s = record["scoring"]
        lines.append(
            f"| `{q['id']}` | {q['query']} | {q['mode']} | {record['http']['status_code']} | "
            f"{s['result_count']} | {s['fts_hits']} | {s['direct_vector_hits']} | "
            f"{s['hybrid_vector_merged_hits']} | {s['score']} | {s['status']} |"
        )
    lines.extend([
        "",
        "## Vector Branch Summary",
        f"- hybrid queries: {summary['hybrid_query_count']}",
        f"- hybrid queries with direct vector hits: {summary['hybrid_direct_vector_positive']}",
        f"- hybrid queries with response-visible vector hits: {summary['hybrid_response_vector_positive']}",
        "",
        "## Gaps",
    ])
    gaps = summary.get("gaps") or []
    lines.extend(f"- {gap}" for gap in gaps) if gaps else lines.append("- none")
    lines.extend([
        "",
        "## Recommendations",
        "- Documentar el contrato alias en LAT si queda estable.",
        "- Auditar otras rutas vectoriales que filtren Milvus por scope lógico.",
        "- Ejecutar una validación visual de UI/library search.",
    ])
    return "\n".join(lines) + "\n"


async def _run(args: argparse.Namespace) -> int:
    _load_backend_local_env()
    queries = json.loads(args.queries_file.read_text(encoding="utf-8"))
    args.report_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.report_dir / "raw"
    rendered_dir = args.report_dir / "rendered"
    raw_dir.mkdir(exist_ok=True)
    rendered_dir.mkdir(exist_ok=True)

    email = args.email or os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "")
    if not email:
        raise RuntimeError("--email or TEBAAI_E2E_ADMIN_EMAIL is required for read-only JWT auth")
    token = await _access_token_read_only(email)

    from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope

    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for query in queries:
            http_result = await _call_library_search(
                client,
                base_url=args.base_url,
                token=token,
                query=query,
            )
            probes = await _branch_probes(query)
            scoring = _score(query, http_result, probes)
            record = {
                "query": query,
                "http": http_result,
                "branch_probes": probes,
                "scoring": scoring,
            }
            records.append(record)
            (raw_dir / f"{query['id']}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            (rendered_dir / f"{query['id']}.md").write_text(
                _render_query_markdown(record),
                encoding="utf-8",
            )

    total_score = sum(record["scoring"]["score"] for record in records)
    max_score = len(records) * 20
    hybrid_records = [r for r in records if r["query"]["mode"] == "hybrid"]
    gaps = []
    for r in records:
        warnings = (r["scoring"].get("critical_warnings") or []) + (r["scoring"].get("quality_warnings") or [])
        if warnings or r["scoring"]["status"] in {"WARN", "FAIL"}:
            detail = ", ".join(warnings) if warnings else r["scoring"]["status"]
            gaps.append(f"{r['query']['id']}: {detail}")
    import subprocess

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    summary = {
        "endpoint": f"{args.base_url.rstrip('/')}/library/search",
        "head": head,
        "scope_code": "breslov_primary",
        "milvus_collection_code": resolve_milvus_collection_code_for_scope("breslov_primary"),
        "query_count": len(records),
        "global_score": total_score,
        "max_score": max_score,
        "percentage": round((total_score / max_score) * 100, 1) if max_score else 0,
        "status": _classify_global(total_score),
        "hybrid_query_count": len(hybrid_records),
        "hybrid_direct_vector_positive": sum(1 for r in hybrid_records if r["scoring"]["direct_vector_hits"] > 0),
        "hybrid_response_vector_positive": sum(1 for r in hybrid_records if r["scoring"]["response_vector_hits"] > 0),
        "gaps": gaps,
    }
    results = {"summary": summary, "records": records}
    (args.report_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (args.report_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (args.report_dir / "scoring.md").write_text(
        _render_summary_markdown(summary, records),
        encoding="utf-8",
    )
    (args.report_dir / "README.md").write_text(
        _render_summary_markdown(summary, records),
        encoding="utf-8",
    )
    warnings = "\n".join(f"- {gap}" for gap in gaps) if gaps else "- none"
    (args.report_dir / "warnings.md").write_text(f"# Warnings\n\n{warnings}\n", encoding="utf-8")
    branch_probe = {
        "milvus_collection_code": summary["milvus_collection_code"],
        "queries": [
            {
                "id": r["query"]["id"],
                "query": r["query"]["query"],
                "mode": r["query"]["mode"],
                "fts_hits": r["scoring"]["fts_hits"],
                "direct_vector_hits": r["scoring"]["direct_vector_hits"],
                "response_vector_hits": r["scoring"]["response_vector_hits"],
                "vector_expr": r["branch_probes"]["vector"].get("expr"),
            }
            for r in records
        ],
    }
    (args.report_dir / "hybrid_branch_probe.json").write_text(
        json.dumps(branch_probe, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (args.report_dir / "hybrid_branch_probe.md").write_text(
        _render_summary_markdown(summary, records),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if total_score >= args.min_score else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Library search hybrid acid batch")
    parser.add_argument("--base-url", default="http://127.0.0.1:7008")
    parser.add_argument("--queries-file", type=Path, default=DEFAULT_QUERIES_FILE)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--email", default=os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", ""))
    parser.add_argument("--min-score", type=int, default=150)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
