"""Read-only safety checks for Likutey Halajot structural detector V1."""
from __future__ import annotations
import asyncio, json
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

async def main() -> None:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("select count(*) total, count(*) filter(where has_text) text_pages, count(*) filter(where is_blank) blanks, count(*) filter(where searchable_by_literal) literals from library_likutey_halajot_page_final_status_v2")
            coverage = await cur.fetchone()
            await cur.execute("select count(*) bad from library_page_structural_classifications_v2 where source_run_id='likutey_halajot_structural_detector_v1_20260714' and classification_action='promote' and (confidence < .85 or jsonb_array_length(evidence_text)=0)")
            unsafe = await cur.fetchone()
            await cur.execute("select document_part,count(*) from library_likutey_halajot_page_final_status_v2 group by document_part order by document_part")
            parts = await cur.fetchall()
            result = {"coverage": coverage, "unsafe_promotions": unsafe["bad"], "parts": parts,
                      "pass": coverage == {"total":284,"text_pages":268,"blanks":16,"literals":268} and unsafe["bad"] == 0}
            print(json.dumps(result, ensure_ascii=False, default=str))
            if not result["pass"]: raise SystemExit(1)
asyncio.run(main())
