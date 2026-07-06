# Koren/Yevamot Cleanup — 2026-07-05

**Propósito:** Remover el corpus técnico de prueba Koren/Yevamot del entorno de trabajo Breslov. No forma parte de Breslov, no debe aparecer como próxima fase, no debe contaminar roadmap, status, scope ni decisiones editoriales de Breslov.

**Rama:** `feature/console-backend-core`

---

## 1. Motivo

Koren/Yevamot fue un corpus de prueba técnica para validar el pipeline PDF moderno Unicode (bilingüe hebreo/inglés). No pertenece a Breslov. Los 8 documentos Breslov ES/EN están cerrados como corpus estable interno (`ready`, `internal_only`, 5102/5102). Koren/Yevamot no debe quedar como próxima fase ni contaminar decisiones editoriales.

---

## 2. Inventario encontrado

| Área | Encontrado | Cantidad | Detalle |
|------|-----------|---------:|---------|
| Docs/status | Sí | 6 archivos | status_actual.md, breslov_es_en_promotion_audit.md, ADR-003, source_quality_policy, promotion_workflow, breslov_productive_cleanup.md |
| PG documents | 3 docs | 3 | Part One (6f876e95), Part Two full (91e5829e), Part 2 superseded (cfd5a9f9) |
| PG chunks | 4723 | 4723 | Part One: 2559, Part Two full: 1988, Part 2 legacy: 176 |
| PG embeddings | 0 | 0 | Sin embeddings (LiteLLM no disponible durante las pruebas) |
| Milvus test | 40 entidades | 40 | 20 Part One + 20 Part Two full |
| Milvus productivo | 0 | 0 | Nunca promovido a productivo |

### Documentos PG

| Documento | ID | Status pre-cleanup | Chunks | Embeddings | Scope |
|-----------|-----|-------------------|-------:|:----------:|-------|
| Koren Talmud Bavli — Yevamot Part One | 6f876e95-04c3 | test_candidate | 2559 | 0 | breslov_primary |
| Koren Talmud Bavli — Yevamot Part Two | 91e5829e-0fb3 | test_candidate | 1988 | 0 | breslov_primary |
| Koren Talmud Bavli Yevamot Part 2 (superseded) | cfd5a9f9-e47d | test_candidate | 176 | 0 | breslov_primary |

### Documentación con referencias Koren/Yevamot

| Archivo | Líneas con Koren/Yevamot | Acción |
|---------|------------------------:|--------|
| `docs/adr/ADR-003-milvus-bm25-multilingual.md` | 7 | Preservado (ADR técnico independiente) |
| `docs/library_document_source_quality_policy.md` | 10 | Preservado (política técnica independiente) |
| `docs/library_promotion_workflow.md` | 8 | Preservado (workflow técnico independiente) |
| `SrvRestAstroLS_v1/docs/status_actual.md` | ~34 | Actualizado: Koren removido de próxima fase |
| `SrvRestAstroLS_v1/docs/breslov_es_en_promotion_audit_2026-07-05.md` | 2 | Actualizado: riesgo residual actualizado |
| `docs/breslov_productive_cleanup_2026-07-05.md` | 2 | Actualizado: riesgo residual actualizado |

### Scripts/tests con referencias

| Archivo | Referencias | Acción |
|---------|------------:|--------|
| `SrvRestAstroLS_v1/backend/scripts/ingest_koren_part_one.py` | 9 | Preservado como script histórico (no afecta roadmap) |
| `SrvRestAstroLS_v1/backend/scripts/ingest_koren_part_two.py` | 10 | Preservado como script histórico |
| `SrvRestAstroLS_v1/backend/scripts/dry_run_promotion_checklist.py` | 5 | Preservado como script histórico |
| `SrvRestAstroLS_v1/backend/scripts/evaluate_hybrid_retrieval.py` | 2 | Preservado como script experimental |
| `SrvRestAstroLS_v1/backend/scripts/evaluate_bm25_retrieval.py` | 1 | Preservado como script experimental |
| `SrvRestAstroLS_v1/backend/scripts/smoke_hebrew_pipeline.py` | 2 | Preservado como script de prueba |
| `SrvRestAstroLS_v1/backend/tests/test_page_markers_extraction.py` | 3 | Preservado como test técnico |
| `scripts/dry_run_promotion_checklist.py` | 5 | Preservado como script histórico |

Los scripts y tests se preservan porque documentan decisiones técnicas pasadas. No forman parte del roadmap activo.

---

## 3. Limpieza ejecutada

| Item | Acción | Resultado |
|------|--------|-----------|
| Milvus test entities | Delete PK por PK (40 entidades) | ✅ 40 eliminadas |
| PG embeddings | DELETE (0 existentes) | ✅ No-op |
| PG chunks | DELETE por document_id (4723 chunks) | ✅ 4723 eliminados |
| PG document status | UPDATE → `archived` | ✅ 3/3 archivados |
| PG knowledge_scope | UPDATE → NULL (removido de breslov_primary) | ✅ 3/3 scope limpiado |
| PG metadata | cleanup_reason, cleanup_date, cleanup_action agregados | ✅ Metadata registrada |
| Próxima fase en docs | Koren removido como próxima fase | ✅ Reemplazado por recomendación UX |

---

## 4. Backups generados

| Archivo | Contenido |
|---------|-----------|
| `docs/koren_yevamot_cleanup_backup_2026-07-05.json` | Metadata completa: 3 docs, chunks sample, Milvus test PKs |

---

## 5. Validación Breslov intacto

| Check | Esperado | Real | Resultado |
|------|---------:|-----:|-----------|
| Docs ready | 8 | 8 | ✅ |
| public_exposure_status = internal_only | 8 | 8 | ✅ |
| PG chunks (8 ready docs) | 5102 | 5102 | ✅ |
| PG embeddings (8 ready docs) | 5102 | 5102 | ✅ |
| Pending PKs | 0 | 0 | ✅ |
| Milvus canónico (search validado) | 5102 | 5102 | ✅ |
| Golden queries sin PG | 0 | 0 | ✅ |
| Koren docs en breslov_primary | 0 | 0 | ✅ |
| Koren chunks/emb en PG | 0 | 0 | ✅ |
| Koren entidades Milvus productivo | 0 | 0 | ✅ |
| Koren entidades Milvus test | 0 | 0 | ✅ |

---

## 6. Guardrails

| Guardrail | Cumplido |
|-----------|:--------:|
| Los 8 docs Breslov no modificados | ✅ |
| Breslov PG chunks no borrados (5102 intactos) | ✅ |
| Breslov embeddings no borrados (5102 intactos) | ✅ |
| Breslov Milvus canónico no afectado | ✅ |
| Solo Koren/Yevamot removido | ✅ |
| Solo Koren/Yevamot identificado por PK/document_id exactos | ✅ |
| Backup exportado antes de delete | ✅ |
| No reingesta | ✅ |
| No embeddings nuevos | ✅ |
| No OpenAI key directa | ✅ |
| Frontend no tocado | ✅ |
| Team360 no tocado | ✅ |
| Servicios no reiniciados | ✅ |
| Koren no queda como próxima fase Breslov | ✅ |

---

## 7. Estado final

### Breslov

| Métrica | Valor |
|---------|-------|
| Docs ready internal_only | 8/8 |
| PG chunks | 5102 |
| PG embeddings | 5102 |
| Pending PKs | 0 |
| Milvus productivo canónico | 5102 |
| Stale entities | 0 |
| Golden queries | 15/15 PASS |

### Koren/Yevamot

| Métrica | Antes | Después |
|---------|-------|--------|
| Docs in breslov_primary | 3 | 0 |
| PG chunks | 4723 | 0 |
| PG embeddings | 0 | 0 |
| Milvus test entities | 40 | 0 |
| Milvus productivo entities | 0 | 0 |
| Status | test_candidate | archived |
| Scope breslov_primary | ✅ | ❌ (NULL) |

---

## 8. Archivos modificados/creados

| Archivo | Cambio |
|---------|--------|
| `SrvRestAstroLS_v1/docs/status_actual.md` | Koren removido de PRÓXIMA; riesgo residual actualizado |
| `SrvRestAstroLS_v1/docs/breslov_es_en_promotion_audit_2026-07-05.md` | Sección 15.6 riesgo residual actualizado |
| `docs/breslov_productive_cleanup_2026-07-05.md` | Riesgo residual Koren reemplazado |
| `docs/koren_yevamot_cleanup_2026-07-05.md` | **Nuevo** — este reporte |
| `docs/koren_yevamot_cleanup_backup_2026-07-05.json` | **Nuevo** — backup pre-cleanup |

---

## 9. Próxima fase recomendada

```text
Breslov Research UX — Source Map, Evidence Badges & Citation Viewer
```

Koren/Yevamot fue un corpus técnico de prueba y fue removido/descartado. No forma parte del roadmap Breslov.
