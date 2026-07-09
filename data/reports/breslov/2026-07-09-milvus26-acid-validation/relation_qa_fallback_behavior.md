# Relation QA fallback behavior

## Result

Observed through direct local invocation of `run_relation_qa` against PostgreSQL.
The backend HTTP CLI was not used because the backend dev server was not running.

## Questions tested

| Question | Elapsed ms | used_milvus | fallback_used | Sources | Retrieval | Warnings |
|---|---:|---|---|---:|---|---|
| Qué relación hay entre alegría y plegaria | 35984 | false | true | 20 | `postgresql_fts_websearch`, `postgresql_ilike_fallback`, `postgresql_cooccurrence` | `milvus_unavailable: MilvusConnectionError — lexical retrieval used`; `no_literal_relation`; `cooccurrence_only`; `deterministic_fallback` |
| Qué relación hay entre sangre y habla | 18888 | false | true | 20 | `postgresql_fts_websearch`, `postgresql_ilike_fallback`, `postgresql_cooccurrence` | `milvus_unavailable: MilvusConnectionError — lexical retrieval used`; `no_literal_relation`; `cooccurrence_only`; `deterministic_fallback` |

## What this confirms

- Milvus failure does not crash Relation QA.
- `used_milvus` is `false` when vector search cannot connect.
- Lexical sources still surface and are used for deterministic fallback.
- The warning payload includes the exception type.

## What this does not confirm

- It does not confirm HTTP server behavior while the backend process is down.
- It does not confirm performance when Milvus is healthy.
