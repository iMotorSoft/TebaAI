"""Freeze the C content/immutability contract from the before snapshot."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
before = json.loads((OUT / "current-c-before.json").read_text())

body = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "purpose": "values that must remain identical after the source restoration",
    "document_id": before["document_id"],
    "logical_document_id": before["logical_document_id"],
    "allowed_to_change": [
        "library_documents.source_path",
        "library_documents.updated_at",
    ],
    "must_not_change": {
        "document_content_digest": before["document"]["content_digest"],
        "document_full_digest_excluding_source_metadata": before["document"]["content_digest"],
        "logical_document": before["logical_document"],
        "generations": before["generations"],
        "generation_rows": before["generation_rows"],
        "active_pointer": before["active_pointer"],
        "texts": before["texts"],
        "pages": before["pages"],
        "chunks": before["chunks"],
        "ingestion_runs": before["ingestion_runs"],
        "embedding_runs": before["embedding_runs"],
        "audit_rows": before["audit_rows"],
        "milvus": before["milvus"],
    },
    "expected": {
        "chunks": before["chunks"]["chunks"],
        "vectors": before["milvus"].get("entities_for_c"),
        "active_generation": (before["active_pointer"] or {}).get("generation_id"),
        "generation_statuses": [row["status"] for row in before["generation_rows"]],
        "chunk_digest": before["chunks"]["digest"],
        "chunk_content_digest": before["chunks"]["content_digest"],
        "pages": before["pages"]["pages"],
    },
    "forbidden_operations": [
        "reingest",
        "extraction",
        "chunk generation",
        "embedding generation",
        "vector rebuild",
        "generation switch",
        "active pointer change",
    ],
}
(OUT / "c-content-immutability-contract.json").write_text(
    json.dumps(body, indent=2, default=str, allow_nan=False) + "\n"
)
print(json.dumps(body["expected"]))
