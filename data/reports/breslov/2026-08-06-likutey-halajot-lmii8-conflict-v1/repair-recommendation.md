# Reparación recomendada — conflicto Likutey Halajot / LM II 8

## Hallazgos

- La metadata canónica de las tres fuentes DEV está persistida bajo `bibliographic_metadata.canonical_identity_v1` (ADR-019).
- `Likutey Halajot LM II 8` (The Rosenberg Edition, ready) declara `work_family=likutey_halajot` y `source_identities=[likutey_moharan_ii:8 develops]`.
- El resolver de scope trata `LH` y `LM II` como familias distintas y exige una source identity explícita para seleccionar comentarios sobre LM II 8.
- La única edición LH que declara la relación fuente lmii:8 es Rosenberg; `Interior Final` no la declara a nivel documento (fuentes por sección/chunk).
## Clasificación (hipótesis A-L)

- A_alias_metadata: True
- B_logical_duplicate: False
- C_same_quote_two_works: False
- D_chunk_wrong_doc: False
- E_page_wrong_doc: False
- F_pg_vs_milvus_drift: False
- G_superseded_active: False
- H_identity_inferred_wrong: False
- I_lesson_confused_with_volume: False
- J_code_collision: False
- K_evidence_collision: False
- L_editorial_ambiguity: True

## Recomendación

No se requiere reparación de datos: la causa fue el diagnóstico previo (ADR-017) y quedó resuelta por el contrato canónico (ADR-019) sin cambiar corpus. `Likutey Halajot LM II 8` es una antología de Likutey Halajot que desarrolla LM II lección 8; las consultas cortas ambiguas retornan `scope_ambiguous` por diseño. Cerrar el gate con resolución técnica sin escritura.