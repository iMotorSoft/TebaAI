# Conflicto Likutey Halajot / LM II 8 — diagnóstico V1 — 2026-08-06

Gate: `TEBAAI_LIKUTEY_HALAJOT_LMII8_CONFLICT_RESOLUTION_V1_DEV_READY`

## Resumen

La investigación read-only confirmó que el "conflicto" del registro `ready`
`Likutey Halajot LM II 8` (The Rosenberg Edition) quedó resuelto por el
contrato canónico de ADR-019, persistido en
`library_documents.bibliographic_metadata.canonical_identity_v1`. **No se
requiere reparación de datos** y no se modificó nada (PostgreSQL solo lectura,
Milvus no alcanzable — ambiental).

## Registros implicados

- `56ddcc3b-8296-4832-ac95-2bfe032cd4c6` — Likutey Halajot LM II 8 (Rosenberg), ready, familia lh, source lmii:8 develops, 1205 chunks.
- `132a791a-d12b-45bc-9b34-dd143605de12` — Likutey Halajot Interior Final, test_candidate, familia lh, 284 páginas page-first / 268 chunks.
- `3715c6e0-db56-49a1-82df-62d0a4d0b5cd` — Likutey Moharán II BRI, test_candidate, familia lmii, sin chunks (original sin ingesta).

## Clasificación

| Hipótesis | Resultado |
|---|---|
| A. Alias de metadata sin corrupción | **Resuelto** (contrato presente y correcto) |
| B. Registro duplicado | Falso (0 duplicados) |
| C. Misma cita en dos obras | Falso (0 chunks compartidos) |
| D. Chunk en documento incorrecto | Falso |
| E. Página en documento incorrecto | Falso |
| F. Drift PG↔Milvus | No verificable (Milvus caído) — pendiente readiness V2 |
| G. Superseded activo | Falso |
| H. Identidad inferida incorrecta | Falso (family lh + source lmii:8 explícitos) |
| I. Lección 8 = volumen | Falso (volumen null; v2 = técnico) |
| J. Colisión de codes | Falso |
| K. Colisión de evidence_id | Falso (0 colisiones) |
| L. Ambigüedad editorial | Diseñada: `Likutey`/`LM` → `scope_ambiguous` (ADR-019) |

## Evidencia

- `baseline.json`, `postgres-records.json`, `milvus-records.json`, `metadata-diff.json`
- `identity-analysis.md`, `page-first-analysis.json`
- `evidence-id-analysis.json`, `duplicate-analysis.json`, `scope-resolution.json`
- `conflict-classification.json`, `repair-recommendation.md`

## Tests

- Nuevo: `backend/tests/test_likutey_halajot_lmii8_conflict_v1.py` (7 tests) + fixture
  `backend/tests/fixtures/likutey_halajot_lmii8_conflict_v1.json`. Verificado que
  **falla con el estado anterior** (sin canonical_identity_v1 → ninguna selección)
  y **pasa con el estado actual**.
- Focalizados fase: 115 PASS (28 archivos, filtro sección 34).

## Pendiente para Promotion Readiness V2

- Reconciliación PG↔Milvus del corpus (requiere Milvus operativo — bloqueado
  ambientalmente; el usuario debe levantarlo como en 2026-08-02).
- Validación de retrieval con Milvus up.
- Matriz técnica completa del documento `test_candidate` Interior Final.

## Corroboración Milvus (2026-08-06, segunda pasada con Milvus operativo)

- Milvus healthy: `tebaai_breslov_chunks_v1` = 5370 entidades, Loaded.
- Ownership correcto: 1205 vectores Rosenberg, 268 Interior Final, 0 LM II BRI
  (coinciden con embeddings PG por documento).
- Sin drift a nivel conteo; sin chunks compartidos; sin duplicados; sin
  colisiones de evidence id.
- Batería de retrieval híbrido real (backend + Milvus): `LH LM II 8` → solo
  Rosenberg; `LM II` / `Likutey` / `LM` → 0 hits (sin contaminación, ambiguos
  sin selección arbitraria).
- Evidencia: `milvus-corroboration.json`.
