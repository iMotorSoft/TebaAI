#! /usr/bin/env python3
"""
CLI: Full Text Search over library document chunks.

Usage:
    uv run python -m scripts.search_library_text --collection breslov --query "plegaria"

    uv run python -m scripts.search_library_text --collection breslov --query "Rebe Najman" --mode auto

    uv run python -m scripts.search_library_text --collection breslov --query "la potencia de la plegaria" --mode phrase --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search library document chunks by text.")
    parser.add_argument("--collection", required=True, help="Collection code to search")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--mode", default="auto", choices=["auto", "fts", "phrase", "trigram"], help="Search mode")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--language", default="es", choices=["es", "en", "he"], help="Document language")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from modules.library.text_search import search_chunks_text

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
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

            results = await search_chunks_text(
                conn,
                collection_code=args.collection,
                query=args.query,
                top_k=args.top_k,
                mode=args.mode,
                language=args.language,
            )

        if args.json:
            clean = []
            for r in results:
                clean.append({k: v for k, v in r.items() if k in (
                    "document_id", "document_title", "author", "collection_code",
                    "chunk_id", "chunk_index", "match_type", "rank",
                    "plain_excerpt", "highlighted_excerpt",
                )})
            print(json.dumps(clean, indent=2, ensure_ascii=False))
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
            if r.get("chapter"):
                ref += f", chapter: {r['chapter']}"
            if r.get("page_start"):
                p = str(r['page_start'])
                if r.get("page_end") and r['page_end'] != r['page_start']:
                    p += f"-{r['page_end']}"
                ref += f", page: {p}"
            print(f"       Reference: {ref}")
            print(f"       Match: {r['match_type']}  Score: {r['rank']}")
            print(f"       Fragment:")
            for line in r.get("highlighted_excerpt", "").split("\n"):
                print(f"         {line.strip()}")
            print()

        return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
