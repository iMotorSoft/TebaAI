# Exact-generation cleanup — required, NOT achieved

Existing manifest cleanup bounds PG deletes by resource ID + physical document_id and vector deletes by exact IDs. Keep these protections. The previous early ready/archived/unknown status rejection is also kept. However `_load` commits before external deletion, so concurrent publication can win after the check. This is not a generation lock/hold.

Proposed protocol: authorize exact candidate generation and manifest ownership; lock logical lifecycle row, reject active or retained generation, transition candidate to DELETING and persist exact resource manifest/tombstone before external effects. Activation must reject DELETING, so a cleanup/activation race has one safe winner. Remove only generation-owned vectors and PG resources, then mark DELETED. Crash resumes the same tombstone idempotently. Failed external deletion keeps DELETING and retries; it never silently permits activation.

Reject shared/preexisting resources rather than assume ownership from was_preexisting=false. A source SHA or logical ID is not a delete predicate. Sibling generations and other logical documents must remain unchanged. Partial builds stay invisible because normal retrieval filters the active pointer, not because cleanup happens quickly.

No cleanup was executed on C or any real document. Active cleanup rejection only has legacy offline status-guard tests; full exact-generation, interrupted-build and concurrent cleanup acceptance is not demonstrated.

## Previous hardening decisions

- Collision rejection before resource claim: KEEP. ON CONFLICT must not register OLD under a new manifest. Later MODIFY to recognize an authorized identical admission replay; never remove the collision defense before exclusive ownership is proved.
- Published/archived cleanup guard: KEEP now; MODIFY in completed lifecycle to use pointer/retention + DELETING fence. Status preflight alone has TOCTOU.
- Invalid PG hydration rejection: KEEP. Orphan/misattributed vector metadata is never evidence. Later add active/candidate membership and epoch validation; valid PG hydration alone is insufficient.

No predecessor code/test/evidence was discarded, staged or committed.
