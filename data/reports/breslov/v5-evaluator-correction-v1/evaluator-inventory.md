# Exact evaluator inventory

Branch/local/upstream HEAD: feature/console-backend-core /
704ae24597e916b56ddec8a71fd0a30d34793aab. No network fetch performed.

## Original instrument

Path: `data/reports/breslov/v5-hybrid-independent-confirmation-v1/run_gate.py`.
Entrypoint: `source_audit(pages, rows, inventory, canonical, *, part)`.
Original SHA-256: `2215246dc08cab7065076f463b4f9486649dea08ad0c5b87a77df8c7e7d9a6af`
(matches the INVALID gate's resume-frozen manifest).

Original lines 130–158 examined only the first linked_region_id and always
resolved it at pdf_page+1. Every endpoint row counted independently; the reverse
endpoint therefore failed the lookup. Original lines 160–168 defined completion
as COMPLETE_LOCAL OR CROSS_PAGE_COMPLETE and flagged every note on a page with
an outgoing canonical continuation. Both bugs reproduced before any edit.

Metrics: per-row ownership certification/provenance checks, body geometry below
notes separator, per-row false links/completions and identity consistency. The
standalone correction preserves ownership/body/legacy identity checks and
normalizes relations before scoring links. Positive/development runner scoring
and minimum_correct_links=3 are untouched; no coverage/majority thresholds added.

## Corrected instrument

Path: `data/reports/breslov/v5-hybrid-independent-confirmation-v1/evaluator.py`.
Same entrypoint/signature, same metrics/violations/linked_pairs return tuple.
Version: `v5-evaluator-correction-v1`. No imports, filesystem access or candidate
execution. `run_gate.py` imports this function instead of defining the old one.
Its certifier import moved inside main() solely to isolate evaluator imports.
main() was NOT called. Valid relation/missed relation diagnostics are excluded
from Part A's zero-error predicate to avoid changing utility/coverage policy.

See semantics contract for canonical endpoint ownership, reciprocal normalization,
completion distinction and new diagnostic counters. Existing linked_pairs keys
from/to/note/target_region/source_ok remain, with from_region/representations added.

## Tests and legacy inputs

New tests: `SrvRestAstroLS_v1/backend/tests/test_v5_evaluator_semantics.py`.
No preexisting source_audit unit tests were found in backend/tests; all new tests
and existing provenance/quality/preseal tests are run with a V5 import blocker.
Original exact helper AST is archived in `legacy_evaluator.py` (no imports/main).
Stored input `resume-evaluator-audit.json` contains synthetic output only and
reproduces the INVALID gate's original metrics exactly. No real stored holdout
results are opened for regression. No protected corpus sets/contracts are parsed.

## Scope

Only evaluator code, evaluator tests and this evidence directory authored.
Existing unrelated modifications, including extractors.py and V5 candidate/tests,
are preserved. The baseline inventories hashes of preexisting modified/untracked
files solely for preservation; hashing is not opening/parsing/evaluating datasets.
The new synthetic cases use invented IDs/pages; no page-specific code paths exist.
