# Rollback eligibility — frozen contract

Only CUTOVER accepts CANDIDATE. ROLLBACK target must:
1. belong to the same logical document and match its source identity;
2. be INACTIVE;
3. have prior successful APPLIED activation audit history;
4. be retained/protected (`retention_hold`);
5. be the immediate previous ACTIVE: pointer.expected_generation_id equals target,
   with a successful target→current CUTOVER/ROLLBACK audit edge;
6. satisfy expected-active CAS (including an already-active rollback retry);
7. not be BUILDING, FAILED or CANDIDATE.

Safe retry: already-active target returns IDEMPOTENT without audit/state mutation.
ROLLBACK checks CAS before idempotency. Existing CUTOVER retry semantics remain.

Known root cause: activate_generation previously required CANDIDATE for every
operation, allowing cutover but rejecting retained INACTIVE rollback.
The current local fix predates this gate; no productive code change is planned.

Preflight results never certify this gate. A new CERT-V2 UUID fixture is
constructed from the same frozen rules during Phase B. Synthetic fixture teardown
uses exact IDs, explicitly removes pointer/generations/documents/logical/collection,
and retains audit. It is not generic retained-generation cleanup.

Cleanup policy is exercised through the real ManifestCleanupService guard using
an isolated metadata loader adapter and forbidden vector adapter; PostgreSQL
protection queries use real fixture rows. No fake service success substitutes for
an actual switch. Committed switches are observed independently before/after
commit; the database unique ACTIVE constraint is checked by the preflight schema.

No Current C writes, reconstruction, embeddings, vector access, readers/worker/
quarantine changes, migrations, service restarts, publication, commits or pushes.
