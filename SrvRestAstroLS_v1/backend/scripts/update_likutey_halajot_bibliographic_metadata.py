#!/usr/bin/env python3
"""
Metadata-only update for Likutey Halajot Interior Final (document 47768aac).

Idempotent. Dry-run by default. Requires --apply to write.
Only touches library_documents.metadata and bibliographic_metadata.
Does NOT touch chunks, embeddings, Milvus, or document status.

Usage:
    uv run python -m scripts.update_likutey_halajot_bibliographic_metadata --dry-run
    uv run python -m scripts.update_likutey_halajot_bibliographic_metadata --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

DOC_ID = "47768aac-704e-4296-9649-53b9ea037096"

# Bibliographic metadata extracted from PDF front matter (pages 1-4)
PROPOSED = {
    "source_quality": {
        "source_kind": "pdf_modern_unicode_si960",
        "canonical_text_role": "candidate",
        "promotion_recommendation": "promovible_con_observaciones",
        "canonical_text_allowed": True,
        "text_quality_status": "pass_layout_aware",
        "layout_status": "layout_aware_parsed",
        "page_mapping_status": "layout_based_mapping",
        "ocr_status": "not_ocr",
        "document_family": "Breslov/LikuteyHalajot",
        "language_hints": ["es", "he"],
        "ingestion_profile": "layout_aware_likutey_halajot",
    },
    "extraction": {
        "method": "layout_aware_pymupdf_dict",
        "pages": 284,
        "parser": "likutey_layout_parser",
    },
    "bibliographic": {
        "work_title_original_he": "ליקוטי הלכות",
        "work_title_original_en": "Likutey Halakhot",
        "work_title_section": "Orach Chaim — Hashkamat HaBoker (Levantándose por la Mañana)",
        "section_he": "אורח חיים — הלכות השכמת הבוקר",
        "volume_info": "The Rosenberg Edition",
        "author": "Reb Noson Sternhartz of Breslov (Rabí Natán de Breslov)",
        "commentator": "Moshé Mykoff",
        "contributor": "Dov Grant",
        "translator_es": "Guillermo Beilinson",
        "editor": "Breslov Research Institute Editorial Staff",
        "publisher": "Breslov Research Institute",
        "publisher_places": ["Jerusalem, Israel", "Monsey, NY, USA"],
        "publication_year": 2020,
        "edition": "First Edition",
        "copyright": "©2020 Breslov Research Institute",
        "rights_statement": "All rights reserved. No part may be reproduced without permission.",
        "public_exposure_status": "internal_only",
        "metadata_status": "complete",
        "metadata_confidence": "high",
        "metadata_source": "pdf_front_matter",
        "metadata_review_notes": (
            "Metadata extracted from PDF pages 1-4. Title page, copyright page, "
            "and credits page all present and consistent. Author (Reb Noson), "
            "commentator/annotator (Moshé Mykoff), Spanish translator (Guillermo Beilinson), "
            "publisher (Breslov Research Institute), year (2020), edition (First) all found. "
            "ISBN not found in visible front matter. "
            "PDF is 'The Rosenberg Edition' containing Orach Chaim section only."
        ),
    },
}


def parse_args():
    p = argparse.ArgumentParser(description="Update Likutey Halajot bibliographic metadata")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--apply", action="store_true", default=False)
    return p.parse_args()


async def main():
    args = parse_args()
    is_dry = not args.apply

    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, execute

    pool = create_pool_from_settings()
    await open_pool(pool)

    async with pool.connection() as conn:
        # Read current metadata
        current = await fetch_one(conn, """
            SELECT id, title, subtitle, author, editor, translator,
                   publisher, publication_year, edition, bibliographic_ref,
                   version_label, metadata, bibliographic_metadata
            FROM library_documents
            WHERE id = %(id)s
        """, {"id": DOC_ID})

        if not current:
            print(f"ERROR: Document {DOC_ID} not found")
            return 1

        print(f"Document: {current['id']}")
        print(f"Current title: {current['title']}")
        print()

        # Show diff
        print("Proposed metadata changes:")
        print("-" * 50)

        fields = [
            ("subtitle", "Levantándose por la Mañana — Hashkamat HaBoker (Orach Chaim)"),
            ("author", "Reb Noson Sternhartz of Breslov (Rabí Natán de Breslov)"),
            ("editor", "Moshé Mykoff (annotator) ; Breslov Research Institute"),
            ("translator", "Guillermo Beilinson"),
            ("publisher", "Breslov Research Institute"),
            ("publication_year", 2020),
            ("edition", "First Edition"),
            ("bibliographic_ref", "Likutey Halakhot: Orach Chaim — Hashkamat HaBoker (The Rosenberg Edition)"),
        ]

        changes = []
        for field, value in fields:
            curr_val = current.get(field)
            if str(curr_val or "") != str(value):
                changes.append((field, curr_val, value))
                print(f"  {field:20s}: {str(curr_val or '-')[:40]:40s} → {str(value)[:50]}")

        # Build new bibliographic_metadata (merge with existing)
        new_bmeta = dict(current.get("bibliographic_metadata") or {})
        new_bmeta.update(PROPOSED)

        # Build new metadata (merge with existing)
        new_meta = dict(current.get("metadata") or {})
        new_meta["ingestion_profile"] = "layout_aware_likutey_halajot"
        new_meta["bibliographic_status"] = "complete"
        new_meta["metadata_confidence"] = "high"
        new_meta["metadata_review_notes"] = PROPOSED["bibliographic"]["metadata_review_notes"]

        print(f"\n  Total field changes: {len(changes)}")
        print(f"  bibliographic_metadata keys: {list(PROPOSED.keys())}")
        print(f"  metadata keys: author, editor, translator, publisher, year, edition")

        if not changes:
            print("\n  No changes needed — metadata already up to date.")
            return 0

        if is_dry:
            print(f"\n  DRY-RUN: Would apply {len(changes)} metadata-only updates.")
            print(f"  Run with --apply to write.")
            return 0

        # Apply
        async with conn.transaction():
            await execute(conn, """
                UPDATE library_documents SET
                    subtitle = %(subtitle)s,
                    author = %(author)s,
                    editor = %(editor)s,
                    translator = %(translator)s,
                    publisher = %(publisher)s,
                    publication_year = %(year)s,
                    edition = %(edition)s,
                    bibliographic_ref = %(ref)s,
                    metadata = %(meta)s::jsonb,
                    bibliographic_metadata = %(bmeta)s::jsonb,
                    updated_at = now()
                WHERE id = %(id)s
            """, {
                "id": DOC_ID,
                "subtitle": "Levantándose por la Mañana — Hashkamat HaBoker (Orach Chaim)",
                "author": "Reb Noson Sternhartz of Breslov (Rabí Natán de Breslov)",
                "editor": "Moshé Mykoff (annotator) ; Breslov Research Institute",
                "translator": "Guillermo Beilinson",
                "publisher": "Breslov Research Institute",
                "year": 2020,
                "edition": "First Edition",
                "ref": "Likutey Halakhot: Orach Chaim — Hashkamat HaBoker (The Rosenberg Edition)",
                "meta": json.dumps(new_meta),
                "bmeta": json.dumps(new_bmeta),
            })

        # Verify
        updated = await fetch_one(conn, """
            SELECT subtitle, author, editor, translator, publisher,
                   publication_year, edition
            FROM library_documents WHERE id = %(id)s
        """, {"id": DOC_ID})

        print(f"\n  Applied successfully!")
        print(f"  Verified: subtitle={updated['subtitle'][:40]}, author={updated['author'][:40]}")
        print(f"  Status NOT changed (still test_candidate)")
        print(f"  Chunks/embeddings NOT touched")

    await close_pool(pool)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
