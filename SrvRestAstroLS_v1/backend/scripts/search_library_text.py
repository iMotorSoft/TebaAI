#! /usr/bin/env python3
"""
CLI: Search library document chunks with FTS, vector, or hybrid modes.

Usage:
    # FTS
    uv run python -m scripts.search_library_text --collection breslov --query "plegaria"

    # Hybrid (FTS + vector)
    uv run python -m scripts.search_library_text \\
        --collection breslov_test \\
        --milvus-collection tebaai_breslov_test_chunks_v1 \\
        --query "La maravilla del cerebro" \\
        --mode hybrid
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search library document chunks.")
    parser.add_argument("--collection", required=True, help="PostgreSQL collection code")
    parser.add_argument("--milvus-collection", help="Milvus collection (required for hybrid mode)")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--mode", default="auto",
                        choices=["auto", "fts", "phrase", "trigram", "hybrid"],
                        help="Search mode")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--language", default="es", choices=["es", "en", "he"],
                        help="Document language")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output-json", help="Write JSON report to file")
    parser.add_argument("--output-md", help="Write Markdown report to file")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled via globalVar.py", file=sys.stderr)
        return 1

    # Safety guards for hybrid cross-contamination
    is_test_collection = args.collection.strip().lower().endswith("_test")
    if args.milvus_collection:
        is_test_milvus = "_test_" in args.milvus_collection
        if is_test_collection and not is_test_milvus:
            print(f"ERROR: Collection '{args.collection}' is test but Milvus "
                  f"'{args.milvus_collection}' is not test. Rejecting.", file=sys.stderr)
            return 1
        if not is_test_collection and is_test_milvus:
            print(f"ERROR: Collection '{args.collection}' is production but Milvus "
                  f"'{args.milvus_collection}' is test. Rejecting.", file=sys.stderr)
            return 1

    if args.mode == "hybrid" and not args.milvus_collection:
        print("ERROR: --milvus-collection is required for hybrid mode", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            from psycopg.rows import dict_row
            conn.row_factory = dict_row
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected 'tebaai', got '{db}'", file=sys.stderr)
                return 1

            if args.mode == "hybrid":
                from modules.library.hybrid_search import search_chunks_hybrid
                from globalVar import EMBEDDINGS_DIMENSION
                results = await search_chunks_hybrid(
                    conn,
                    collection_code=args.collection,
                    query=args.query,
                    top_k=args.top_k,
                    language=args.language,
                    milvus_collection=args.milvus_collection,
                )
            else:
                from modules.library.text_search import search_chunks_text
                results = await search_chunks_text(
                    conn,
                    collection_code=args.collection,
                    query=args.query,
                    top_k=args.top_k,
                    mode=args.mode,
                    language=args.language,
                )

        # Output
        if args.json or args.output_json:
            clean = []
            for r in results:
                item = {k: v for k, v in r.items() if k in (
                    "document_id", "document_title", "author", "collection_code",
                    "chunk_id", "chunk_index", "match_type", "rank",
                    "fts_rank", "vector_score", "hybrid_score",
                    "source_signals",
                    "page_start", "page_end", "reference_label",
                    "plain_excerpt", "highlighted_excerpt",
                )}
                # Convert UUIDs and decimals
                for k, v in item.items():
                    if hasattr(v, "iso_format"):
                        item[k] = str(v)
                clean.append(item)
            output = json.dumps(clean, indent=2, ensure_ascii=False, default=str)
            if args.output_json:
                with open(args.output_json, "w", encoding="utf-8") as f:
                    f.write(output)
                print(f"JSON: {args.output_json}")
            else:
                print(output)
            if args.output_md:
                _write_md(results, args.collection, args.query, args.milvus_collection or "", args.output_md)
            return 0

        if not results:
            print("No results found.")
            return 0

        print(f"\n── {len(results)} result(s) for '{args.query}' in collection '{args.collection}' ──\n")
        for i, r in enumerate(results):
            print(f"  [{i+1}] {r['document_title']}")
            if r.get("author"):
                print(f"       Author: {r['author']}")
            ref = f"chunk {r['chunk_index']}"
            if r.get("reference_label"):
                ref += f", ref: {r['reference_label']}"
            if r.get("section"):
                ref += f", section: {r['section']}"
            if r.get("page_start"):
                p = str(r['page_start'])
                if r.get("page_end") and r['page_end'] != r['page_start']:
                    p += f"-{r['page_end']}"
                ref += f", page: {p}"
            print(f"       Reference: {ref}")
            signals = r.get("source_signals", [])
            sig_str = f" [{', '.join(signals)}]" if signals else ""
            print(f"       Match: {r['match_type']}{sig_str}  Score: {r['rank']}")
            if r.get("fts_rank") is not None:
                print(f"       FTS rank: {r['fts_rank']}  Vector score: {r.get('vector_score', 'N/A')}")
            print(f"       Fragment:")
            for line in r.get("highlighted_excerpt", "").split("\n"):
                print(f"         {line.strip()}")
            print()

        if args.output_md:
            _write_md(results, args.collection, args.query, args.milvus_collection or "", args.output_md)

        return 0

    finally:
        await close_pool(pool)


def _write_md(results: list[dict], collection: str, query: str, milvus: str, path: str) -> None:
    lines = [
        f"# Hybrid Search: {collection}",
        "",
        f"**Query**: {query}",
        f"**Collection**: {collection}",
        f"**Milvus**: {milvus or 'N/A'}",
        f"**Results**: {len(results)}",
        "",
        "| # | Title | Chunk | Type | Score | Source | Page | Ref |",
        "|---|-------|-------|------|-------:|--------|-----:|-----|",
    ]
    for i, r in enumerate(results):
        ref = r.get("reference_label", "")
        pg = f"{r.get('page_start', '')}-{r.get('page_end', '')}" if r.get("page_start") else ""
        sig = ", ".join(r.get("source_signals", []))
        lines.append(
            f"| {i+1} | {r.get('document_title', '')[:40]} "
            f"| {r.get('chunk_index', '')} "
            f"| {r.get('match_type', '')} "
            f"| {r.get('rank', 0)} "
            f"| {sig} "
            f"| {pg} "
            f"| {ref[:50]} |"
        )
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD: {path}")


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
