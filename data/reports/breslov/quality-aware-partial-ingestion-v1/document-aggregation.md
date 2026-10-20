# Document aggregation and readiness

Aggregate all relevant classified regions: FULL / PARTIAL / UNUSABLE, identical
semantics to page aggregation. Not an average score and not majority voting.
The sample matrix is PARTIAL; no full-document classification was executed.

Reuse existing document lifecycle: draft -> test_candidate -> ready, and worker
completed_with_warnings. Do not add READY_WITH_WARNINGS/PARTIAL_READY yet.
`ready` must mean all published content accepted, not source perfection.
Editorial/legal publication remains a separate requirement.

Proposed durable metadata: document metadata.quality_v1 carries policy version,
aggregate/counts; page layout_notes.quality_v1 carries full region inventory;
chunk metadata.quality_v1 carries accepted region identity + source hash + policy.
Document-text extraction_metadata carries aggregate partiality. Existing JSONB
columns suffice for this design; no migration or database writes performed.

Retry safety needs attention: existing gateway uses deterministic document/text
IDs and ON CONFLICT DO NOTHING. Do not attach new quality metadata to an old
canonical text/chunk set silently. Explicit pipeline+quality versioning and
attempt reconciliation must prove the same accepted content is persisted.

No integration enabled: offline golden requirements are not all met. No readiness
claim from unit tests or resource reconciliation, which cannot prove text quality.
