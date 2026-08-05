# PostgreSQL–Milvus controlled eventual consistency

No distributed transaction is claimed. Every PG stage commits deterministic IDs and manifest rows before the next stage. The isolated Milvus schema adds `attempt_key`, `job_id` and `attempt_number`; upsert is followed by flush and strong-consistency attempt query. Completion requires exact chunk/embedding/vector counts with zero missing, orphan, duplicate or metadata mismatch.

A crash after vector upsert but before manifest registration is still recoverable: cleanup queries the exact attempt key, then deletes Milvus first and manifest-owned PG IDs in FK-safe order. `already_absent` is successful and every cleanup action is audited. Real E2E reconciled 2/2/2 and cleanup twice produced 13 deletes + one already-absent, then 14 already-absent with no failures.
