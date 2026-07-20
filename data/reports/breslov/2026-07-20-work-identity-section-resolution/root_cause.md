# Root Cause Analysis: Work Identity and Section Resolution

## Symptom

Querying "Moshé, tú lo has dicho bien" returned Likutey Moharán II as primary
evidence or no evidence at all, despite the phrase existing in
`LIKUTEY MOHARÁN I int (imprenta).pdf` at section `LIKUTEY MOHARÁN #2:6`,
printed page 73.

## Root Cause 1: Case-Sensitive Literal Matching

`_compute_literal_match_kind()` in `investigative_qa_v1.py` used
case-sensitive `term in quote` checks for Latin-script terms.

The terms list included both the original-case phrase `"Moshé, tú lo has dicho bien"`
and a lowercased variant `"moshé"`. Since `"moshé"` (lowercase m) does not
match `"Moshé"` (uppercase M) in the quote, the condition
`all(term in quote for term in terms)` failed.

```
terms = ["Moshé, tú lo has dicho bien", "moshé"]
"moshé" in "Moshé, tú lo has dicho bien" → False (case mismatch)
```

This caused `literal_match_kind` to be `"single_term"` instead of `"exact_phrase"`,
which in turn prevented `_deterministic_claims()` from creating any claims
and primary evidence.

## Root Cause 2: No Separate Work Identity Resolver

The system used a hardcoded `WORK_TITLES` dict mapping work codes to display
names, with no canonical work identity resolver. Work identity was tied to
hardcoded strings rather than document metadata or filename resolution,
making it fragile and difficult to extend.

## Root Cause 3: No Robust Section Parser

Section labels like `#2:6` were parsed ad-hoc in specific functions.
The regex for LM XV sections hardcoded `II` in the section label pattern,
though the work itself was correctly identified as "Likutey Moharán XV KDP".

## Root Cause 4: Additional Evidence Not Displayed

When an exact phrase appeared in multiple works (LMI and LMII), the
deterministic renderer only showed primary evidence. Non-primary exact
matches from other works were hidden from the answer_markdown.

## Fix Applied

1. **Case-insensitive matching**: Changed `_compute_literal_match_kind()` to
   use `term.lower() in quote.lower()` for Latin-script terms. Hebrew
   matching (which has no case) remains unchanged.

2. **Work identity resolver**: Created `modules/library/work_identity.py`
   with `resolve_work_identity()` and `resolve_from_filename()` functions
   that map physical filenames and work codes to canonical work metadata,
   including canonical_work_title, part, volume, edition, and display_title.

3. **Section parser**: Created `parse_section_label()` in
   `work_identity.py` that handles `#2:6`, `II #83:8`, `I #2:6`, and
   variants with spacing. Never infers volume from a section number.

4. **Additional evidence display**: Updated `render()` to show
   `## Apariciones adicionales` for non-primary exact phrase matches
   from different works.

## Files Changed

- `backend/modules/library/investigative_qa_v1.py` — literal match fix,
  claim update for additional evidence, render update
- `backend/modules/library/work_identity.py` — **NEW**: canonical work
  identity resolver and section parser
- `backend/tests/test_work_identity.py` — **NEW**: 29 tests
