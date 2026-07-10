# Milvus 2.6 acid findings

## Scope

- Project scope: `breslov_primary`
- Productive Milvus collection: `tebaai_breslov_chunks_v1`
- Embedding alias: `openai_text_embedding_3_small`
- Vector dimension: `1536`
- Metric/index expected by project: `COSINE` + `HNSW`

## Read-only acid probe

- Milvus connected: yes.
- PostgreSQL connected: yes.
- Milvus productive entities: `5102`.
- PostgreSQL ready chunks in `breslov_primary`: `5102`.
- Schema fields include `pk`, `chunk_id`, `document_id`, `collection_code`, `content_sha256`, `content_preview`, `embedding`.
- HNSW index params reported: `M=16`, `efConstruction=200`, metric `COSINE`.
- PG to Milvus sample by `chunk_id`: `50/50` found.
- Missing sample vectors: `0`.
- Duplicate sample vectors: `0`.

## Contract failure found

All queried productive Milvus entities use legacy metadata:

```json
{"collection_code_counts_sample": {"breslov": 5102}}
```

The current `search_chunks_hybrid()` path filters vectors with:

```text
collection_code == "breslov_primary"
```

That returns zero vector hits. The Relation QA vector path uses:

```text
collection_code == "breslov"
```

That returns vector hits.

Measured examples:

| Query | `breslov_primary` hits | `breslov` hits |
| --- | ---: | ---: |
| `alegría plegaria` | 0 | 5 |
| `sangre habla` | 0 | 5 |
| `hitbodedut` | 0 | 5 |
| `zzzzzzzzzz` | 0 | 5 |

Impact: Milvus itself is available and searchable, but the general hybrid search path currently loses vector recall for `breslov_primary` because the Milvus metadata still stores the legacy code `breslov`.

## Runtime behavior

Direct `search_chunks_hybrid(conn, knowledge_scope_code="breslov_primary", ...)` returned only `["fts"]` source signals for tested queries. `vector_score` was `null` for all returned rows.

Relation QA local run used Milvus successfully for both tested relation questions:

- `Qué relación hay entre alegría y plegaria`
- `Qué relación hay entre sangre y habla`

Both runs used deterministic fallback for synthesis, but retrieval included `milvus_dense_cosine`.

## Temporary write/search/drop probe

Isolated collection: `tebaai_milvus26_acid_temp_20260709`

- Inserted vectors: `100/100`.
- Insert failures: `0`.
- HNSW index created.
- Search results: `5`.
- Search latency: `0.026s`.
- Final count before cleanup: `100`.
- `--drop-after`: executed.
- Follow-up check: temporary collection no longer exists.

## Tooling note

PyMilvus emitted deprecation warnings for ORM-style APIs (`connections`, `utility`, `Collection`). Functional behavior passed, but scripts should migrate to `MilvusClient` before PyMilvus 3.1.
