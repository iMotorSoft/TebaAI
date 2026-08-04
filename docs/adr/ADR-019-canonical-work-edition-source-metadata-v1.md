# ADR-019 — Canonical Work–Edition–Source Metadata V1

**Status:** Accepted (DEV)
**Date:** 2026-08-04
**Gate:** `TEBAAI_CANONICAL_WORK_EDITION_SOURCE_METADATA_V1_DEV_READY`

## Context

The promotion-readiness audit confused a Likutey Halajot anthology's containing
work with the Likutey Moharán II lesson it develops. The following scope review
proved that `Likutey Halajot LM II 8` belongs to Likutey Halajot and uses LM II,
lesson 8 as a source. Separately, the bibliographic planner had previously
confused technical suffix `_v2` with volume 2. Family-only queries also lacked a
formal way to distinguish one edition from another.

Free `title`, `filename`, `document_code` and section labels were carrying
several independent dimensions. That overloading made correct evidence appear
like scope contamination and encouraged edition expectations inside family
scope.

## Decision

Introduce an internal, additive canonical identity contract with these separate
dimensions:

- `work_family`: containing bibliographic family;
- `canonical_work`: normalized work identity;
- `edition`: publication/edition label with provenance;
- `volume`: bibliographic volume only when explicitly approved;
- `source_work`: work developed, commented on, quoted or referenced;
- `source_lesson`: unit inside that source work;
- `technical_version`: pipeline or technical representation version;
- `document_instance`: PostgreSQL ID, source filename/hash and lifecycle status.

Confirmed document-level identity is persisted under the existing JSONB field:

```text
library_documents.bibliographic_metadata.canonical_identity_v1
```

No schema migration is required. Runtime dataclasses validate provenance and
provide additive request/response fields. Legacy fallback from filename,
`document_code` or old edition metadata is allowed only as `derived` and emits a
warning; it cannot establish volume or source relations.

Source identities that govern a whole document may be persisted at document
level. Source identities that vary by section or chunk remain section/chunk
metadata; they must not be forced onto the whole document.

## Provenance policy

Every canonical value has one of:

```text
explicit | derived | unresolved | conflicting
```

A non-null value cannot be `unresolved`. A null value cannot be `explicit` or
`derived`. Volume provenance may never be technical version or source lesson.

For Interior Final, PDF page 10 is retained as an explicit physical-source hint
for volume 1 with `pending_approval`; runtime volume remains null/unresolved.

## Canonical identities

### Likutey Halajot LM II 8

```text
work_family       = Likutey Halajot
canonical_work    = Likutey Halajot
edition           = The Rosenberg Edition (explicit, title page)
volume            = null / unresolved
source_work       = Likutey Moharán II
source_lesson     = 8
source_relation   = develops
technical_version = null / unresolved
status            = ready
```

### Interior Final

```text
work_family       = Likutey Halajot
canonical_work    = Likutey Halajot
edition           = Interior Final (derived from source filename label)
volume            = null / unresolved
physical hint     = 1, explicit PDF page 10, pending approval
source identity   = section/chunk level; not forced document-wide
technical_version = v2, derived from page-first pipeline
status            = test_candidate
```

### Original Likutey Moharán II source

```text
work_family       = Likutey Moharán II
canonical_work    = Likutey Moharán II
edition           = Edición española BRI (derived document label)
volume            = null / unresolved
technical_version = layout_v1
status            = test_candidate
```

## Scope levels

Canonical scope is resolved before retrieval and ranking:

- family scope includes all legitimate editions in the family;
- edition scope restricts one edition label;
- document scope restricts one SHA-256/document instance;
- source scope selects documents with an explicit source relation;
- original-work lesson scope selects persisted structural lesson units;
- comparative scope permits both original and commentary families with roles
  kept separate;
- ambiguous `Likutey` or `LM` returns `scope_ambiguous`, never an arbitrary
  family.

Scope labels are removed only from deterministic lexical/heading variants. The
intact original query remains the semantic embedding and audit surface.

## API and UI

The investigative request accepts optional additive fields:

```text
scope_family
scope_edition
scope_document_sha256
scope_source_work
scope_source_lesson
```

Evidence hits add optional canonical identity fields. Existing fields are not
removed or renamed. The source panel displays canonical work, edition and
source work/lesson separately; technical version appears only as secondary
metadata, never as bibliographic volume.

## Invariants

```text
work_family != source_work
source_lesson != volume
technical_version != volume
family scope != edition scope
status != bibliographic identity
LH != LM II
```

## No decisions

- no document was promoted and no status changed;
- no schema migration was created or run;
- no corpus was reingested;
- no embedding was recalculated and no Milvus entity changed;
- no legal permission or bibliographic volume was approved;
- note 36 and PDF ligature normalization remain outside this phase;
- no production rollout is authorized.

## Consequences

- legitimate Likutey Halajot editions coexist in family scope;
- explicit edition and document scopes are reproducible;
- LM II lesson 8 can be represented as original evidence or as a source
  relation without changing the commentary's family;
- the planner remains honest for `_v2`, `II` and lesson numbers;
- Relation and Investigative QA can explain source roles additively;
- a future normalized relational schema may replace the JSONB contract without
  breaking its semantics.

## Rollback

Code and UI changes can be reverted without changing text, chunks or vectors.
The DEV metadata backfill is reversible by removing only
`canonical_identity_v1` from the three guarded source-hash rows, restoring the
captured before values in the phase report. Status must remain unchanged.

## Evidence

`data/reports/breslov/2026-08-04-canonical-work-edition-source-metadata-v1-dev/`
