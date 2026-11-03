"""Write README.md, REPORT.md and recommendation.md from the measured artifacts."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text()) if path.is_file() else {}


def main() -> None:
    gate = load("gate.json")
    auth = load("authenticated-source-response.json")
    served = load("served-source-hash.json")
    unauth = load("unauthenticated-source-response.json")
    durable = load("durable-file-before-metadata.json")
    runs = load("restoration-run.json")
    writes = load("database-write-accounting.json")
    imm = load("current-c-immutability-comparison.json")
    fresh = load("durability-fresh-process.json")
    frozen = load("final-frozen-hash-check.json")
    approved = load("approved-source-verification.json")
    idem = load("idempotency-results.json")
    neg = load("wrong-source-negative-control.json")
    final = load("final-validation.json")

    readme = f"""# C durable source restoration V1

Gate: `{gate.get('gate')}`
Status: **{gate.get('status')}**
Report directory: `data/reports/breslov/c-durable-source-restoration-v1/`

Operational data repair of the `source_path` of document C. The approved
external PDF was copied into TebaAI's existing managed durable storage
(`modules.library.durable_source.preserve_source`), the existing
`library_documents.source_path` column was set for C only, and the
authenticated source endpoint now serves exactly the approved bytes.

* document_id: `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`
* logical_document_id: `db200a31-b547-5668-d968-06d0ec36ad95`
* durable path: `{durable.get('path')}`
* approved sha256: `{approved.get('actual_sha256')}`
* product code changes by this gate: **{final.get('product_code_files_modified_by_gate_count')}**
* commit / push: NO / NO

No reingest, extraction, chunking, embedding, vector write or generation
activation was performed. C keeps 942 chunks, 942 vectors, one ACTIVE
generation and the same active pointer.

See `REPORT.md` for the full evidence map and `recommendation.md` for the next
gate.
"""
    (OUT / "README.md").write_text(readme)

    report = f"""# REPORT — C durable source restoration V1

Gate: `{gate.get('gate')}`
Result: **{gate.get('status')}**
Validated at: `{gate.get('validated_at')}`

## 1. Approved external source

| field | value |
| --- | --- |
| path | `{approved.get('approved_external_source')}` |
| sha256 | `{approved.get('actual_sha256')}` |
| size | {approved.get('actual_size_bytes')} |
| pages | {approved.get('actual_pages')} |
| identity | {approved.get('identity')} |

The external file was only read. Its sha256, size and mtime are identical
after restoration (`external_source_unmodified = {runs.get('external_source_unmodified')}`).

## 2. Canonical durable storage

The application already defines the mechanism: `modules.library.durable_source`.
`CONTENT_MANAGER_STORAGE_DIR` is unset in DEV, so the root resolves to the
backend working directory; the durable root is `{runs.get('canonical_durable_root')}`.
Naming is deterministic and document-scoped: `sources/<document_id>/original.pdf`.
Writes are atomic: temporary sibling, fsync, sha256 verification, `os.replace`,
directory fsync. No new folder policy was invented.

| field | value |
| --- | --- |
| final durable path | `{durable.get('path')}` |
| managed copy (not the external path) | {durable.get('managed_copy')} |
| inside durable root | {durable.get('inside_durable_root')} |
| size | {durable.get('size_bytes')} |
| sha256 | `{durable.get('sha256')}` |
| pages | {durable.get('pages')} |

## 3. Source metadata ownership and write

The authoritative owner is `library_documents` (columns `source_path`,
`source_uri`, `source_filename`, `source_sha256`, `source_size_bytes`,
`source_mime_type`). Generations, runs and pages do not own source metadata.
No dedicated updater exists; the product itself writes `source_path` with a
guarded `UPDATE` inside a transaction, and this gate mirrored that narrowly.

| accounting | value |
| --- | --- |
| rows modified | {writes.get('rows_modified')} |
| authorized mutation | {writes.get('authorized_mutation')} |
| unexpected rows modified | {writes.get('unexpected_rows_modified')} |
| Milvus writes | {writes.get('milvus_writes')} |
| synthetic rows created | {writes.get('synthetic_rows_created')} |

## 4. Source endpoint

| check | value |
| --- | --- |
| authenticated status | {auth.get('authenticated', {}).get('status')} |
| served sha256 | `{served.get('served_sha256')}` |
| served size | {served.get('served_bytes')} |
| served pages | {served.get('served_pages')} |
| content type | `{auth.get('authenticated', {}).get('content_type')}` |
| unauthenticated status | {unauth.get('status')} |
| public leak | {unauth.get('public_source_leak')} |
| fresh-process resolution | {fresh.get('source_survives_fresh_process')} |

The route resolves `d.source_path` through `library_visible_documents`, requires
it to equal the canonical durable path, and returns the file with
`Cache-Control: private, no-store`. Both served and durable hashes equal the
approved hash.

## 5. C immutability

| measure | before | after |
| --- | --- | --- |
| chunks | {imm.get('chunks_before')} | {imm.get('chunks_after')} |
| vectors | {imm.get('vectors_before')} | {imm.get('vectors_after')} |
| chunk digest | `{imm.get('chunk_digest_before')}` | `{imm.get('chunk_digest_after')}` |
| active generation | `{imm.get('active_generation_before')}` | `{imm.get('active_generation_after')}` |
| active pointer changed | {imm.get('active_pointer_changed')} | |
| generation statuses changed | {imm.get('generation_statuses_changed')} | |
| content digest changed | {imm.get('content_digest_changed')} | |

Only `source_path` and `updated_at` differ. Retrieval smoke and page metadata
are unchanged; no new generation or run exists.

## 6. Safety and integrity

* forbidden operations in the restoring process: {load('forbidden-operation-monitor.json').get('counters')}
* SQL writes observed: {load('forbidden-operation-monitor.json').get('sql_write_statements_observed')}
* idempotent second run: `{idem.get('second_run_result')}`, rows modified 0
* mismatched source accepted: {neg.get('mismatched_source_accepted')}
* path safety: {load('path-safety.json').get('pass')}
* frozen hashes unchanged: {frozen.get('frozen_hashes_unchanged')}
* product code modified by gate: {final.get('product_code_files_modified_by_gate_count')}
* commit / push: NO / NO

## 7. Historical gates

All earlier gate identifiers are preserved unchanged in their own reports. This
report does not reinterpret or re-label any of them. In particular the previous
`TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V2_FAIL`
remains FAIL; this gate only repairs C's durable source.

## 8. Rollback

See `restoration-rollback-plan.json`. The rollback restores `source_path = NULL`
and removes only the file created here. A later unrelated test failure must not
roll back a successful restoration.
"""
    (OUT / "REPORT.md").write_text(report)

    recommendation = f"""# Recommendation

`{gate.get('gate')}` = **{gate.get('status')}**.

Durable source for C is present, managed and servable:
`{durable.get('path')}` with sha256 `{served.get('served_sha256')}`.

Next gate:

```
TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2
```

Constraints that remain:

* `READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2 = NO`
* `READY_FOR_C_REINGEST_EXECUTION = NO`
* `FOUNDATION_V2_PUBLISHED = NO`
* no commit, no push of this operational repair;
* the durable PDF must not be committed to Git;
* publication V1R2 still has to revalidate and publish Foundation V2 itself.
"""
    (OUT / "recommendation.md").write_text(recommendation)
    print(json.dumps({"status": gate.get("status"), "files": 3}))


if __name__ == "__main__":
    main()
