# Rollback / retention contract — NOT IMPLEMENTED

The [prior rollback runbook](../c-controlled-reingest-plan-v1/C_ROLLBACK_RUNBOOK.md) remains binding. Normal rollback must atomically CAS expected NEW→OLD through the same active-generation primitive, retaining NEW inactive/quarantined and requiring **no** parsing, chunk recreation, embedding/model/API calls or vector reconstruction.

Retain OLD document/text/pages/chunks/embeddings/actual vectors/runs/manifests/citation identity/source and audit under an explicit hold until validation/stabilization close and a separate authorized cleanup gate. No arbitrary TTL/window was invented. Neither OLD nor NEW was deleted in this gate; no cutover means post-cutover retention/rollback cannot be claimed tested.

Existing cleanup now refuses documents already ready/archived or with unknown state **before** status/vector/PG/temp side effects. That guard is not a durable retention hold and does not serialize a concurrent publication/cleanup race. Archived OLD source is currently excluded by the source repository's ready/test_candidate policy, another outstanding rollback-viewer prerequisite.

Source durability remains unresolved for current C: external original hash/pages match, deterministic durable copy absent, source_path/source_uri NULL. Reuse `durable_source.preserve_source` in a separately verified metadata-only repair within this prerequisite's continuation; validate configured root persistence/backups/lifecycle, hash/size/pages and authenticated source access. Do not copy the PDF into Git. No repair was attempted here and no rollback reconstructs OLD as a workaround.
