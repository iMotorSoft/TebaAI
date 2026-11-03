"""Offline evidence summarizer. Does not import application code or connect."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).parent
C = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"


def load(name):
    return json.loads((OUT / name).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def summary(label):
    pg, mv, source = (load(f"{kind}-{label}.json") for kind in ("postgres", "milvus", "source"))
    assert pg["selected_document_id"] == C
    doc = next(d for d in pg["documents"] if d["id"] == C)
    assert doc["source_sha256"] == SHA
    generations = [d for d in pg["documents"] if d["source_sha256"] == SHA
                   and d["knowledge_scope_id"] == doc["knowledge_scope_id"]]
    vectors = [row for row in mv["collections"]["tebaai_breslov_chunks_v1"]["records"]
               if row.get("document_id") == C]
    result = {
        "captured_at": pg["captured_at"], "document_id": C,
        "document_metadata": doc,
        "explicit_active_generation_pointer": None,
        "active_resolution": "OBSERVED_SOLE_READY_DOCUMENT_AND_SOLE_COMPLETED_RUN_NOT_A_POINTER",
        "observed_active_run": pg["runs"][0]["run_id"] if len(pg["runs"]) == 1 else None,
        "generation_document_count_by_scope_and_source": len(generations),
        "run_count": len(pg["runs"]), "historical_live_runs": pg["runs"],
        "active_chunk_count_observed": len(pg["chunks"]), "active_vector_count_observed": len(vectors),
        "source_metadata": source,
        "fingerprints": {kind: digest(pg[kind]) for kind in ("runs", "pages", "chunks", "texts", "embeddings")},
        "document_metadata_sha256": digest(doc), "vectors_sha256": digest(vectors),
        "global_content_hashes": pg["content_hashes"],
    }
    save(f"{label}-inventory.json", result)
    return result


if __name__ == "__main__":
    before, after = summary("before"), summary("after")
    keys = ["document_metadata_sha256", "fingerprints", "vectors_sha256", "historical_live_runs",
            "generation_document_count_by_scope_and_source", "active_chunk_count_observed", "active_vector_count_observed"]
    comparisons = {key: before[key] == after[key] for key in keys}
    source = after["source_metadata"]
    external = next(r for r in source["references"] if "Download/Tora/Breslov/" in r["path"])
    assert external["exists"] and external["sha256"] == SHA and external["pages"] == 284
    save("source-verification.json", {
        "source": external, "approved_sha256": SHA, "sha256_match": external["sha256"] == SHA,
        "before_after_source_equal": before["source_metadata"] == after["source_metadata"],
        "source_durable": False, "durable_reference_missing": True,
        "durable_copy_performed": False, "source_metadata_writes": 0,
        "note": "Original availability is verified, not durable OLD storage/backup or a working viewer.",
    })
    save("integrity-verification.json", {
        "comparisons": comparisons, "current_c_content_unchanged": all(comparisons.values()),
        "global_content_hashes_equal": before["global_content_hashes"] == after["global_content_hashes"],
        "current_c_postgresql_writes_by_gate": 0, "current_c_milvus_writes_by_gate": 0,
        "c_reingest_executed": False, "production_touched": False,
        "limitations": "Digest comparison is not a restorable vector export or an audit of other processes.",
    })
    assert all(comparisons.values()), "C changed: readiness forbidden"
    print("C_UNCHANGED", after["observed_active_run"], after["active_chunk_count_observed"], after["active_vector_count_observed"])
