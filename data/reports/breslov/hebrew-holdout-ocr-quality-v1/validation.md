# Validación y revisión

- Branch: `feature/console-backend-core`.
- HEAD inicial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
- `git diff --check`: PASS (worktree tracked completo).
- Archivos nuevos del reporte: validación adicional de trailing whitespace y JSON parse PASS.
- Tests focalizados: **124 passed, 0 failed**, salida íntegra `tests.txt`.
- Replay search sellado: PASS técnico; gate de calidad **FAIL_RECALL**.
- Replay OCR real: 16 regiones, 32 muestras fijas, 64 llamadas locales texto/TSV; gate **BLOCKED**.
- Semantic preflight/model/fallback: `PASS_LOCAL_FIXTURE_EMBEDDINGS`; no equivalencia léxica ni evaluación de vectores persistidos.
- Hash de reglas y módulos fuente: verificado por runner, sin cambios tras freeze.
- Hash de holdout: verificado; no reanotación tras resultados.
- Hash de política OCR: verificado; sin tuning tras replay.
- Revisión de código: no imports de repositories/PG/Milvus/worker, no escrituras fuera del directorio del reporte; gateway usa fachada existente, no credenciales nuevas ni secret outputs.
- Revisión visual: seis rasters del documento nuevo y tres crops OCR adicionales inspeccionados. Folios 149/37 completos en el crop; fallos no atribuibles a recorte de dígitos. Goldens OCR restantes reutilizados del audit previo.
- Revisión de resultados: no golden/expected/metrics en señales de `decide`; synthetic unit accepts no se cuentan como OCR real aceptado; controles sin transcript tienen métricas null.
- Ranking: sólo contrato del clasificador offline con original exact; no se certifica ranking end-to-end.
- No LAT/@lat/frontend/runtime editados: lat check, pnpm, E2E y suite completa no aplican a este reporte aislado.

## Comando de tests

```bash
cd SrvRestAstroLS_v1/backend
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_hebrew_lexical_normalizer.py ../../data/reports/breslov/hebrew-holdout-ocr-quality-v1/test_validation.py -q
```

## Archivos / impacto

Sólo se añadió `data/reports/breslov/hebrew-holdout-ocr-quality-v1/`: informes Markdown,
JSON de reglas/fixtures/resultados, hashes, scripts y tests aislados, log de tests y
crops regionales originales. No se editó status_actual.md ni cambios previos del worktree.
No se copiaron PDFs íntegros, vectores ni secretos al reporte.

Commit/push/reset/reingest/PG writes/Milvus writes/production: **NO**.
Conexiones PostgreSQL/Milvus: **NO**. Servicios permanentes intactos.
READY_FOR_C_REINGEST: **NO**.

Riesgos/próximo paso: ver recommendation.md. No hay autorización de integración.
