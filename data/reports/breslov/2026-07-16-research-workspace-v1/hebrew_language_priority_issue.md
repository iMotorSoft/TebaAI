# Hebrew Language Priority Issue — Resolved

## Before

- Hebrew literal phrases embedded in Spanish queries were split into individual words
- Concept extraction regex `[\wáéíóúñÁÉÍÓÚÑ]+` did not match Hebrew characters
- Hebrew stop words (`כי`, `יש`, `את`, etc.) were used as search terms, producing noise
- No phrase-level search for Hebrew literals
- No language-aware ranking — Spanish results could appear before Hebrew matches
- Language detection did not separate interface language from retrieval language
- Combining mark `ׁ` (U+05C1) could be wrongly attached to non-Hebrew characters like `:` in PDF geometry reconstruction

## After

### Combining mark fix (Phase 1)

- `_readable_line()` in `likutey_moharan_ii_layout.py`: Hebrew combining marks only attach to Hebrew base letters (U+05D0–U+05EA), not to punctuation
- Orphan combining marks prefer Hebrew-letter clusters over non-Hebrew clusters
- Test `test_real_projection_merges_the_section_heading_and_omits_page_number`: PASS

### Hebrew phrase detection and concept extraction (Phase 2-7)

- New `_extract_literal_phrases()`: detects contiguous Hebrew word sequences (3+ letters with 2+ words), skipping Hebrew stop words
- New `_hebrew_content_words()`: extracts meaningful Hebrew words, filtering stop words
- Updated `_clean_concept()`: regex now includes `\u0590-\u05ff` for Hebrew characters
- Updated `relation_concepts()`: for Hebrew queries, uses extracted literal phrase as first concept, content words as additional concepts
- Hebrew stop words: `כי`, `יש`, `את`, `וה`, `על`, `של`, `לא`, etc.

### Language-aware analysis (Phase 5)

- New `_detect_interface_language()`: strips Hebrew characters to detect the user's framework language
- New `_analyze_query_language()`: separates `interface_language` from `primary_retrieval_language` and `query_language`
- Mixed queries like "donde aparece \[hebrew\]" → interface=es, primary_retrieval=he
- Pure Hebrew queries → interface=he, primary_retrieval=he
- Pure Spanish → interface=es, primary_retrieval=es

### Hit model with language metadata (Phase 7-8)

- `Hit.language_match`: "exact" | "primary" | "secondary" | "fallback"
- `Hit.literal_match_kind`: "exact_phrase" | "normalized" | "no_niqqud" | "single_term" | "semantic" | "none"
- `Hit.retrieval_tier`: 0 (exact match in query language) to 4 (fallback)
- `_sort_key()`: primary sort by `retrieval_tier`, then relation_priority
- `_compute_retrieval_tier()`: exact Hebrew phrase → tier 0, single Hebrew term → tier 1, secondary language → tier 3, fallback → tier 4

### Phrase-level search (Phase 7)

- New `_phrase_fetch()`: searches for exact phrase as a whole using ILIKE
- `run()`: executes phrase search first, then individual term search
- Phrase-matched entries promoted to tier 0 with exact_phrase literal_match_kind

### Frontend (Phase 12)

- `Hit` interface extended with `language_match`, `literal_match_kind`, `retrieval_tier`
- `researchLabels.ts`: added `languageMatchLabels`, `literalKindLabels`, `languageMatchLabel()`, `literalKindLabel()`
- `ResearchWorkspace.svelte`: evidence cards show language labels ("Traducción / ampliación", "Otro idioma") and literal match labels ("Coincidencia literal exacta")

### Tests (Phase 14-16)

- 32 new tests covering: language detection, phrase extraction, hit language metadata, sorting, retrieval tiers, concept extraction for Hebrew
- All 827 backend tests PASS
- Frontend check: 0 errors, 0 warnings
- Frontend build: 7 pages

## Root cause

The original bug had two independent causes:

1. **No Hebrew literal phrase detection**: The `relation_concepts()` function splits queries into individual word concepts. For a Hebrew phrase like `כי יש עון שמעכב תשובה`, it would extract `כי` and `יש` as concepts — both are Hebrew stop words that match almost every Hebrew text fragment, producing noise.

2. **No language-aware ranking**: The `_sort_key()` function only sorted by relation_relevance and matched_concepts count. A Spanish semantic match could outrank a Hebrew literal match because there was no language component in the sort key.

## Status

HEBREW_LITERAL_LANGUAGE_PRIORITY_FULL_PASS
READY_FOR_MANUAL_HEBREW_SEARCH_REVIEW
