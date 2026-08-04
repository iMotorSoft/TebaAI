# ADR-018 — Breslov Corpus Scope Integrity Review V1

**Status:** Accepted (blocked DEV review)
**Date:** 2026-08-04
**Gate:** `TEBAAI_BRESLOV_CORPUS_SCOPE_INTEGRITY_V1_DEV_BLOCKED`

## Context

The Likutey Halajot promotion-readiness audit attributed three natural Relation
QA primaries to cross-family contamination. The disputed `ready` row is titled
`Likutey Halajot LM II 8`; an isolated internal reference to Likutey Moharán II,
lesson 8 was interpreted as proof that the whole source belonged to the Likutey
Moharán II family.

The requested repair would have removed that row from Likutey Halajot scope and
classified it as Likutey Moharán II. This review audited the source's persisted
front matter, contents, representative body chunks and runtime resolver before
changing code or data.

## Finding and root cause

The disputed source is **Likutey Halajot**, not Likutey Moharán II:

- its title page says `Likutey Halajot`;
- its subtitle says it contains eleven lessons **based on** Likutey Moharán II,
  lesson 8;
- its contents enumerate `Hiljot Tzitzit`, `Hiljot Kriat HaTorá`, `Hiljot Beit
  HaKneset` and other Likutey Halajot discourses;
- its edition note says the selected Likutey Halajot lessons are especially
  those based on LM II, 8;
- persisted chunks mention Likutey Halajot in 489 chunks and Hiljot headings in
  422 chunks.

The first incorrect layer was therefore the **2026-08-03 audit diagnosis**, not
SQL, Milvus or the title resolver. It conflated these distinct fields:

```text
work_family = Likutey Halajot
source_lesson = Likutey Moharán II, lesson 8
edition/selection = eleven Spanish lessons based on that source lesson
```

The runtime title resolver currently includes the row in `lh` and excludes it
from `lmii`. That behavior agrees with the source. The row's free title is terse,
and the schema lacks a canonical persisted `work_family`, but neither fact
makes the row an LM II work.

## Decision

Do not apply the proposed reclassification, exclusion, status change or ranking
penalty. Removing this source from Likutey Halajot scope would persist false
bibliographic metadata and reduce valid family recall.

The scope-integrity phase is blocked because its mandatory outcome assumes that
a valid Likutey Halajot edition is a different work family. Likewise, a query
scoped only to the work family cannot objectively require `Interior Final` over
another valid Likutey Halajot edition. Edition-level selection needs an explicit
edition/source scope contract and reviewed canonical metadata; it must not be
smuggled into family scope or ranking.

A separate future ADR may introduce canonical fields such as:

```text
work_family
canonical_work_title
edition_or_selection
source_lesson_work
source_lesson_part
source_lesson_number
```

and exact, auditable aliases. That architecture decision must define migration,
legacy fallback and ambiguous-query warnings before changing persisted data.

## Alias rule

`LH` and `LM II` are distinct identities. A source-lesson reference inside a
book does not replace the containing book's family. Shared token `Likutey` is
not sufficient for automatic resolution. Comparative cross-family retrieval
must remain explicit.

## Independent defect

The expanded note-36 query remains open. The canonical page contains the PDF
extraction surface `reﬁ namiento` (compatibility ligature plus inserted space),
while the query contains `refinamiento`. This is a literal-normalization issue,
not evidence of family contamination, and requires a separate focused fix and
25/25 rerun.

## No decisions

- no document status changed;
- no title, document code or bibliographic metadata changed;
- no document was deleted, hidden or demoted;
- no corpus was reingested;
- no embedding was recalculated;
- no Milvus entity was modified;
- `Interior Final` remains `test_candidate`;
- no promotion or production change was authorized.

## Consequences

- ADR-017's technical readiness and `NOT_READY_FOR_PROMOTION` recommendation
  remain valid, but its cross-family diagnosis is superseded by this ADR;
- natural QA results cannot be upgraded to 5/5 by excluding the disputed row;
- a future readiness review must separate family correctness from edition-level
  evidence preference;
- note 36, canonical family metadata, legal permission and editorial metadata
  remain independent blockers.

## Rollback

No runtime or data correction was applied, so operational rollback is not
needed. Reverting this ADR/report/test restores only the earlier, now disproved
diagnosis; it does not alter corpus state.

## Evidence

`data/reports/breslov/2026-08-04-corpus-scope-integrity-v1-dev/`
