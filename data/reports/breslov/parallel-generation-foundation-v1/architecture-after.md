# Architecture after — no runtime activation

The foundation implementation requested by this gate was **not completed**. Runtime, schema, index, active identity and source metadata remain unchanged by this attempt. No generation infrastructure is certified or deployed. This is not an alternative implementation or an approval to proceed.

Added: fresh guarded read-only inventory, protected-C integrity comparison, six deterministic blocker reproductions, selected regressions, existing uniqueness migration test on temporary tables, and explicit proposed contracts. Green blocker tests deliberately reproduce unsafe behavior; they are not acceptance tests.

## Minimal proposed extension, not implemented

1. Preserve existing physical `document_id` as generation identity; introduce logical identity and explicit pointer/epoch.
2. Move ordinary source-duplicate ownership to a scoped logical-source reservation, coordinated with guarded generation admission. Keep migration 042 until the replacement and every reader are ready.
3. Integrate one authorized request generation context into all repositories and Milvus expressions before ranking; explicit restricted candidate mode, no broad boolean opt-in.
4. One PG lifecycle lock for admissions, publication, CAS and cleanup; durable deletion tombstones for external cleanup; retained OLD cannot be candidate-cleaned.
5. Reuse `durable_source`, prove configured storage persistence/retention/backup, and separately audit any source-only C repair.

These five steps remain implementation work. No unused runtime module, auto-discovered SQL migration or half-enabled candidate API was installed. See [migration plan](migration-plan.md) for coordinated deployment/rollback requirements.
