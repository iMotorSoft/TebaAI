# Revisión editorial + legal + decisión de promoción V1 — Likutey Halajot — 2026-08-06

Gates:
- `TEBAAI_CONTENT_MANAGER_PRIMARY_QUEUED_JOB_RECONCILIATION_V1_DEV_READY` → **SAFE_CANCEL_COMPLETED**
- `TEBAAI_LIKUTEY_HALAJOT_EDITORIAL_REVIEW_PACKAGE_V1_READY` → **READY** (paquete preparado; revisión humana pendiente)
- `TEBAAI_LIKUTEY_HALAJOT_LEGAL_REVIEW_PACKAGE_V1_READY` → **READY** (dossier factual; decisión legal pendiente)
- `TEBAAI_LIKUTEY_HALAJOT_PROMOTION_DECISION_V1_READY` → **READY** (decisión registrada: bloqueada por revisiones pendientes)

## Resultado

```json
{
  "document_id": "132a791a-d12b-45bc-9b34-dd143605de12",
  "technical_result": "TECHNICALLY_READY_FOR_EDITORIAL_REVIEW",
  "editorial_review": { "status": "EDITORIAL_REVIEW_PENDING", "reviewer": null },
  "legal_review": { "status": "LEGAL_REVIEW_REQUIRED", "reviewer": null },
  "promotion_decision": "BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED",
  "promotion_executed": false
}
```

**Estado de la fase: `BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED`** — resultado
válido; faltan las decisiones humanas editorial y legal. No se promovió nada.

## Job queued reconciliado (SAFE_CANCEL_COMPLETED)

- `b482318e-3063-48c6-8728-c513639af836` (breslov_primary, queued, 0 recursos,
  origen fixture E2E del frontend mal configurado) → cancelado
  `queued → cancelled` vía `cancel_job` oficial, con transición de auditoría
  registrada (`editor_cancelled`, actor 965d0a0e). Sin mutación del corpus.

## Hallazgos editoriales para revisión humana

- H1: portada dice "THE ROSENBERG EDITION" vs edición persistida "Interior Final"
- H2: pág. 143 con artefacto de extracción en encabezado (cuerpo intacto)
- H3: portada con bytes de control en el bloque hebreo
- (detalle en `editorial-review-package.md` y `editorial-sampling.json`)

## Archivos

`baseline.json`, `package-contract.json`, `technical-summary.json`,
`editorial-review-package.md`, `editorial-sampling.json`, `legal-facts.json`,
`legal-review-questionnaire.md`, `decision-matrix.json`,
`promotion-decision.json`, `queued-job-reconciliation.json`,
`non-mutation-results.json`, `test-results.json`, `future-promotion-plan.md`,
`rollback-plan.md`.

Script: `SrvRestAstroLS_v1/backend/scripts/build_likutey_halajot_editorial_legal_review_package_v1.py`
(read-only; PG `SET TRANSACTION READ ONLY`).

## Registro de evidencia de decisiones humanas

| Tipo | Fecha | Responsable | Referencia | Ubicación segura |
|---|---|---|---|---|
| (pendiente) | | | | |
