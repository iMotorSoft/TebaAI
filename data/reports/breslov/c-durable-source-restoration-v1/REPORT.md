# REPORT — C durable source restoration V1

Gate: `TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_V1`
Result: **PASS**
Validated at: `2026-10-23T12:18:16.292419+00:00`

## 1. Approved external source

| field | value |
| --- | --- |
| path | `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf` |
| sha256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| size | 4550267 |
| pages | 284 |
| identity | PASS |

The external file was only read. Its sha256, size and mtime are identical
after restoration (`external_source_unmodified = True`).

## 2. Canonical durable storage

The application already defines the mechanism: `modules.library.durable_source`.
`CONTENT_MANAGER_STORAGE_DIR` is unset in DEV, so the root resolves to the
backend working directory; the durable root is `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/backend`.
Naming is deterministic and document-scoped: `sources/<document_id>/original.pdf`.
Writes are atomic: temporary sibling, fsync, sha256 verification, `os.replace`,
directory fsync. No new folder policy was invented.

| field | value |
| --- | --- |
| final durable path | `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf` |
| managed copy (not the external path) | True |
| inside durable root | True |
| size | 4550267 |
| sha256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| pages | 284 |

## 3. Source metadata ownership and write

The authoritative owner is `library_documents` (columns `source_path`,
`source_uri`, `source_filename`, `source_sha256`, `source_size_bytes`,
`source_mime_type`). Generations, runs and pages do not own source metadata.
No dedicated updater exists; the product itself writes `source_path` with a
guarded `UPDATE` inside a transaction, and this gate mirrored that narrowly.

| accounting | value |
| --- | --- |
| rows modified | 1 |
| authorized mutation | source_path for C only (plus updated_at) |
| unexpected rows modified | 0 |
| Milvus writes | 0 |
| synthetic rows created | 0 |

## 4. Source endpoint

| check | value |
| --- | --- |
| authenticated status | 200 |
| served sha256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| served size | 4550267 |
| served pages | 284 |
| content type | `application/pdf` |
| unauthenticated status | 401 |
| public leak | False |
| fresh-process resolution | True |

The route resolves `d.source_path` through `library_visible_documents`, requires
it to equal the canonical durable path, and returns the file with
`Cache-Control: private, no-store`. Both served and durable hashes equal the
approved hash.

## 5. C immutability

| measure | before | after |
| --- | --- | --- |
| chunks | 942 | 942 |
| vectors | 942 | 942 |
| chunk digest | `589789b3bf591d2ae6006b845ad03b35` | `589789b3bf591d2ae6006b845ad03b35` |
| active generation | `1a8af56b-fc17-d9f9-ffc2-9efde54aa95b` | `1a8af56b-fc17-d9f9-ffc2-9efde54aa95b` |
| active pointer changed | False | |
| generation statuses changed | False | |
| content digest changed | False | |

Only `source_path` and `updated_at` differ. Retrieval smoke and page metadata
are unchanged; no new generation or run exists.

## 6. Safety and integrity

* forbidden operations in the restoring process: {'ingest_calls': 0, 'extract_calls': 0, 'chunk_generation_calls': 0, 'embedding_calls': 0, 'vector_insert_delete_calls': 0, 'generation_activation_calls': 0}
* SQL writes observed: [{'keyword': 'UPDATE', 'statement': 'UPDATE library_documents SET source_path=%s, updated_at=now() WHERE id=%s AND source_path IS NULL AND source_sha256=%s'}]
* idempotent second run: `NOOP_ALREADY_RESTORED`, rows modified 0
* mismatched source accepted: False
* path safety: True
* frozen hashes unchanged: True
* product code modified by gate: 0
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
