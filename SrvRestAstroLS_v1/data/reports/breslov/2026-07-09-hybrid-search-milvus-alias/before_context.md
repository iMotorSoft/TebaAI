# Before Context

Before the fix:

```text
logical scope: breslov_primary
Milvus filter: collection_code == "breslov_primary"
productive Milvus metadata: collection_code == "breslov"
```

Observed effect:

- PostgreSQL FTS branch returned results.
- Milvus direct search with `collection_code == "breslov_primary"` returned `0`.
- Milvus direct search with `collection_code == "breslov"` returned hits.
- `search_chunks_hybrid()` returned only `["fts"]` source signals for tested queries.

Relation QA was not affected because it already filters Milvus with:

```text
collection_code == "breslov"
```
