#! /usr/bin/env python3
"""
CLI: Search Milvus vector index.

Usage:
    uv run python -m scripts.search_milvus \\
        --collection breslov \\
        --milvus-collection tebaai_breslov_chunks_v1 \\
        --query "plegaria y emuná" \\
        --top-k 5
"""

from __future__ import annotations

import argparse
import sys

import globalVar as gv
from infrastructure.milvus.client import ensure_collection, search_vectors
from modules.embeddings.client import embed_text


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Milvus vector index.")
    parser.add_argument("--collection", default="breslov", help="Collection code filter")
    parser.add_argument("--milvus-collection", default=gv.MILVUS_COLLECTION_BRESLOV, help="Milvus collection name")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args()

    # Ensure collection exists
    ensure_collection(args.milvus_collection, dimension=gv.EMBEDDINGS_DIMENSION)

    # Embed query
    print(f"Embedding query: {args.query}")
    query_vec = embed_text(args.query)
    print(f"Query dimension: {len(query_vec)}")

    # Search
    expr = f'collection_code == "{args.collection}"'
    results = search_vectors(
        collection_name=args.milvus_collection,
        query_embedding=query_vec,
        top_k=args.top_k,
        expr=expr,
    )

    print()
    if not results:
        print("No results found.")
        return 0

    print(f"── Top {len(results)} results ──")
    for i, hit in enumerate(results):
        print(f"\n  [{i+1}] Score: {hit['distance']:.4f}")
        print(f"      Title:     {hit.get('title', 'N/A')}")
        print(f"      Document:  {hit.get('document_id', 'N/A')}")
        print(f"      Chunk:     {hit.get('chunk_id', 'N/A')} (index {hit.get('chunk_index', 'N/A')})")
        preview = hit.get("content_preview", "")
        print(f"      Preview:   {preview[:150]}..." if len(preview) > 150 else f"      Preview:   {preview}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
