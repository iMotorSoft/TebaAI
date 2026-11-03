# State transition contract

One authoritative primitive remains `activate_generation`; `switch_generation` still owns the transaction and rejected-attempt audit. Signature unchanged.

- CUTOVER: same-logical CANDIDATE, matching source identity, expected-active CAS → ACTIVE.
- ROLLBACK: same-logical retained INACTIVE, immediate previous active, successful activation audit and switch-edge audit, matching source identity, expected-active CAS → ACTIVE.
- Departing ACTIVE becomes INACTIVE with `retention_hold=true` atomically with the pointer and APPLIED audit. No new schema or lifecycle marker.
- BUILDING, FAILED, cross-document targets, arbitrary INACTIVE and stale CAS remain rejected without mutation.
- CUTOVER retains its preexisting already-active retry behavior (IDEMPOTENT, no duplicate audit), including the original stale expectation on a retry. This is a no-op, not a CAS bypass for mutation.
- ROLLBACK checks CAS before its already-active no-op: stale retry raises GenerationConflictError; retry with expected=current returns IDEMPOTENT and adds no audit.

Logical row, pointer and target are locked in the caller transaction. Readers and publication/quarantine behavior are unchanged. CANDIDATE remains the existing structural-completeness admission contract: this gate does not introduce a new evidence-reconciliation policy.

Applied audit continues to record logical document, from/to/expected IDs, operation, result and database timestamp. Rollback is explicitly ROLLBACK, never relabeled CUTOVER. Separate committed switches have separate timestamps; tests inside one rollback-only transaction verify edges/operations rather than infer ordering from UUIDs when timestamps tie.
