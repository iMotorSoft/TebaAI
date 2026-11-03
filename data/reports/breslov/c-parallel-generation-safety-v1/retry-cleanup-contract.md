# Retry / cleanup contract — PARTIAL HARDENING ONLY

Implemented:

1. New document UUID collision fails inside existing PG transaction before creating an ingestion run, canonical text, pages or manifest ownership records. A duplicate generation request cannot claim the already-existing generation's resources through this INSERT path. This is a refusal, not a supported resume protocol.
2. Cleanup loads document status and rejects already-ready, archived and unknown states before constructing Milvus index, writing cleanup status, deleting PG/source/temp data. Known absent documents retain existing idempotent cleanup behavior.
3. Existing exact manifest vector IDs and PG resource+document bounds are preserved; ordinary synthetic cleanup and repeat-cleanup tests pass.

Still missing and blocking:

- A shared publication/cleanup/retry lifecycle lock and retained-generation hold. The new preflight check alone has a TOCTOU window.
- Cross-manifest ownership validation for historical collisions and incomplete builds; a default `was_preexisting=false` is not evidence of exclusive ownership.
- Controlled same-source/new-version admission and idempotent build seal/resume. New UUID guard does not bypass source uniqueness.
- Exact-generation cleanup of failed candidates under concurrent publication; primary vector ownership validation before every delete; legacy destructive scripts fenced by common lifecycle authority.
- Fault injection covering partial chunks/vectors, death/recovery/retry and concurrent readers against actual transaction machinery.

`CLEANUP_SCOPE = EXACT_GENERATION_ONLY` is the required contract, **not achieved by this patch**. No cleanup, retry, failure compensation or worker was run against any real document. No claim of complete interrupted-build invisibility is made while normal text readers lack generation predicates.

Do not enable versioned admission or auto-clean OLD on the strength of these local guards. Definitive OLD cleanup remains outside scope and requires another gate after rollback-window closure.
