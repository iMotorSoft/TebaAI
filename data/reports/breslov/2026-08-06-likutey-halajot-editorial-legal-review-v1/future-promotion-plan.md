# Plan de promoción controlada posterior — NO ejecutar

Gate futuro (independiente): `TEBAAI_LIKUTEY_HALAJOT_CONTROLLED_PROMOTION_V1`

## Precondiciones

- [ ] `editorial_review` = `EDITORIAL_APPROVED` o `EDITORIAL_APPROVED_WITH_NON_BLOCKING_NOTES`
- [ ] `legal_review` = `LEGAL_APPROVED_FOR_DEFINED_USE` o `LEGAL_APPROVED_WITH_RESTRICTIONS`
- [ ] Restricciones documentadas y responsables identificados
- [ ] Evidencia de decisión registrada (tipo, fecha, responsable, referencia)
- [ ] Plan de rollback aprobado

## Alcance

- document_id: `132a791a-d12b-45bc-9b34-dd143605de12`
- status inicial: `test_candidate` → status esperado: `ready`
- sin reingesta · sin recalcular embeddings · sin reindexación global
- Milvus: solo re-verificación read-only de la colección (los vectores ya existen)

## Transacción PostgreSQL (borrador conceptual)

1. `UPDATE library_documents SET status='ready' WHERE id=... AND status='test_candidate'` dentro de transacción con verificación de conteo de filas (1).
2. Confirmar que el runner de migraciones no interfiera (`TEBAAI_POSTGRES_AUTO_MIGRATE=false` en producción).
3. Verificar que el scope/ranking incluya el documento como `ready` (ADR-016: la evidencia exacta del test_candidate ya prioriza; el paso a ready amplía recall general).

## Validaciones previas a la transacción

- PG↔Milvus Interior Final 268/268 (missing/orphans/mismatches = 0)
- Retrieval literal/FTS/híbrido PASS sobre los 5 goldens
- `audit_likutey_halajot_promotion_readiness_v2.py` → `TECHNICALLY_READY_FOR_EDITORIAL_REVIEW`
- Playwright Content Manager 11/11 (sin regresión)
- Backend completo 0 failed

## Validaciones posteriores

- Re-ejecutar la batería de retrieval (goldens + scope LH/LM II)
- Re-ejecutar la reconciliación PG↔Milvus del documento
- Auditoría read-only de evidencia (evidence IDs estables, nota 35 ≠ 36 ≠ heading)
- Verificar que `Likutey Halajot LM II 8` (ready) e Interior Final (ready) conviven en family scope LH sin duplicados (son ediciones distintas)

## Rollback (resumen — ver rollback-plan.md)

- `UPDATE library_documents SET status='test_candidate'` (mismo ID, dentro de transacción)
- Metadata, chunks, embeddings y vectores no se tocan → no hay rollback de datos
- Invalidar cachés de búsqueda/UI si aplica

## Auditoría y responsables

- Scripts: `audit_likutey_halajot_promotion_readiness_v2.py` + batería de retrieval
- Responsable de ejecución: a definir en el gate posterior
- Ventana operativa: a definir (recomendado fuera de ventanas de usuario activo)
- Logs: conservar job/transición si se usa el Content Manager; conservar evidencia en `data/reports/`

## NO incluye

- Publicación · deploy · push · cambios a otros documentos · cambios a producción
