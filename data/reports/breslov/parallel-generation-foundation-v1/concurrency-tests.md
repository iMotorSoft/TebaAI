# Concurrency — NOT executed / NOT demonstrated

No foundation admission/CAS/cleanup lifecycle primitive exists to test. A mocked lock or an independent toy CAS table would not certify production repository behavior. No PostgreSQL transaction concurrency or actual Milvus candidate isolation test was executed. The temporary-table migration test is not a concurrency test.

Required deterministic tests on explicitly isolated synthetic PG resources:

1. Barrier-start two identical admissions, same logical+operation key: one generation/one exclusive resource owner; loser observes identical persisted result. Same key/different request digest must reject.
2. Two independent connections attempt OLD->A and OLD->B. Exactly one commit; loser STALE_ACTIVE_GENERATION; audit and epoch agree with winner. Roll back/retry at transaction boundaries to expose false successes.
3. Stale switch after committed cutover must not mutate pointer, target state or audit. Repeat with a lost response and same-operation replay, distinguishing replay from a new stale operation.
4. Cleanup vs activation on the same generation: whichever obtains lifecycle lock first determines eligibility. DELETING fence must survive process death before/after vector delete; cleanup cannot delete an activated target, activation cannot select a deleting target.
5. Interrupted build with partial chunks/vectors remains invisible to all normal routes before, during and after retry/cleanup. Sibling/OLD PG and vector fingerprints unchanged.

Use two real psycopg async connections and synchronization barriers, not timing sleeps. Candidate fixtures must never use protected C UUID/SHA or primary resources. Milvus tests must use a separately approved isolated collection; do not mutate primary vectors as a proxy. Retain actual transaction results and denominators. All five requirements remain pending.
