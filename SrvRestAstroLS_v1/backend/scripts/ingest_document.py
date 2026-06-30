#! /usr/bin/env python3
"""
CLI document ingestion for TebaAI library.

For PDFs, the canonical extractor is PyMuPDF4LLM and content is stored as Markdown.

Usage:
    uv run python -m scripts.ingest_document \\
        --file /path/to/doc.pdf --title "Title" \\
        --language en --collection breslov_test \\
        --status test_candidate --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a document into the TebaAI library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", "--source-path", dest="file", required=True,
                        help="Path to the source file")
    parser.add_argument("--title", required=True, help="Document title")
    parser.add_argument("--language", required=True, choices=["es", "en", "he"],
                        help="Document language code")
    parser.add_argument("--collection", required=True, help="Collection code")
    parser.add_argument("--source-type",
                        choices=["book", "article", "pdf", "markdown", "text", "other"],
                        help="Source type (inferred from extension when omitted)")
    parser.add_argument("--collection-name", help="Display name for the collection")
    parser.add_argument("--subtitle", help="Document subtitle")
    parser.add_argument("--author", help="Author name")
    parser.add_argument("--publisher", help="Publisher name")
    parser.add_argument("--publication-year", type=int, help="Publication year")
    parser.add_argument("--bibliographic-ref", help="Bibliographic reference string")
    parser.add_argument("--version-label", help="Version label")
    parser.add_argument("--status", default="ready",
                        choices=["draft", "ready", "test_candidate", "archived", "error"],
                        help="Document lifecycle status")
    parser.add_argument("--metadata-json", help="JSON object stored as bibliographic metadata")
    parser.add_argument("--created-by-email", help="Email of the creating user")
    parser.add_argument("--dry-run", action="store_true", help="Validate without persisting")
    parser.add_argument("--apply", action="store_true", help="Actually persist to database")
    parser.add_argument("--extractor", default=None, help="Extraction engine (pymupdf4llm for PDF)")
    parser.add_argument("--content-format", default=None, help="Content format (markdown for PDF)")
    parser.add_argument("--output-json", help="Write JSON report to file")
    parser.add_argument("--output-md", help="Write Markdown report to file")

    args = parser.parse_args(argv)
    if args.source_type is None:
        args.source_type = _infer_source_type(args.file)
    return args


def _infer_source_type(file_path: str) -> str:
    extension = pathlib.Path(file_path).suffix.lower()
    return {".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".txt": "text"}.get(extension, "other")


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import transaction
    from modules.library.schemas import IngestDocumentRequest
    from modules.library.service import ingest_document

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: PostgreSQL not enabled via globalVar.py", file=sys.stderr)
        return 1

    req = IngestDocumentRequest(
        file_path=args.file,
        title=args.title,
        language=args.language,
        collection=args.collection,
        source_type=args.source_type,
        collection_name=args.collection_name,
        subtitle=args.subtitle,
        author=args.author,
        publisher=args.publisher,
        publication_year=args.publication_year,
        bibliographic_ref=args.bibliographic_ref,
        version_label=args.version_label,
        status=args.status,
        metadata_json=args.metadata_json,
        created_by_email=args.created_by_email,
        dry_run=args.dry_run or not args.apply,
    )

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected 'tebaai', got '{db}'", file=sys.stderr)
                return 1

        is_dry = args.dry_run or not args.apply
        if is_dry:
            print("── Dry-run mode: validating without persisting ──")

        async with transaction(pool) as conn:
            if is_dry:
                await conn.execute("SET TRANSACTION READ ONLY")
            result = await ingest_document(conn, req)

        # Detect extractor
        from modules.library.extractors import detect_text_format
        ext = pathlib.Path(args.file).suffix.lower()
        text_format, extractor_method = detect_text_format(ext)

        report = {
            "collection": result.collection_code,
            "document_id": str(result.document_id),
            "title": result.title,
            "language": result.language,
            "status": result.status,
            "source_sha256": result.source_sha256,
            "content_sha256": result.content_sha256,
            "content_length": result.content_length,
            "is_new": result.is_new,
            "dry_run": result.dry_run,
            "extractor": str(extractor_method.value) if hasattr(extractor_method, 'value') else str(extractor_method),
            "content_format": str(text_format.value) if hasattr(text_format, 'value') else str(text_format),
            "will_create_chunks": False,
            "will_touch_milvus": False,
            "will_call_litellm": False,
        }

        outcome = "validated" if result.dry_run else "persisted"
        print(f"\n── Document ingestion {outcome} successfully ──")
        for k, v in report.items():
            print(f"  {k}: {v}")

        if args.output_json:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            print(f"JSON: {args.output_json}")

        return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
