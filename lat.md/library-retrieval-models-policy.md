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

Generation remains outside general search. It is allowed in the dedicated
evidence-first relation QA contract approved by ADR-005 and in the simple
grounded research path approved for the DEV gate by ADR-006.

| Attribute | Value |
|-----------|-------|
| Generative model in production | `openai_gpt-5.4-nano` via LiteLLM |
| Generative surface | `POST /library/relation-qa` and `POST /library/investigative-qa/v1` |
| RAG | Bounded evidence-first editorial synthesis; no open-domain chat |
| Interpretative answer generation | Implemented only for Relation QA |
| LLM reranking | Not implemented |
| LLM synthesis | Optional and downstream of canonical PG evidence |

`POST /library/investigative-qa/v1` uses `simple_rag` as its primary DEV path:
the intact original query is embedded, Milvus supplies candidate chunk IDs,
PostgreSQL complements literal retrieval and rehydrates complete canonical
Markdown, and the model renders only from the selected context. Intent and
specialized parsers are optional enrichment and cannot block this retrieval.

The endpoint exposes `TEBAAI_RESEARCH_PIPELINE=simple_rag|advanced|compare`.
`simple_rag` is the DEV default; no production rollout is implied by this
policy update.

For short ASCII proper-name queries, `simple_rag` must prioritize canonical
PostgreSQL literal evidence over vector similarity. Nominal connectors such as
`of` remain part of phrase matching. A `semantic_only` candidate without the
nominal tokens cannot be primary, and an exact literal candidate must enter the
generation context. Approximate spelling variants remain retrieval hints,
produce an explicit partial result, and never establish editorial identity by
themselves. The accepted DEV design is recorded in
`docs/adr/ADR-009-short-proper-name-literal-retrieval.md`.

`POST /library/search` continues to retrieve bibliographic evidence only. It does not call a generative model or return interpretative synthesis. `POST /library/investigative-qa/v1` may call the same model solely for schema-validated multilingual query understanding and evidence-bound rendering under ADR-005; retrieval remains deterministic and downstream.

## Investigative Relation QA

Relation QA is an editorial research API, not a devotional chatbot or a replacement for source reading.

The endpoint must:

1. authorize and resolve `knowledge_scope_code` before retrieval;
2. retrieve first and synthesize second;
3. rehydrate every Milvus candidate from PostgreSQL;
4. return structured sources, evidence types, warnings and method metadata;
5. keep `literal_relation_found` deterministic;
6. label model interpretation as `ai_inference` or `INFERIDA_POR_IA`;
7. reject unknown model source IDs and fall back deterministically on invalid output;
8. keep `content_preview` and `composite_page_context` out of final citations.
9. return explicit claim-to-evidence associations with stable IDs for conversational consumers;
10. separate literal fidelity from relevance and relational strength;
11. prevent single-term matches from becoming primary evidence for a relational query;
12. apply requested per-work limits to the final deduplicated result set.

The accepted design and consequences are documented in `docs/adr/ADR-005-breslov-investigative-relation-qa-endpoint.md`.

Any future generative surface, open-domain RAG pipeline, or LLM-based reranking beyond ADR-005 and ADR-006 must:

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
- Do not call a generative LLM inside `POST /library/search` or any surface not approved by ADR.
- Do not invent bibliographic metadata (chapter, page, section).
- Do not change the embedding model without updating this policy and running
  the evaluation harness.
- Do not change the embedding model mid-phase without re-indexing all chunks.
- Do not hardcode API keys or model names in code — use `core/config.py`.

## Conversational investigative query understanding

`POST /library/investigative-qa/v1` supports bounded ES/EN/HE query interpretation and follow-up context.

- Unicode preprocessing, Hebrew morphology, work mapping and query variants are deterministic.
- LiteLLM returns strict JSON; model normalization is rebuilt and grounded by backend code.
- Model failure always falls back without turning infrastructure failure into `no_evidence` by itself.
- PostgreSQL evidence decides whether a match exists; model output never supplies citations or pages.
- Conversation history is capped at 15 questions and cannot carry arbitrary source IDs into retrieval.
- Translation aliases are secondary, explicit expansions and cannot replace the Hebrew subject as authority.

## Future directions (not implemented)

The following capabilities require explicit design and validation before implementation.

- Sparse vectors (Milvus hybrid search with BM25).
- Cross-encoder reranking.
- Open-domain or conversational RAG beyond the bounded Relation QA contract.
- Multi-hop retrieval for intertextual questions.
