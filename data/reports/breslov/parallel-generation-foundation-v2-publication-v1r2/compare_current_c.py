#!/usr/bin/env python3
"""Compare CURRENT C before/after the frozen candidate validation."""
from __future__ import annotations
import json, pathlib

OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
FIELDS = ["document", "logical", "generations", "active_pointer", "chunks", "embeddings",
          "pages", "runs", "visible_in_library_visible_documents", "viewer_publication",
          "representative_chunks", "source", "milvus"]

before = json.loads((OUT / "current-c-before.json").read_text())
after = json.loads((OUT / "current-c-after.json").read_text())
diffs = []
for field in FIELDS:
    if before.get(field) != after.get(field):
        diffs.append({"field": field, "before": before.get(field), "after": after.get(field)})
expected = before.get("expected", {})
checks = {
    "same_document": before.get("document_id") == after.get("document_id"),
    "same_logical_document": before.get("logical_document_id") == after.get("logical_document_id"),
    "active_generation_unchanged": (after.get("active_pointer") or {}).get("generation_id") == expected.get("active_generation"),
    "chunks_942": (after.get("chunks") or {}).get("count") == 942,
    "vectors_942": (after.get("milvus") or {}).get("document_vector_count") == 942,
    "embeddings_942": (after.get("embeddings") or {}).get("count") == 942,
    "source_sha_unchanged": (after.get("source") or {}).get("source_sha256") == (before.get("source") or {}).get("source_sha256"),
    "chunk_digest_unchanged": (after.get("chunks") or {}).get("digest") == (before.get("chunks") or {}).get("digest"),
    "page_digest_unchanged": (after.get("pages") or {}).get("digest") == (before.get("pages") or {}).get("digest"),
    "embedding_digest_unchanged": (after.get("embeddings") or {}).get("digest") == (before.get("embeddings") or {}).get("digest"),
    "no_field_differences": not diffs,
}
report = {
    "gate": GATE, "CURRENT_C_DOCUMENT": before.get("document_id"),
    "CURRENT_C_LOGICAL": before.get("logical_document_id"),
    "CURRENT_C_ACTIVE_GENERATION": expected.get("active_generation"),
    "CURRENT_C_CHUNKS": 942, "CURRENT_C_VECTORS": 942,
    "CURRENT_C_SOURCE_SHA256": (before.get("source") or {}).get("source_sha256"),
    "field_differences": diffs, "checks": checks,
    "CURRENT_C_PRESERVED": "YES" if all(checks.values()) else "NO",
    "PASS": all(checks.values()),
}
(OUT / "current-c-immutability-comparison.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({"PASS": report["PASS"], "PRESERVED": report["CURRENT_C_PRESERVED"],
                  "differences": len(diffs)}, indent=2))
