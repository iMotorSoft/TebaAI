#!/usr/bin/env python3
"""Read-only canonical work/edition/source metadata V1 audit."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

import globalVar
from modules.library.bibliographic_planner import resolve_volume_for_document
from modules.library.canonical_metadata import (
    document_matches_scope,
    identity_from_document,
    resolve_canonical_scope,
)

TARGET_HASHES = [
    "c04601782711751c14539224e8f679a740090b9d7f5f09d8877db9c3b6a5ff74",
    "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a",
    "ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61",
]
QUERIES = [
    "¿Dónde habla Likutey Halajot sobre la plegaria?",
    "Buscá esto solo en Interior Final.",
    "¿Dónde desarrolla Likutey Halajot la lección 8 de Likutey Moharán II?",
    "¿Dónde está la lección 8 de Likutey Moharán II?",
    "Compará Likutey Moharán II 8 con Likutey Halajot.",
    "Likutey",
]


def dump(output: Path, name: str, value: Any) -> None:
    (output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


async def audit(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    async with await psycopg.AsyncConnection.connect(
        globalVar.POSTGRES_DSN, row_factory=dict_row
    ) as conn:
        await conn.execute("SET TRANSACTION READ ONLY")
        rows = await (
            await conn.execute(
                """
                SELECT d.id::text AS document_id, d.title, d.source_filename,
                       d.source_sha256, d.status, d.document_code, d.edition,
                       d.metadata, d.bibliographic_metadata,
                       ks.knowledge_scope_code,
                       (SELECT count(*) FROM library_document_chunks c WHERE c.document_id=d.id) AS chunks,
                       (SELECT count(*) FROM library_content_nodes_v2 n
                         JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id
                         WHERE u.document_id=d.id) AS content_nodes
                FROM library_documents d
                JOIN knowledge_scopes ks ON ks.id=d.knowledge_scope_id
                WHERE d.source_sha256 = ANY(%s::text[])
                ORDER BY d.title
                """,
                (TARGET_HASHES,),
            )
        ).fetchall()
    if len(rows) != 3:
        raise RuntimeError("canonical source inventory is incomplete")

    identities = [identity_from_document(dict(row)) for row in rows]
    public = [identity.public() for identity in identities]
    by_hash = {identity.source_sha256: identity for identity in identities}
    scopes = []
    for query in QUERIES:
        scope = resolve_canonical_scope(query, identities)
        scopes.append({
            "query": query,
            "scope": scope.public(),
            "matching_documents": [
                identity.source_filename for identity in identities
                if document_matches_scope(identity, scope)
            ],
        })

    disputed = by_hash[TARGET_HASHES[0]]
    interior = by_hash[TARGET_HASHES[1]]
    lmii = by_hash[TARGET_HASHES[2]]
    failures: list[str] = []
    if disputed.family_code != "likutey_halajot":
        failures.append("source_lesson_changed_work_family")
    if not disputed.source_identities or disputed.source_identities[0].lesson_number != 8:
        failures.append("source_relation_missing")
    if disputed.volume.value is not None or interior.volume.value is not None or lmii.volume.value is not None:
        failures.append("non_explicit_volume_resolved")
    if interior.technical_version.value != "v2":
        failures.append("technical_version_missing")
    family_scope = resolve_canonical_scope("Likutey Halajot", identities)
    edition_scope = resolve_canonical_scope("Interior Final", identities)
    family_docs = [item for item in identities if document_matches_scope(item, family_scope)]
    edition_docs = [item for item in identities if document_matches_scope(item, edition_scope)]
    if len(family_docs) <= len(edition_docs):
        failures.append("family_and_edition_scope_indistinguishable")
    if any(
        value.confidence == "explicit" and value.source in {"unresolved", "filename", "document_code"}
        for identity in identities
        for value in (identity.edition, identity.volume, identity.technical_version)
    ):
        failures.append("untraceable_explicit_metadata")

    planner = []
    for row in rows:
        volume = resolve_volume_for_document(dict(row))
        planner.append({
            "source_filename": row["source_filename"],
            "document_code": row["document_code"],
            "technical_version": identity_from_document(dict(row)).technical_version.public(),
            "planner_volume_number": volume.volume_number,
            "planner_volume_source": volume.volume_source.value,
            "pass": volume.volume_number is None,
        })
        if volume.volume_number is not None:
            failures.append(f"planner_inferred_volume:{row['source_filename']}")

    dimension_matrix = [
        {
            "dimension": "work_family",
            "current_field": "bibliographic_metadata.canonical_identity_v1.work_identity",
            "persisted": True,
            "derived": False,
            "scope": True,
            "ranking": False,
        },
        {
            "dimension": "canonical_work",
            "current_field": "bibliographic_metadata.canonical_identity_v1.work_identity",
            "persisted": True,
            "derived": False,
            "scope": True,
            "ranking": False,
        },
        {
            "dimension": "edition",
            "current_field": "bibliographic_metadata.canonical_identity_v1.edition_identity",
            "persisted": True,
            "derived": "allowed_with_provenance",
            "scope": True,
            "ranking": False,
        },
        {
            "dimension": "volume",
            "current_field": "bibliographic_metadata.canonical_identity_v1.edition_identity",
            "persisted": True,
            "derived": False,
            "scope": True,
            "ranking": False,
        },
        {
            "dimension": "source_work/source_lesson",
            "current_field": "bibliographic_metadata.canonical_identity_v1.source_identities",
            "persisted": "document_when_global; section/chunk_when_local",
            "derived": False,
            "scope": True,
            "ranking": False,
        },
        {
            "dimension": "technical_version",
            "current_field": "metadata.pipeline/document_code plus canonical technical provenance",
            "persisted": True,
            "derived": True,
            "scope": False,
            "ranking": False,
        },
        {
            "dimension": "document_instance",
            "current_field": "library_documents id/filename/hash/status",
            "persisted": True,
            "derived": False,
            "scope": True,
            "ranking": "status tiebreak only",
        },
    ]
    dump(output, "document-dimension-inventory.json", {"documents": rows, "dimensions": dimension_matrix})
    dump(output, "canonical-identity-matrix.json", public)
    dump(output, "source-relations.json", [source.public() | {"document": identity.source_filename} for identity in identities for source in identity.source_identities])
    dump(output, "scope-family-results.json", [item for item in scopes if item["scope"]["scope_family"] and not item["scope"]["scope_edition"]])
    dump(output, "scope-edition-results.json", [item for item in scopes if item["scope"]["scope_edition"]])
    dump(output, "scope-source-results.json", [item for item in scopes if item["scope"]["scope_source_work"] or item["scope"]["cross_family"]])
    dump(output, "planner-volume-results.json", planner)
    dump(output, "ambiguous-query-results.json", [item for item in scopes if item["scope"]["scope_ambiguous"]])
    dump(output, "api-contract-results.json", {
        "optional_request_fields": ["scope_family", "scope_edition", "scope_document_sha256", "scope_source_work", "scope_source_lesson"],
        "optional_hit_fields": ["work_family", "canonical_work", "edition", "volume_number", "source_work", "source_lesson", "source_relation", "technical_version", "metadata_warnings"],
        "breaking_changes": False,
    })
    dump(output, "audit-invariants.json", {"failures": failures, "pass": not failures})
    if failures:
        raise SystemExit("canonical metadata audit failed: " + ", ".join(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(audit(args.output))
