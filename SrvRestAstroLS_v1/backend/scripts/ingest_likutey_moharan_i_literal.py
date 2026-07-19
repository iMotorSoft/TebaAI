"""Targeted, idempotent page-first ingest for the physical LMI BRI PDF.

The raw embedded text layer is retained in library_pages_v2 for audit. Citable
literal text is reconstructed from glyph geometry to remove extractor-inserted
inter-grapheme spaces while preserving logical Unicode order and niqqud.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path

import fitz
import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search
from modules.library.hebrew_pdf_layout import readable_line, readable_page

SOURCE = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARÁN I int (imprenta).pdf")
DOCUMENT_CODE = "likutey_moharan_i_spanish_bri"
PIPELINE_VERSION = "likutey_moharan_i_literal_page_first_v1"
EDITION_ID = "likutey_moharan_i_spanish_bri_page_first_v1"
EXPECTED_SHA256 = "71fb3c763c34d13465441c57b2bf3a65629fcdc37a7588f21e4fbf21f984b8d7"
HEADER_RE = re.compile(r"LIKUTEY\s*MOHAR[ÁA]N\s*#\s*(\d+(?::\d+)?)", re.I)
HEBREW_BASE_RE = re.compile(r"[\u05d0-\u05ea]")


def exact_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_projection(page: fitz.Page) -> tuple[str, str, int | None, str | None]:
    raw = page.get_text("text", sort=False).strip()
    rawdict = page.get_text("rawdict", sort=False)
    logical = readable_page(rawdict)
    printed_page = None
    section = None
    for block in rawdict.get("blocks", []):
        for line in block.get("lines", []):
            value = readable_line(line).strip()
            y0 = float(line.get("bbox", (0, 9999, 0, 9999))[1])
            if y0 < 170 and value.isdigit():
                printed_page = int(value)
            match = HEADER_RE.search(value.replace(" ", ""))
            if match:
                section = f"LIKUTEY MOHARÁN #{match.group(1)}"
    return raw, logical, printed_page, section


async def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Source PDF unavailable: {SOURCE}")
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_sha != EXPECTED_SHA256:
        raise SystemExit("Physical PDF checksum does not match the reviewed source")

    document = fitz.open(SOURCE)
    projections = [page_projection(page) for page in document]
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM library_documents WHERE source_sha256=%s", (source_sha,))
            existing = await cur.fetchone()
            if existing:
                document_id = existing["id"]
            else:
                await cur.execute(
                    """SELECT collection_id,knowledge_scope_id,organization_id,workspace_id,project_id
                       FROM library_documents WHERE document_code='likutey_moharan_ii_spanish_bri'"""
                )
                base = await cur.fetchone()
                if not base:
                    raise RuntimeError("Tenant/scope template document is unavailable")
                await cur.execute(
                    """INSERT INTO library_documents(
                           id,collection_id,title,language,source_type,source_path,source_filename,
                           source_mime_type,source_size_bytes,source_sha256,status,metadata,
                           bibliographic_metadata,organization_id,workspace_id,project_id,
                           knowledge_scope_id,document_code,canonical_text_role)
                       VALUES(gen_random_uuid(),%s,%s,'es','pdf',%s,%s,'application/pdf',%s,%s,
                           'test_candidate',%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,'candidate') RETURNING id""",
                    (
                        base["collection_id"], "Likutey Moharán I — edición española BRI",
                        str(SOURCE), SOURCE.name, SOURCE.stat().st_size, source_sha,
                        json.dumps({"literal_layout_profile": PIPELINE_VERSION, "physical_pages": len(document)}),
                        json.dumps({"edition": "Spanish BRI", "physical_file_verified": True}),
                        base["organization_id"], base["workspace_id"], base["project_id"],
                        base["knowledge_scope_id"], DOCUMENT_CODE,
                    ),
                )
                document_id = (await cur.fetchone())["id"]

            await cur.execute(
                """SELECT run_id FROM library_ingestion_runs_v2
                   WHERE document_id=%s AND pipeline_version=%s AND status='completed'
                   ORDER BY finished_at DESC LIMIT 1""",
                (document_id, PIPELINE_VERSION),
            )
            completed = await cur.fetchone()
            if completed:
                print(json.dumps({"status": "already_completed", "document_id": str(document_id), "run_id": str(completed["run_id"]), "pages": len(document), "sha256": source_sha}))
                return

            await cur.execute(
                """INSERT INTO library_ingestion_runs_v2(document_id,pipeline_version,scope_code,status)
                   VALUES(%s,%s,'breslov_research','started') RETURNING run_id""",
                (document_id, PIPELINE_VERSION),
            )
            run_id = (await cur.fetchone())["run_id"]
            await cur.execute(
                """INSERT INTO library_content_units_v2(
                       document_id,unit_type,canonical_ref,title,order_index,language_original,
                       is_breslov_primary_source,is_direct_rebbe_nachman,source_run_id,metadata_json)
                   VALUES(%s,'work','LMI-BRI','Likutey Moharán I — edición española BRI',1,'he',true,true,%s,%s::jsonb)
                   ON CONFLICT(document_id,canonical_ref) WHERE canonical_ref IS NOT NULL
                   DO UPDATE SET source_run_id=EXCLUDED.source_run_id RETURNING content_unit_id""",
                (document_id, run_id, json.dumps({"physical_file_name": SOURCE.name})),
            )
            work_unit = (await cur.fetchone())["content_unit_id"]

            textual_pages = 0
            current_section = None
            for page_number, (raw, logical, printed_page, detected_section) in enumerate(projections, 1):
                current_section = detected_section or current_section
                await cur.execute(
                    """INSERT INTO library_pages_v2(run_id,document_id,page_number,text,char_count,extraction_method,confidence,layout_notes)
                       VALUES(%s,%s,%s,%s,%s,'pymupdf_embedded_text_raw',.90,%s::jsonb)
                       RETURNING page_id""",
                    (run_id, document_id, page_number, raw, len(raw), json.dumps({"raw_sha256": exact_hash(raw), "logical_sha256": exact_hash(logical)})),
                )
                legacy_page_id = (await cur.fetchone())["page_id"]
                await cur.execute(
                    """INSERT INTO library_page_anchors_v2(
                           source_file_id,document_id,edition_id,pdf_page_number,printed_page_number,
                           page_label,section_page_label,legacy_page_id,confidence,metadata_json)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,.99,%s::jsonb)
                       ON CONFLICT(document_id,pdf_page_number,edition_id) DO UPDATE SET
                           printed_page_number=EXCLUDED.printed_page_number,
                           section_page_label=EXCLUDED.section_page_label,
                           legacy_page_id=EXCLUDED.legacy_page_id,
                           metadata_json=EXCLUDED.metadata_json
                       RETURNING page_anchor_id""",
                    (
                        document_id, document_id, EDITION_ID, page_number, printed_page,
                        str(printed_page) if printed_page is not None else None, current_section,
                        legacy_page_id,
                        json.dumps({"physical_file_name": SOURCE.name, "source_sha256": source_sha, "extraction": "glyph_geometry_logical_order_v1"}),
                    ),
                )
                anchor_id = (await cur.fetchone())["page_anchor_id"]
                if not logical:
                    continue
                textual_pages += 1
                canonical_ref = f"LMI-BRI-PDF-{page_number:04d}"
                language = "he" if len(HEBREW_BASE_RE.findall(logical)) >= 20 else "es"
                await cur.execute(
                    """INSERT INTO library_content_units_v2(
                           parent_content_unit_id,document_id,unit_type,canonical_ref,title,order_index,
                           language_original,is_breslov_primary_source,is_direct_rebbe_nachman,
                           source_run_id,metadata_json)
                       VALUES(%s,%s,'page',%s,%s,%s,%s,true,true,%s,%s::jsonb)
                       ON CONFLICT(document_id,canonical_ref) WHERE canonical_ref IS NOT NULL
                       DO UPDATE SET title=EXCLUDED.title,source_run_id=EXCLUDED.source_run_id,
                           metadata_json=EXCLUDED.metadata_json RETURNING content_unit_id""",
                    (work_unit, document_id, canonical_ref, current_section or f"PDF page {page_number}", page_number, language, run_id, json.dumps({"section": current_section, "printed_page": printed_page})),
                )
                page_unit = (await cur.fetchone())["content_unit_id"]
                normalized = normalize_hebrew_search(logical)
                literal_hash = exact_hash(logical)
                await cur.execute(
                    """INSERT INTO library_content_nodes_v2(
                           content_unit_id,node_role,content_type,relation_to_primary,authority_level,
                           language,script,literal_text,normalized_text,literal_hash,page_anchor_id,
                           node_order,citable,source_run_id,metadata_json,link_status,review_status)
                       VALUES(%s,'satellite','citable_page_text','same_page','primary_parallel',%s,
                           'mixed',%s,%s,%s,%s,1,true,%s,%s::jsonb,'linked','deterministic')
                       RETURNING content_node_id""",
                    (page_unit, language, logical, normalized, literal_hash, anchor_id, run_id, json.dumps({"source_run_id": PIPELINE_VERSION, "section": current_section, "canonical_projection": "glyph_geometry_logical_order_v1", "raw_text_retained": True})),
                )
                node_id = (await cur.fetchone())["content_node_id"]
                await cur.execute(
                    """INSERT INTO library_literal_spans_v2(
                           content_node_id,start_char,end_char,literal_text,normalized_text,hash,metadata_json)
                       VALUES(%s,0,%s,%s,%s,%s,%s::jsonb)""",
                    (node_id, len(logical), logical, normalized, literal_hash, json.dumps({"normalizer": "normalize_hebrew_search_v1"})),
                )
                await cur.execute(
                    """INSERT INTO library_semantic_units_v2(
                           content_node_id,text,text_hash,chunk_order,chunker_name,language,source_run_id,metadata_json)
                       VALUES(%s,%s,%s,1,'page_first_no_embedding_v1',%s,%s,%s::jsonb)""",
                    (node_id, logical, literal_hash, language, run_id, json.dumps({"vectorized": False})),
                )

            await cur.execute(
                """UPDATE library_ingestion_runs_v2 SET status='completed',finished_at=now(),
                       metrics_json=%s::jsonb,warnings_json='[]'::jsonb WHERE run_id=%s""",
                (json.dumps({"physical_pages": len(document), "textual_pages": textual_pages, "source_sha256": source_sha, "ocr_used": False, "embeddings": False}), run_id),
            )
        await conn.commit()
    print(json.dumps({"status": "completed", "document_id": str(document_id), "run_id": str(run_id), "pages": len(document), "textual_pages": textual_pages, "sha256": source_sha}))


if __name__ == "__main__":
    asyncio.run(main())
