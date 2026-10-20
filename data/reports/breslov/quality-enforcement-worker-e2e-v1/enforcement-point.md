# QUALITY_ENFORCEMENT_POINT

Required location: in `ConcretePageFirstPipeline.run`, after source-backed
extraction/provenance and BEFORE `gateway.persist_document_and_pages`.
Filtering only before `persist_chunks` would already be too late for canonical
text. Accepted units must also be transported separately to chunking so overlap
cannot bridge a rejected region.

## Exact structural blocker found in this run

The offline adapter consumes certificates; it does not issue them.
`map_layout_page` requires explicit note direction and sometimes a certified
note zone. `classify_owned_unit` requires evidence references, visual/source
assessment and text/order/structure verification. In the closed offline gate,
these come from manually reviewed goldens and explicit assertions in
`region-markdown-provenance-editorial-boundaries-v1/validate_offline.py`.
They are NOT outputs of the generic worker's extraction stage.

There is no approved runtime certificate issuer/registry/trust contract, no
certificate field in `CreateJobRequest` or `PageFirstIngestionRequest`, and no
provenance or quality inventory in `ExtractedPage`. Arbitrary administrative
notes are not trusted certificates. A file-hash allowlist authorizes an E2E
upload; it does not certify a region's reading order or text fidelity.

Consequently, a literal connection using only available runtime evidence
classifies GOOD_A and GOOD_C as UNRESOLVED too. The executable
`audit_contract_boundary.py` reuses the actual classifier and demonstrates
this without a PDF or indexing: three UNRESOLVED, aggregate UNUSABLE, zero
accepted units. BAD_B triggers the actual replacement-character diagnostic.
This is a contract precondition probe, NOT the requested controlled E2E.

Assigning positive flags because U+FFFD is absent, guessing LTR/zone, or importing
fixture-specific quality labels into the worker would evade the declared
certificate requirement. Globally enabling rejection without a trusted positive
path would stop normal ingestion and cannot prove good-neighbor preservation.
Neither shortcut was implemented.

## Safe scope if certificates become available

A certified separable unit can be quarantined independently. An unsupported
layout with no defensible complete ownership inventory must fail closed at the
whole physical page, without representing it as an empty FULL page. If the
remaining document has no accepted evidence, the job cannot produce a usable
candidate. This is a proposed integration rule, not a current runtime guarantee.

## Unproven

Worker filtering, durable quarantine, isolated chunks, embeddings exclusion,
publication with explicit PARTIAL, queries/citations, retry and reconciliation
remain unimplemented/unproven. No PASS_ARCHITECTURE_NOT_READY_FOR_C is claimed.
Ordinary full-suite failures are separately recorded, NOT used as the reason
for this structural BLOCKED decision.
