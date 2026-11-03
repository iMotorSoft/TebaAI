# Architecture before — observed, not proposed

`library_documents.id` owns canonical texts, chunks and Milvus `document_id`. Pages belong to document + ingestion run. A run is an attempt/provenance identity, not the owner of the chunks. `chunk_set_version=1` is not a generation pointer.

Migration 042 prevents scoped same-source physical documents via `uq_library_documents_scope_collection_sha256`; its unscoped counterpart protects legacy rows. Upload duplicate checks and job idempotency supplement this physical constraint. They do not provide controlled generation admission.

No logical-document table or active pointer exists in the inspected runtime/migrations. Normal visibility varies by route: scope-only lexical/hybrid queries, ready/test_candidate sets in research/relation, latest completed run in viewer/Book QA. This is unsafe for parallel admission even if the index were removed.

C inventory: [before](before-c-inventory.json). Previous complete implementation map: [predecessor](../c-parallel-generation-safety-v1/implementation-map.md). This report rechecks hybrid/text/viewer/gateway/cleanup/Milvus code and records additional synthetic reproductions. Other route entries are static audit/antecedent findings, not new end-to-end certification.
