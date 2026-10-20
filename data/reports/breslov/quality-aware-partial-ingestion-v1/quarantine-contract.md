# Quarantine contract

Rejected region metadata: source SHA (document identity offline), physical page,
region ID, optional bbox and coordinate system, classification, disposition,
reason codes, source method, diagnostic summary, evidence references, candidate
hash/length, quality_policy_version. Never copy rejected text into searchable
metadata. In DEV persistence add document_id/attempt/run linkage from gateway.

PostgreSQL is operational truth: existing page layout_notes JSONB, not report
files as runtime storage. Reports are offline evidence only. No new storage,
SQL patch, migration, vector deletion or corpus editing in this phase.

Keep source locator/hash and evidence so a future extractor can re-evaluate
rejected regions. Incremental processing is not implemented. Source retention
needs an explicit lifecycle: worker currently deletes temporary upload after
success; metadata alone cannot reconstruct the PDF. Preserve a durable approved
source reference before promising future regional reprocessing.

Proposed page-scoped evidence response: available accepted evidence plus quality
and unavailable_regions metadata. Region-scoped lookup may return
`source_region_unreliable` when location is supplied; generic text query cannot
infer that an unmatched query is in quarantine without a separate reliable
locator. Do not search rejected strings or offer semantic neighbors as literal
substitutes. Current backend API has NOT been extended.

Unavailable PDF/page references are transparency locators, never literal quotes.
All citations and embeddings must originate only from accepted bounded chunks.
