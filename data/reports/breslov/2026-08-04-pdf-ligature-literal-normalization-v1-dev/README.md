# PDF Ligature Literal Normalization V1 — DEV report

Phase: `TEBAAI_PDF_LIGATURE_LITERAL_NORMALIZATION_V1_DEV`

Date: 2026-08-04 (DEV only)

## Result

**Gate: `TEBAAI_PDF_LIGATURE_LITERAL_NORMALIZATION_V1_DEV_READY`**

| Control | Result |
| --- | --- |
| Note 36 reproduced | PASS |
| Ligature identified (U+FB01 `ﬁ`, U+FB02 `ﬂ`) | PASS |
| Internal extraction space identified | PASS |
| NFKC evaluated / ligatures expanded | PASS |
| Conservative split reconstruction (insert-space-only variants) | PASS |
| Real words never joined (`la flor`, `por fin`, `fi nal`) | PASS |
| Original text preserved | PASS |
| Original quote preserves `reﬁ namiento` / `Inﬁ nito` | PASS |
| Offset policy: canonical footnote block quoted, no invented offsets | PASS |
| Normalization idempotent | PASS |
| Note 36 PRIMARY | PASS |
| `footnote_literal_exact` / footnote 36 | PASS |
| Literal batch | **25/25** (before 24/25) |
| Note 35, Mishkán, Bondad, Melodías, Salmos | PASS |
| Proper names | PASS |
| Hebrew with/without niqqud (same evidence) | PASS |
| Canonical metadata intact | PASS |
| Planner Azamra | `unresolved` (unchanged) |
| Negatives | PASS |
| Focused backend tests | 382 passed |
| Full backend | 1482 passed |
| Frontend | 0 errors, 70 tests, build PASS |
| Admin E2E / Guest E2E / Mobile E2E | 3/3 PASS |
| ADR-020 | PASS |
| Fixture | PASS |
| Audit script | PASS (exit 0) |

## Root cause (note 36)

- Query: `Birur hace referencia a la extracción y refinamiento de las chispas`
- Original extracted surface: `reﬁ namiento` (U+FB01 + internal space) and
  `Inﬁ nito` (U+FB01 + internal space).
- `search_text_normalized` expands the ligature (NFKC) to `refi namiento` but
  keeps the extraction space, so the clean query `refinamiento` could not be
  located as a literal substring.
- Additionally, the extractor interleaves an inline parenthetical gloss
  (`Birur (pl. birurim; lit. “tamizar”) hace …`), which broke contiguity for
  the full sentence query.
- The Interior Final chunks have `search_vector_es`/`search_vector_simple`
  NULL, so the literal lane is the only retrieval path for this edition.

## Implementation

- New module `backend/modules/library/pdf_ligature_normalization.py`:
  - `expand_pdf_compatibility_characters` — explicit NFKC + ligature table
    (`ﬀ`→ff, `ﬁ`→fi, `ﬂ`→fl, `ﬃ`→ffi, `ﬄ`→ffl, `ﬅ`→st, `ﬆ`→st);
  - `normalize_pdf_search_text` — canonical search form (NFKC + whitespace
    collapse; never joins words);
  - `build_pdf_literal_match_variants` — matching-only variants that *insert*
    the extraction space after an embedded ligature digraph
    (`refinamiento` → `refi namiento`); never removes spaces;
  - `elide_parenthetical_glosses` — matching-only elision of inline glosses
    preceded by a letter (preserves `(Salmos 16:1)` at line/block starts);
  - idempotent, deterministic, Hebrew-safe.
- `simple_research_rag.py`: fragmentation variants appended to query variants;
  footnote-number detection tests canonical + fragmentation variants against
  gloss-elided note blocks.
- `simple_research_repository.py`: literal-lane SQL normalizes both sides with
  gloss elision (PostgreSQL regexp with lookbehind), one CTE reused for the
  exact-match family of signals.
- Additive optional Hit fields: `matched_normalized_text`,
  `normalization_applied`, `normalization_kinds` (no UI exposure).

## Notes

- `oﬃcina` (U+FB03 FFI) expands mechanically to `officina`; the phase prompt
  example assumed orthography, which the normalization invariants explicitly
  forbid (normalization is not a spelling corrector). `oﬁcina` (U+FB01) →
  `oficina`.
- The batch's note-36 query sits at case 18 in the previous 25-case order; it
  is re-run exactly as-is (no query substitution). 25/25.
- Evidence ID for note 36: `ev-e419ec6448d2d992` (stable across 10 admin +
  10 guest runs; same page chunk also hosts note 35).
- PostgreSQL was only read. Milvus was only inspected (5370 entities, loaded).
- `Interior Final` remains `test_candidate`; nothing promoted.
