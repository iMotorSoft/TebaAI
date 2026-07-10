#!/usr/bin/env python3
"""Milvus dummy insert probe: test Milvus without LiteLLM."""

from __future__ import annotations

import argparse, json, math, random, sys, time
from pathlib import Path
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

PROHIBITED = {"tebaai_breslov_chunks_v1", "tebaai_breslov_test_chunks_v1"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Milvus Dummy Insert Probe")
    parser.add_argument("--collection", default="tebaai_breslov_bookqa_v2_dummy_insert_probe_v1")
    parser.add_argument("--dim", type=int, default=1536)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--drop-after", action="store_true")
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()

    if args.collection in PROHIBITED:
        print(f"ERROR: Cannot use prohibited collection '{args.collection}'"); return 1

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"Milvus Dummy Insert Probe")
    print(f"  Collection: {args.collection}")
    print(f"  Dim: {args.dim}, Count: {args.count}, Batch: {args.batch_size}")

    connections.connect(alias="default", host="127.0.0.1", port=19530, timeout=30)

    if utility.has_collection(args.collection):
        utility.drop_collection(args.collection)

    schema = CollectionSchema([
        FieldSchema("pk", DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema("vec", DataType.FLOAT_VECTOR, dim=args.dim),
    ])
    col = Collection(args.collection, schema)
    print("  Created collection")

    # Insert batches
    total_inserted = 0
    failures = 0
    latencies = []
    batches = math.ceil(args.count / args.batch_size)

    for b in range(batches):
        batch_size = min(args.batch_size, args.count - total_inserted)
        entities = []
        for i in range(batch_size):
            idx = total_inserted + i
            entities.append({
                "pk": f"dummy_{idx}",
                "vec": [random.random() for _ in range(args.dim)],
            })
        start = time.time()
        try:
            col.insert(entities)
            elapsed = round(time.time() - start, 3)
            latencies.append(elapsed)
            total_inserted += batch_size
        except Exception as exc:
            failures += batch_size
            print(f"  Batch {b+1} FAIL: {exc}")
            break
        if (b + 1) % 5 == 0:
            print(f"  Batch {b+1}/{batches}: {total_inserted} inserted")

    # Flush and index
    col.flush()
    col.create_index("vec", {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}})
    print(f"  Index created")

    # Search test
    col.load()
    query = [random.random() for _ in range(args.dim)]
    start = time.time()
    results = col.search(data=[query], anns_field="vec", param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=5)
    search_elapsed = round(time.time() - start, 3)

    final_count = col.num_entities
    col.release()

    dropped_after = False
    if args.drop_after:
        utility.drop_collection(args.collection)
        dropped_after = True
        print("  Dropped collection")

    connections.disconnect("default")

    report = {
        "collection": args.collection, "dim": args.dim,
        "requested_count": args.count, "batch_size": args.batch_size,
        "inserted": total_inserted, "failures": failures,
        "final_count": final_count,
        "latency_avg": round(sum(latencies) / len(latencies), 3) if latencies else 0,
        "latency_min": min(latencies) if latencies else 0,
        "latency_max": max(latencies) if latencies else 0,
        "latencies": latencies[:20],
        "search_elapsed": search_elapsed,
        "search_results": len(results[0]) if results else 0,
        "search_distances": [round(h.distance, 4) for h in results[0]] if results and results[0] else [],
        "dropped_after": dropped_after,
    }
    print(f"\n  Inserted: {total_inserted}/{args.count} in {batches} batches")
    print(f"  Failures: {failures}")
    print(f"  Avg insert latency: {report['latency_avg']}s")
    print(f"  Search latency: {search_elapsed}s")
    print(f"  Final count: {final_count}")

    (report_dir / "milvus_dummy_insert_probe.json").write_text(json.dumps(report, indent=2))
    print(f"  Report: {report_dir / 'milvus_dummy_insert_probe.json'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
