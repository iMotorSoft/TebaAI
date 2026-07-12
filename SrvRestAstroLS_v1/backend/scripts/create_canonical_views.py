#!/usr/bin/env python3
"""Create canonical document model views for evidence, search, and relation units."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import psycopg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PG = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"],
      "host": os.environ.get("DB_PG_IP", "localhost"),
      "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}

VIEWS = [
    # 1. Citable evidence
    """
    CREATE OR REPLACE VIEW library_citable_evidence_v2 AS
    SELECT
        c.id AS chunk_id,
        c.document_id,
        d.title AS document_title,
        d.document_code,
        d.status AS document_status,
        c.chunk_uid,
        c.chunk_index,
        c.language,
        c.content AS literal_text,
        c.content_sha256 AS text_hash,
        c.page_start,
        c.page_end,
        c.block_type AS zone_type,
        c.block_subtype AS zone_subtype,
        c.evidence_role,
        c.citable,
        c.section_title,
        c.node_path,
        c.metadata,
        c.bibliographic_metadata
    FROM library_document_chunks c
    JOIN library_documents d ON d.id = c.document_id
    WHERE c.citable = true
      AND c.content IS NOT NULL
      AND length(trim(c.content)) > 0
    """,

    # 2. Search units
    """
    CREATE OR REPLACE VIEW library_search_units_v2 AS
    SELECT
        c.id AS unit_id,
        c.document_id,
        d.title,
        c.chunk_uid,
        c.chunk_index,
        c.language,
        c.content AS search_text,
        c.page_start,
        c.page_end,
        c.block_type,
        c.evidence_role,
        c.citable,
        c.is_empty,
        c.paragraph_index,
        c.section_title,
        c.node_path
    FROM library_document_chunks c
    JOIN library_documents d ON d.id = c.document_id
    """,

    # 3. Relation units
    """
    CREATE OR REPLACE VIEW library_relation_units_v2 AS
    SELECT
        c.id AS unit_id,
        c.document_id,
        d.title,
        c.chunk_uid,
        c.chunk_index,
        c.language,
        c.content,
        c.page_start,
        c.page_end,
        c.block_type AS zone_type,
        c.evidence_role,
        c.section_title,
        c.node_path,
        s.section_id,
        s.section_type,
        s.path AS section_path
    FROM library_document_chunks c
    JOIN library_documents d ON d.id = c.document_id
    LEFT JOIN library_sections_v2 s ON s.document_id = c.document_id
        AND s.page_start <= COALESCE(c.page_start, 0)
        AND (s.page_end IS NULL OR s.page_end >= COALESCE(c.page_end, 0))
    """,

    # 4. Page zones (for page-based documents)
    """
    CREATE OR REPLACE VIEW library_page_zones_v2 AS
    SELECT
        p.page_id AS zone_id,
        p.document_id,
        d.title AS document_title,
        p.run_id,
        p.page_number,
        p.text AS literal_text,
        p.char_count,
        p.extraction_method,
        p.confidence,
        p.layout_notes,
        'main_text'::text AS zone_type,
        'page'::text AS zone_source
    FROM library_pages_v2 p
    JOIN library_documents d ON d.id = p.document_id
    WHERE p.char_count > 0
    """,
]


async def main():
    print("Creating canonical document model views...")
    conn = await psycopg.AsyncConnection.connect(**PG)
    
    for i, sql in enumerate(VIEWS, 1):
        try:
            await conn.execute(sql)
            await conn.commit()
            print(f"  [OK] View {i} created")
        except Exception as e:
            await conn.rollback()
            print(f"  [FAIL] View {i}: {e}")
    
    # Verify
    cur = await conn.execute("""
        SELECT table_name FROM information_schema.views 
        WHERE table_schema = 'public' AND table_name LIKE '%v2'
        ORDER BY table_name
    """)
    rows = await cur.fetchall()
    print(f"\n  Total views: {len(rows)}")
    for r in rows:
        cur2 = await conn.execute(f"SELECT COUNT(*) FROM {r[0]}")
        count = (await cur2.fetchone())[0]
        print(f"    {r[0]:40s} rows: {count}")
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
