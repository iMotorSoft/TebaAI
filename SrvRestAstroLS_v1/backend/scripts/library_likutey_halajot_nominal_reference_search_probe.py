"""Read-only search probe for literal Likutey Halajot nominal references."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference")
    parser.add_argument("--normalized")
    parser.add_argument("--reference-kind")
    parser.add_argument("--note-number")
    parser.add_argument("--halakhah")
    parser.add_argument("--pdf-page", type=int)
    parser.add_argument("--query")
    args = parser.parse_args()
    clauses, params = [], []
    for column, value in (("surface_form", args.reference), ("normalized_reference_name", args.normalized),
                          ("reference_kind", args.reference_kind), ("visible_note_number", args.note_number),
                          ("halakhah_header_hint", args.halakhah)):
        if value:
            clauses.append(f"{column} ILIKE %s")
            params.append(f"%{value}%")
    if args.pdf_page:
        clauses.append("pdf_page=%s")
        params.append(args.pdf_page)
    if args.query:
        clauses.append("text_quote ILIKE %s")
        params.append(f"%{args.query}%")
    if not clauses:
        parser.error("provide at least one search option")
    sql = "SELECT * FROM library_likutey_halajot_nominal_reference_search_v1 WHERE " + " AND ".join(clauses) + " ORDER BY pdf_page,visible_note_number"
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            print(json.dumps(await cur.fetchall(), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
