# Same-source admission — proposed, NOT implemented

Ordinary upload: resolve existing scoped source reservation; an exact duplicate reports/rejects the existing logical document, never silently creates a candidate. Preserve existing UI/API duplicate behavior and legacy unscoped protection.

Controlled admission requires authorized actor/scope, logical document ID, source hash, purpose (e.g. controlled_reingest/rechunk/vector regeneration), operation key, immutable parser/config/build digest and provenance source reference. A free-form purpose string alone is not authorization. Verify source reservation belongs to the same logical tenant/collection.

Lock logical lifecycle row. `UNIQUE(logical_document_id, operation_key)` serializes equivalent admissions; store canonical request digest. Same key+same digest returns the same generation; same key+different digest rejects. Different explicitly approved operation keys may create A/B/C candidates, even from identical bytes/config. Do not hardcode a two-generation limit.

Physical generation UUID must be independent of attempt retries. Resource claims require admitted generation ownership, exact manifest and immutable chunk/vector IDs. Retrying an attempt may resume only matching sealed resources or clean its own failed candidate; no second claim of OLD. An operation tombstone survives cleanup. Admission never moves active pointer.

Migration 042 currently blocks this path. No new admission function/job/API exists after this attempt. It is unsafe to bypass duplicate checks or vary SHA/scope/collection to force admission.
