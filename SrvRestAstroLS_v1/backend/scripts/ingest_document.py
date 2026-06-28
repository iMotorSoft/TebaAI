#! /usr/bin/env python3
"""
CLI document ingestion for TebaAI library.

Usage:
    uv run python -m scripts.ingest_document \\
        --file /path/to/document.md \\
        --title "Document Title" \\
        --language es \\
        --collection breslov \\
        --source-type markdown

Requirements:
    - PostgreSQL must be running and accessible
    - Database must be 'tebaai' with migration 003 applied
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a document into the TebaAI library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python -m scripts.ingest_document \\\n"
            "      --file /tmp/doc.md --title \"Mi doc\" \\\n"
            "      --language es --collection general --source-type markdown\n\n"
            "  uv run python -m scripts.ingest_document \\\n"
            "      --file /tmp/doc.pdf --title \"PDF Doc\" \\\n"
            "      --language en --collection breslov --source-type pdf \\\n"
            "      --author \"Author Name\" --dry-run\n"
        ),
    )

    parser.add_argument("--file", required=True, help="Path to the source file")
    parser.add_argument("--title", required=True, help="Document title")
    parser.add_argument(
        "--language", required=True, choices=["es", "en", "he"],
        help="Document language code",
    )
    parser.add_argument("--collection", required=True, help="Collection code (e.g. breslov, general)")
    parser.add_argument(
        "--source-type", required=True,
        choices=["book", "article", "pdf", "markdown", "text", "other"],
        help="Source type",
    )

    parser.add_argument("--collection-name", help="Display name for the collection (defaults to --collection)")
    parser.add_argument("--subtitle", help="Document subtitle")
    parser.add_argument("--author", help="Author name")
    parser.add_argument("--publisher", help="Publisher name")
    parser.add_argument("--publication-year", type=int, help="Publication year")
    parser.add_argument("--bibliographic-ref", help="Bibliographic reference string")
    parser.add_argument("--version-label", help="Version label (e.g. 1.0, draft-2)")
    parser.add_argument("--metadata-json", help="JSON string with extra metadata")
    parser.add_argument("--created-by-email", help="Email of the creating user")
    parser.add_argument("--dry-run", action="store_true", help="Validate and extract but do not persist")

    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import transaction
    from modules.library.schemas import IngestDocumentRequest
    from modules.library.service import ingest_document

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
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
        metadata_json=args.metadata_json,
        created_by_email=args.created_by_email,
        dry_run=args.dry_run,
    )

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            # Verify database
            cur = conn.cursor()
            await cur.execute("SELECT current_database()")
            db = (await cur.fetchone())["current_database"]
            if db != "tebaai":
                print(f"ERROR: Expected database 'tebaai', got '{db}'", file=sys.stderr)
                return 1

        if args.dry_run:
            print("── Dry-run mode: validating without persisting ──")

        async with transaction(pool) as conn:
            result = await ingest_document(conn, req)

        print()
        print("── Document ingested successfully ──")
        print(f"  Collection:     {result.collection_code}")
        print(f"  Document ID:    {result.document_id}")
        print(f"  Title:          {result.title}")
        print(f"  Language:       {result.language}")
        print(f"  Status:         {result.status}")
        print(f"  Source SHA-256: {result.source_sha256}")
        print(f"  Content SHA-256:{result.content_sha256}")
        print(f"  Content length: {result.content_length} chars")
        print(f"  Is new:         {'yes' if result.is_new else 'no (duplicate)'}")
        print(f"  Dry run:        {'yes' if result.dry_run else 'no'}")
        print()
        return 0

    finally:
        await close_pool(pool)


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
