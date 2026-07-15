"""Read-only search probe for the safe Likutey Halajot page-first corpus."""
from __future__ import annotations

import argparse
import asyncio
import json

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-page", type=int)
    parser.add_argument("--query")
    parser.add_argument("--final-status")
    parser.add_argument("--unit-label")
    parser.add_argument("--document-part")
    args = parser.parse_args()
    if not any((args.pdf_page, args.query, args.final_status, args.unit_label, args.document_part)):
        parser.error("provide --pdf-page, --query, --final-status, --unit-label, or --document-part")

    if args.final_status:
        sql = "SELECT * FROM library_likutey_halajot_page_final_status_v2 WHERE final_page_status=%s ORDER BY pdf_page"
        params = (args.final_status,)
    elif args.pdf_page:
        sql = "SELECT * FROM library_likutey_halajot_search_ready_v2 WHERE pdf_page=%s"
        params = (args.pdf_page,)
    elif args.unit_label:
        sql = "SELECT * FROM library_likutey_halajot_search_ready_v2 WHERE unit_label ILIKE %s ORDER BY pdf_page"
        params = (f"%{args.unit_label}%",)
    elif args.document_part:
        sql = "SELECT * FROM library_likutey_halajot_search_ready_v2 WHERE document_part=%s ORDER BY pdf_page"
        params = (args.document_part,)
    else:
        sql = "SELECT * FROM library_likutey_halajot_search_ready_v2 WHERE normalized_text ILIKE %s ORDER BY pdf_page"
        params = (f"%{args.query}%",)
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            print(json.dumps(await cur.fetchall(), default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
