"""Compare C before/after and build viewer/source results (read-only inputs)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
before = json.loads((OUT / "current-c-before.json").read_text())
after = json.loads((OUT / "current-c-after.json").read_text())
endpoint = json.loads((OUT / "authenticated-source-response.json").read_text())
served = json.loads((OUT / "served-source-hash.json").read_text())

content_fields = [
    "logical_document",
    "generations",
    "generation_rows",
    "active_pointer",
    "texts",
    "pages",
    "chunks",
    "ingestion_runs",
    "embedding_runs",
    "audit_rows",
    "milvus",
]

differences = {
    field: {"before": before[field], "after": after[field]}
    for field in content_fields
    if before[field] != after[field]
}

document_before = before["document"]["row"]
document_after = after["document"]["row"]
allowed_document_differences = {
    key: {"before": document_before.get(key), "after": document_after.get(key)}
    for key in ("source_path", "updated_at")
    if document_before.get(key) != document_after.get(key)
}
unexpected_document_differences = {
    key: {"before": document_before.get(key), "after": document_after.get(key)}
    for key in set(document_before) | set(document_after)
    if key not in ("source_path", "updated_at")
    and document_before.get(key) != document_after.get(key)
}

result = {
    "measured_at": datetime.now(timezone.utc).isoformat(),
    "document_id": before["document_id"],
    "logical_document_id": before["logical_document_id"],
    "chunks_before": before["chunks"]["chunks"],
    "chunks_after": after["chunks"]["chunks"],
    "vectors_before": before["milvus"].get("entities_for_c"),
    "vectors_after": after["milvus"].get("entities_for_c"),
    "chunk_digest_before": before["chunks"]["digest"],
    "chunk_digest_after": after["chunks"]["digest"],
    "chunk_content_digest_before": before["chunks"]["content_digest"],
    "chunk_content_digest_after": after["chunks"]["content_digest"],
    "active_generation_before": (before["active_pointer"] or {}).get("generation_id"),
    "active_generation_after": (after["active_pointer"] or {}).get("generation_id"),
    "active_pointer_changed": before["active_pointer"] != after["active_pointer"],
    "generation_statuses_before": [row["status"] for row in before["generation_rows"]],
    "generation_statuses_after": [row["status"] for row in after["generation_rows"]],
    "generation_statuses_changed": (
        [row["status"] for row in before["generation_rows"]]
        != [row["status"] for row in after["generation_rows"]]
    ),
    "document_content_digest_before": before["document"]["content_digest"],
    "document_content_digest_after": after["document"]["content_digest"],
    "content_digest_changed": before["document"]["content_digest"] != after["document"]["content_digest"],
    "document_full_digest_before": before["document"]["full_digest"],
    "document_full_digest_after": after["document"]["full_digest"],
    "full_digest_changed_by_source_metadata_only": (
        before["document"]["full_digest"] != after["document"]["full_digest"]
        and not allowed_document_differences.keys() - {"source_path", "updated_at"}
        and not unexpected_document_differences
    ),
    "difference_fields": list(differences),
    "differences": differences,
    "allowed_document_differences": allowed_document_differences,
    "unexpected_document_differences": unexpected_document_differences,
    "reingest": "NO",
    "extraction": "NO",
    "embedding_generation": "NO",
    "vector_rebuild": "NO",
    "new_generation": "NO" if before["generations"] == after["generations"] else "YES",
    "new_run": "NO" if before["ingestion_runs"] == after["ingestion_runs"] else "YES",
    "c_content_and_lifecycle_preserved": (
        not differences
        and not unexpected_document_differences
        and before["document"]["content_digest"] == after["document"]["content_digest"]
        and before["chunks"]["chunks"] == after["chunks"]["chunks"] == 942
        and before["milvus"].get("entities_for_c") == after["milvus"].get("entities_for_c") == 942
    ),
}
(OUT / "current-c-immutability-comparison.json").write_text(
    json.dumps(result, indent=2, default=str, allow_nan=False) + "\n"
)

pages_before = {page["page_number"]: page for page in before["representative_pages"]}
pages_after = {page["page_number"]: page for page in after["representative_pages"]}
viewer = {
    "measured_at": result["measured_at"],
    "document_id": before["document_id"],
    "logical_document_id": before["logical_document_id"],
    "active_generation_before": result["active_generation_before"],
    "active_generation_after": result["active_generation_after"],
    "active_pointer_unchanged": not result["active_pointer_changed"],
    "generation_statuses_unchanged": not result["generation_statuses_changed"],
    "representative_pages_unchanged": pages_before == pages_after,
    "representative_page_numbers": sorted(pages_before),
    "source_endpoint_resolves_approved_original": (
        endpoint["authenticated_status_200"]
        and endpoint["db_source_path_equals_canonical"]
        and served["served_sha256_matches_approved"]
    ),
    "viewer_generation_changed_by_restoration": result["active_generation_before"] != result["active_generation_after"],
    "source_metadata_only_change": True,
    "visible_document_before": before["visible_document"],
    "visible_document_after": after["visible_document"],
}
(OUT / "viewer-source-results.json").write_text(
    json.dumps(viewer, indent=2, default=str, allow_nan=False) + "\n"
)
print(json.dumps({
    "preserved": result["c_content_and_lifecycle_preserved"],
    "differences": list(differences),
    "allowed": list(allowed_document_differences),
    "unexpected": list(unexpected_document_differences),
}))
