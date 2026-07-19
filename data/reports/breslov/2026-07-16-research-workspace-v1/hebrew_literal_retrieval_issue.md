# Hebrew literal retrieval — root cause and resolution

Date: 2026-07-18

## Reproduction

The real endpoint returned `no_evidence` for the pointed phrase, the unpointed phrase, and `אחטם לך`. It classified Hebrew text through the relation-oriented path and searched only the previously registered works with raw `ILIKE` expressions.

## Root cause

This was a compound data and retrieval defect:

1. The screenshot source was absent from `library_documents`. The similarly named Likutey Moharán II PDF was present, but it is not the physical source of printed page 76.
2. The PDF embedded text layer inserts spaces between Hebrew grapheme clusters. Raw substring search therefore cannot find normal logical Hebrew input.
3. Query and indexed text did not share a niqqud-insensitive Hebrew normalization.
4. `/library/investigative-qa/v1` had no explicit `literal_lookup` intent and could render the relation-specific no-evidence message.
5. A page-wide mixed Hebrew/Spanish snippet was directionally `mixed`; a line-scoped literal context was required for semantic `lang=he` and `dir=rtl`.

## Resolution

- Identified and ingested only the physical source PDF using a page-first, no-OCR, no-embedding run.
- Retained raw embedded page text for audit and stored a geometry-derived logical Unicode projection as citable literal text.
- Added one shared derived Hebrew search normalization; canonical text remains pointed and unchanged.
- Added PostgreSQL literal/FTS/trigram support over `normalized_text` and a physical-source audit view.
- Added deterministic intent routing and literal-first endpoint rendering.
- Added line-scoped snippets, stable content-node evidence IDs, physical document metadata, page anchor, physical page, printed page, and section.

No strings are reversed. No translation is generated or substituted. No other document was reingested.
