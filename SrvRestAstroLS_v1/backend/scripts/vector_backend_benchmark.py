#!/usr/bin/env python3
"""Comparable read-only retrieval benchmark over the V2 development corpus.

Embedding generation is deliberately outside the measured interval so that the
numbers compare retrieval stores, not LiteLLM network latency.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

import psycopg
from pymilvus import Collection, connections, utility

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from modules.library.vector_backends import query_embedding

QUERIES = [
    "punto bueno", "nekudá tová", "teshuvá vergüenza", "confesión delante de un estudioso de Torá",
    "hitbodedut noche lugar apartado", "Shabat alegría alma adicional", "pensamientos extraños plegaria",
    "temor perfecto ángeles", "pureza sexual lenguaje sagrado", "tzitzit protege pecado sexual",
    "Keter EHIéH arrepentimiento",
]


def pg_config():
    return {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
            "host": os.environ.get("DB_PG_IP", "localhost"), "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}


def percentile(values, fraction):
    return round(sorted(values)[max(0, min(len(values) - 1, int((len(values) - 1) * fraction)))], 3)


def vector_literal(vector):
    return "[" + ",".join(map(str, vector)) + "]"


async def main(args):
    vectors = {query: await query_embedding(query) for query in QUERIES}
    connections.connect(alias="default", host=os.environ.get("TEBAAI_MILVUS_HOST", "127.0.0.1"), port=os.environ.get("TEBAAI_MILVUS_PORT", "19530"), timeout=10)
    collection = Collection(args.collection)
    if "Loaded" not in str(utility.load_state(args.collection)):
        collection.load()
    output = []
    with psycopg.connect(**pg_config()) as pg:
        for top_k in args.top_k:
            for query in QUERIES:
                for backend in ("sql_page", "pgvector", "milvus", "auto"):
                    timings, counts, pages, errors = [], [], [], []
                    for iteration in range(args.warmup + args.iterations):
                        started = time.perf_counter()
                        try:
                            if backend == "sql_page":
                                token = query.split()[0].lower()
                                with pg.cursor() as cursor:
                                    cursor.execute("SELECT page_number FROM library_pages_v2 WHERE run_id=%s AND lower(text) LIKE %s LIMIT %s", (args.run_id, f"%{token}%", top_k))
                                    rows = cursor.fetchall()
                                    hit_pages = [row[0] for row in rows]
                            elif backend == "pgvector":
                                with pg.cursor() as cursor:
                                    cursor.execute(
                                        "SELECT page FROM library_vector_embeddings_v2_dev WHERE knowledge_scope_code=%s AND run_id=%s::uuid AND embedding <=> %s::vector IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s",
                                        (args.scope_code, args.run_id, vector_literal(vectors[query]), vector_literal(vectors[query]), top_k),
                                    )
                                    hit_pages = [row[0] for row in cursor.fetchall()]
                            else:
                                hits = collection.search(
                                    data=[vectors[query]], anns_field="embedding",
                                    param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=top_k,
                                    expr=f'knowledge_scope_code == "{args.scope_code}" and run_id == "{args.run_id}"',
                                    output_fields=["page"],
                                )
                                hit_pages = [hit.entity.get("page") for hit in hits[0]]
                            elapsed = (time.perf_counter() - started) * 1000
                            if iteration >= args.warmup:
                                timings.append(elapsed); counts.append(len(hit_pages)); pages.extend(hit_pages)
                        except Exception as exc:
                            if iteration >= args.warmup:
                                errors.append(f"{type(exc).__name__}: {exc}")
                    output.append({
                        "backend": backend, "backend_used": "milvus" if backend == "auto" else backend,
                        "query": query, "top_k": top_k, "latencies_ms": timings,
                        "p50_latency_ms": percentile(timings, .5) if timings else None,
                        "p95_latency_ms": percentile(timings, .95) if timings else None,
                        "success_rate": round(len(timings) / args.iterations, 3),
                        "error_rate": round(len(errors) / args.iterations, 3),
                        "hit_count": round(statistics.mean(counts), 2) if counts else 0,
                        "unique_pages": len(set(pages)), "errors": errors,
                    })
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps({"collection": args.collection, "run_id": args.run_id, "scope": args.scope_code, "warmup": args.warmup, "iterations": args.iterations, "results": output}, ensure_ascii=False, indent=2))
    print(json.dumps({"results": len(output), "backends": ["milvus", "pgvector", "auto", "sql_page"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="tebaai_breslov_chunks_v2_dev")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope-code", default="breslov_test")
    parser.add_argument("--top-k", default="5,10,20")
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--json-out", type=Path, required=True)
    parsed = parser.parse_args(); parsed.top_k = [int(value) for value in parsed.top_k.split(",")]
    asyncio.run(main(parsed))
