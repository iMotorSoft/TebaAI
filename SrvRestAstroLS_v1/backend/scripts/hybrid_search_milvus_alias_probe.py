#!/usr/bin/env python3
"""Read-only probe for the hybrid search Milvus collection_code alias."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import globalVar

DEFAULT_QUERIES = ["alegría", "plegaria", "hitbodedut", "sangre habla"]
DEFAULT_REPORT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "reports"
    / "breslov"
    / "2026-07-09-hybrid-search-milvus-alias"
)


def _elapsed_ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))


def _direct_vector_hits(
    *,
    query: str,
    top_k: int,
    milvus_collection: str,
    milvus_collection_code: str,
) -> dict[str, Any]:
    from infrastructure.milvus.client import close_connection, create_connection, search_vectors
    from modules.embeddings.client import embed_text

    result: dict[str, Any] = {
        "hits": 0,
        "elapsed_ms": None,
        "expr": f'collection_code == "{milvus_collection_code}"',
        "error": None,
    }
    start = time.perf_counter()
    try:
        create_connection()
        vector = embed_text(query)
        hits = search_vectors(
            collection_name=milvus_collection,
            query_embedding=vector,
            top_k=top_k,
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


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
    from modules.library.hybrid_search import (
        resolve_milvus_collection_code_for_scope,
        search_chunks_hybrid,
    )
    from modules.library.text_search import search_chunks_text

    milvus_collection_code = resolve_milvus_collection_code_for_scope(args.scope_code)
    report: dict[str, Any] = {
        "scope_code": args.scope_code,
        "milvus_collection": args.milvus_collection,
        "milvus_collection_code": milvus_collection_code,
        "alias_used": milvus_collection_code != args.scope_code,
        "queries": [],
        "warnings": [],
    }
    if milvus_collection_code is None:
        report["warnings"].append("milvus_collection_code_unresolved")
        return report

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            for query in args.queries:
                start = time.perf_counter()
                fts_rows = await search_chunks_text(
                    conn,
                    knowledge_scope_code=args.scope_code,
                    query=query,
                    top_k=args.top_k,
                    mode="auto",
                    language=args.language,
                )
                fts_elapsed = _elapsed_ms(start)

                vector = _direct_vector_hits(
                    query=query,
                    top_k=args.top_k,
                    milvus_collection=args.milvus_collection,
                    milvus_collection_code=milvus_collection_code,
                )

                start = time.perf_counter()
                hybrid_rows = await search_chunks_hybrid(
                    conn,
                    knowledge_scope_code=args.scope_code,
                    query=query,
                    top_k=args.top_k,
                    language=args.language,
                    milvus_collection=args.milvus_collection,
                )
                hybrid_elapsed = _elapsed_ms(start)
                vector_rows = [
                    row for row in hybrid_rows
                    if "vector" in (row.get("source_signals") or [])
                ]
                report["queries"].append(
                    {
                        "query": query,
                        "fts_hits": len(fts_rows),
                        "fts_elapsed_ms": fts_elapsed,
                        "direct_vector_hits": vector["hits"],
                        "direct_vector_expr": vector["expr"],
                        "direct_vector_elapsed_ms": vector["elapsed_ms"],
                        "direct_vector_error": vector["error"],
                        "hybrid_hits": len(hybrid_rows),
                        "hybrid_vector_hits": len(vector_rows),
                        "hybrid_elapsed_ms": hybrid_elapsed,
                        "hybrid_source_signals": [
                            row.get("source_signals") for row in hybrid_rows[:5]
                        ],
                        "top_titles": [
                            row.get("document_title") for row in hybrid_rows[:3]
                        ],
                    }
                )
    finally:
        await close_pool(pool)
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hybrid Search Milvus Alias Probe",
        "",
        f"- logical scope: `{report['scope_code']}`",
        f"- Milvus collection: `{report['milvus_collection']}`",
        f"- Milvus metadata collection_code: `{report['milvus_collection_code']}`",
        f"- alias used: `{report['alias_used']}`",
        "",
        "| Query | FTS hits | Direct vector hits | Hybrid hits | Hybrid vector hits |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("queries", []):
        lines.append(
            f"| `{row['query']}` | {row['fts_hits']} | {row['direct_vector_hits']} | "
            f"{row['hybrid_hits']} | {row['hybrid_vector_hits']} |"
        )
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid search Milvus alias probe")
    parser.add_argument("--scope-code", default="breslov_primary")
    parser.add_argument("--milvus-collection", default=globalVar.MILVUS_COLLECTION_BRESLOV)
    parser.add_argument("--language", default="es")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = asyncio.run(_run_probe(args))
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "hybrid_alias_probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (args.report_dir / "hybrid_alias_probe.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
