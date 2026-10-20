# V2/V3 -> V4 gap analysis

| Capability | V2 | V3 | V4 |
|---|---|---|---|
| Region discovery / IDs | yes | yes | yes |
| Note proofs | yes | yes | yes |
| Generic body proof | no | restricted | generic centred-caption frame, canonical order |
| Cross-page editorial model | no | yes | yes, resolved document-wide |
| 3-digit note markers | no | no | yes |
| Real page/box/line permutation | fail | fail | PASS |
| Sealed-holdout safety | pass | pass | pass |
| Sealed-holdout utility | partial | fail | pass |

V4 reuses V1 region IDs and native evidence, V2 note proofs, and the V3
separator/caption model, replacing delegated selected-line ordering with a
single canonicalization step.
