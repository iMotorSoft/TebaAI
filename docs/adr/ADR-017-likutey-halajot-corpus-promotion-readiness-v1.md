# ADR-017 — Likutey Halajot Corpus Promotion Readiness V1

**Status:** Accepted (DEV audit)
**Date:** 2026-08-03
**Result:** `NOT_READY_FOR_PROMOTION`

> **Erratum (2026-08-04):** ADR-018 supersedes only this audit's
> cross-family diagnosis. Full front matter and contents prove that
> `Likutey Halajot LM II 8` is a Likutey Halajot anthology based on Likutey
> Moharán II, lesson 8—not a Likutey Moharán II work. The readiness result
> remains `NOT_READY_FOR_PROMOTION` because natural edition selection, note 36,
> metadata and legal blockers remain open.

## Context

`LIKUTEY HALAJOT (Interior Final).pdf` is a `test_candidate`. Its native
page-first ingestion, exact editorial ranking and five canonical editorial
controls were already closed in DEV. Promotion had not been authorized and
readiness had not yet reconciled source integrity, all pages/chunks/vectors,
related records, bibliographic truth, status behavior, legal evidence and
rollback as one gate.

Readiness and promotion are separate actions. This audit is read-only with
respect to the corpus and vector index.

## Decision

Audit before any status change and retain `test_candidate`. Do not promote
automatically. A future promotion requires a separate explicit authorization
and a clean rerun of every blocking control.

The V1 recommendation is **`NOT_READY_FOR_PROMOTION`**.

## Evidence and criteria

### Technical integrity

- source identity resolves uniquely by filename and SHA-256;
- local PDF is valid, unencrypted and has 284 physical pages;
- all 16 text-empty pages are visually blank in the source;
- PostgreSQL has 284 unique continuous page rows, 268 textual pages and 268
  unique, nonempty, normalized and page-anchored chunks;
- Milvus reconciles 268/268 with PostgreSQL: missing, orphan, duplicate and
  metadata-mismatch counts are zero; model/dimension are
  `openai_text_embedding_3_small`/1536;
- the five canonical controls remain deterministic (Salmos 20/20; the other
  four 10/10 in this audit).

### Blocking functional findings

1. Natural Investigative QA wrappers do not preserve the canonical selection:
   four of five audited questions selected another ready work instead of
   Interior Final, although the direct canonical heading/note/reference
   surfaces pass.
2. Scoped relation questions are contaminated by an existing `ready` record
   titled `Likutey Halajot LM II 8`; sampled content in that record identifies
   `LIKUTEY MOHARÁN II #8`. It resolves to the same Likutey-Halajot family and
   can become PRIMARY for Mishkán, melody/prayer and favorable-judgment
   questions.
3. An expanded literal note query containing PDF ligatures/normalization can
   lose to semantic evidence from that conflicting record.
4. Exact `Interior Final` scoping is therefore not reliable enough for a
   ready-only corpus.

No binary duplicate of the candidate hash exists. The blocker is conflicting
work identity/scope metadata and its observed ranking impact, not duplicate
bytes.

### Bibliographic truth

The prior `Tomo 2` answer was false: the planner interpreted technical suffix
`document_code=..._v2` as a bibliographic volume. The general parser now accepts
only explicit `volume|volumen|vol|tomo` labels, and unresolved volume now means
`volume_number=null`, never “obra completa (un volumen)”. API validation is
stable 10/10 with `Tomo no resuelto` and no `Tomo 2`.

The PDF itself supplies explicit front-matter evidence:

- PDF 3: Rabí Natán de Breslov; annotated by Moshé Mykoff with Dov Grant;
  Spanish translation by Guillermo Beilinson; published by Breslov Research
  Institute;
- PDF 4: Copyright © 2020, first edition;
- PDF 10: “el primer volumen ... está ahora en sus manos”.

Thus the physical source explicitly describes **volume 1**, but that value and
other critical fields are not persisted. Runtime correctly remains unresolved
until approved metadata is persisted in a separate authorized phase.

### Legal/editorial

Legal classification is `LEGAL_REVIEW_REQUIRED`. PDF 4 states that translation,
reproduction, storage or transmission requires prior written editor consent.
No evidence of that consent was found. Public exposure is not approved by this
ADR.

Editorial status is conditional: headings, critical notes/references and
printed pages work, but persisted chunk roles are coarse page-level metadata,
256/268 chunk printed-page labels are null and rely on deterministic runtime
recovery, and front-matter fields are absent from canonical metadata.

### Status impact

The pure simulation proves:

- `test_candidate` is available only when the DEV read-only inclusion flag is
  active; `ready` would expose it to normal ready-only retrieval;
- status does not change combined scores or deterministic tie-break keys;
- exact editorial evidence still outranks semantic-only evidence;
- promotion removes the candidate warning but cannot fix work-scope ambiguity.

### Operational criteria and rollback

A future phase must capture a logical backup and baseline, resolve the source by
hash, change only `library_documents.status`, rerun all gates and rollback only
`ready → test_candidate` on failure. It must not reingest, recalculate embeddings
or mutate Milvus.

## Consequences

- Gate closes the audit, not the promotion:
  `TEBAAI_LIKUTEY_HALAJOT_CORPUS_PROMOTION_READINESS_V1_DEV_READY`.
- Document status remains `test_candidate`.
- Before reconsideration: resolve the conflicting ready work identity/scope,
  close natural Investigative/Relation QA regressions, persist reviewed
  bibliographic metadata and close legal permission.
- A later audit may change the recommendation; this ADR does not authorize the
  status write.

## No decision

- no document status changed;
- no PostgreSQL corpus row, page, chunk or embedding changed;
- no Milvus vector changed;
- no production deployment or push occurred;
- no legal right or volume number was inferred from filenames or technical
  version labels.

## Evidence

`data/reports/breslov/2026-08-03-likutey-halajot-promotion-readiness-v1-dev/`
