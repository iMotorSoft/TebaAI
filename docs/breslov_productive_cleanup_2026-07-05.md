# Breslov Productive Cleanup — 2026-07-05

**Propósito:** Reporte standalone del cleanup canónico de Milvus productivo `tebaai_breslov_chunks_v1` tras la promoción de 8 documentos ES/EN Breslov a `ready`.

**Rama:** `feature/console-backend-core`

---

## 1. Resumen ejecutivo

Se eliminaron **1991 entidades extra** del índice vectorial productivo que no tenían chunk correspondiente en PostgreSQL. El corpus canónico de 5102 vectores ahora **coincide 100% con PG** y las golden queries retornan **0 resultados sin texto PostgreSQL**.

| Métrica | Pre-cleanup | Post-cleanup |
|---------|:-----------:|:------------:|
| Entidades canónicas | 5102 | 5102 |
| Entidades extra (stale) | 1991 | **0** |
| PG pending PKs | 0 | 0 |
| Golden queries sin PG | 11/75 | **0/75** (15/15 PASS) |
| Docs ready (internal_only) | 8/8 | 8/8 (sin cambios) |

---

## 2. Fases ejecutadas

### Fase 1: Diagnóstico post-promoción

| Actividad | Detalle |
|-----------|---------|
| Análisis | Per-doc comparison PG vs Milvus productive |
| Hallazgo 1 | Likutey: PG=1205, Prod=1297 (+92 old-pipeline entities) |
| Hallazgo 2 | 162 Likutey + 1 CLI test doc = 163 stale (`source_type` no vacío) |
| Hallazgo 3 | 1828 entities with `source_type=''` (Likutey 1039, La Potencia 643, El Jardín 146) |
| Causa | Pipeline original e índices previos insertaron entidades sin tracking en PG |

### Fase 2: Delete 163 stale entities (old pipeline)

| Aspecto | Valor |
|---------|-------|
| Método | PK por PK, batches de 50, `pk in [...]` |
| Likutey old-pipeline | 162 PKs |
| CLI test doc | 1 PK |
| Total | 163 |
| Backup | `docs/milvus_productive_stale_entities_2026-07-05.json` (7.4 KB) |
| Validación | Search Strong — 0 stale en resultados |

### Fase 3: Re-embed 70 orphaned Likutey chunks

Tras la Fase 2, quitar 163 entidades expuso 70 PG chunks sin vector:

| Aspecto | Valor |
|---------|-------|
| Chunks huérfanos | 70 (índices 1041–1204) |
| Embeddings | LiteLLM `openai_text_embedding_3_small`, dim=1536 |
| Batches | 5 (16×4 + 6 last) |
| Éxito | 70/70 (0 fallos) |
| Milvus | Upsert directo a `tebaai_breslov_chunks_v1` |
| PG actualizado | `milvus_primary_key` en `library_chunk_embeddings` |

### Fase 4: Delete 1828 stale entities (empty source_type)

| Aspecto | Valor |
|---------|-------|
| Origen | Pipeline más antiguo, previo al sistema de tracking actual |
| Documentos | Likutey (1039), La Potencia (643), El Jardín (146) |
| `source_type` | '' (vacío) |
| `collection_code` | 'breslov' |
| Método | PK por PK, batches de 100 |
| Total | 1828 |
| Backup | `docs/milvus_stale_empty_source_type_backup_2026-07-05.json` (360 KB) |
| Validación | Search Strong — 0 resultados con `source_type=''` |

### Fase 5: Golden queries finales

15 queries ejecutadas con `consistency_level=Strong`:

| # | Query | Result |
|---|-------|--------|
| 1 | ¿Qué es un Tzadik según Breslov? | ✅ |
| 2 | ¿Cómo vencer la tristeza? | ✅ |
| 3 | ¿Qué significa no tener miedo? | ✅ |
| 4 | ¿En qué libros se toca el miedo? | ✅ |
| 5 | ¿En qué libros se toca la tristeza? | ✅ |
| 6 | ¿Dónde aparece hitbodedut / plegaria personal? | ✅ |
| 7 | ¿Qué dice La Potencia de la Plegaria sobre rezar? | ✅ |
| 8 | ¿Qué aparece en KITZUR sobre alegría? | ✅ |
| 9 | ¿Dónde aparece el puente angosto? | ✅ |
| 10 | maravilla cerebro fe | ✅ |
| 11 | alegría servicio Dios | ✅ |
| 12 | tzadik conexión | ✅ |
| 13 | joy spiritual prayer | ✅ |
| 14 | light of tzadik | ✅ |
| 15 | zzzzz (negativa) | ✅ |

**15/15 PASS — 0 resultados sin texto PostgreSQL.**

---

## 3. Métricas finales

| Métrica | Valor |
|---------|-------|
| Docs promoted | 8/8 (ready, internal_only) |
| PG chunks | 5102 |
| PG embeddings | 5102 |
| PG milvus_primary_key pending | 0 |
| Milvus canonical entities (confirmed) | 5102 |
| Milvus stale entities removed | 1991 (163 + 1828) |
| Chunks re-embedded (orphaned) | 70 |
| Chunks re-embedded (Phase 6 repair) | 96 |
| Pending PKs resolved (Phase 4) | 71 |
| Golden queries pass rate | 15/15 (100%) |
| Results without PG text | 0 |

---

## 4. Archivos de backup

| Archivo | Contenido | Tamaño |
|---------|-----------|--------|
| `docs/backup_pre_promotion_2026-07-05.json` | Snapshot PG pre-promoción (8 docs, 5102 chunks) | ~5 MB |
| `docs/rollback_promotion_2026-07-05.sql` | SQL para revertir PG a estado pre-promoción | ~2 KB |
| `docs/milvus_productive_stale_entities_2026-07-05.json` | 163 PKs eliminados (old pipeline) | ~7 KB |
| `docs/milvus_stale_empty_source_type_backup_2026-07-05.json` | 1828 PKs eliminados (empty source_type) | ~360 KB |

---

## 5. Validaciones

| Validación | Resultado |
|------------|-----------|
| Per-doc PG ↔ Milvus match | ✅ 8/8 docs coinciden exactamente |
| Total canonical count | ✅ 5102/5102 |
| Pending PKs in PG | ✅ 0 |
| Stale entities in search results | ✅ 0 |
| Golden queries — results without PG text | ✅ 0/75 |
| CLI test doc in productive | ✅ 0 |
| `git diff --check` | ✅ 0 errors |
| Milvus test collection intact | ✅ 7315 entities (untouched) |

---

## 6. Guardrails

| Guardrail | Cumplido |
|-----------|:--------:|
| PG tracking limpio (0 pending) | ✅ |
| Solo base tebaai | ✅ |
| `knowledge_scope_id` routing (no `collection_id`) | ✅ |
| `library_collections_legacy` no usado | ✅ |
| No reingesta de PDFs | ✅ |
| No re-chunking | ✅ |
| No más embeddings recalculados (tras repair + cleanup) | ✅ |
| Backup exportado antes de cada delete | ✅ |
| No delete de registros PG | ✅ |
| No truncado de Milvus | ✅ |
| No tocar frontend | ✅ |
| No tocar Team360 | ✅ |
| No reiniciar servicios | ✅ |
| No compactar Milvus (comportamiento interno programado) | ✅ |
| No OpenAI key directa (solo LiteLLM) | ✅ |
| Texto canónico siempre desde PostgreSQL | ✅ |

---

## 7. Riesgos residuales

1. **Milvus `num_entities` = 6930** (vs. 5102 canónicas). `num_entities` no decrece con delete hasta compactación interna automática del segmento. La búsqueda ANN con `consistency_level=Strong` filtra correctamente las entidades borradas (validado con golden queries).

2. **1828 entidades eliminadas** referencian 3 documentos Breslov que sí existen en PG (Likutey Halajot, La Potencia de la Plegaria, El Jardín de las Almas). No contaminan resultados — sus `chunk_id` no existen en PG y el ANN search no las retorna.

3. **Koren/Yevamot** fue removido de `breslov_primary` y archivado como corpus de prueba técnica. Ver `docs/koren_yevamot_cleanup_2026-07-05.md`.

4. **Colección Milvus test** `tebaai_breslov_test_chunks_v1` intacta con 7315 entidades. Acumula vectores de múltiples fases experimentales. No se modificó durante el cleanup.

---

## 8. Documentos de referencia

- `docs/status_actual.md` — estado técnico vigente (sección «Breslov ES/EN Productive Promotion & Canonical Cleanup»)
- `docs/breslov_es_en_promotion_audit_2026-07-05.md` — auditoría completa con sección 15 (cleanup)
- `docs/backup_pre_promotion_2026-07-05.json` — snapshot PG pre-promoción
- `docs/rollback_promotion_2026-07-05.sql` — rollback SQL
- `docs/milvus_productive_stale_entities_2026-07-05.json` — 163 PKs eliminados
- `docs/milvus_stale_empty_source_type_backup_2026-07-05.json` — 1828 PKs eliminados
