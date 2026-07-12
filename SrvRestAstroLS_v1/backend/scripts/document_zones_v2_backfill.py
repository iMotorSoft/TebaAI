#!/usr/bin/env python3
"""Backfill V2 pages into library_document_chunks as canonical zones.

The existing library_document_chunks table already supports zone classification
via block_type and evidence_role. This script backfills page-level zones for
documents ingested via Ingesta V2 that only exist in library_pages_v2.

Strategy:
  - One chunk per page with text
  - block_type = 'main_text'
  - evidence_role = 'primary_evidence'
  - citable = true
  - chunk_uid = '{run_id}:page:{page_number}'
  - page_start = page_end = page_number

Usage:
  uv run python scripts/document_zones_v2_backfill.py \
    --run-id 492acd8d-06bd-42ac-a511-f3ec52f97bb3 \
    --document-id 27f175ea-bc80-4161-b1fa-bf5c8b8a3f25 \
    --collection-id e53f40ac-98a8-43f4-bfa6-e0b9e6ffed8c \
    --scope breslov_primary \
    --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import psycopg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PG = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
      "host": os.environ.get("DB_PG_IP", "localhost"),
      "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}


async def backfill_zones(args: argparse.Namespace) -> dict[str, Any]:
    conn = await psycopg.AsyncConnection.connect(**PG)
    await conn.execute("SET search_path TO public")
    report: dict[str, Any] = {
        "status": "STARTED",
        "run_id": args.run_id,
        "scope": args.scope,
        "document_id": args.document_id,
        "collection_id": args.collection_id,
    }

    # Fetch pages with text — use separate session
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT page_number, text, char_count FROM library_pages_v2 WHERE run_id = %s AND char_count > 0 ORDER BY page_number",
            (args.run_id,),
        )
        pages = await cur.fetchall()
    report["pages_with_text"] = len(pages)

    # Count existing chunks
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM library_document_chunks WHERE document_id = %s",
            (args.document_id,),
        )
        existing = (await cur.fetchone())[0]
    report["existing_chunks"] = existing

    if args.dry_run:
        await conn.close()
        return {**report, "status": "DRY_RUN", "chunks_to_create": len(pages)}

    inserted = 0
    skipped = 0
    errors = []

    for row in pages:
        page_number = row[0]
        text = row[1]
        char_count = row[2]

        chunk_uid = f"{args.run_id}:page:{page_number}"
        content_sha256 = hashlib.sha256(text.encode()).hexdigest()

        await conn.execute("SAVEPOINT sp_zone_" + str(page_number))

        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id FROM library_document_chunks WHERE chunk_uid = %s",
                    (chunk_uid,),
                )
                if await cur.fetchone():
                    await conn.execute("RELEASE SAVEPOINT sp_zone_" + str(page_number))
                    skipped += 1
                    continue

            chunk_id = str(uuid.uuid4())
            text_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO library_document_chunks
                    (id, document_id, document_text_id, collection_id,
                     chunk_index, chunk_uid, language,
                     content, content_sha256, content_length,
                     page_start, page_end,
                     block_type, evidence_role, citable,
                     metadata, bibliographic_metadata,
                     is_empty)
                VALUES
                    (%s, %s, %s, %s,
                     %s, %s, %s,
                     %s, %s, %s,
                     %s, %s,
                     %s, %s, %s,
                     %s::jsonb, %s::jsonb,
                     %s)
            """, (
                chunk_id, args.document_id, text_id, args.collection_id,
                page_number, chunk_uid, "es",
                text, content_sha256, char_count,
                page_number, page_number,
                "main_text", "primary_evidence", True,
                '{}',
                json.dumps({"source": "v2_zone_backfill", "run_id": args.run_id, "scope": args.scope}),
                False,
            ))
            await conn.execute("RELEASE SAVEPOINT sp_zone_" + str(page_number))
            inserted += 1
        except Exception as e:
            await conn.execute("ROLLBACK TO SAVEPOINT sp_zone_" + str(page_number))
            errors.append(f"page_{page_number}: {e}")
            continue

        if inserted % 100 == 0:
            print(f"  ... {inserted} chunks inserted")

    await conn.commit()
    await conn.close()

    report["status"] = "BACKFILL_OK" if not errors else "BACKFILL_PARTIAL"
    report["inserted"] = inserted
    report["skipped"] = skipped
    report["errors"] = errors
    report["error_count"] = len(errors)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill V2 pages as canonical zones")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--scope", default="breslov_primary")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(backfill_zones(args))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
