# ADR-016 — Canonical Editorial Evidence Selection V1

**Status:** Accepted (DEV)
**Date:** 2026-08-03
**Prerequisite:** ADR-014 (Native Page-First PDF Ingestion), ADR-015 (Exact
Editorial Evidence Ranking V1)

## Context

With Milvus healthy and ADR-015 closed, three editorial problems remained:

1. **Exact headings lose to adjacent body chunks.** The headings
   `CONSTRUYENDO UN MISHKÁN`, `INCLINADO HACIA LA BONDAD` and
   `MELODÍAS Y PLEGARIAS` exist as real structural blocks on PDF pages
   51/53/56 (printed 33/35/38) of `LIKUTEY HALAJOT (Interior Final).pdf`,
   but live retrieval selected the adjacent body chunks on pages 52/55/57
   with `structural_heading_all_tokens_ordered`.
2. **Printed references alternate PRIMARY.** `Salmos 16:1` alternated the
   active primary between LH page 55 and "Cruzando el Puente Angosto"
   page 368, and `printed_page` was `null` for LH 55 (golden 37).
3. **PRIMARY depended on claim generation.** The claim-grounding step could
   change the primary evidence between runs because the canonical primary
   was not fixed before generative synthesis.

The golden contract (pages 51/33, 53/35, 56/38, 55/37, exact match types)
was not flexed: the corpus genuinely contains the heading blocks and the
visible printed folios.

## Cause Root

### Headings — two independent losses

1. **Unreachable heading lines.** The page-first V2 corpus stores full page
   text in `library_document_chunks.content`, but the structural search only
   ILIKEs `section_title` and `search_text_normalized`. The heading line
   (`4 ■ CONSTRUYENDO UN MISHKÁN`) inside `content` was never compared, so
   the golden chunk (page 51) could only reach `structural_heading_partial`
   via scattered body words.
2. **Inherited `section_title` misclassification.** Adjacent body chunks
   inherit the heading as `section_title` (e.g. page 52 carries
   `4 ■ CONSTRUYENDO UN MISHKÁN`), so they classified as
   `structural_heading_all_tokens_ordered` (130) and outranked the golden
   chunk (80). Additionally the general literal lane tagged the golden
   chunk as `exact_phrase` (strength 30), and `_literal_evidence_strength`
   lacked structural heading types, so the merge discarded the stronger
   structural classification (strength 0).

### Printed references — false positive and ordering

3. **Substring false positive.** The general literal lane is ILIKE-based:
   `%salmos 16:1%` matches `(Salmos 16:10)` in the Cruzando chunk, which was
   then tagged `printed_reference_exact` and boosted +15, outranking LH 55.
4. **Arrival-order leakage.** `merge_results` assigned `literal_rank` by
   input list order; the printed-reference lane and structural lane prepend
   items, so combined scores changed with retrieval order.
5. **`printed_page` loss.** `extract_printed_page` returned `null` at
   ingestion for odd folio pages (bare `"  37"` line preceded by binary RTL
   glyph preambles), and the evidence resolver returned `None` at the first
   non-matching line, never reaching the visible folio.
6. **PRIMARY not fixed before IA.** `priority_literal_query` excluded printed
   references (footnote-triggered only), so primary fell to claim ordering,
   which varies run to run.

## Decision

**1. Heading line recovery.** `_structural_heading_lines` recognizes numbered
editorial heading lines with the `■` symbol inside chunk content, and
separates content-derived heading lines from inherited `section_title`
metadata (`heading_from_content`). Content headings outrank metadata-inherited
headings in classification and selection.

**2. Canonical heading primary.** For a nominal heading query,
`structural_heading_exact|normalized|accent_folded` is the PRIMARY; adjacent
body chunks matching `all_tokens_ordered` are context, never the canonical
cite. `_literal_evidence_strength` now ranks all structural heading types
above generic `exact_phrase`, so the merge preserves the structural
classification.

**3. Exact reference surface.** `printed_reference_exact` tagging requires the
chunk to contain the exact reference surface with verse boundary:
`16:1` never matches `16:10`, `16:11` or `116:1` (both the shared regex and
the SQL boundary construction enforce `(?!\d)` guards).

**4. Deterministic ranking.** `merge_results` sorts the literal list by
`(literal_score DESC, chunk_id)` before assigning ranks, and the final sort
key is `(combined_score, semantic_score, document_id, chunk_id)` — a stable
canonical key, never arrival order.

**5. PRIMARY fixed before IA.** `priority_literal_query` now includes
`is_printed_reference`; the backend selects `primary_evidence_id`
deterministically before claim generation, and claim grounding can only
associate claims with allowed evidence IDs — it cannot change the PRIMARY.

**6. Printed page recovery.** A canonical non-null `printed_page` is preserved
through merge/dedupe/enrichment; when the stored label is NULL, the visible
printed folio is recovered from the opening running header of the page
content (bare `"37"` line or `"38 LIKUTEY HALAJOT"` header), skipping binary
RTL glyph preambles.

**7. Explicit work scope.** `Salmos 16:1 en Likutey Halajot` (and question
forms) filter the reference lane to the LH document and add the bare
reference surface as a query variant; LH page 55 is the unambiguous PRIMARY.

## No Decisions

- No hardcoded queries, pages, document IDs or filenames in ranking.
- No per-work or per-document boosts.
- No goldens changed to 52/55/57.
- No page-range tolerance.
- No generative AI in primary selection; no reingestion; no corpus or
  embedding changes; no Milvus/PostgreSQL/LiteLLM changes.

## Consecuencias

- Ranking is explainable: exact editorial lanes dominate, status only
  tiebreaks equivalents, and the final key is stable.
- Primary evidence is stable across runs and identical for admin/guest.
- The heading chunk is the canonical cite; the associated body is context.
- Multiple works with a real occurrence remain visible as secondary evidence.
- The IA is limited to synthesis over allowed evidence IDs.

## Casos de Aceptación

| Query | PDF | Printed | Match type | Source layer | PRIMARY |
|---|---|---|---|---|---|
| CONSTRUYENDO UN MISHKÁN | 51 | 33 | structural_heading_exact | section_heading | sí |
| INCLINADO HACIA LA BONDAD | 53 | 35 | structural_heading_exact | section_heading | sí |
| MELODÍAS Y PLEGARIAS | 56 | 38 | structural_heading_exact | section_heading | sí |
| Salmos 16:1 | 55 | 37 | printed_reference_exact | marginal_reference | sí |
| nota 35 | 56 | 38 | footnote_literal_exact | footnote | sí |

Salmos 16:1: 20/20 ejecuciones con el mismo PRIMARY (`ev-716847bfff6da041`),
20/20 con `printed_page=37`. Cruzando 368 permanece como evidencia secundaria
(`exact_phrase`), sin boost de referencia.

## Files Changed

| File | Change |
|---|---|
| `backend/modules/library/simple_research_rag.py` | heading line recovery + provenance, canonical selection, exact-surface tagging, deterministic merge, primary-before-IA, printed-page recovery, scope handling, `_literal_evidence_strength`, `literal_match_kind` passthrough |
| `backend/modules/library/simple_research_repository.py` | structural/reference candidate ordering + stable tie-break, reference boundary regex |
| `backend/modules/library/page_first_evidence.py` | printed folio recovery from visible header |
| `backend/modules/library/editorial_evidence_v2.py` | `_BIBLICAL_REFERENCE` verse boundary `(?!\d)` |
| `backend/tests/test_canonical_editorial_evidence_selection.py` | new unit coverage (headings, references, determinism, pages, grounding) |
| `astro/src/components/research/investigativeQaClient.ts` | `marginal_reference` source layer |
| `astro/src/components/research/researchLabels.ts` | marginal reference label |
| `astro/e2e/research-guest.spec.ts`, `research-structural-heading.spec.ts`, `research-kokhavey-gedalia.spec.ts` | golden contracts |
| `backend/tests/fixtures/likutey_halajot_page_first_v2_acceptance.json` | `expected_match_type`, `expected_source_layer`, `expected_primary`, `expected_printed_page`, `expected_stable_primary` |

## Validation

- Backend: 1430 passed, 0 failed (baseline 1409 + 21 new).
- Frontend: check 0 errors / 0 warnings, 69 tests passed, build PASS (8 pages).
- E2E Playwright: 75 passed, 25 skipped (documentados), 0 failed.
- API: 5/5 casos canónicos × 5 runs idénticos; Salmos 20/20 idéntico.
- Milvus healthy (5.370 entidades), `semantic_status=ok`, sin degraded.

## See Also

- ADR-014 (Native Page-First PDF Ingestion)
- ADR-015 (Exact Editorial Evidence Ranking V1)
- `docs/breslov/page-first-and-editorial-retrieval-conventions.md`
