# Hybrid Search Milvus Alias

## Problem

The productive Milvus collection `tebaai_breslov_chunks_v1` is healthy, but its entities store the historical metadata value `collection_code="breslov"`.

The general library hybrid search used the logical runtime scope `breslov_primary` directly in the Milvus filter:

```text
collection_code == "breslov_primary"
```

That made the vector branch empty while PostgreSQL FTS continued to work.

## Previous Evidence

The Milvus 2.6 acid run found:

- Milvus entities: `5102`
- PostgreSQL ready chunks in `breslov_primary`: `5102`
- PG to Milvus sample: `50/50`
- sample duplicates: `0`
- temporary insert/search/drop: pass
- productive Milvus metadata sample: `collection_code="breslov"`

## Decision

Do not migrate metadata, reindex vectors, or modify productive Milvus. Implement a code-level routing alias:

```text
breslov_primary -> breslov
```

PostgreSQL remains scoped by the logical `knowledge_scope_code`. Only the Milvus vector filter uses the historical metadata code.

## Fix

Added `resolve_milvus_collection_code_for_scope()` in `modules/library/hybrid_search.py`.

`search_chunks_hybrid()` now resolves the Milvus metadata code before calling `search_vectors()`.

## Validation

- Unit tests: `tests/test_library_search_hybrid_milvus_alias.py`
- Live read-only probe: `scripts/hybrid_search_milvus_alias_probe.py`
- Relation QA regression: passed; Relation QA code was not changed.

## Why Metadata Was Not Migrated

Milvus is a derived index and the productive vectors are already consistent with PostgreSQL by count and sample round-trip. A metadata migration would require writing to productive Milvus and carries unnecessary operational risk for this routing bug.

## Remaining Risks

- Other retrieval code that independently filters Milvus by logical scope may need the same resolver in a later pass.
- Dense retrieval still returns nearest neighbors for negative queries; lexical or confidence gating remains a separate quality concern.
- PyMilvus ORM-style APIs emit deprecation warnings and should be migrated to `MilvusClient` before PyMilvus 3.1.
