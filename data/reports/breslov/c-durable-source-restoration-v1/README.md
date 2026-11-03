# C durable source restoration V1

Gate: `TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_V1`
Status: **PASS**
Report directory: `data/reports/breslov/c-durable-source-restoration-v1/`

Operational data repair of the `source_path` of document C. The approved
external PDF was copied into TebaAI's existing managed durable storage
(`modules.library.durable_source.preserve_source`), the existing
`library_documents.source_path` column was set for C only, and the
authenticated source endpoint now serves exactly the approved bytes.

* document_id: `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`
* logical_document_id: `db200a31-b547-5668-d968-06d0ec36ad95`
* durable path: `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf`
* approved sha256: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
* product code changes by this gate: **0**
* commit / push: NO / NO

No reingest, extraction, chunking, embedding, vector write or generation
activation was performed. C keeps 942 chunks, 942 vectors, one ACTIVE
generation and the same active pointer.

See `REPORT.md` for the full evidence map and `recommendation.md` for the next
gate.
