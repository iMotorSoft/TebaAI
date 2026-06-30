#! /usr/bin/env python3
"""
CLI: Chunk documents in the library.

Supports strategies:
  - generic:          paragraph-based chunking (original default)
  - sijot-aware:      section-aware chunking for Sija documents
  - heading-aware:    Markdown heading-based chunking
  - lesson-aware:     lesson-based chunking for KITZUR-style books

Usage:
    uv run python -m scripts.chunk_documents --collection breslov_test \\
        --document-title "Kokhavey Ohr" --strategy heading-aware --dry-run

    uv run python -m scripts.chunk_documents --collection breslov_test \\
        --document-title "KITZUR" --strategy lesson-aware --apply
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from uuid import UUID, uuid4


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk documents in a library collection.")
    parser.add_argument("--collection", required=True, help="Collection code to chunk")
    parser.add_argument("--document-title", default=None, help="Specific document title (optional)")
    parser.add_argument("--chunk-size-chars", type=int, default=1800, help="Max chars per chunk")
    parser.add_argument("--chunk-overlap-chars", type=int, default=250, help="Overlap between chunks")
    parser.add_argument("--min-chunk-chars", type=int, default=200, help="Min chars per chunk")
    parser.add_argument("--strategy", default="generic",
                        choices=["generic", "sijot-aware", "heading-aware", "lesson-aware"],
                        help="Chunking strategy")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be chunked without inserting")
    parser.add_argument("--apply", action="store_true", help="Persist chunks to database")
    parser.add_argument("--output-json", default=None, help="Output JSON path (dry-run only)")
    parser.add_argument("--output-md", default=None, help="Output Markdown path (dry-run only)")
    return parser.parse_args(argv)


# ── Markdown structural chunking helpers ─────────────────────────────


def _detect_sections(md: str, strategy: str) -> list[dict]:
    sections = []
    if strategy in ("heading-aware",):
        for m in re.finditer(r'^#{1,3}\s+(.+)', md, re.MULTILINE):
            sections.append({
                "position": m.start(), "type": "heading",
                "number": None, "label": m.group(1).strip(),
                "title": m.group(1).strip(),
            })
    elif strategy == "lesson-aware":
        for m in re.finditer(r'(?i)^#{0,3}\s*(?:lecci[óo]n|lesson|tor[áa]|tora)\s+(\d+)', md, re.MULTILINE):
            sections.append({
                "position": m.start(), "type": "lesson",
                "number": int(m.group(1)), "label": m.group(0).strip(),
                "title": m.group(0).strip(),
            })
    return sorted(sections, key=lambda x: x["position"])


def _generic_chunks_from_md(md: str, chunk_size: int, overlap: int, min_chunk: int) -> list[dict]:
    """Fallback generic chunking producing DB-format dicts (without document IDs)."""
    paragraphs = re.split(r'\n\n+', md)
    result = []
    current = ""
    idx = 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > chunk_size:
            if len(current) >= min_chunk:
                result.append({"content": current.strip(), "chunk_index": idx})
                idx += 1
            overlap_text = current[-overlap:] if overlap > 0 and len(current) > overlap else ""
            current = overlap_text
        if current:
            current += "\n\n" + para
        else:
            current = para
    if current.strip() and len(current.strip()) >= min_chunk:
        result.append({"content": current.strip(), "chunk_index": idx})
    return result


def _chunk_markdown_structure(
    md: str, strategy: str, chunk_size: int, overlap: int, min_chunk: int,
) -> list[dict]:
    """Structure-aware chunking on Markdown. Returns list of dicts with content/strategy/section info."""
    sections = _detect_sections(md, strategy)
    if not sections:
        raw = _generic_chunks_from_md(md, chunk_size, overlap, min_chunk)
        for r in raw:
            r["section_type"] = None
            r["section_number"] = None
            r["section_label"] = None
            r["section_title"] = None
            r["source_strategy"] = strategy
        return raw

    result = []
    idx = 0
    for i, sec in enumerate(sections):
        sec_start = sec["position"]
        sec_end = sections[i + 1]["position"] if i + 1 < len(sections) else len(md)
        sec_content = md[sec_start:sec_end].strip()
        if not sec_content:
            continue

        sec_type = sec["type"]
        sec_num = sec["number"]
        sec_label = sec.get("label", "") or ""

        if len(sec_content) <= chunk_size * 1.2:
            result.append({
                "content": sec_content, "chunk_index": idx,
                "section_type": sec_type, "section_number": sec_num,
                "section_label": sec_label, "section_title": sec_label,
                "source_strategy": strategy,
            })
            idx += 1
        else:
            heading_match = re.match(r'(#{1,3}\s+.*?)(?:\n|$)', sec_content)
            heading_line = heading_match.group(1) if heading_match else ""
            remaining = sec_content[len(heading_line):].strip() if heading_line else sec_content
            current = heading_line
            for para in re.split(r'\n\n+', remaining):
                para = para.strip()
                if not para:
                    continue
                if current and len(current) + len(para) + 2 > chunk_size:
                    if len(current) >= min_chunk or (not result and heading_line):
                        result.append({
                            "content": current.strip(), "chunk_index": idx,
                            "section_type": sec_type, "section_number": sec_num,
                            "section_label": sec_label, "section_title": sec_label,
                            "source_strategy": strategy,
                        })
                        idx += 1
                    overlap_text = current[-overlap:] if overlap > 0 and len(current) > overlap else ""
                    current = overlap_text
                if current:
                    current += "\n\n" + para
                else:
                    current = para
            if current.strip() and len(current.strip()) >= min_chunk:
                result.append({
                    "content": current.strip(), "chunk_index": idx,
                    "section_type": sec_type, "section_number": sec_num,
                    "section_label": sec_label, "section_title": sec_label,
                    "source_strategy": strategy,
                })
                idx += 1

    return result


def _build_db_chunks(
    raw_chunks: list[dict], doc_id: UUID, text_id: UUID,
    doc_title: str, language: str, collection_id: UUID,
) -> list[dict]:
    """Convert raw chunk dicts to DB-ready format with FTS fields."""
    import datetime
    result = []
    for rc in raw_chunks:
        content = rc["content"]
        content_bytes = content.encode("utf-8")
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        cidx = rc.get("chunk_index", 0)

        section_info = {}
        if rc.get("section_type"):
            section_info["section_type"] = rc["section_type"]
        if rc.get("section_number") is not None:
            section_info["section_number"] = rc["section_number"]
        if rc.get("section_label"):
            section_info["section_label"] = rc["section_label"]
        if rc.get("section_title"):
            section_info["section_title"] = rc["section_title"]

        metadata: dict = {
            "chunking": {
                "strategy": rc.get("source_strategy", "generic"),
                "source": "persisted_markdown",
                "markdown_extraction_engine": "pymupdf4llm",
                "document_status": "test_candidate",
            },
        }
        if section_info:
            metadata["section"] = section_info

        result.append({
            "id": uuid4(),
            "document_id": doc_id,
            "document_text_id": text_id,
            "chunk_index": cidx,
            "chunk_uid": hashlib.sha256(f"{doc_id}/{text_id}/{cidx}".encode()).hexdigest()[:24],
            "language": language,
            "content": content,
            "content_sha256": sha256,
            "content_length": len(content),
            "char_start": 0,
            "char_end": len(content),
            "token_count_estimate": max(1, len(content) // 4),
            "metadata": metadata,
            "collection_id": collection_id,
            "page_start": None,
            "page_end": None,
            "chapter": None,
            "section": section_info.get("section_label") if section_info else None,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
        })
    return result


# ── Main CLI ──────────────────────────────────────────────────────────


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one as fo

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled via globalVar.py", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            from psycopg.rows import dict_row
            conn.row_factory = dict_row
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected 'tebaai', got '{db}'", file=sys.stderr)
                return 1

            # Resolve collection
            await cur.execute(
                "SELECT id, code FROM library_collections WHERE code = %(code)s",
                {"code": args.collection},
            )
            col = await cur.fetchone()
            if not col:
                print(f"ERROR: Collection '{args.collection}' not found", file=sys.stderr)
                return 1
            coll_id = col["id"]
            print(f"Collection: {col['code']} ({coll_id})")

            # Build document query
            doc_params: dict = {"coll_id": str(coll_id)}
            title_filter = ""
            if args.document_title:
                title_filter = " AND d.title = %(title)s"
                doc_params["title"] = args.document_title

            # Structural strategies allow test_candidate; generic requires ready
            if args.strategy in ("sijot-aware", "heading-aware", "lesson-aware"):
                status_filter = "d.status IN ('ready', 'test_candidate')"
            else:
                status_filter = "d.status = 'ready'"

            await cur.execute(f"""
                SELECT d.id AS doc_id, t.id AS text_id, d.title, d.language,
                       d.collection_id, t.content, d.status, d.bibliographic_metadata
                FROM library_documents d
                JOIN library_document_texts t ON t.document_id = d.id
                WHERE d.collection_id = %(coll_id)s
                  AND {status_filter}
                  AND NOT EXISTS (
                      SELECT 1 FROM library_document_chunks ch WHERE ch.document_id = d.id
                  )
                  {title_filter}
            """, doc_params)
            docs = await cur.fetchall()

            if not docs:
                print("No unchunked documents found.")
                from modules.library.vector_repository import count_chunks
                existing = await count_chunks(conn, collection_id=coll_id)
                print(f"Existing chunks in collection: {existing}")
                return 0

            print(f"Documents to chunk: {len(docs)}")

            # Strategy-specific guards
            if args.strategy in ("heading-aware", "lesson-aware") and args.apply:
                if not args.collection.endswith("_test"):
                    print(f"ERROR: Strategy '{args.strategy}' apply requires *_test collection",
                          file=sys.stderr)
                    return 1
                for doc in docs:
                    if doc["status"] != "test_candidate":
                        print(f"ERROR: Strategy '{args.strategy}' apply requires test_candidate, "
                              f"got '{doc['status']}' for '{doc['title']}'", file=sys.stderr)
                        return 1
                    bib = doc.get("bibliographic_metadata") or {}
                    te = bib.get("text_extraction") or {}
                    if te.get("engine") != "pymupdf4llm" or te.get("format") != "markdown":
                        print(f"ERROR: '{doc['title']}' missing pymupdf4llm/markdown text_extraction "
                              f"(got {te})", file=sys.stderr)
                        return 1
                    if args.strategy == "heading-aware" and "Kokhavey" not in doc["title"]:
                        print(f"ERROR: heading-aware strategy is for Kokhavey Ohr, "
                              f"not '{doc['title']}'", file=sys.stderr)
                        return 1
                    if args.strategy == "lesson-aware" and "KITZUR" not in doc["title"].upper():
                        print(f"ERROR: lesson-aware strategy is for KITZUR, "
                              f"not '{doc['title']}'", file=sys.stderr)
                        return 1

            if args.strategy == "sijot-aware" and args.apply:
                for doc in docs:
                    if doc["status"] != "test_candidate":
                        print(f"ERROR: Sijot-aware apply requires test_candidate status, "
                              f"got '{doc['status']}' for '{doc['title']}'", file=sys.stderr)
                        return 1

            # Preflight for structural strategies
            preflight_metrics = None
            if args.strategy == "sijot-aware":
                from scripts.compare_chunking_strategies import (
                    _compute_sijot_aware_chunks, _compute_sijot_metrics, SIJOT_EXPECTED_COUNT,
                )
                for doc in docs:
                    tc = _compute_sijot_aware_chunks(doc["content"])
                    tm = _compute_sijot_metrics(tc)
                    print(f"  Preflight {doc['title']}: {tm.sijot_detected}/{SIJOT_EXPECTED_COUNT} Sijot")
                    if args.apply and (tm.sijot_detected < SIJOT_EXPECTED_COUNT or tm.missing_sijot
                                       or tm.chunks_crossing_sections > 0):
                        print("ERROR: Preflight failed for sijot-aware apply", file=sys.stderr)
                        return 1
                    preflight_metrics = tm

            if args.strategy in ("heading-aware", "lesson-aware"):
                for doc in docs:
                    sections = _detect_sections(doc["content"], args.strategy)
                    test_chunks = _chunk_markdown_structure(
                        doc["content"], args.strategy,
                        args.chunk_size_chars, args.chunk_overlap_chars, args.min_chunk_chars,
                    )
                    print(f"  Preflight {doc['title']}: {len(sections)} sections, {len(test_chunks)} chunks")

            # Process each document
            import datetime
            total_chunks = 0
            all_chunks_for_dry_run: list[dict] = []

            for doc in docs:
                raw_doc_id = doc["doc_id"]
                raw_text_id = doc["text_id"]
                doc_id_inst = raw_doc_id if isinstance(raw_doc_id, UUID) else UUID(raw_doc_id)
                text_id = raw_text_id if isinstance(raw_text_id, UUID) else UUID(raw_text_id)
                content = doc["content"]

                if args.strategy in ("heading-aware", "lesson-aware"):
                    raw = _chunk_markdown_structure(
                        content, args.strategy,
                        args.chunk_size_chars, args.chunk_overlap_chars, args.min_chunk_chars,
                    )
                    result = _build_db_chunks(
                        raw, doc_id_inst, text_id,
                        doc["title"], doc["language"], doc["collection_id"],
                    )
                elif args.strategy == "sijot-aware":
                    from scripts.compare_chunking_strategies import _compute_sijot_aware_chunks
                    from modules.library.chunking import convert_temporary_chunks_to_db_format
                    tmp = _compute_sijot_aware_chunks(content)
                    result = convert_temporary_chunks_to_db_format(
                        tmp, doc_id_inst, text_id, language=doc["language"],
                    )
                    for c in result:
                        c["collection_id"] = doc["collection_id"]
                        c["page_start"] = None
                        c["page_end"] = None
                        c["chapter"] = None
                        c["section"] = c.get("metadata", {}).get("section", {}).get("section_label")
                        c["created_at"] = datetime.datetime.utcnow()
                        c["updated_at"] = datetime.datetime.utcnow()
                else:
                    from modules.library.chunking import chunk_text
                    result = chunk_text(
                        content, doc_id_inst, text_id,
                        language=doc["language"],
                        chunk_size=args.chunk_size_chars,
                        overlap=args.chunk_overlap_chars,
                        min_chunk=args.min_chunk_chars,
                    )
                    for c in result:
                        c["collection_id"] = doc["collection_id"]
                        c["page_start"] = None
                        c["page_end"] = None
                        c["chapter"] = None
                        c["section"] = None
                        c["metadata"] = {}
                        c["created_at"] = datetime.datetime.utcnow()
                        c["updated_at"] = datetime.datetime.utcnow()

                total_chunks += len(result)

                if args.dry_run or not args.apply:
                    all_chunks_for_dry_run.append({
                        "title": doc["title"],
                        "chunks": len(result),
                        "sample": result[0] if result else None,
                    })
                    print(f"  {doc['title']}: {len(result)} chunks")
                else:
                    from modules.library.vector_repository import create_chunks
                    if result:
                        inserted = await create_chunks(conn, result)
                        print(f"  {doc['title']}: {len(result)} chunks (inserted {inserted})")

            if args.dry_run or not args.apply:
                print(f"\nDry-run total: {total_chunks} chunks would be created")
                return 0

            from modules.library.vector_repository import count_chunks
            final = await count_chunks(conn, collection_id=coll_id)
            print(f"\nChunks created: {total_chunks}")
            print(f"Total chunks in collection: {final}")
            return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    if not args.dry_run and not args.apply:
        print("WARNING: Running in apply mode by default (legacy behavior). "
              "Use --dry-run to preview or --apply to confirm.", file=sys.stderr)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
