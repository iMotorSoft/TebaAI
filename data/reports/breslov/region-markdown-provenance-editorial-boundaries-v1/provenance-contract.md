# Minimal forward ownership contract V1

Implementation: `backend/modules/library/region_markdown_provenance.py`.
Offline only; canonical runtime remains PyMuPDF4LLM Markdown, unchanged.

## Identity and representations

- `ProvenancePage`: source SHA256, physical one-based PDF page, emitted
  `markdown`, diagnostic `canonical_text`, ordered ownership units.
- `Ownership`: deterministic `region_id`, physical page, `source_bbox`,
  ordered `parts`, role, optional note identity, end reason, half-open
  Markdown and canonical-text ranges, method/status, transformation metadata,
  optional `continuation_of` region ID on the preceding physical page.
- `SourcePart`: exact layout-line bbox, native `(block,line)` reference(s),
  stable `source_sequence`, original extracted text and optional column.
  Native block IDs are the first elements of `source_line_ids`; they are not
  invented replacements. The line fragment identity ALSO includes its bbox
  because the real extractor can split a native line geometrically.

`source_bbox` is a bounding **envelope**, NOT a claim to own every other object
inside that rectangle. The exact physical region is the ordered union of
`parts`. Cross-column65's envelope overlaps unrelated regions; its part list
never includes those neighboring source lines. All consumers must retain
parts, never reconstruct membership from the envelope alone.

Region ID = version + document SHA + physical page + ordered native line
references/geometric fragments + envelope, hashed deterministically. No random
IDs, filename, known page or known note constants. Note identity is recognized
from source text within a declared editorial zone, not used to decide columns.

## Offsets (never interchangeable)

All offsets count **Python Unicode code points**, not bytes or JS UTF-16.
All are page-local and half-open `[start,end)` in an immutable candidate.

- `SourcePart.source_text`: local source offsets are `[0,len(source_text))`.
  No PDF byte offset or source glyph-to-codepoint bijection is claimed.
- `canonical_*`: offsets in **diagnostic semantic projection**, source spans
  concatenated per source line, lines joined by `\n`, units by `\n\n`.
  This projection is NOT a replacement plain-text ingestion engine and is not
  persisted as the library canonical format.
- `markdown_*`: offsets in the exact decorated Markdown emitted by the
  installed PyMuPDF4LLM unit serializer. Wrappers and trailing separators are
  owned by the unit that emits them.

`spans_for_region(id)` answers region→Markdown.
`owners(start,end)` answers Markdown→source editorial region(s).
An arbitrary subfragment returns its containing editorial unit(s), NOT a
false per-glyph claim. One unit can own several physical blocks/columns.
A native source block can be split into several editorial units (60/61/etc).
Cross-page continuation is an explicit relation between separately ranged
page-local units; offsets are never extended into a different page string.

## Editorial boundaries

Default adapter supports a bottom note zone anchored by extractor `footnote`
boxes. An explicit **certified geometric zone** is also supported when labels
are absent (real57). Direction is an explicit layout parameter, validated
against visible source in these goldens. Columns derive from disjoint line
x-projections; within-column order is vertical geometry. Native sequence
remains authoritative outside the note zone and is not arbitrarily permuted.

The historical pure numbered-start recognizer is reused. No SI-960 code or SQL
script import. A terminal boundary is `NEXT_NOTE_IN_COLUMN_FLOW` or
`PAGE_BOUNDARY`; the latter does NOT prove editorial termination. Continuing
that note requires an explicit same-source/adjacent-page link and note-zone
certificate where labels are unavailable. Leading unowned continuation fails
UNRESOLVED. Unknown numeric-start syntax also fails, never gets swallowed by
the previous note. Exact terminal36 and66 are tested on57 and168 respectively.

## Exclusion / quality

`exclude(ids)` returns unchanged original Markdown slices, preserving sequence
and region IDs. Unknown quarantine IDs are rejected. It does NOT rebase the
original offsets, bridge quarantined gaps or publish anything. Consumers must
use separate evidence units, not quote across an exclusion gap.

`classify_owned_unit` is a thin adapter to existing `region_quality.py`;
it accepts only tracked ownership, requires external verification certificates
and refuses unsupported transformations. The quality/quarantine contract is
not reimplemented. A clean string is still not a quality certificate.

Unresolved input raises `UnresolvedLayout` with reason; callers must record
UNRESOLVED rather than silently fall back to substring matching. No worker
exception handling or enforcement was added in this phase.
