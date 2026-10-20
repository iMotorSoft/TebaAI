# Page aggregation

All supplied regions accepted => FULL. Some accepted and some rejected => PARTIAL.
No accepted regions, including an empty supplied inventory => UNUSABLE.
Blank physical pages must stay as blank pages in the existing model; UNUSABLE
here means no textual evidence, not proof of corruption.

`QualityPage.metadata()` always lists every supplied region and derived state.
Canonical Markdown contains accepted text only; partiality is out-of-band
metadata, not a warning placeholder that could become embedding/citation text.
A production page response must return both text AND quality metadata.

Chunk `evidence_units` independently. Never chunk the concatenated partial page
across a rejected gap: adjacency/overlap could fabricate a contiguous quotation.
The current gateway chunks entire page Markdown and has no quality-unit path;
this requirement is not integrated.

Inventory completeness and reading order require a source-backed adapter.
The aggregate is not a completeness certificate. Real167 Spanish body is a safe
offline unit, Hebrew rejected; current Spanish notes have an independent order
error. Page55 result classifies only a sample, not its whole page.
