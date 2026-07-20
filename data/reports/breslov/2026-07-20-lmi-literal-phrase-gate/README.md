# LMI Literal Phrase Retrieval Gate — 2026-07-20

## Status

**`LMI_LITERAL_PHRASE_RETRIEVAL_FULL_PASS`**
**`READY_FOR_LITERAL_PIPELINE_INTEGRATION_REVIEW`**

## Summary

The literal phrase retrieval gate for `LIKUTEY MOHARÁN I int (imprenta).pdf` is now PASS. Both focal phrases are recoverable via deterministic path (AI disabled) with correct intent, page, section, and match classification.

## Focal Cases

| Query | Status | Intent | PDF Page | Printed | Section | Match Kind |
|-------|--------|--------|----------|---------|---------|------------|
| "Ellos salen fuera de la comunidad judía como resultado de sus malas acciones" | ok | literal_lookup | 203 | 183 | #4:10 | exact_phrase |
| "Moshé, tú lo has dicho bien" | ok | literal_lookup | 93 | 73 | #2:6 | exact_phrase |

## Changes Made

### 1. `investigative_qa_v1.py` — `_compute_literal_match_kind()`
- Collapse whitespace in quote (`" ".join(quote.split())`) before checking term presence
- Add punctuation-agnostic fallback check (remove commas/quotes before comparison)
- Normalize newlines/whitespace in Latin terms before matching

### 2. `multilingual_query.py` — `_latin_literal_from_question()` (new function)
- Detect Latin-script declarative sentences as literal phrase candidates
- Conservative heuristics: >= 5 tokens, no interrogative/command words, no HTML/JSON
- Falls back gracefully to concept lookup when criteria not met

### 3. `multilingual_query.py` — `deterministic_interpret()`
- Route Latin literal candidates to `literal_lookup` intent
- Populate `literal_phrases` for full-phrase search

## Verification

| Gate | Result |
|------|--------|
| Backend tests | 1003 PASS (no regressions) |
| Frontend check | 0 errors, 0 warnings |
| Frontend build | 7 pages PASS |
| `git diff --check` | PASS |
| Adversarial safety | 4/4 PASS (all rejected) |
| Exact phrase (long) | PASS |
| Exact phrase (short) | PASS |
| Newline variant | PASS |
| With quotes variant | PASS |
| Lowercase+no-accent | FAIL (expected - needs secondary tier) |

## Known Limitations

- **Unaccented variants** (e.g., "judia" without accent) are not matched. The `normalize_hebrew_search` function preserves Spanish accents. This requires an unaccenting pass in a future tier.
- **Short literal phrases** (5-7 tokens) are detected but with less specificity. The heuristic is conservative to avoid false positives.

## Services

- Backend: http://127.0.0.1:7008 (PID 127570)
- Astro: http://127.0.0.1:3008 (PID 115205)
- Login: http://127.0.0.1:3008/login
- Research: http://127.0.0.1:3008/research
