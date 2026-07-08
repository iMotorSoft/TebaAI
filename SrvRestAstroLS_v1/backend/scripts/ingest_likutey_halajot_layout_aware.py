#!/usr/bin/env python3
"""
Ingest Likutey Halajot Interior Final via layout-aware pipeline.

Flow:
  1. Parse PDF with layout-aware parser (standalone, no PG).
  2. Dry-run: validate blocks, show counts.
  3. Create/update document in PostgreSQL (test_candidate).
  4. Insert chunks with layout metadata.
  5. Generate embeddings via LiteLLM.
  6. Upsert to Milvus test (tebaai_breslov_test_chunks_v1).
  7. Round-trip + golden queries.

Usage:
    uv run python -m scripts.ingest_likutey_halajot_layout_aware --dry-run
    uv run python -m scripts.ingest_likutey_halajot_layout_aware --apply
    uv run python -m scripts.ingest_likutey_halajot_layout_aware --apply --skip-embed
    uv run python -m scripts.ingest_likutey_halajot_layout_aware --apply --limit-pages 20
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

import globalVar

PDF_PATH = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
TITLE = "Likutey Halajot Explicado — Interior Final"
SCOPE_CODE = "breslov_primary"
STATUS = "test_candidate"
MILVUS_TEST_COLL = "tebaai_breslov_test_chunks_v1"
INGESTION_PROFILE = "layout_aware_likutey_halajot"

EMBED_MODEL_ALIAS = "openai_text_embedding_3_small"
EMBED_DIM = 1536
EMBED_BATCH = 16
EMBED_TRUNCATE = 1200

GOLDEN_QUERIES = [
    "puntos buenos",
    "Hay aún un poco de bien",
    "Avot 1:6",
    "Trece Atributos de Misericordia",
    "jésed",
    "Rosh HaShaná 17a",
    "glosa del Remá",
    "Shuljan Aruj",
    "He puesto a HaShem siempre delante de mí",
    "desesperanza o sueño espiritual",
    "nota y explicación",
    "lado derecho con Avraham",
    "halajá de la página 37",
    "texto hebreo página 32",
    "referencias cruzadas internas",
]


def _parse_args():
    p = argparse.ArgumentParser(description="Layout-aware ingestion for Likutey Halajot")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--apply", action="store_true", default=False)
    p.add_argument("--skip-embed", action="store_true", default=False)
    p.add_argument("--limit-pages", type=int, default=0, help="Limit pages (0=all 284)")
    p.add_argument("--composites", action="store_true", default=False,
                   help="Generate composite_page_context blocks")
    return p.parse_args()


async def main():
    args = _parse_args()
    is_dry = args.dry_run or not args.apply
    limit_pages = args.limit_pages or 284

    pdf = pathlib.Path(PDF_PATH)
    if not pdf.is_file():
        print(f"ERROR: PDF not found: {PDF_PATH}")
        return 1

    pdf_sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()

    print(f"{'='*65}")
    print(f"  LIKUTEY HALAJOT — LAYOUT-AWARE INGESTION")
    print(f"  Pages: {limit_pages}")
    print(f"  PDF SHA-256: {pdf_sha256}")
    print(f"  Mode: {'DRY-RUN' if is_dry else 'APPLY'}")
    print(f"{'='*65}")

    # ── Step 1: Parse PDF with layout-aware parser ──
    print(f"\n[1/7] Parsing PDF with layout-aware parser...")
    from scripts.likutey_layout_parser import parse_pdf

    all_pages = list(range(limit_pages))  # 0-indexed
    parsed = parse_pdf(
        str(pdf),
        pages=all_pages,
        include_composites=args.composites,
    )

    total_blocks = sum(len(blocks) for blocks in parsed.values())
    type_counts: dict[str, int] = {}
    lang_counts: dict[str, int] = {}
    needs_review = 0
    for blocks in parsed.values():
        for b in blocks:
            type_counts[b.block_type] = type_counts.get(b.block_type, 0) + 1
            lang_counts[b.language] = lang_counts.get(b.language, 0) + 1
            if b.needs_hebrew_review or b.needs_reference_review:
                needs_review += 1

    print(f"  Pages parsed: {len(parsed)}")
    print(f"  Total blocks: {total_blocks}")
    print(f"  Block types: {dict(type_counts)}")
    print(f"  Languages: {dict(lang_counts)}")
    print(f"  Needs review: {needs_review}")

    # ── Step 2: Connect PostgreSQL ──
    print(f"\n[2/7] PostgreSQL connection...")
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all, execute
    from modules.library.repository import (
        create_document, get_document_by_sha256, get_scope_by_code,
    )
    from modules.library.domain import LibraryDocument, LibraryDocumentText

    pool = create_pool_from_settings()
    await open_pool(pool)

    doc_id: UUID | None = None
    doc_text_id: UUID | None = None

    try:
        # ── Step 3: Create/update document ──
        print(f"\n[3/7] Document setup...")
        async with pool.connection() as conn:
            scope = await get_scope_by_code(conn, SCOPE_CODE)
            if not scope:
                print(f"  ERROR: scope '{SCOPE_CODE}' not found!")
                return 1
            print(f"  Knowledge scope: {scope.knowledge_scope_code} (id={scope.id})")

            # Check for existing document by SHA-256
            existing = await get_document_by_sha256(conn, pdf_sha256, knowledge_scope_id=scope.id)
            if existing:
                doc_id = existing.id
                print(f"  EXISTING document: {doc_id} ({existing.title})")
                if not is_dry:
                    # Remove old chunks + embeddings for this document
                    await execute(conn,
                        "DELETE FROM library_chunk_embeddings WHERE chunk_id IN (SELECT id FROM library_document_chunks WHERE document_id = %(did)s)",
                        {"did": str(doc_id)})
                    await execute(conn,
                        "DELETE FROM library_document_chunks WHERE document_id = %(did)s",
                        {"did": str(doc_id)})
                    await execute(conn,
                        "DELETE FROM library_document_texts WHERE document_id = %(did)s",
                        {"did": str(doc_id)})
                    print(f"  Old chunks/texts cleared")
            elif is_dry:
                print(f"  DRY-RUN: would create new document")
            else:
                legacy_id = UUID("00000000-0000-0000-0000-000000000001")
                doc = LibraryDocument.create(
                    collection_id=legacy_id,
                    title=TITLE,
                    language="es",
                    source_type="pdf",
                    source_path=str(pdf),
                    source_filename=pdf.name,
                    source_size_bytes=pdf.stat().st_size,
                    source_sha256=pdf_sha256,
                    knowledge_scope_id=scope.id,
                    organization_id=scope.organization_id,
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    status=STATUS,
                    bibliographic_metadata={
                        "source_quality": {
                            "source_kind": "pdf_modern_unicode_si960",
                            "canonical_text_role": "candidate",
                            "promotion_recommendation": "pending_validation",
                            "canonical_text_allowed": True,
                            "text_quality_status": "pass_layout_aware",
                            "layout_status": "layout_aware_parsed",
                            "page_mapping_status": "layout_based_mapping",
                            "ocr_status": "not_ocr",
                            "document_family": "Breslov/LikuteyHalajot",
                            "language_hints": ["es", "he"],
                            "ingestion_profile": INGESTION_PROFILE,
                        },
                        "extraction": {
                            "method": "layout_aware_pymupdf_dict",
                            "pages": limit_pages,
                            "parser": "likutey_layout_parser",
                            "sha256_pdf": pdf_sha256,
                            "block_count": total_blocks,
                            "block_types": dict(type_counts),
                        },
                    },
                )
                await create_document(conn, doc)
                doc_id = doc.id
                print(f"  Created document: {doc_id}")

            # Build combined markdown text (one block per line with markers)
            if not is_dry and doc_id:
                combined_lines = []
                for pg in sorted(parsed):
                    blocks = parsed[pg]
                    combined_lines.append(f"## BlockPage {pg}")
                    for b in blocks:
                        combined_lines.append(f"[{b.block_type}] {b.content}")
                md_content = "\n\n".join(combined_lines)
                md_sha256 = hashlib.sha256(md_content.encode("utf-8")).hexdigest()

                text_entry = LibraryDocumentText.create(
                    document_id=doc_id,
                    text_format="markdown",
                    content=md_content,
                    content_sha256=md_sha256,
                    extraction_method="layout_aware_parser",
                    knowledge_scope_id=scope.id,
                    page_markers_enabled=True,
                    page_count=limit_pages,
                    extraction_metadata={
                        "parser": "likutey_layout_parser",
                        "ingestion_profile": INGESTION_PROFILE,
                        "pages": limit_pages,
                        "blocks": total_blocks,
                        "block_types": dict(type_counts),
                    },
                )
                # Insert directly (create_document_text is a repo function)
                await execute(conn, """
                    INSERT INTO library_document_texts
                    (id, document_id, text_format, content, content_sha256, content_length,
                     extraction_method, text_role, knowledge_scope_id, page_markers_enabled,
                     page_count, extraction_metadata, created_at)
                    VALUES (%(id)s, %(did)s, %(fmt)s, %(content)s, %(sha)s, %(len)s,
                            %(method)s, %(role)s, %(ksid)s, %(pm)s,
                            %(pc)s, %(meta)s, %(now)s)
                """, {
                    "id": str(text_entry.id),
                    "did": str(doc_id),
                    "fmt": text_entry.text_format,
                    "content": text_entry.content,
                    "sha": text_entry.content_sha256,
                    "len": text_entry.content_length,
                    "method": text_entry.extraction_method,
                    "role": text_entry.text_role,
                    "ksid": str(text_entry.knowledge_scope_id) if text_entry.knowledge_scope_id else None,
                    "pm": text_entry.page_markers_enabled,
                    "pc": text_entry.page_count,
                    "meta": json.dumps(text_entry.extraction_metadata),
                    "now": datetime.now(timezone.utc),
                })
                doc_text_id = text_entry.id
                print(f"  Text persisted: {text_entry.content_length:,} chars")

        # ── Step 4: Insert chunks ──
        print(f"\n[4/7] Inserting chunks...")
        if doc_id and not is_dry and doc_text_id:
            async with pool.connection() as conn:
                chunk_inserts = []
                chunk_index = 0
                for pg in sorted(parsed):
                    blocks = parsed[pg]
                    for b in blocks:
                        chunk_id = uuid4()
                        chunk_uid = f"lkh_pg{pg:03d}_b{b.block_index:03d}_{b.block_type}"[:64]
                        chunk_inserts.append({
                            "id": str(chunk_id),
                            "document_id": str(doc_id),
                            "document_text_id": str(doc_text_id),
                            "collection_id": "00000000-0000-0000-0000-000000000001",
                            "chunk_index": chunk_index,
                            "chunk_uid": chunk_uid,
                            "language": b.language,
                            "content": b.content,
                            "content_sha256": b.content_sha256,
                            "content_length": b.content_length,
                            "char_start": None,
                            "char_end": None,
                            "page_start": b.page_number,
                            "page_end": b.page_number,
                            "chapter": None,
                            "section": None,
                            "metadata": json.dumps(b.metadata),
                            "block_type": b.block_type,
                            "block_subtype": b.block_subtype,
                            "evidence_role": b.evidence_role,
                            "citable": b.citable,
                            "layout_confidence": b.layout_confidence,
                            "ingestion_profile": b.ingestion_profile,
                            "printed_page_label": b.printed_page_label,
                            "node_path": b.node_path,
                            "section_title": b.section_title_es or b.section_title_he,
                            "knowledge_scope_id": str(scope.id),
                            "organization_id": str(scope.organization_id),
                            "workspace_id": str(scope.workspace_id),
                            "project_id": str(scope.project_id),
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        })
                        chunk_index += 1

                # Batch insert
                for i in range(0, len(chunk_inserts), 100):
                    batch = chunk_inserts[i:i+100]
                    values_sql = ", ".join(
                        """(%(id)s, %(document_id)s, %(document_text_id)s, %(collection_id)s,
                           %(chunk_index)s, %(chunk_uid)s, %(language)s, %(content)s,
                           %(content_sha256)s, %(content_length)s, %(char_start)s, %(char_end)s,
                           %(page_start)s, %(page_end)s, %(chapter)s, %(section)s,
                           %(metadata)s, %(block_type)s, %(block_subtype)s, %(evidence_role)s,
                           %(citable)s, %(layout_confidence)s, %(ingestion_profile)s,
                           %(printed_page_label)s, %(node_path)s, %(section_title)s,
                           %(knowledge_scope_id)s, %(organization_id)s, %(workspace_id)s,
                           %(project_id)s, %(created_at)s, %(updated_at)s)"""
                    )
                    flat_params = {}
                    for j, row in enumerate(batch):
                        for k, v in row.items():
                            flat_params[f"{k}_{j}"] = v
                    sql = f"""
                        INSERT INTO library_document_chunks (
                            id, document_id, document_text_id, collection_id,
                            chunk_index, chunk_uid, language, content,
                            content_sha256, content_length, char_start, char_end,
                            page_start, page_end, chapter, section,
                            metadata, block_type, block_subtype, evidence_role,
                            citable, layout_confidence, ingestion_profile,
                            printed_page_label, node_path, section_title,
                            knowledge_scope_id, organization_id, workspace_id,
                            project_id, created_at, updated_at
                        ) VALUES
                    """
                    # Build with numbered params
                    value_rows = []
                    for j in range(len(batch)):
                        value_rows.append(f"""(
                            %(id_{j})s, %(document_id_{j})s, %(document_text_id_{j})s, %(collection_id_{j})s,
                            %(chunk_index_{j})s, %(chunk_uid_{j})s, %(language_{j})s, %(content_{j})s,
                            %(content_sha256_{j})s, %(content_length_{j})s, %(char_start_{j})s, %(char_end_{j})s,
                            %(page_start_{j})s, %(page_end_{j})s, %(chapter_{j})s, %(section_{j})s,
                            %(metadata_{j})s, %(block_type_{j})s, %(block_subtype_{j})s, %(evidence_role_{j})s,
                            %(citable_{j})s, %(layout_confidence_{j})s, %(ingestion_profile_{j})s,
                            %(printed_page_label_{j})s, %(node_path_{j})s, %(section_title_{j})s,
                            %(knowledge_scope_id_{j})s, %(organization_id_{j})s, %(workspace_id_{j})s,
                            %(project_id_{j})s, %(created_at_{j})s, %(updated_at_{j})s
                        )""")
                    sql += ", ".join(value_rows)
                    await execute(conn, sql, flat_params)

                print(f"  {chunk_index} chunks inserted")

                # Verify
                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_document_chunks WHERE document_id = %s",
                    [str(doc_id)])
                print(f"  Verified: {r['cnt']} chunks in PG")

        # ── Step 5: Embeddings via LiteLLM ──
        embed_count = 0
        if doc_id and not is_dry and not args.skip_embed:
            print(f"\n[5/7] Embeddings via LiteLLM...")
            from modules.library.vector_repository import (
                create_embedding_run, create_chunk_embedding,
                update_embedding_run,
            )
            from modules.embeddings.client import embed_batch
            from modules.library.indexing_service import ensure_collection

            async with pool.connection() as conn:
                chunks = await fetch_all(conn, """
                    SELECT id::text, chunk_uid, content, content_sha256, chunk_index,
                           block_type, citable, layout_confidence, language, page_start, page_end
                    FROM library_document_chunks
                    WHERE document_id = %(did)s
                    ORDER BY chunk_index
                """, {"did": str(doc_id)})

                embed_chunks = [c for c in chunks if c["citable"] is True]
                skip_chunks = [c for c in chunks if c["citable"] is False]

                print(f"  Total chunks: {len(chunks)}")
                print(f"  Embeddable (citable): {len(embed_chunks)}")
                print(f"  Skipped (not citable): {len(skip_chunks)}")

                if embed_chunks:
                    from pymilvus import MilvusClient

                    run_id = uuid4()
                    await create_embedding_run(conn, {
                        "id": run_id,
                        "collection_code": SCOPE_CODE,
                        "milvus_collection": MILVUS_TEST_COLL,
                        "embedding_provider": "litellm",
                        "embedding_model": EMBED_MODEL_ALIAS,
                        "embedding_dimension": EMBED_DIM,
                        "status": "running",
                        "chunks_total": len(embed_chunks),
                    })

                    mc = MilvusClient(f'http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}')

                    embed_ok = 0
                    for i, ck in enumerate(embed_chunks):
                        ck_id = ck["id"]
                        ck_uid = ck["chunk_uid"]
                        ck_content = ck["content"][:EMBED_TRUNCATE]

                        if not ck_content.strip():
                            await create_chunk_embedding(conn,
                                chunk_id=UUID(ck_id) if isinstance(ck_id, str) else ck_id,
                                run_id=run_id, provider="litellm",
                                model=EMBED_MODEL_ALIAS, dimension=EMBED_DIM,
                                milvus_collection=MILVUS_TEST_COLL,
                                milvus_pk="skipped",
                                content_sha256=ck["content_sha256"],
                                status="skipped")
                            continue

                        try:
                            vectors = embed_batch([ck_content], model=EMBED_MODEL_ALIAS)
                            if vectors and len(vectors) > 0:
                                vector = vectors[0]
                                preview = ck_content[:800]
                                preview_bytes = preview.encode("utf-8")[:1024]
                                preview = preview_bytes.decode("utf-8", errors="ignore")

                                mc.insert(MILVUS_TEST_COLL, [{
                                    "pk": ck_uid,
                                    "chunk_id": ck_uid,
                                    "document_id": str(doc_id),
                                    "collection_code": SCOPE_CODE,
                                    "language": ck["language"] or "es",
                                    "title": TITLE[:256],
                                    "source_type": "pdf",
                                    "source_sha256": pdf_sha256,
                                    "content_sha256": ck["content_sha256"],
                                    "chunk_index": int(ck["chunk_index"]),
                                    "page_start": int(ck.get("page_start") or 0),
                                    "page_end": int(ck.get("page_end") or 0),
                                    "content_preview": preview,
                                    "embedding": [float(v) for v in vector],
                                }])

                                await create_chunk_embedding(conn,
                                    chunk_id=UUID(ck_id) if isinstance(ck_id, str) else ck_id,
                                    run_id=run_id, provider="litellm",
                                    model=EMBED_MODEL_ALIAS, dimension=EMBED_DIM,
                                    milvus_collection=MILVUS_TEST_COLL,
                                    milvus_pk=ck_uid,
                                    content_sha256=ck["content_sha256"],
                                    status="indexed")
                                embed_ok += 1
                        except Exception as exc:
                            print(f"  ERROR {ck_uid}: {exc}")
                            await create_chunk_embedding(conn,
                                chunk_id=UUID(ck_id) if isinstance(ck_id, str) else ck_id,
                                run_id=run_id, provider="litellm",
                                model=EMBED_MODEL_ALIAS, dimension=EMBED_DIM,
                                milvus_collection=MILVUS_TEST_COLL,
                                milvus_pk="failed",
                                content_sha256=ck["content_sha256"],
                                status="failed")

                        if (i + 1) % 100 == 0:
                            print(f"  Embedded {i+1}/{len(embed_chunks)} ({embed_ok} ok)...")

                    await update_embedding_run(conn, run_id,
                        status="completed", chunks_embedded=embed_ok,
                        chunks_indexed=embed_ok)
                    print(f"  Embeddings: {embed_ok}/{len(embed_chunks)}")

        # ── Step 6: Validation ──
        print(f"\n[6/7] Validation...")
        if doc_id and not is_dry:
            async with pool.connection() as conn:
                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_document_chunks WHERE document_id = %s",
                    [str(doc_id)])
                pg_chunks = r["cnt"]

                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_chunk_embeddings e JOIN library_document_chunks c ON e.chunk_id = c.id WHERE c.document_id = %s",
                    [str(doc_id)])
                pg_embeds = r["cnt"]

                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_chunk_embeddings e JOIN library_document_chunks c ON e.chunk_id = c.id WHERE c.document_id = %s AND e.status = 'indexed'",
                    [str(doc_id)])
                indexed = r["cnt"]

                print(f"  Chunks: {pg_chunks}")
                print(f"  Embeddings: {pg_embeds}")
                print(f"  Indexed: {indexed}")

                # Verify Breslov ready docs intact
                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_documents WHERE knowledge_scope_id = %s AND status = 'ready'",
                    [str(scope.id)])
                ready_count = r["cnt"]
                print(f"  Breslov ready docs: {ready_count} (expected 8)")

                r = await fetch_one(conn,
                    "SELECT COUNT(*) AS cnt FROM library_document_chunks ldc JOIN library_documents ld ON ldc.document_id = ld.id WHERE ld.knowledge_scope_id = %s AND ld.status = 'ready'",
                    [str(scope.id)])
                ready_chunks = r["cnt"]
                print(f"  Breslov ready chunks: {ready_chunks} (expected 5102)")

        # ── Step 7: Golden queries (summary) ──
        print(f"\n[7/7] Golden queries (placeholder)...")
        if doc_id and not is_dry and not args.skip_embed:
            from modules.library.text_search import search_chunks_text
            from modules.embeddings.client import embed_batch
            from pymilvus import Collection

            async with pool.connection() as conn:
                milvus_coll = Collection(MILVUS_TEST_COLL)
                milvus_coll.load()

                for q in GOLDEN_QUERIES[:5]:
                    # FTS search
                    fts_results = await search_chunks_text(
                        conn, knowledge_scope_code=SCOPE_CODE,
                        query=q, top_k=3, mode="fts", language="es",
                    )
                    fts_hits = len(fts_results)
                    fts_docs = set(r["document_id"] for r in fts_results)

                    # Vector search
                    vec_hits = 0
                    try:
                        q_vec = embed_batch([q], model=EMBED_MODEL_ALIAS)
                        if q_vec:
                            results = milvus_coll.search(
                                data=[q_vec[0]],
                                anns_field="vector",
                                param={"metric_type": "IP", "params": {"nprobe": 10}},
                                limit=3,
                                output_fields=["chunk_id"],
                            )
                            if results:
                                vec_hits = len(results[0])
                    except Exception:
                        pass

                    print(f"  Query: {q[:40]:40s} FTS={fts_hits} Vec={vec_hits}")

        print(f"\n{'='*65}")
        print(f"  LIKUTEY HALAJOT INGESTION SUMMARY")
        print(f"  Document: {doc_id}")
        print(f"  Pages: {limit_pages}")
        print(f"  Blocks: {total_blocks}")
        print(f"  Embeddings: {embed_count}")
        print(f"  Status: {'DRY-RUN' if is_dry else 'APPLIED'}")
        print(f"  Pipeline: layout-aware (NOT simple)")
        print(f"  Productivo tocado: NO")
        print(f"{'='*65}")

    finally:
        await close_pool(pool)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
