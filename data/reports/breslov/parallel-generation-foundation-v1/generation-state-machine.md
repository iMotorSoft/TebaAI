# Generation lifecycle — proposed, NOT enforced

Minimal proposed stored states: BUILDING, READY, FAILED, QUARANTINED, DELETING, DELETED. ACTIVE/INACTIVE are derived exclusively from the explicit logical pointer, not independently mutable booleans/statuses.

- Admission -> BUILDING, invisible.
- BUILDING -> READY only after immutable build/provenance seal, durable source and complete expected resources are verified. This is foundation integrity, not C extraction quality approval.
- BUILDING -> FAILED or QUARANTINED; always invisible.
- READY + selected by pointer = ACTIVE; READY + not selected = retained INACTIVE or unactivated candidate.
- READY -> FAILED/QUARANTINED only when inactive, under lifecycle lock; active requires first switching to an eligible retained target in one valid transaction.
- Non-active failed/unpublished candidate -> DELETING -> DELETED via exact resource cleanup. Retained former-active generations require separate explicit retention-release authorization, outside this gate.
- DELETING/DELETED cannot be activated/resumed. Keep the admission tombstone so retry cannot recreate deleted resources under the same operation key.

Reject all unlisted transitions. Initial unpublished logical documents may have no active pointer and return no normal evidence. Once published, committed NULL/invalid pointer is forbidden. Regions/quality certificates belong to physical generation + run/page, never the logical row. NEW quarantine must not modify OLD region status.

Existing `library_documents.status` remains an editorial/legacy projection, not a new active authority. Existing cleanup guards remain necessary until the lifecycle replaces their admission check with a shared transactional fence.
