# Rollback plan

The blocking-report changes are documentation and a read-only audit script; reverting them performs no data operation.

The initial Content Manager runtime baseline can be disabled by removing its route registrations and frontend page without touching existing valid documents. Migration 040 must not be dropped automatically on a shared database. Any future rollback of persisted upload/job rows requires an explicit, scoped migration after confirming no worker owns a job.

No rollback against PostgreSQL or Milvus is needed for this assessment because no write test, migration or ingestion was executed.
