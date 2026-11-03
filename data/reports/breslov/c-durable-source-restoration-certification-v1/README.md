# C durable source restoration certification V1

Gate: `TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1`
Result: **TEBAAI_BRESLOV_C_DURABLE_SOURCE_RESTORATION_CERTIFICATION_V1_PASS**

Read-only certification of the already-restored managed source for document C
(`ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`). No restoration, metadata write, ingest, generation
activation or Foundation V2 publication occurred.

External, durable and served PDFs were proven byte-identical
(`440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`), the authenticated endpoint served 284 pages, the
unauthenticated request was rejected, a fresh backend process resolved the
managed copy, and document C stayed at the ACTIVE generation
`1a8af56b-fc17-d9f9-ffc2-9efde54aa95b` with 942 chunks and
942 vectors.

See `REPORT.md`, `gate.json`, `final-validation.json` and
`recommendation.md`. Commit and push were not performed.
