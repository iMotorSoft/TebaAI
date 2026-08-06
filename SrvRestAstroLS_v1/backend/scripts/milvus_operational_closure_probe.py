#!/usr/bin/env python3
"""Read-only Milvus closure probe; --safe-load changes only in-memory load state."""
from __future__ import annotations

import argparse, asyncio, json, time
from pathlib import Path

import httpx
from pymilvus import Collection, connections, utility

from globalVar import LITELLM_API_KEY, LITELLM_BASE_URL, MILVUS_CONNECT_TIMEOUT_SECONDS, MILVUS_HOST, MILVUS_PORT, RESEARCH_EMBEDDING_MODEL_ALIAS


async def embedding(query: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{LITELLM_BASE_URL}/v1/embeddings", headers={"Authorization": f"Bearer {LITELLM_API_KEY}"}, json={"model": RESEARCH_EMBEDDING_MODEL_ALIAS, "input": query})
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


async def run(args: argparse.Namespace) -> int:
    report = {"collection": args.collection, "scope": args.scope, "run_id": args.run_id, "safe_load_requested": args.safe_load, "connection_ok": False, "events": [], "search_ok_before": "skipped", "search_ok_after": "skipped"}
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=MILVUS_CONNECT_TIMEOUT_SECONDS)
    try:
        report["connection_ok"] = True
        if args.collection not in utility.list_collections():
            report["status"] = "COLLECTION_NOT_FOUND"; return finish(args, report)
        col = Collection(args.collection)
        report["load_state_before"] = str(utility.load_state(args.collection))
        report["num_entities"] = col.num_entities
        report["fields"] = [field.name for field in col.schema.fields]
        report["vector_field"] = next((field.name for field in col.schema.fields if field.name == "embedding"), None)
        if "Loaded" not in report["load_state_before"]:
            report["status"] = "COLLECTION_FOUND_NOT_LOADED"
            if not args.safe_load:
                report["recommendation"] = "OPTIONAL_SAFE_LOAD_PROBE_REQUIRED"; return finish(args, report)
            started = time.monotonic(); col.load(); report["events"].append("Collection.load called by explicit --safe-load")
            deadline = time.monotonic() + args.load_timeout
            while time.monotonic() < deadline and "Loaded" not in str(utility.load_state(args.collection)):
                await asyncio.sleep(0.2)
            report["safe_load_latency_ms"] = round((time.monotonic() - started) * 1000, 2)
        report["load_state_after"] = str(utility.load_state(args.collection))
        if "Loaded" not in report["load_state_after"]:
            report["status"] = "COLLECTION_FOUND_NOT_LOADED"; return finish(args, report)
        report["metadata_sample"] = col.query(expr="pk != ''", output_fields=[f.name for f in col.schema.fields if f.name != "embedding"], limit=args.limit)
        vector = await embedding(args.query)
        started = time.monotonic()
        hits = col.search(data=[vector], anns_field="embedding", param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=args.limit, output_fields=[f.name for f in col.schema.fields if f.name != "embedding"])
        report["search_latency_ms"] = round((time.monotonic() - started) * 1000, 2)
        report["search_hits"] = [{"id": hit.id, "distance": hit.distance, "fields": hit.entity.to_dict() if hit.entity else {}} for hit in hits[0]]
        report["search_ok_after"] = True; report["status"] = "SEARCH_OK"
    except Exception as exc:
        report["status"] = "SEARCH_FAILED"; report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        connections.disconnect("default")
    return finish(args, report)


def finish(args: argparse.Namespace, report: dict) -> int:
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({k: report.get(k) for k in ("collection", "status", "load_state_before", "load_state_after", "num_entities", "search_ok_after", "error")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="tebaai_breslov_bookqa_v2_kitzur_test_pages_v1")
    parser.add_argument("--scope", default="breslov_primary"); parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=5); parser.add_argument("--query", default="hitbodedut noche lugar apartado")
    parser.add_argument("--safe-load", action="store_true"); parser.add_argument("--load-timeout", type=float, default=20)
    parser.add_argument("--json-out", type=Path, required=True)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
