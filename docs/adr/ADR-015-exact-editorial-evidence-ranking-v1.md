# ADR-015 — Exact Editorial Evidence Ranking V1

**Status:** Accepted (DEV)
**Date:** 2026-07-31
**Prerequisite:** ADR-014 (Native Page-First PDF Ingestion)

## Context

After the page-first reingestion of Likutey Halajot (ADR-014), the document's
chunks were correctly classified with editorial roles (`marginal_reference`,
`structural_heading_exact`, `commentary`). However, the retrieval ranking
preferred semantic hits from `ready` documents over exact editorial matches
from the `test_candidate` document.

**Concrete case:** `Salmos 16:1` returned `Likutey Halajot LM II 8` (ready,
semantic match) as primary evidence instead of `Likutey Halajot — Interior
Final` (test_candidate, exact marginal reference on page 55).

## Cause Root

`build_query_variants("Salmos 16:1")` generated two variants:

```
["Salmos 16:1", "salmos"]
```

The short variant `"salmos"` was produced by `detect_short_english_name_query()`,
which classified "Salmos" as a short English proper name and stripped the
chapter:verse qualifier. This variant triggered ILIKE `%salmos%` on dozens of
chunks from `ready` documents, each receiving `exact_match=True` and a
`literal_score` comparable to the complete exact match on page 55.

The ranking then favored `ready` over `test_candidate` at equal scoring,
pushing the exact marginal reference below the result cap.

**Dual misclassification:** The query was simultaneously treated as:

1. A printed biblical reference (`_BIBLICAL_REFERENCE` regex matched)
2. A short English name (`detect_short_english_name_query` also matched)

The main flow in `run_simple_rag()` correctly suppressed the English-name
detection when `is_printed_reference=True`, but `build_query_variants()` ran
its own detection without that context.

## Decision

Two complementary fixes:

**Fix 1 — Suppress unqualified variant generation**

`build_query_variants` receives `is_printed_reference: bool = False`. When
`True`, the internal call to `detect_short_english_name_query` is skipped.

**Fix 2 — Tag exact literal matches as printed_reference_exact**

After the literal search returns, when `is_printed_reference=True`, items
with `exact_match=True` and no explicit `literal_match_type` are tagged as
`printed_reference_exact`. Without this, they arrive at `merge_results` with
generic `exact_phrase` (priority +0) instead of `printed_reference_exact`
(priority +15), and combined with missing Milvus semantic scores they are
outranked by FTS-only chunks from `ready` documents.

**Files changed:**

| File | Line(s) | Change |
|---|---|---|
| `simple_research_rag.py` | 483 | `is_printed_reference` param added to `build_query_variants` |
| `simple_research_rag.py` | 487 | Guard: skip short-English-name when True |
| `simple_research_rag.py` | 1471 | Caller passes `is_printed_reference=True` |
| `simple_research_rag.py` | 1530–1536 | Tag exact literal matches as `printed_reference_exact` |

**General rule:**

> A query detected as a printed biblical reference must not generate variants
> from the short-English-name expansion lane. Structured queries require
> structured variants.

## Evidence Precedence Tiers

Evidence strength determines primary ranking. Status acts as tiebreaker only
when evidence strength is equivalent.

| Tier | Match Type | Examples |
|---|---|---|
| 1 — Exact editorial | `printed_reference_exact`, `structural_heading_exact`, `footnote_literal_exact`, `body_literal_exact` | `(Salmos 16:1)`, `CONSTRUYENDO UN MISHKÁN` |
| 2 — Normalized exact | `printed_reference_normalized`, `structural_heading_normalized`, `hebrew_exact_normalized` | `salmos 16:1`, `inclinado hacia la bondad` |
| 3 — Short proper name exact | `english_name_exact`, `english_name_variant` | `Gedalia of Linitz` |
| 4 — Literal partial | `hebrew_all_tokens_ordered`, `hebrew_compact` | Partial token match |
| 5 — Semantic strong | Milvus distance ≤ threshold | Vector similarity |
| 6 — Semantic medium / Thematic | FTS without exact ILIKE | Cross-document similarity |
| 7 — AI inferred | LLM claim without direct chunk match | Generated assertions |

Within the same tier, `ready` documents are preferred over `test_candidate`.
Across tiers, evidence strength dominates.

```
Exact scoped test_candidate  >  semantic ready
Ready exact                  >  test_candidate semantic
```

## Status Documental Policy

| Status | Retrieval | Primary eligibility |
|---|---|---|
| `ready` | Yes | Full, preferred at equal evidence |
| `test_candidate` | Yes (DEV only) | Full, tiebroken by ready at equal evidence |
| `superseded` | Yes | No primary unless explicit |
| `archived` | No | Excluded |
| `invalid` | No | Excluded |

`test_candidate` is consultable in DEV. It must not be treated as equivalent to
`invalid`. It must not be promoted to `ready` to force a ranking outcome.

## Exact Editorial Lanes

Before the final hybrid ranking merge, dedicated lanes preserve exact matches:

- **printed_reference_exact** — `_BIBLICAL_REFERENCE` regex matches coupled with literal ILIKE
- **structural_heading_exact** — heading normalization + exact ILIKE
- **footnote_literal_exact** — footnote body text + marker resolution
- **body_phrase_exact** — quoted body text
- **short_proper_name** — proper name in English
- **Hebrew exact** — niqqud-preserving exact match

If any exact lane produces valid candidates, at least one slot is reserved
before semantic candidates fill the result set.

## Anti-Regression Rules

1. `Salmos 16:1` must NOT generate the variant `"salmos"` (unqualified)
2. `16:1` must NOT match `16:10` (boundary rules in regex)
3. A printed reference must NOT be classified as a short English name
4. A semantic `ready` must NOT displace an exact `test_candidate`
5. An exact `ready` CAN win over a semantic `test_candidate`
6. `test_candidate` must never be excluded from primary eligibility solely
   due to status
7. Short queries retain the complete canonical chunk quote; phrases of three
   or more terms locate their literal span, allowing whitespace-normalized
   matches across PDF line wraps.
8. An exact literal in `source_layer=footnote` is classified as
   `footnote_literal_exact`, with the marker anchor and next heading preserved
   as distinct fields.

**Test coverage:** `tests/test_simple_research_rag.py`, `tests/test_ai_model_routing.py`,
focal batch `tests -k "printed_reference or structural_heading or footnote"`

## Validation

| Query | Doc | Page | Primary |
|---|---|---|---|
| `Salmos 16:1` | LH Interior Final (test_candidate) | 55 | PRIMARY (fix verificado) |
| `(Salmos 16:1)` | LH Interior Final (test_candidate) | 55 | PRIMARY (fix verificado) |
| `(Salmos 16:1)` | LH Interior Final (test_candidate) | 55 | PRIMARY |
| `salmos 16:1` | LH Interior Final (test_candidate) | 55 | PRIMARY |
| `CONSTRUYENDO UN MISHKÁN` | LH Interior Final | 51 | PRIMARY |
| `INCLINADO HACIA LA BONDAD` | LH Interior Final | 53 | PRIMARY |
| `MELODÍAS Y PLEGARIAS` | LH Interior Final | 56 | PRIMARY |
| `El hombre se une a HaShem` | LH Interior Final | 56 | PRIMARY |
| `Gedalia of Linitz` | Kokhavey Ohr | — | PRIMARY (regression) |

Backend: 1401 passed. Frontend check/build/test: PASS.

## See Also

- ADR-014 (Native Page-First PDF Ingestion)
- `docs/breslov/page-first-and-editorial-retrieval-conventions.md`
