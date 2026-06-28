# TebaAI — Library Retrieval Models Policy

This policy separates authoritative content, textual search, semantic retrieval and any future generative stage.

## Purpose

This document defines the embedding model, search strategies, query modes, and
the boundary between retrieval and generative response for the TebaAI library.

It exists to prevent confusion between:

- embedding model vs. generative model;
- textual search vs. semantic search vs. hybrid retrieval;
- retrieval of evidence vs. interpretative answer generation.

## Embeddings

Indexing and querying use one embedding contract so vectors remain comparable.

| Attribute | Value |
|-----------|-------|
| Model | `text-embedding-3-small` |
| Internal alias | `openai_text_embedding_3_small` |
| Dimension | 1536 |
| Operational provider | LiteLLM (localhost:4000) |
| Usage | chunk embedding at index time, query embedding at search time |
| Vector database | Milvus 2.6 |
| Milvus collection | `tebaai_breslov_chunks_v1` |
| Entities (2026-06-28) | 1991 vectors |

Only `text-embedding-3-small` is used for both indexing and querying. No other
embedding model is configured.

## Textual / Literal Search

PostgreSQL provides authoritative lexical, phrase and fuzzy retrieval over persisted chunk text.

| Attribute | Value |
|-----------|-------|
| Engine | PostgreSQL 18 Full Text Search |
| Accent tolerance | `unaccent` extension |
| Fuzzy / trigram | `pg_trgm` extension |
| FTS configuration | `spanish` (search_vector_es) and `simple` (search_vector_simple) |
| Ranking | `ts_rank_cd` |
| Highlighting | `ts_headline` / `<mark>` tags in highlighted_excerpt |
| Source of truth | `library_document_chunks.content` |

FTS is used for modes `auto`, `fts`, `phrase`, and as the FTS branch of `hybrid`.

## Semantic / Vector Search

Milvus provides semantic candidates that are always enriched and authorized from PostgreSQL.

| Attribute | Value |
|-----------|-------|
| Engine | Milvus 2.6 |
| Query embedding | `text-embedding-3-small` via LiteLLM |
| Metric | COSINE |
| Index | HNSW (M=16, efConstruction=200) |
| Search params | ef=64 |
| Enrichment | PostgreSQL fetches full chunk metadata for each Milvus hit |
| Highlight | only when a literal match exists in the chunk content |

Semantic search alone (vector-only results) may not produce highlighted excerpts.
It is used as the vector branch of `hybrid` mode and independently via
`scripts/search_milvus.py`.

## Hybrid Search

Hybrid mode combines normalized PostgreSQL and Milvus signals while deduplicating by stable chunk identity.

| Attribute | Value |
|-----------|-------|
| Mode name | `hybrid` |
| Components | PostgreSQL FTS (mode=auto) + Milvus vector search |
| Merge | deduplication by `chunk_id` |
| Scoring | `0.55 × normalized_fts_rank + 0.45 × normalized_vector_score` |
| Single-source score | `0.70 × fts` (FTS only) or `0.45 × vector` (vector only) |
| Phrase bonus | +0.10 if literal `<mark>` match exists |
| Source signals | `["fts"]`, `["vector"]`, or `["fts", "vector"]` |
| Response fields | `rank`, `fts_rank`, `vector_score`, `hybrid_score`, `source_signals` |
| PostgreSQL | always the source of truth — Milvus results are enriched from PG |

## Query Modes Summary

Each public query mode maps to an explicit retrieval engine and use case.

| Mode | Engine | Use case |
|------|--------|----------|
| `auto` | PostgreSQL FTS (phrase + fts merge) | General text search, default |
| `fts` | PostgreSQL FTS (tsvector only) | Lexical search with ranking |
| `phrase` | PostgreSQL FTS (ILIKE on unaccent) | Exact/near-exact phrase |
| `trigram` | PostgreSQL pg_trgm | Fuzzy / typo-tolerant |
| `hybrid` | PostgreSQL FTS + Milvus | Combined textual + semantic |

## Generative Model

Generation is outside the current retrieval contract and cannot be introduced implicitly.

| Attribute | Value |
|-----------|-------|
| Generative model in production | None |
| RAG | Not implemented |
| Interpretative answer generation | Not implemented |
| LLM reranking | Not implemented |
| LLM synthesis | Not implemented |

**TebaAI currently retrieves bibliographic evidence only. It does not generate
interpretative answers, summaries, or conversational responses.**

Any future phase that introduces a generative model, RAG pipeline, or LLM-based
reranking must:

1. Create a new ADR or update this policy.
2. Keep retrieval separate from generation (retrieval first, generation second).
3. Never call a generative model as part of the `POST /library/search` endpoint.
4. Never invent citations, chapters, pages, or bibliographic references.
5. Always return the original textual evidence alongside any generated content.
6. Document the model name, provider, and version in this policy.

## Prohibitions

These constraints protect source authority, citation integrity and embedding compatibility.

- Do not replace PostgreSQL with Milvus as the source of truth.
- Do not replace Milvus with PostgreSQL for vector search.
- Do not call a generative LLM inside retrieval endpoints.
- Do not invent bibliographic metadata (chapter, page, section).
- Do not change the embedding model without updating this policy and running
  the evaluation harness.
- Do not change the embedding model mid-phase without re-indexing all chunks.
- Do not hardcode API keys or model names in code — use `core/config.py`.

## Future directions (not implemented)

The following capabilities require explicit design and validation before implementation.

- Sparse vectors (Milvus hybrid search with BM25).
- Cross-encoder reranking.
- RAG with cited evidence.
- Conversational search with follow-up context.
- Multi-hop retrieval for intertextual questions.
