# TebaAI — Breslov Test Corpus Policy

This policy isolates experimental bibliographic documents from the production Breslov corpus and its derived indexes.

## Corpus boundary

Production and test documents use separate PostgreSQL collections with distinct lifecycle expectations.

| Collection | Purpose | Allowed document status | Product evaluation |
| --- | --- | --- | --- |
| `breslov` | Validated production bibliography | `ready` | included |
| `breslov_test` | Controlled ingestion and retrieval experiments | `test_candidate` | excluded |

No command may silently fall back from `breslov_test` to `breslov`. Dry-run resolves a missing collection in memory and runs inside a PostgreSQL read-only transaction; only an explicit apply may create or populate the test collection.

Collections whose code ends in `_test` are created with metadata `{"status": "test"}` and cannot accept documents with status `ready` through the ingestion boundary.

## Document lifecycle

Document status represents readiness for use, independently of extraction success.

- `ready`: accepted for the target corpus and its normal retrieval workflow.
- `test_candidate`: extracted for controlled validation but not accepted as production evidence.
- `draft`, `archived`, and `error`: existing lifecycle states retained for compatibility.

Migration 008 adds `test_candidate` to the document status constraint and adds document-level `bibliographic_metadata`. Existing documents remain unchanged.

## El Alma del Rebe Najmán

The first test candidate is a local PDF whose normal text extraction is suitable for controlled evaluation.

- source: `EL ALMA DEL REBE - KINDLE.pdf`;
- target collection: `breslov_test`;
- status: `test_candidate`;
- language: Spanish;
- extracted content: 643,028 characters;
- current state: document and text persisted, no chunks;
- PDF internal title/author metadata is inconsistent and is not bibliographic authority;
- physical PDF pages must not be presented as printed or canonical pagination.

The candidate is not part of the production Breslov corpus and must not affect its evaluation fixtures or quality metrics.

## Retrieval and indexing isolation

Test-corpus retrieval remains separate from production indexes and evaluation.

- Do not include `breslov_test` in the principal bibliographic evaluation harness.
- Do not index test chunks in `tebaai_breslov_chunks_v1`.
- If vector indexing is later approved, use `tebaai_breslov_test_chunks_v1`.
- Do not call LiteLLM or create embeddings until test chunking has passed its own validation.
- Do not expose `test_candidate` documents as production-ready evidence.

## Promotion

Promotion requires explicit evidence and must never happen by changing collection or status implicitly.

Before moving a candidate to `breslov`/`ready`, validate extraction, section-aware chunking, literal search, references, duplicate handling, page semantics and retrieval quality. Promotion requires a separate controlled phase.
