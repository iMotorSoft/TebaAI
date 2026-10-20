# Safety floor preserved on evaluated evidence

New sealed holdout: 30 pages, 366 emitted regions, 360 independently source-annotated units. Correct provenance certifications: 27; correct ACCEPTED: 17. Both unsafe CERTIFIED+ACCEPTED and incorrect CERTIFIED provenance (regardless of quality) are **0**. False body certifications: **0**.

Five exact V1 false certifications remain UNRESOLVED in V3. Live V2 former-holdout regression: 18 pages, 20 V3 certifications, zero mismatches against its frozen expected source-unit/zone annotations. See `v1-v2-regression-results.json`.

Headers, footers, source-language text, interleaved sidebars and unknown layouts are not rescued by clean-looking strings. Provenance UNRESOLVED always forces quality UNRESOLVED. Source PDF errors are not newly attributed. No visual-source defect is invented to explain parser differences.

The body proof separates horizontal native provenance from exact textual quality. Nine holdout body units have certified ownership/zone but insufficient acceptance proof; they remain quality UNRESOLVED. This does not mean their text was repaired or approved.

Limits: source/IR and low-resolution source-contact review by the implementing agent, not independent human adjudication or exhaustive glyph fidelity QA. Zero observed unsafe cases is not a universal safety guarantee. The runtime candidate remains offline and the gate FAIL forbids worker integration.

A separate native-backed permutation regression was found: V2's selected-line iteration order is not canonicalized at the V3 delegation boundary. It can withhold notes and links and change continuation discovery IDs. This was not repaired after holdout opening. Same-input three-run determinism passes, permutation does not. See `permutation-analysis.json`.
