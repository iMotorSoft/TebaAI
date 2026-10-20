# Safety analysis — V4

| Metric | Value |
|---|---|
| Unsafe false certifications | 0 |
| Unsafe false provenance certifications | 0 |
| False body certifications | 0 |
| Unsafe false continuations | 0 |
| False editorial completions | 0 |
| Five V1 unsafe zones still unresolved | YES (all UNRESOLVED) |

V4 never promotes a footer, editorial heading or note to a body certificate;
retained non-body certificates and failed bodies are downgraded to
`UNRESOLVED` + `LAYOUT_UNSUPPORTED`, matching V3 policy. Footer lineage such
as V1 `region-6bcfd2e337fb9ad3f7934fe4` stays `UNRESOLVED`.
