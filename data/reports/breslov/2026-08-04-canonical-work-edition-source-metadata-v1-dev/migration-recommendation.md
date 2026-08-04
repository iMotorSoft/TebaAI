# Migration recommendation

## V1 decision

No schema migration is required for this phase. The existing authoritative
`library_documents.bibliographic_metadata` JSONB column can represent the
versioned `canonical_identity_v1` contract without changing status, text,
chunks, embeddings or Milvus.

Confirmed document-wide identity was persisted for the three audited DEV
sources. Section-varying source relations are intentionally not forced into the
document object.

## Future normalized schema

A later migration may be justified when curation requires uniqueness,
referential integrity or high-volume source-relation queries. Candidate tables:

- canonical works/families and aliases;
- document editions/volumes;
- document/section/chunk source relations with provenance;
- metadata assertions and review state.

That migration requires its own ADR, backfill, compatibility view and rollback.
It is not needed for V1 behavior and must not be introduced merely to replace a
validated JSON contract.
