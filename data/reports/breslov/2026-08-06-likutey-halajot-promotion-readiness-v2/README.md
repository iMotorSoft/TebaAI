# Likutey Halajot — Promotion Readiness V2 — 2026-08-06

Gate: `TEBAAI_LIKUTEY_HALAJOT_PROMOTION_READINESS_V2_DEV_READY` (auditoría)
Estado global: `TEBAAI_LIKUTEY_HALAJOT_TECHNICAL_READINESS_V2_DEV_BLOCKED`
(pendiente verificación Milvus + legal)

## Resultado

```json
{
  "technical_result": "NOT_READY_TECHNICAL_BLOCKERS",
  "technical_blockers": ["PostgreSQL↔Milvus", "Retrieval híbrido"],
  "editorial_review": "PENDIENTE",
  "legal_review": "LEGAL_REVIEW_REQUIRED",
  "promotion_executed": false
}
```

Los dos controles bloqueados son **ambientales** (Milvus caído desde las
13:26 del 2026-08-06, contenedor `milvus26-standalone` Exited(1), etcd
timeouts; sin restart policy). Ninguno es un defecto del corpus: el cierre
2026-07-31 ya verificó PG↔Milvus 268/268 con Milvus operativo, pero el
contrato de la fase exige conteos reales y no históricos.

## Matriz técnica (resumen)

| Control | Resultado |
|---|---|
| Identidad documental | PASS |
| Metadata canónica | PASS (ADR-019) |
| Page-first | PASS (284 páginas v2) |
| Páginas físicas | PASS (284; 268+16 blancas justificadas) |
| Referencias impresas | PASS (Salmos 16:1, ADR-016) |
| Headings | PASS (51/53/56 structural_heading_exact) |
| Notas al pie | PASS (nota 35; ligaduras ADR-020) |
| Chunks | PASS (268, integridad 0 fallos) |
| Evidence IDs | PASS (268 IDs, 0 colisiones, ADR-021) |
| PostgreSQL↔Milvus | BLOCKED (Milvus caído) |
| Duplicados | PASS (0) |
| Retrieval literal | PASS (goldens deterministas + tests) |
| Retrieval híbrido | BLOCKED (Milvus caído) |
| Español | PASS |
| Inglés / Hebreo | NA |
| QA cruzado | PASS (LH ≠ LM II; conflicto resuelto) |
| Warnings técnicos | ACEPTABLE |
| Revisión editorial | PENDIENTE |
| Legal/copyright | PENDIENTE (LEGAL_REVIEW_REQUIRED) |

## Conflicto LM II 8

Resuelto por el contrato canónico (ADR-019): `Likutey Halajot LM II 8`
(Rosenberg, ready) es familia LH con source `lmii:8 develops`; el resolver lo
excluye del scope lmii y lo selecciona solo para consultas LH con relación
fuente. No contaminación, no duplicados, no colisiones de evidence id.

## Evidencia

`baseline.json`, `technical-matrix.json`, `metadata-results.json`,
`page-first-results.json`, `evidence-results.json`, `pg-milvus-results.json`,
`retrieval-results.json`, `multilingual-results.json`,
`editorial-blockers.json`, `legal-blockers.json`, `recommendation.json`,
`duplicate-version-matrix.json`, `rollback-plan.md`.

Script: `SrvRestAstroLS_v1/backend/scripts/audit_likutey_halajot_promotion_readiness_v2.py`
(read-only; PG `SET TRANSACTION READ ONLY`; Milvus sin load/write).

## Para cerrar READY

1. Usuario: levantar Milvus (precedente 2026-08-02) — el agente no debe
   iniciarlo.
2. Re-ejecutar el audit V2 → PG↔Milvus y retrieval híbrido PASS.
3. Revisión editorial humana (metadatos, naturalidad, notas).
4. Legal: permiso de exposición (LEGAL_REVIEW_REQUIRED).
