"""Reproducibly seed canonical ContentUnit/ContentNode evidence from a V2 page run.

This is intentionally a migration adapter, not a PDF layout parser: every V2 page
becomes one primary node and one anchored semantic boundary. Rich satellite parsing
must be supplied by a layout-aware source-specific ingestion profile.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.investigative_model import normalize_literal, stable_hash


async def migrate(run_id: UUID, apply: bool) -> dict[str, object]:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT document_id FROM library_ingestion_runs_v2 WHERE run_id=%s", (run_id,))
            run = await cur.fetchone()
            if not run:
                raise ValueError(f"unknown run_id: {run_id}")
            document_id = run["document_id"]
            await cur.execute("SELECT page_id, page_number, text, confidence FROM library_pages_v2 WHERE run_id=%s ORDER BY page_number", (run_id,))
            pages = await cur.fetchall()
            result: dict[str, object] = {"run_id": str(run_id), "document_id": str(document_id), "pages": len(pages), "created_nodes": 0, "dry_run": not apply}
            if not apply:
                return result
            await cur.execute("""INSERT INTO library_content_units_v2
                (document_id, unit_type, canonical_ref, title, order_index, language_original, source_run_id, metadata_json)
                VALUES (%s,'work',%s,'Migración V2: documento completo',0,'es',%s,jsonb_build_object('migration_adapter','v2_page'))
                ON CONFLICT (document_id, canonical_ref) WHERE canonical_ref IS NOT NULL DO UPDATE SET title=EXCLUDED.title
                RETURNING content_unit_id""", (document_id, f"v2-run:{run_id}", run_id))
            root = (await cur.fetchone())["content_unit_id"]
            for index, page in enumerate(pages, start=1):
                text = page["text"]
                is_blank = not text.strip()
                await cur.execute("""INSERT INTO library_page_anchors_v2
                    (source_file_id, document_id, edition_id, pdf_page_number, legacy_page_id, confidence, metadata_json)
                    VALUES (%s,%s,'legacy-v2',%s,%s,%s,jsonb_build_object('migration_adapter','v2_page'))
                    ON CONFLICT (document_id,pdf_page_number,edition_id) DO UPDATE SET legacy_page_id=EXCLUDED.legacy_page_id
                    RETURNING page_anchor_id""", (document_id, document_id, page["page_number"], page["page_id"], page["confidence"] or 0.8))
                anchor = (await cur.fetchone())["page_anchor_id"]
                await cur.execute("""INSERT INTO library_content_units_v2
                    (parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,language_original,source_run_id,metadata_json)
                    VALUES (%s,%s,'page',%s,%s,%s,'es',%s,jsonb_build_object('migration_adapter','v2_page'))
                    ON CONFLICT (document_id,canonical_ref) WHERE canonical_ref IS NOT NULL DO UPDATE SET title=EXCLUDED.title
                    RETURNING content_unit_id""", (root, document_id, f"v2-run:{run_id}:pdf:{page['page_number']}", f"PDF página {page['page_number']}", index, run_id))
                unit = (await cur.fetchone())["content_unit_id"]
                content_type = "blank" if is_blank else "spanish_main_text"
                authority = "non_evidential" if is_blank else "secondary_explanatory"
                await cur.execute("""INSERT INTO library_content_nodes_v2
                    (content_unit_id,node_role,content_type,authority_level,language,script,literal_text,normalized_text,literal_hash,page_anchor_id,node_order,citable,source_run_id,metadata_json)
                    SELECT %s,'primary',%s,%s,'es','latin',%s,%s,%s,%s,1,%s,%s,jsonb_build_object('migration_adapter','v2_page')
                    WHERE NOT EXISTS (SELECT 1 FROM library_content_nodes_v2 WHERE content_unit_id=%s AND node_order=1 AND source_run_id=%s)
                    RETURNING content_node_id""", (unit, content_type, authority, text, normalize_literal(text), stable_hash(text), anchor, not is_blank, run_id, unit, run_id))
                node = await cur.fetchone()
                if node:
                    node_id = node["content_node_id"]
                    if not is_blank:
                        normalized = normalize_literal(text)
                        await cur.execute("""INSERT INTO library_literal_spans_v2
                            (content_node_id,start_char,end_char,literal_text,normalized_text,hash,metadata_json)
                            VALUES (%s,0,%s,%s,%s,%s,jsonb_build_object('migration_adapter','full_node_span'))""",
                            (node_id, len(text), text, normalized, stable_hash(text)))
                        await cur.execute("""INSERT INTO library_semantic_units_v2
                            (content_node_id,literal_span_id,text,text_hash,chunk_order,chunker_name,chunker_config_json,language,source_run_id,metadata_json)
                            SELECT %s,literal_span_id,%s,%s,1,'v2_page_adapter',jsonb_build_object('crosses_page',false),'es',%s,jsonb_build_object('migration_adapter','whole_page')
                            FROM library_literal_spans_v2 WHERE content_node_id=%s AND start_char=0""",
                            (node_id, normalized, stable_hash(text), run_id, node_id))
                    result["created_nodes"] = int(result["created_nodes"]) + 1
            await conn.commit()
            return result

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(migrate(args.run_id, args.apply)), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
