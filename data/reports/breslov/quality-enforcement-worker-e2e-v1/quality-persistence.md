# Quality persistence — inspected options, not implemented

Existing JSONB surfaces are sufficient for a minimal future integration:

- `library_pages_v2.layout_notes`: policy version, original page aggregate and
  complete ordered region metadata; attach document/run/page foreign-key chain.
- `library_document_texts.extraction_metadata`: reproducibility policy/provenance
  versions, source hash and certified canonical hash.
- `library_documents.metadata`: explicit document quality independent of lifecycle.
- `library_document_chunks.metadata`: accepted region ID/provenance linkage,
  policy version; chunk each accepted unit independently.
- Job diagnostic/technical_details: partiality summary and quarantine counts.

Reuse `ClassifiedRegion.metadata()`; it omits rejected text, retaining source
hash, physical page, region ID, bbox, classification, reason, policy version,
source method, evidence refs and candidate digest/length. Add forward ownership
metadata with source text replaced by digests, never rejected searchable text.
Nested page metadata inherits the document tenant chain, not a new public route.
Audit access must remain permission-scoped.

No runtime write currently persists this structure. No quarantine table or
endpoint was added. Offline metadata must not be presented as durable audit.

`ready` is a publication lifecycle state, not FULL quality. Existing metadata
and `completed_with_warnings` can represent ready + PARTIAL without a new state,
but APIs do not currently expose/enforce the quality contract. Publication
permits completed_with_warnings and merges metadata, so no state-machine/schema
obstruction is established; this is NOT an end-to-end proof. Silent partiality
must be prevented explicitly before enabling this path.

Source retention is a further limitation: successful finalize removes the
temporary upload. Hash/location audit survives if persisted, but future regional
reprocessing requires approved durable source retention. No retention change
was made in this run.
