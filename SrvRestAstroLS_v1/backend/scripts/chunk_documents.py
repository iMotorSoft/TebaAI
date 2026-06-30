#! /usr/bin/env python3
"""
CLI: Chunk documents in the library.

Supports two strategies:
  - generic:     paragraph-based chunking (original default)
  - sijot-aware: section-aware chunking for documents with Sija headings

Usage:
    uv run python -m scripts.chunk_documents --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" --strategy sijot-aware --dry-run

    uv run python -m scripts.chunk_documents --collection breslov_test \\
        --document-title "El Alma del Rebe Najmán" --strategy sijot-aware --apply

Requirements:
    - PostgreSQL must be running and accessible
    - Database must be 'tebaai' with migrations applied
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk documents in a library collection.")
    parser.add_argument("--collection", required=True, help="Collection code to chunk")
    parser.add_argument("--document-title", default=None, help="Specific document title (optional)")
    parser.add_argument("--chunk-size-chars", type=int, default=1800, help="Max chars per chunk")
    parser.add_argument("--chunk-overlap-chars", type=int, default=250, help="Overlap between chunks")
    parser.add_argument("--min-chunk-chars", type=int, default=200, help="Min chars per chunk")
    parser.add_argument("--strategy", default="generic", choices=["generic", "sijot-aware"],
                        help="Chunking strategy (default: generic)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be chunked without inserting")
    parser.add_argument("--apply", action="store_true", help="Persist chunks to database")
    parser.add_argument("--output-json", default=None, help="Output JSON path (dry-run only)")
    parser.add_argument("--output-md", default=None, help="Output Markdown path (dry-run only)")
    return parser.parse_args(argv)


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

            # ── Resolve collection ──────────────────────────────────
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

            # ── Build document query ────────────────────────────────
            doc_params: dict = {"coll_id": str(coll_id)}
            title_filter = ""
            if args.document_title:
                title_filter = " AND d.title = %(title)s"
                doc_params["title"] = args.document_title

            # For sijot-aware, allow test_candidate; for generic, require ready
            if args.strategy == "sijot-aware":
                status_filter = "d.status IN ('ready', 'test_candidate')"
            else:
                status_filter = "d.status = 'ready'"

            await cur.execute(f"""
                SELECT d.id AS doc_id, t.id AS text_id, d.title, d.language,
                       d.collection_id, t.content, d.status
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

            # ── Safety guards for sijot-aware apply ──────────────
            if args.strategy == "sijot-aware" and args.apply:
                for doc in docs:
                    if doc["status"] != "test_candidate":
                        print(f"ERROR: Sijot-aware apply requires test_candidate status, "
                              f"got '{doc['status']}' for '{doc['title']}'", file=sys.stderr)
                        return 1
                if not args.collection.endswith("_test"):
                    print(f"ERROR: Sijot-aware apply requires a *_test collection, "
                          f"got '{args.collection}'", file=sys.stderr)
                    return 1

            # ── Preflight for sijot-aware: validate detection quality ──
            sijot_metrics = None
            if args.strategy == "sijot-aware":
                from scripts.compare_chunking_strategies import (
                    _compute_sijot_aware_chunks,
                    _compute_sijot_metrics,
                    SIJOT_EXPECTED_COUNT,
                )
                for doc in docs:
                    test_chunks = _compute_sijot_aware_chunks(doc["content"])
                    test_metrics = _compute_sijot_metrics(test_chunks)
                    print(f"  Preflight {doc['title']}: {test_metrics.sijot_detected}/"
                          f"{SIJOT_EXPECTED_COUNT} Sijot, "
                          f"{len(test_metrics.missing_sijot)} missing, "
                          f"{test_metrics.chunks_crossing_sections} cross-section")
                    if test_metrics.sijot_detected < SIJOT_EXPECTED_COUNT:
                        print(f"ERROR: Sijot detection incomplete "
                              f"({test_metrics.sijot_detected}/{SIJOT_EXPECTED_COUNT}).",
                              file=sys.stderr)
                        if args.apply:
                            return 1
                    if test_metrics.missing_sijot:
                        print(f"WARNING: {len(test_metrics.missing_sijot)} missing Sijot "
                              f"({test_metrics.missing_sijot}).", file=sys.stderr)
                        if args.apply:
                            return 1
                    if test_metrics.chunks_crossing_sections > 0:
                        print(f"WARNING: {test_metrics.chunks_crossing_sections} chunks "
                              f"cross section boundaries.", file=sys.stderr)
                        if args.apply:
                            return 1
                    sijot_metrics = test_metrics

            # ── Process each document ────────────────────────────────
            from uuid import UUID
            import datetime

            total_chunks = 0
            all_chunks_for_dry_run: list[dict] = []

            for doc in docs:
                raw_doc_id = doc["doc_id"]
                raw_text_id = doc["text_id"]
                doc_id = raw_doc_id if isinstance(raw_doc_id, UUID) else UUID(raw_doc_id)
                text_id = raw_text_id if isinstance(raw_text_id, UUID) else UUID(raw_text_id)
                content = doc["content"]

                if args.strategy == "sijot-aware":
                    from scripts.compare_chunking_strategies import (
                        _compute_sijot_aware_chunks,
                    )
                    from modules.library.chunking import convert_temporary_chunks_to_db_format
                    tmp_chunks = _compute_sijot_aware_chunks(content)
                    result = convert_temporary_chunks_to_db_format(
                        tmp_chunks, doc_id, text_id, language=doc["language"],
                    )
                else:
                    from modules.library.chunking import chunk_text
                    result = chunk_text(
                        content, doc_id, text_id,
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
                    section_label = None
                    if c.get("metadata", {}).get("section", {}).get("section_label"):
                        section_label = c["metadata"]["section"]["section_label"]
                    c["section"] = section_label
                    if "metadata" not in c or not c["metadata"]:
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
                report = _build_dry_run_report(args, docs, total_chunks, all_chunks_for_dry_run, sijot_metrics)
                if args.output_json:
                    import json
                    with open(args.output_json, "w", encoding="utf-8") as f:
                        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
                    print(f"JSON report: {args.output_json}")
                if args.output_md:
                    with open(args.output_md, "w", encoding="utf-8") as f:
                        f.write(_build_md_report(args, report))
                    print(f"Markdown report: {args.output_md}")
                print(f"\nDry-run total: {total_chunks} chunks would be created")
                return 0

            from modules.library.vector_repository import count_chunks
            final = await count_chunks(conn, collection_id=coll_id)
            print(f"\nChunks created: {total_chunks}")
            print(f"Total chunks in collection: {final}")
            return 0

    finally:
        await close_pool(pool)


def _build_dry_run_report(args: argparse.Namespace, docs: list[dict],
                          total_chunks: int, chunks_list: list[dict],
                          sijot_metrics) -> dict:
    report = {
        "collection": args.collection,
        "document_title": args.document_title or "all",
        "strategy": args.strategy,
        "dry_run": True,
        "documents": len(docs),
        "total_chunks": total_chunks,
    }
    if sijot_metrics and args.strategy == "sijot-aware":
        from scripts.compare_chunking_strategies import SIJOT_EXPECTED_COUNT
        report["sijot_detected"] = sijot_metrics.sijot_detected
        report["expected_sijot"] = SIJOT_EXPECTED_COUNT
        report["missing_sijot"] = sijot_metrics.missing_sijot
        report["chunks_crossing_sections"] = sijot_metrics.chunks_crossing_sections
        report["chunks_with_section_metadata"] = sijot_metrics.chunks_with_section_metadata
    return report


def _build_md_report(args: argparse.Namespace, report: dict) -> str:
    lines = [
        f"# Chunk dry-run: {report['strategy']} on {report['collection']}",
        "",
        f"**Document**: {report['document_title']}",
        f"**Strategy**: {report['strategy']}",
        f"**Total chunks**: {report['total_chunks']}",
        f"**Documents**: {report['documents']}",
        "",
    ]
    if "sijot_detected" in report:
        lines += [
            "## Sijot detection",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Sijot detected | {report['sijot_detected']}/{report['expected_sijot']} |",
            f"| Missing | {report.get('missing_sijot', [])} |",
            f"| Cross-section | {report.get('chunks_crossing_sections', 0)} |",
            f"| With section metadata | {report.get('chunks_with_section_metadata', 0)} |",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    if not args.dry_run and not args.apply:
        print("WARNING: Running in apply mode by default (legacy behavior). "
              "Use --dry-run to preview or --apply to confirm.", file=sys.stderr)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
