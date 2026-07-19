# Hebrew PDF copy/paste literal retrieval

## Reproduction

The exact input `ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta` was received unchanged by the API. It contains 15 ASCII spaces, combining Hebrew marks separated from their base letters, no bidi controls, and a trailing Spanish localization instruction.

Before this correction, the contiguous-Hebrew regular expression extracted only `לָּ`. Retrieval therefore searched a short, non-distinctive fragment and could return unrelated pages (or no evidence under the full UI filter set). The visually reconstructed synthesis was not the query used by retrieval.

## Root cause and correction

The defect was in backend query parsing, before SQL retrieval. Script-based extraction now separates the Hebrew span from surrounding Spanish, English, or Hebrew localization instructions. Combining marks are reassociated with their preceding Hebrew base in logical Unicode order. When PDF spacing destroys real word boundaries, a maximum of 64 candidates is generated and PostgreSQL's canonical derived Hebrew text selects the valid segmentation. Normal indexed phrase retrieval then performs evidence ranking.

No canonical corpus text, page anchor, evidence ID, or index content was modified. No string is reversed, translated, transliterated, or globally stripped of spaces.

## Required source

- Physical PDF: `LIKUTEY MOHARÁN I int (imprenta).pdf`
- Document: `6673da69-eb38-40bf-9f5c-447ff3ba6725`
- Physical page: 96
- Printed page: 76
- Section: `LIKUTEY MOHARÁN #2:7`
- Page anchor: `c211a30b-eef4-4fb4-a558-45e89c314db3`
- Stable evidence: `lmi-dc3eecd6-64b1-4f09-ac9b-d47e4fd70df1`

## Automated result

- Focused backend: 113 passed.
- Copy/paste batch: 20/20.
- Negative batch: 8/8.
- Authenticated HTTP: 6/6.
- SQL literal: 5 pages; FTS phrase: 3 pages; trigram: 6 candidates, maximum similarity 1.0.
- Vector retrieval: not used.
