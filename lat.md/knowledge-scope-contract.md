# TebaAI Knowledge Scope Contract

This contract defines the authoritative corpus boundary and the traceability required from source document to every derived retrieval representation.

## Core Rule

TebaAI resolves authorization and scope before retrieval, keeps canonical text in PostgreSQL and treats every Milvus record as rebuildable derived state.

```text
KnowledgeScope -> LibraryDocument -> LibraryDocumentText -> LibraryDocumentChunk -> ChunkEmbedding
       PostgreSQL authority                                      Milvus derivative
```

`library_collections_legacy` is historical and read-only. It is not a routing key for ingestion, indexing, retrieval, validation or promotion.

## Knowledge Scope

`knowledge_scopes` is the only primary corpus container for active knowledge flows.

The stable identity is the PostgreSQL UUID. `knowledge_scope_code` is a human-readable identifier unique inside a project and must be resolved to the UUID before repository work.

Required scope context is:

```text
organization_id
workspace_id
project_id
knowledge_scope_id
knowledge_scope_code
scope_type
language_policy
status
```

Only an active, authorized scope may serve normal retrieval. Draft, archived or error scopes require an explicit administrative or validation flow.

## Documents and Texts

`library_documents` owns source identity, bibliographic metadata, lifecycle, tenant context and version linkage.

`library_document_texts` owns extracted or normalized text variants. The canonical text role must be explicit; raw or auxiliary variants cannot silently replace the approved text.

Every document operation preserves scope, document identity, content hash, canonical text role, lifecycle status and chunk-set version.

Source quality and promotion remain governed by the documented library workflow; ingestion success alone does not make a document production evidence.

## Chunks

`library_document_chunks` is the authoritative retrievable text unit.

Each chunk must trace to one document and scope, retain stable ordering, and carry enough version and provenance data to reproduce its derivation.

```text
chunk_id
document_id
knowledge_scope_id
chunk_index
content
chunk_set_version
chunking_strategy
chunking_version
language
page and section metadata when supported
```

Document and chunk tenant fields must agree. A repository must not trust duplicated tenant metadata without validating the owning document and scope.

## Embeddings and Milvus

Embedding rows and Milvus entities are derived representations of an authoritative PostgreSQL chunk.

The derivation identity includes chunk, scope and chunk-set version plus embedding alias, version, dimension, integrity evidence, target collection and vector status.

A model or chunk-set change makes the previous vector stale. Mixed dimensions or silently mixed model aliases are invalid.

Milvus candidates must be filtered by scope, then rehydrated from PostgreSQL. Missing, unauthorized, archived or version-mismatched chunks are discarded rather than served from vector metadata.

## Retrieval Invariants

Every retrieval path applies the same scope and authority rules regardless of search engine.

1. Resolve authenticated tenant and project context.
2. Resolve `knowledge_scope_code` to the authorized PostgreSQL scope.
3. Filter PostgreSQL retrieval by `knowledge_scope_id` and allowed lifecycle state.
4. Filter Milvus by the corresponding scope metadata and expected index version.
5. Rehydrate final evidence from PostgreSQL by stable chunk identity.
6. Return source and limitation metadata with the result.

Client-provided organization, workspace, project or scope identifiers are requests, not proof of authorization.

## Degraded Retrieval

PostgreSQL lexical retrieval is the explicit degraded path when Milvus or query embeddings are unavailable.

The response must identify the effective retrieval mode and degradation reason. TebaAI may reduce recall, but it must not broaden the scope or present lexical-only results as hybrid/vector results.

## Validation and Promotion

Validation runs and promotion events are operational evidence, not optional annotations.

Promotion requires source quality, chunk integrity, page/reference checks when applicable, embedding integrity for vector-enabled scopes and golden-query evidence appropriate to the target.

Production indexing must be auditable by scope, document set, chunk-set version, embedding alias and target. Test and production collections cannot be cross-written.

## Non-Goals

This contract does not introduce a second source of truth or capabilities without measured need.

- no ArangoDB knowledge authority;
- no pgvector primary retrieval path;
- no physical database or Milvus collection per tenant by default;
- no GraphRAG entities or relations without an ADR and evaluation;
- no authorization based only on frontend filtering or Milvus metadata.

## Implementation Sequence

New knowledge features should close authority and isolation before adding retrieval sophistication.

1. Repository-level scope resolution and tenant checks.
2. Consistent scope/version propagation through documents, chunks and embeddings.
3. Retrieval rehydration and stale-vector rejection.
4. Validation and promotion evidence.
5. Only then reranking, conversational RAG or graph retrieval.

Related policies are [[tenant-context-authorization-policy]], [[library-retrieval-models-policy]], [[embeddings-configuration-policy]] and [[service-preflight-methodology]].
