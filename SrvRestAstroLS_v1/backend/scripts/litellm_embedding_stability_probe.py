#!/usr/bin/env python3
"""Diagnose LiteLLM embedding stability in isolation (no Milvus)."""

from __future__ import annotations

import argparse, asyncio, json, os, time
from pathlib import Path
from typing import Any

import httpx
import psycopg

PG_CONF = {
    "user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
    "host": os.environ.get("DB_PG_IP", "localhost"),
    "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai",
}


async def embed_one(text: str, client: httpx.AsyncClient) -> dict[str, Any]:
    from globalVar import LITELLM_BASE_URL, LITELLM_API_KEY
    start = time.time()
    try:
        r = await client.post(
            f"{LITELLM_BASE_URL}/v1/embeddings",
            headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
            json={"input": text[:3000], "model": "openai_text_embedding_3_small"},
            timeout=60,
        )
        elapsed = round(time.time() - start, 3)
        if r.status_code != 200:
            return {"success": False, "latency": elapsed, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
        data = r.json()
        vec = data["data"][0]["embedding"]
        return {"success": True, "latency": elapsed, "dim": len(vec)}
    except Exception as exc:
        return {"success": False, "latency": round(time.time() - start, 3), "error": str(exc)[:200]}


async def main() -> int:
    parser = argparse.ArgumentParser(description="LiteLLM Embedding Stability Probe")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"LiteLLM Embedding Stability Probe")
    print(f"  Limit: {args.limit}, Delay: {args.delay}s")

    # Load page texts
    conn = await psycopg.AsyncConnection.connect(**PG_CONF)
    texts = []
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT text FROM library_pages_v2 WHERE run_id = %s AND char_count > 0 ORDER BY page_number LIMIT %s",
            (args.run_id, args.limit),
        )
        async for r in cur:
            texts.append(r[0][:1000])
    await conn.close()
    print(f"  Texts loaded: {len(texts)}")

    if not texts:
        print("ERROR: No texts found"); return 1

    # Probe embeddings
    async with httpx.AsyncClient() as client:
        results = []
        for i, t in enumerate(texts):
            r = await embed_one(t, client)
            results.append(r)
            if (i + 1) % 10 == 0:
                ok = sum(1 for x in results if x["success"])
                fail = sum(1 for x in results if not x["success"])
                print(f"  {i+1}/{len(texts)}: {ok} ok, {fail} fail")
            await asyncio.sleep(args.delay)

    # Stats
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    latencies = [r["latency"] for r in successes]
    avg_lat = round(sum(latencies) / len(latencies), 3) if latencies else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else (max(latencies) if latencies else 0)
    dims = set(r["dim"] for r in successes if "dim" in r)

    report = {
        "total": len(results), "successes": len(successes), "failures": len(failures),
        "latency_avg": avg_lat, "latency_p95": p95, "latency_min": min(latencies) if latencies else 0,
        "latency_max": max(latencies) if latencies else 0,
        "dims": list(dims),
        "model": "openai_text_embedding_3_small",
        "errors": [r["error"] for r in failures[:10]],
    }
    (report_dir / "embedding_probe.json").write_text(json.dumps(report, indent=2))
    print(f"\n  Results: {report['successes']}/{report['total']} OK, {report['failures']} failures")
    print(f"  Latency: avg={avg_lat}s p95={p95}s dims={dims}")
    print(f"  Report: {report_dir / 'embedding_probe.json'}")
    return 0 if report["failures"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
