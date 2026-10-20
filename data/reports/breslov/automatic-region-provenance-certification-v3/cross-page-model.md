# Physical segment ≠ editorial unit

`REGION`: source-backed geometric ownership emitted with Markdown lineage.
`PAGE_SEGMENT`: that region's physical-page contribution, with independent provenance/quality.
`EDITORIAL_UNIT`: deterministic identity and relation between demonstrated note segments.

Minimal states:

- `COMPLETE_LOCAL`: existing fully proven V2 note closes before the next explicit marker.
- `CONTINUES_NEXT_PAGE`: first segment of a demonstrated complete adjacent-page unit.
- `CONTINUED_FROM_PREVIOUS`: linked next-page segment, ending before the next explicit marker.
- `CONTINUATION_UNRESOLVED`: no sufficient editorial linkage/completion proof. Also the default for body, whose page cut does not establish editorial completion.

`continuation_status=CROSS_PAGE_COMPLETE` is emitted only when the actual next-page end is demonstrated. The first segment is never marked `COMPLETE_LOCAL`. Arbitrarily long chains are not supported: missing next explicit end remains unresolved rather than guessed.

Editorial ID: SHA-256 of version, document SHA, origin physical page and source-backed origin region ID, truncated to 24 hex digits with `editorial-` prefix. No random UUID, text similarity or unstable iteration ordering.

Each segment retains page, bbox, source block/line IDs, parts with column, Markdown range, editorial ID and reciprocal link. No concatenated cross-page string, no persisted Markdown offsets reused, no worker integration. When a page's local notes are reserialized, all retained non-note slices keep exact original contents and receive recalculated offsets. Note flow order is column-major, not bbox-y sorting.
