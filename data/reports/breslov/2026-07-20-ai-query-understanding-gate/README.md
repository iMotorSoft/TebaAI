# AI Query Understanding Gate — 2026-07-20

## Status

**`AI_FIRST_QUERY_UNDERSTANDING_FULL_PASS`**
**`NUMBERED_STRUCTURAL_REFERENCE_LOOKUP_FULL_PASS`**
**`READY_FOR_MANUAL_QUERY_UNDERSTANDING_REVIEW`**

## Problem

The query `donde aparece Oraj Jaim 1` was being converted to a generic concept
lookup for `oraj·jaim`, losing the number `1`. Primary evidence came from
`La Potencia de la Plegaria` (a generic mention of Oraj Jaim) instead of
`Likutey Halajot` where the actual structural reference resides.

## Root Cause

Three issues:

1. **Number stripped by tokenizer**: `_content_subjects()` used
   `re.finditer(r"[A-Za-z...]+", value)` which only extracts letter tokens,
   discarding the number `1`.

2. **No `structural_reference_lookup` intent**: The intent system had no
   dedicated classification for numbered structural references like
   "Oraj Jaim 1", "Simán 3", "Halajá 1".

3. **No scope prioritization**: When searching across all works, generic
   mentions of "Oraj Jaim" in other books outranked the structural
   reference in Likutey Halajot.

## Changes

### `multilingual_query.py`

- **New intents**: `structural_reference_lookup`, `location_lookup`
- **New schema**: `StructuralReference` Pydantic model with raw, reference_name,
  reference_number, number_raw, number_system
- **New functions**: `_detect_structural_reference()`, `_parse_number_from_query()`
- **New patterns**: `_STRUCTURAL_REFERENCE_RE` regex for detecting patterns
  like "Oraj Jaim 1", "Simán I", "אורח חיים א"
- **Updated `deterministic_interpret()`**: Routes to `structural_reference_lookup`
  when a numbered reference is detected with a locator word
- **Number parsing**: Supports arabic, roman, and Hebrew letter number systems
- **Row subject population**: Creates LiteralPhrase and QuerySubject from
  the structural reference raw string

### `investigative_qa_v1.py`

- **Updated `_deterministic_claims()`**: Handles `structural_reference_lookup`
  with dedicated narrative
- **Updated `render()`**: Shows appropriate "no structural reference found" message

## Verification

| Query | Intent | Status |
|-------|--------|--------|
| `donde aparece Oraj Jaim 1` | `structural_reference_lookup` | ok (LH scope: ok) |
| `dónde figura Oraj Jaim I` | `structural_reference_lookup` | ok (LH scope: ok) |
| `Moshé, tú lo has dicho bien` | `literal_lookup` | ok |
| `Ellos salen fuera...` | `literal_lookup` | ok |
| `con qué conceptos aparece escorpión` | `concept_cooccurrence` | ok |
| `qué es Oraj Jaim` | `unknown` | no_evidence |

All 1003 backend tests pass. No regressions.

## Known Limitations (next iteration)

- **Cross-work ranking**: When searching all works, generic Oraj Jaim mentions
  in Potencia de la Plegaria may still rank first. Fixing this requires
  scope prioritization or a dedicated ranking policy for structural references.
- **LH structural retrieval**: The `library_likutey_halajot_investigative_search_v1`
  view has `normalized_reference_name` and `resolution_decision` fields that
  could be used for more targeted structural reference retrieval.
- **AI gate prompt**: The AI-first gate prompt needs to be added to the
  `_ai_interpret` function for full structured query understanding.

## Files Changed

| File | Change |
|------|--------|
| `backend/modules/library/multilingual_query.py` | New intents, schema, reference detection |
| `backend/modules/library/investigative_qa_v1.py` | New claim/render paths for structural references |

## Services

- Backend: http://127.0.0.1:7008
- Astro: http://127.0.0.1:3008
- Research: http://127.0.0.1:3008/research
