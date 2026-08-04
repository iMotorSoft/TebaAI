# Future promotion and rollback plan (not executed)

## Preconditions

1. Re-run identity resolution by SHA-256, filename and family; require exactly one candidate.
2. Require status `test_candidate`, hash match, 284 pages, 268 chunks and 268/268 PG↔Milvus.
3. Resolve the conflicting ready record titled `Likutey Halajot LM II 8` whose sampled content identifies `LIKUTEY MOHARÁN II #8`.
4. Persist and editorially approve the explicit front-matter metadata, including first volume; obtain/record legal permission for intended exposure.
5. Re-run expanded literal, Investigative QA, Relation QA, scope, admin, guest and mobile gates with zero blocking failures.
6. Capture a logical backup and read-only baseline. Do not touch embeddings or Milvus.

## Future status change

- Table: `library_documents`.
- Resolve row by source SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`; verify filename.
- Expected current value: `status='test_candidate'`.
- Intended future value: `status='ready'`.
- Use one bounded transaction with an exact expected-row-count assertion.
- The currently observed document ID is evidence only; the execution must resolve it again and must not rely on a historical hardcode.

No SQL write statement was executed or included in this audit.

## Verification after a separately authorized promotion

- status and only status changed;
- 284 pages, 268 chunks and 268 embeddings unchanged;
- Milvus remains 268/268 with no writes;
- five canonical goldens and expanded batch pass;
- before/after ranking and scope signatures match the approved simulation;
- admin, guest and mobile E2E pass;
- no `test_candidate_read_only` warning for this source.

## Rollback

If any verification fails, use a separate bounded transaction to reverse only:

```text
ready → test_candidate
```

Then verify normal ready-only retrieval excludes the candidate, DEV read-only retrieval still includes it, the warning is restored, all row/vector counts remain unchanged, and admin/guest/mobile auth is unaffected.

Rollback requires no reingestion, embedding recalculation or Milvus mutation.
