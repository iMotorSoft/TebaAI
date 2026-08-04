#!/usr/bin/env python3
"""Guarded metadata-only DEV backfill for canonical identity V1.

Default mode is dry-run. ``--apply`` updates only the
``bibliographic_metadata.canonical_identity_v1`` JSON object for three sources
resolved by SHA-256. It never changes status, text, chunks, embeddings or Milvus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

import globalVar

IDENTITIES: dict[str, dict[str, Any]] = {
    "c04601782711751c14539224e8f679a740090b9d7f5f09d8877db9c3b6a5ff74": {
        "work_identity": {
            "family_code": "likutey_halajot",
            "family_label": "Likutey Halajot",
            "canonical_work_code": "likutey_halajot",
            "canonical_work_label": "Likutey Halajot",
            "confidence": "explicit",
            "source": "source_front_matter_and_contents",
        },
        "edition_identity": {
            "edition_label": "The Rosenberg Edition",
            "edition_confidence": "explicit",
            "edition_source": "pdf_page_1_title_page",
            "volume_number": None,
            "volume_confidence": "unresolved",
            "volume_source": "unresolved",
        },
        "source_identities": [{
            "source_work_code": "likutey_moharan_ii",
            "source_work_label": "Likutey Moharán II",
            "source_lesson": 8,
            "source_relation": "develops",
            "confidence": "explicit",
            "source": "pdf_pages_1_3_17_and_contents",
        }],
        "technical_identity": {
            "version": None,
            "confidence": "unresolved",
            "source": "unresolved",
        },
    },
    "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a": {
        "work_identity": {
            "family_code": "likutey_halajot",
            "family_label": "Likutey Halajot",
            "canonical_work_code": "likutey_halajot",
            "canonical_work_label": "Likutey Halajot",
            "confidence": "explicit",
            "source": "pdf_title_and_running_headers",
        },
        "edition_identity": {
            "edition_label": "Interior Final",
            "edition_confidence": "derived",
            "edition_source": "source_filename_label",
            "volume_number": None,
            "volume_confidence": "unresolved",
            "volume_source": "unresolved",
            "physical_source_volume_hint": 1,
            "physical_source_volume_hint_confidence": "explicit",
            "physical_source_volume_hint_source": "pdf_page_10",
            "metadata_approval_status": "pending_approval",
        },
        "source_identities": [],
        "source_identity_scope": "section_or_chunk_only",
        "technical_identity": {
            "version": "v2",
            "confidence": "derived",
            "source": "library_documents.metadata.pipeline",
            "pipeline": "likutey_halajot_page_first_v2",
        },
    },
    "ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61": {
        "work_identity": {
            "family_code": "likutey_moharan_ii",
            "family_label": "Likutey Moharán II",
            "canonical_work_code": "likutey_moharan_ii",
            "canonical_work_label": "Likutey Moharán II",
            "confidence": "explicit",
            "source": "pdf_title_and_section_headers",
        },
        "edition_identity": {
            "edition_label": "Edición española BRI",
            "edition_confidence": "derived",
            "edition_source": "document_title",
            "volume_number": None,
            "volume_confidence": "unresolved",
            "volume_source": "unresolved",
        },
        "source_identities": [],
        "technical_identity": {
            "version": "layout_v1",
            "confidence": "derived",
            "source": "library_documents.metadata.layout_profile",
        },
    },
}
EXPECTED_STATUSES = {
    "c04601782711751c14539224e8f679a740090b9d7f5f09d8877db9c3b6a5ff74": "ready",
    "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a": "test_candidate",
    "ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61": "test_candidate",
}


async def run(*, apply: bool, evidence: Path | None) -> None:
    async with await psycopg.AsyncConnection.connect(
        globalVar.POSTGRES_DSN, row_factory=dict_row
    ) as conn:
        rows = await (
            await conn.execute(
                """
                SELECT id::text, title, source_filename, source_sha256, status,
                       bibliographic_metadata, updated_at
                FROM library_documents
                WHERE source_sha256 = ANY(%s::text[])
                ORDER BY source_sha256
                """,
                (list(IDENTITIES),),
            )
        ).fetchall()
        if len(rows) != len(IDENTITIES):
            raise RuntimeError("canonical sources are not unique and complete")
        for row in rows:
            if row["status"] != EXPECTED_STATUSES[row["source_sha256"]]:
                raise RuntimeError("document status guard failed")
        before = [dict(row) for row in rows]
        if apply:
            for row in rows:
                await conn.execute(
                    """
                    UPDATE library_documents
                    SET bibliographic_metadata = jsonb_set(
                            coalesce(bibliographic_metadata, '{}'::jsonb),
                            '{canonical_identity_v1}', %s::jsonb, true
                        )
                    WHERE id=%s::uuid AND source_sha256=%s AND status=%s
                    """,
                    (
                        json.dumps(IDENTITIES[row["source_sha256"]], ensure_ascii=False),
                        row["id"], row["source_sha256"], row["status"],
                    ),
                )
            await conn.commit()
        else:
            await conn.rollback()

        after_rows = await (
            await conn.execute(
                """
                SELECT id::text, title, source_filename, source_sha256, status,
                       bibliographic_metadata, updated_at
                FROM library_documents
                WHERE source_sha256 = ANY(%s::text[])
                ORDER BY source_sha256
                """,
                (list(IDENTITIES),),
            )
        ).fetchall()
        result = {
            "mode": "apply" if apply else "dry_run",
            "rows": len(after_rows),
            "status_changes": [
                row["source_sha256"] for row in after_rows
                if row["status"] != EXPECTED_STATUSES[row["source_sha256"]]
            ],
            "before": before,
            "after": [dict(row) for row in after_rows],
            "changed_fields": ["bibliographic_metadata.canonical_identity_v1"] if apply else [],
            "forbidden_changes": [],
        }
        if evidence:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
                encoding="utf-8",
            )
        print(json.dumps({
            "mode": result["mode"],
            "rows": result["rows"],
            "status_changes": result["status_changes"],
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply, evidence=args.evidence))
