# Simple RAG Hebrew literal DEV gate — sanitized evidence

Date: 2026-07-29

Initial branch: `feature/console-backend-core`

Initial HEAD: `302d3c5f627a33ee2de90991e88dcbd266b62dc6`

## Baseline

All five API queries preserved `original_query`, returned 30 Milvus hits and
zero literal hits. A semantic-only fragment without `ומצרים`, `נסים` or
`לקראתו` was incorrectly primary.

| Query form | Baseline literal | Baseline primary |
|---|---:|---|
| pointed | 0 | unrelated semantic |
| unpointed | 0 | unrelated semantic |
| fragmented | 0 | unrelated semantic |
| first two tokens | 0 | unrelated semantic |
| distinctive token | 0 | unrelated semantic |

## Canonical source

- document ID: `3715c6e0-db56-49a1-82df-62d0a4d0b5cd`
- physical file: `LIKUTEY MOHARAN II Interior.pdf`
- SHA-256: `ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61`
- title page: *Likutey Moharán*, physical volume 2, lessons 7–16
- canonical work display: *Likutey Moharán I*
- primary node: `8b0ec486-7596-43a3-97b0-c08d2221d70e`
- page node: `eca92e46-5070-4be1-8d3f-c15b819ba3be`
- physical PDF page: 14
- printed page: 4
- section: Torá 7:1
- document status: `test_candidate` (DEV read-only)
- source table/view: `library_content_nodes_v2`,
  `library_lmii_search_ready_v2`

The same phrase also occurs at physical page 122 / printed page 112 / Torá 9:5.

Milvus contains neither the document ID nor the primary node ID. No corpus
embedding was created or recalculated.

## Final real API

| Query form | Literal hits | Result | Primary |
|---|---:|---|---|
| pointed | 3 | complete | LMI I, Torá 7:1, PDF 14 / printed 4 |
| unpointed | 3 | complete | LMI I, Torá 7:1, PDF 14 / printed 4 |
| fragmented | 3 | complete | LMI I, Torá 7:1, PDF 14 / printed 4 |

Observed total latency for the critical forms was approximately 6.5–9.1 s.
Literal PostgreSQL cost approximately 2.8–4.8 s, two Hebrew embeddings plus
Milvus approximately 0.7–2.5 s, and grounded synthesis approximately 3.7–4.8 s.

## Expanded batches

The real Hebrew batch covered pointed/unpointed/fragmented forms, partial
tokens, the distinctive token, `תְּהִלָּתִי אֶחְטָם לָךְ`,
`תהילתי אחטם לך`, `אזמרה`, and `מה הקשר בין דיבור לאמונה`.
The spelling variant `תהילתי` is recovered as `hebrew_bigram`, contextual
rather than falsely exact.

The real regression batch passed nine ES/EN queries: Azamra, two speech/relation
questions, Psalm 19, scorpion, sadness, fear, hitbodedut and an English joy
question. Each returned evidence; all finished as `complete`.

## Validation

- focused backend: 344 passed
- backend full: 1248 passed, 94 pre-existing deprecation/security warnings
- frontend check: 0 errors, 0 warnings, 0 hints
- frontend unit: 59 passed
- frontend build: PASS
- Playwright real DEV gate: 3 passed (admin three forms, mobile RTL, guest
  read-only/admin redirect/logout)

No credentials, tokens, cookies, JWTs, peppers or DSNs are included.
