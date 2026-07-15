"""Critical integrity checks for literal-only nominal reference metadata."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
              SELECT count(*) total,
               count(*) FILTER (WHERE position(r.surface_form in r.text_quote)=0) bad_surface_in_quote,
               count(*) FILTER (WHERE position(r.text_quote in n.text_quote)=0 AND position(r.text_quote in z.text_quote)=0) bad_quote_in_parent,
               count(*) FILTER (WHERE position(r.text_quote in p.literal_text)=0) bad_quote_in_page,
               count(*) FILTER (WHERE r.validation_status NOT IN ('validated','ambiguous_surface_form','needs_editorial_review')) bad_status
              FROM library_likutey_halajot_nominal_references_v1 r
              LEFT JOIN library_likutey_halajot_note_source_units_v1 n ON n.id=r.parent_note_source_unit_id
              LEFT JOIN library_likutey_halajot_fine_zones_v1 z ON z.id=r.parent_fine_zone_id
              JOIN library_content_nodes_v2 p ON p.page_anchor_id=r.page_anchor_id AND p.metadata_json->>'source_run_id'='likutey_halajot_page_first_v1'
            """)
            result = await cur.fetchone()
    print(json.dumps(result, default=str))
    if any(result[key] for key in ("bad_surface_in_quote", "bad_quote_in_parent", "bad_quote_in_page", "bad_status")):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
