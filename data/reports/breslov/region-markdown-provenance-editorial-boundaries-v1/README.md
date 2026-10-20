# Region → Markdown provenance + editorial boundaries V1

**`TEBAAI_BRESLOV_REGION_MARKDOWN_PROVENANCE_AND_EDITORIAL_BOUNDARIES_V1_PASS`**

Offline golden gate only. **Worker enforcement remains NOT INTEGRATED.**
`READY_FOR_C_REINGEST = NO`.

## Result

| Golden | Proven result |
|---|---|
|167 / printed149|All five Spanish body units mapped independently of headers, Hebrew and notes; notes60–66 exact boundaries/order/column ownership PASS; Hebrew regions separately addressable; candidate aggregate PARTIAL.|
|55|Corrupt notes heading (native Cc/overlay → layout U+FFFD) excluded exactly; preceding verified good body tail and complete next note33 unchanged; entire remaining original slice sequence identical, not merely equal counts. No repair.|
|56|35 complete across both columns;36 page-local boundary plus actual editorial end on57 before37; exact source ownership, decorated ranges, order and stable offsets PASS.|

65 crosses columns on167. 66's true end is on168 before67; that supporting
continuation is also verified. A PDF page cut is never called an editorial end.
Goldens are small manually reviewed source-derived expectations, not productive
page/note branches. The five visual crop PNGs retain only necessary notes.

## Minimum implementation / reuse

New isolated `backend/modules/library/region_markdown_provenance.py` retains
PyMuPDF4LLM's existing layout IR, reuses the safe historical
`editorial_evidence_v2.detect_footnote_number`, and calls the installed
PyMuPDF4LLM serializer on copied editorial units. Offsets are captured while
appending output. Region→Markdown and Markdown→region queries use identity,
not substring matching. A thin bridge reuses `region_quality.py` unchanged.

No runtime caller or shared extraction/Markdown module was modified.
No SI-960, OCR, font repair, visibility change, search expansion, worker,
embeddings, reingest, publication or corpus write.

Contracts: [pipeline trace](pipeline-trace.md),
[provenance](provenance-contract.md), [transformations](transformation-contract.md).
Raw evidence/ranges: `page167-provenance.json`, `page167-notes-order.json`,
`page55-neighbor-preservation.json`, `page56-note-boundaries.json`.

## Required architectural answers

| Question | Answer |
|---|---|
|Where is provenance first available?|Native PDF extraction blocks/spans with geometry, retained in ParsedDocument/PageLayout/LayoutBox/textlines.|
|Where was it previously lost?|Normal string return from ParsedDocument.to_markdown / _layout_to_markdown.|
|Minimum preserving change?|Retain IR, form source-backed editorial units, serialize and record ranges together.|
|Does Markdown require reverse mapping?|NO.|
|Can quality attach to an exact textual unit?|YES offline, with explicit source parts and original Markdown ranges.|
|Can quarantine avoid deleting good neighbors?|YES, demonstrated with exact original slices and ordered sequence on55, plus separate167 body/notes/Hebrew ownership.|

## Validation

**585 passed, 0 failed** in the prior related suite plus30 new tests;
original555-test baseline retained. Focused:63 passed (new30 + existing quality33).
`git diff --check` PASS; explicit new-file whitespace check PASS.
Three fresh PDF parses: identical full result digests. Note geometry input
permutations: identical IDs/bounds/order/offsets. Repeated report generation:
identical JSON evidence hashes. See `test-results.json`, `tests-focused.txt`,
`tests-related.txt`, `idempotence-results.json`, `genericity-check.json`.

Full backend suite **NOT RUN**: all implementation/tests are new isolated files;
no existing shared extractor, serializer, worker, API, repository, configuration
or runtime import was changed. The complete related555-test suite was rerun,
not substituted with only the new tests. Frontend/LAT unchanged; frontend checks
and `lat check` not applicable.

From `SrvRestAstroLS_v1/backend`:

```sh
uv run pytest -q tests/test_region_markdown_provenance.py tests/test_region_quality.py
uv run python ../../data/reports/breslov/region-markdown-provenance-editorial-boundaries-v1/validate_offline.py
```

The validator verifies exact real PDF SHA, committed small IR fixture equality,
manual golden boundaries, three fresh runs, permutations and quality exclusion.
It accepts an optional source PDF path. It depends on installed backend test
tools (pytest/MarkdownIt); no service preflight or connection is needed.

## Honest limits

- This is a forward adapter for declared text/bottom-note layouts, NOT a
  universal automatic layout detector. Column direction is a source-verified
  layout parameter. Page57 has no footnote labels, so its geometric note-zone
  certificate is explicit fixture data. Unsupported layouts return UNRESOLVED.
- Supporting57/168 evidence covers notes only. The unrelated duplicated body
  line on full57 is rejected, not dropped or repaired to make the gate pass.
- Page55's previous whole body box has a separate marginal-text interleaving
  defect. Its verified good tail and unchanged neighboring slices are proved;
  the entire box is NOT certified flawless by the preservation test.
- An unrelated page56 body dehyphenation is explicitly UNRESOLVED and cannot be
  certified safe through the quality bridge. No silent character fix.
- These boundaries/offsets describe a new offline candidate, NOT existing
  persisted Markdown. Integration must regenerate via the forward path; never
  attach these offsets to old Markdown or assume the current worker is safe.

## Offline counters

`known_bad_text_indexed_candidate = 0`
`known_bad_text_citable_candidate = 0`
`good_text_lost_due_neighbor_failure = 0`
`quarantined_regions_untracked = 0`

Only offline candidates/evidence units; no guarantee about PG/Milvus or current
real citations. `offline-quality-recheck.json` retains region metadata and
explicit unsupported transformations.

## Worktree / operations

Branch `feature/console-backend-core`.
HEAD initial/final `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Initial9 tracked modifications and23 untracked status entries preserved;
see `initial-worktree.txt` and `worktree-results.json` (directory entries may
contain multiple files). No initial file modified by this phase. New files:
new adapter, new tests, two small fixtures and this report directory only.
No commit/push/reset/clean/rebase/stash/branch change.

Production modified = NO; production services touched = NO.
C reingested = NO; PostgreSQL writes = NO; Milvus writes = NO;
publication changes = NO; services managed = NO; new embeddings = NO.

**NEXT_GATE = `TEBAAI_BRESLOV_QUALITY_ENFORCEMENT_WORKER_E2E_V1`**
Not executed here. See [recommendation](recommendation.md).
