#!/usr/bin/env python3
"""
Cleanup Milvus duplicate entities created by repair re-run.

Identifies 1828 duplicate PKs in tebaai_breslov_chunks_v1
and removes the ones NOT referenced by PG milvus_primary_key.

Usage:
  # Dry-run (default): identify duplicates, backup PKs to delete
  uv run python -m scripts.cleanup_milvus_duplicates --dry-run

  # Apply: delete duplicates from Milvus
  uv run python -m scripts.cleanup_milvus_duplicates --apply
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from typing import Any

MILVUS_PROD_COLL = "tebaai_breslov_chunks_v1"
AFFECTED_PREFIXES = ["56ddcc3b", "43ba4f4b", "76f2adbc"]


def find_duplicates() -> dict[str, list[str]]:
    """Find chunk_ids with >1 PK in Milvus for affected docs."""
    from pymilvus import Collection, connections

    connections.connect(host="127.0.0.1", port=19530)
    c = Collection(MILVUS_PROD_COLL)
    c.load()

    by_chunk: dict[str, list[str]] = defaultdict(list)
    for prefix in AFFECTED_PREFIXES:
        results = c.query(
            expr=f'document_id like "{prefix}%"',
            output_fields=["pk", "chunk_id"],
            limit=16384,
        )
        for r in results:
            cid = r.get("chunk_id", "")
            pk = r.get("pk", "")
            if cid:
                by_chunk[cid].append(pk)

    c.release()
    connections.disconnect("default")
    return {k: v for k, v in by_chunk.items() if len(v) > 1}


async def get_pg_pks(pool, chunk_ids: list[str]) -> dict[str, str]:
    """Get milvus_primary_key from PG for given chunk_ids."""
    pg_pks: dict[str, str] = {}
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for i in range(0, len(chunk_ids), 100):
                batch = chunk_ids[i : i + 100]
                placeholders = ",".join(["%s"] * len(batch))
                await cur.execute(
                    f"""
                    SELECT c.id::text, e.milvus_primary_key
                    FROM library_chunk_embeddings e
                    JOIN library_document_chunks c ON c.id = e.chunk_id
                    WHERE c.id::text IN ({placeholders})
                      AND e.status IS DISTINCT FROM 'stale'
                    """,
                    batch,
                )
                for r in await cur.fetchall():
                    pg_pks[r["id"]] = r["milvus_primary_key"]
    return pg_pks


def classify_duplicates(
    dups: dict[str, list[str]], pg_pks: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Return (pks_to_delete, pks_to_keep)."""
    to_delete: list[str] = []
    to_keep: set[str] = set()
    matched = 0
    fallback = 0

    for cid, pks in dups.items():
        pg_pk = pg_pks.get(cid)
        found = False
        for pk in pks:
            if pg_pk and pk == pg_pk:
                to_keep.add(pk)
                found = True
                matched += 1
            else:
                to_delete.append(pk)
        if not found and pks:
            to_keep.add(pks[0])
            to_delete = [p for p in to_delete if p != pks[0]]
            fallback += 1

    print(f"  PKs matching PG: {matched}")
    print(f"  PKs fallback (no PG match): {fallback}")
    print(f"  PKs to DELETE: {len(to_delete)}")
    print(f"  PKs to KEEP: {len(to_keep)}")
    return to_delete, list(to_keep)


def backup_pks(to_delete: list[str], to_keep: list[str], path: str) -> None:
    backup = {
        "timestamp": time.time(),
        "collection": MILVUS_PROD_COLL,
        "pks_to_delete": to_delete,
        "pks_to_keep": to_keep,
        "count_delete": len(to_delete),
        "count_keep": len(to_keep),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2)
    print(f"  ✅ Backup: {len(to_delete)} PKs to delete → {path}")


def execute_delete(pks: list[str]) -> dict[str, Any]:
    """Delete PKs from Milvus in batches."""
    from pymilvus import Collection, connections

    connections.connect(host="127.0.0.1", port=19530)
    c = Collection(MILVUS_PROD_COLL)
    c.load()

    result = {"total": len(pks), "deleted": 0, "errors": []}

    for i in range(0, len(pks), 100):
        batch = pks[i : i + 100]
        pk_list = json.dumps(batch)
        try:
            expr = f'pk in {pk_list}'
            c.delete(expr)
            result["deleted"] += len(batch)
        except Exception as exc:
            err = f"Delete failed for batch {i//100+1}: {exc}"
            print(f"    ❌ {err}")
            result["errors"].append(err)

    result["final_num_entities"] = c.num_entities
    c.release()
    connections.disconnect("default")
    return result


async def validate(pool) -> dict[str, Any]:
    """Validate Milvus state after cleanup."""
    from pymilvus import Collection, connections

    result: dict[str, Any] = {}

    connections.connect(host="127.0.0.1", port=19530)
    c = Collection(MILVUS_PROD_COLL)
    c.load()
    result["milvus_num_entities"] = c.num_entities

    # Unique chunks
    all_results = c.query(expr='pk != ""', output_fields=["pk", "chunk_id", "document_id", "source_type"], limit=15000)
    seen_chunks = set()
    doc_counts = {}
    for r in all_results:
        cid = r.get("chunk_id", "")
        did = r.get("document_id", "")[:12]
        if cid:
            seen_chunks.add(cid)
        doc_counts[did] = doc_counts.get(did, 0) + 1
    result["unique_chunks"] = len(seen_chunks)
    result["by_document"] = doc_counts

    # Duplicates check
    chunk_pks = defaultdict(list)
    for r in all_results:
        cid = r.get("chunk_id", "")
        pk = r.get("pk", "")
        if cid:
            chunk_pks[cid].append(pk)
    dups_final = {k: v for k, v in chunk_pks.items() if len(v) > 1}
    result["duplicates_remaining"] = len(dups_final)

    # Stale
    stale = c.query(expr='source_type == ""', output_fields=["pk"], limit=10000)
    result["stale_empty_source_type"] = len(stale)

    c.release()
    connections.disconnect("default")

    # PG counts
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            total_pg = 0
            for did in ["56ddcc3b-8296-4832-ac95-2bfe032cd4c6",
                         "43ba4f4b-d3ee-49b6-8d09-dfa152379893",
                         "76f2adbc-b79a-4432-9ea5-521a337a5502"]:
                await cur.execute(
                    "SELECT count(*) FROM library_chunk_embeddings e "
                    "JOIN library_document_chunks c ON c.id = e.chunk_id "
                    "WHERE c.document_id = %s AND e.status IS DISTINCT FROM 'stale'",
                    (did,),
                )
                total_pg += (await cur.fetchone())["count"]
            result["pg_active_embeddings"] = total_pg

    result["match"] = result.get("unique_chunks", 0) == result.get("pg_active_embeddings", 0) \
        if "unique_chunks" in result else False

    return result


async def main():
    parser = argparse.ArgumentParser(description="Cleanup Milvus duplicate entities")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry-run (default)")
    parser.add_argument("--apply", action="store_true", help="Execute delete")
    args = parser.parse_args()

    is_apply = args.apply
    mode = "APPLY" if is_apply else "DRY-RUN"

    print(f"\n{'='*60}")
    print(f"  CLEANUP MILVUS DUPLICATES — {mode}")
    print(f"{'='*60}")

    # 1. Find duplicates
    print("\n[1/4] Finding duplicate chunk_ids in Milvus...")
    dups = find_duplicates()
    print(f"  → {len(dups)} duplicated chunk_ids found")
    if not dups:
        print("  ✅ No duplicates found. Nothing to clean.")
        return 0

    # 2. Get PG milvus_primary_key
    print("\n[2/4] Querying PG milvus_primary_key...")
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        dup_ids = list(dups.keys())
        pg_pks = await get_pg_pks(pool, dup_ids)
        print(f"  → {len(pg_pks)} PG records found")

        # 3. Classify
        print("\n[3/4] Classifying PKs to keep/delete...")
        to_delete, to_keep = classify_duplicates(dups, pg_pks)

        if not to_delete:
            print("  ✅ Nothing to delete.")
            return 0

        # Backup
        backup_pks(to_delete, to_keep, "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/cleanup_duplicates_pks.json")

        if is_apply:
            # Confirm
            confirm = input(f"\n  Delete {len(to_delete)} PKs from Milvus prod? (yes/N): ").strip().lower()
            if confirm != "yes":
                print("  ❌ Cancelado.")
                return 1

            print("\n[4/4] Executing delete...")
            del_result = execute_delete(to_delete)
            print(f"  Deleted: {del_result['deleted']}/{del_result['total']}")
            if del_result["errors"]:
                print(f"  Errors: {len(del_result['errors'])}")
                for e in del_result["errors"][:3]:
                    print(f"    ❌ {e}")

            # Validate
            print("\n  Validating post-cleanup...")
            val = await validate(pool)
            print(f"  Milvus num_entities: {val.get('milvus_num_entities', '?')}")
            print(f"  Unique chunks: {val.get('unique_chunks', '?')}")
            print(f"  Duplicates remaining: {val.get('duplicates_remaining', '?')}")
            print(f"  Stale source_type='': {val.get('stale_empty_source_type', '?')}")
            print(f"  PG↔Milvus match: {'✅' if val.get('match') else '❌'}")

            if val.get("duplicates_remaining", 1) == 0 and val.get("match"):
                print(f"\n  ✅ Cleanup completed successfully.")
                print(f"  Milvus prod: {val.get('milvus_num_entities', '?')} entities, "
                      f"{val.get('unique_chunks', '?')} unique chunks, "
                      f"0 duplicates.")
                return 0
            else:
                print(f"\n  ⚠️  Cleanup completed with issues. Review above.")
                return 1
        else:
            print("\n[4/4] Dry-run complete — no writes.")
            print(f"\n  📊 Summary:")
            print(f"  PKs to DELETE: {len(to_delete)}")
            print(f"  PKs to KEEP: {len(to_keep)}")
            print(f"  Backup: data/reports/breslov/2026-07-08-milvus-relation-qa/backups/cleanup_duplicates_pks.json")
            print(f"  Expected final num_entities: 5102")
            print(f"  Expected final duplicates: 0")
            print(f"\n  To execute: uv run python -m scripts.cleanup_milvus_duplicates --apply")
            return 0

    finally:
        await close_pool(pool)


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
