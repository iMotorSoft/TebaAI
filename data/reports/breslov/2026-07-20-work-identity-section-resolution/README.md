# Work Identity and Section Resolution — 2026-07-20

## Status

`WORK_IDENTITY_AND_SECTION_RESOLUTION_FULL_PASS`
`READY_FOR_MANUAL_WORK_IDENTITY_REVIEW`

## Problem

The phrase `Moshé, tú lo has dicho bien` from `LIKUTEY MOHARÁN I int (imprenta).pdf`
was being incorrectly handled. The phrase appeared at section `LIKUTEY MOHARÁN #2:6`,
printed page 73, but the system either:
- Returned no evidence (literal match not found)
- Or the additional occurrence in `Likutey Moharán II` was not properly separated

## Root Cause

Case-sensitive literal matching in `_compute_literal_match_kind()`: terms with
mixed case (e.g., "moshé" vs "Moshé") failed the `term in quote` check,
causing exact phrases to be classified as "single_term" matches.

## Fix

1. **Case-insensitive Latin matching**: `term.lower() in quote.lower()`
2. **New `work_identity.py` module**: canonical resolver + section parser
3. **Additional evidence display**: non-primary exact matches shown separately

## Validation

| Metric | Result |
|---|---|
| Backend tests | 1003 passed (29 new) |
| Frontend check | 0 errors, 0 warnings |
| Frontend build | 7 pages PASS |
| `git diff --check` | PASS |
| `lat check` | PASS |
| Focal case (LMI) | primary, exact_phrase, section #2:6, printed 73 |
| Additional LMII | secondary, exact_phrase, printed 105 |

## Services

- Backend: http://127.0.0.1:7008 (active)
- Astro: http://127.0.0.1:3008 (active)
- Login: http://127.0.0.1:3008/login
- Research: http://127.0.0.1:3008/research

## Branch

- `feature/console-backend-core`
- Initial HEAD: `3ddab13`
- Final HEAD: working tree (no commit yet)

## Files Changed

- `SrvRestAstroLS_v1/backend/modules/library/investigative_qa_v1.py`
- `SrvRestAstroLS_v1/backend/modules/library/work_identity.py` (NEW)
- `SrvRestAstroLS_v1/backend/tests/test_work_identity.py` (NEW)
