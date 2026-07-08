# Breslov Milvus Productive Repair Plan

**Date:** 2026-07-08
**Status:** EJECUTADO Y CERRADO

> Este documento conserva el plan previo a la ejecución. La reparación fue autorizada, aplicada y seguida por un cleanup de duplicados. El resultado canónico está en `milvus_productive_baseline_restoration.md`.

## 1. Resumen

Restaurar **1828 entidades** faltantes en `tebaai_breslov_chunks_v1` desde PostgreSQL, para alcanzar el baseline canónico de 5102 entidades con match PG↔Milvus 100%.

## 2. Documentos afectados

| Documento | document_id | PG chunks | PG embeddings | Milvus actual | Faltan |
|---|---|---|---|---|---|
| Likutey Halajot LM II 8 | 56ddcc3b-8296-4832-ac95-2bfe032cd4c6 | 1205 | 1205 | 166 | **1039** |
| La Potencia de la Plegaria | 43ba4f4b-d3ee-49b6-8d09-dfa152379893 | 646 | 646 | 3 | **643** |
| El Jardín de las Almas | 76f2adbc-b79a-4432-9ea5-521a337a5502 | 147 | 147 | 1 | **146** |
| **Total** | | **1998** | **1998** | **170** | **1828** |

## 3. Estado actual de PG embeddings

Todos los 1828 chunks faltantes tienen en PG:
- ✅ status = `indexed`
- ✅ milvus_primary_key (hash, del pipeline anterior)
- ✅ content_sha256
- ✅ embedding_model_alias = `openai_text_embedding_3_small`, dimension = 1536
- ✅ contenido textual disponible
- ❌ vector de embedding NO almacenado en PG (solo en Milvus, ya eliminado)

**Conclusión:** Los vectores no se pueden recuperar de PG. Se requiere re-embedding vía LiteLLM.

## 4. Causa de la pérdida

La FASE D del cleanup del 2026-07-05 eliminó 1828 entidades en Milvus con `source_type=''`. Los 3 documentos fueron ingestados por un pipeline anterior que no poblaba `source_type`, por lo que todas sus entidades en Milvus productivo tenían `source_type=''` y fueron eliminadas junto con las stale.

La FASE C del mismo cleanup re-embebió solo 70 chunks de Likutey con `source_type='book'` (los 166 sobrevivientes actuales incluyen esos 70 + otros con source_type poblado por otras razones).

## 5. Estrategia de reparación

### 5.1 Re-embedding desde PG

Para cada chunk faltante:
1. Leer `ch.content` desde `library_document_chunks`
2. Generar embedding vía LiteLLM (`openai_text_embedding_3_small`)
3. Construir entidad Milvus con `source_type='book'` y `collection_code='breslov'`
4. Usar **nuevo UUID** como PK (para estandarizar con el formato actual)
5. Upsert a `tebaai_breslov_chunks_v1`
6. Actualizar `milvus_primary_key` en PG con el nuevo UUID

### 5.2 Normalización de source_type

Todas las nuevas entidades usarán `source_type='book'`. Las 170 entidades sobrevivientes ya tienen `source_type='book'` (verificadas). Post-repair, el 100% de las entidades productivas tendrá `source_type='book'`.

### 5.3 Volumen estimado

| Documento | Chunks | Chars totales | Embeddings | Costo estimado* |
|---|---|---|---|---|
| Likutey Halajot LM II 8 | 1039 | ~1.5M | 1039 | Mínimo |
| La Potencia de la Plegaria | 643 | ~1.0M | 643 | Mínimo |
| El Jardín de las Almas | 146 | ~0.2M | 146 | Mínimo |
| **Total** | **1828** | **~2.7M** | **1828** | |

*Costo vía LiteLLM → OpenAI: ~1828 × ~0.02¢ ≈ $0.37 USD estimado.

### 5.4 Distribución por lotes

Embeddings en batches de 16 (configuración actual `EMBEDDINGS_BATCH_SIZE = 16`):
- Likutey: 65 batches
- Potencia: 41 batches
- Jardín: 10 batches
- **Total: ~116 batches**

LiteLLM timeout: 60s por batch. Estimado total: ~15-20 minutos.

## 6. Dry-run (previo a reparación)

### 6.1 Verificar exactitud de la lista

```sql
-- Confirmar chunk_ids faltantes comparando PG vs Milvus
SELECT c.id, c.chunk_index, c.document_id
FROM library_document_chunks c
JOIN library_chunk_embeddings e ON e.chunk_id = c.id
WHERE c.document_id IN ('56ddcc3b-...', '43ba4f4b-...', '76f2adbc-...')
AND e.status IS DISTINCT FROM 'stale'
AND e.milvus_primary_key NOT IN (
    -- PKs existentes en Milvus productivo
)
ORDER BY c.document_id, c.chunk_index;
```

### 6.2 Verificar conectividad

```bash
# PG
psql -h 127.0.0.1 -d tebaai -c "SELECT count(*) FROM library_chunk_embeddings WHERE status='indexed'"

# Milvus
python -c "from pymilvus import Collection; c=Collection('tebaai_breslov_chunks_v1'); c.load(); print(c.num_entities)"

# LiteLLM
curl -s http://127.0.0.1:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

### 6.3 Backup

```bash
# Backup PG embeddings table (solo estos 3 docs)
python scripts/backup_embeddings_for_repair.py --doc-ids "56ddcc3b...,43ba4f4b...,76f2adbc..."

# Backup Milvus entidades existentes
python scripts/export_milvus_entities.py --collection tebaai_breslov_chunks_v1 --output docs/backup_milvus_pre_repair_2026-07-08.json
```

## 7. Script de reparación propuesto

```
scripts/repair_milvus_productive_embeddings.py
```

### Flujo:

```
1. Leer chunk_ids faltantes → PG query
2. Para cada documento:
   a. Leer batches de chunks (size=16)
   b. Generar embeddings vía LiteLLM
   c. Construir entidades Milvus con:
      - pk → uuid4 nuevo
      - chunk_id → chunk.id
      - document_id → document.id
      - collection_code → "breslov"
      - source_type → "book"
      - title → document.title
      - language → document.language
      - content_sha256 → e.content_sha256
      - chunk_index → c.chunk_index
      - page_start → c.page_start
      - page_end → c.page_end
      - content_preview → c.content[:1024]
      - embedding → vector generado
   d. Upsert a tebaai_breslov_chunks_v1 (batch size=100)
   e. PG: UPDATE milvus_primary_key con nuevo pk
3. Validar: PG embeddings count = Milvus entities count
```

### Modos:

| Flag | Efecto |
|---|---|
| `--dry-run` | Solo lista chunk_ids, no embebbe ni upserta |
| `--apply` | Ejecuta upsert real |
| `--batch-size` | Tamaño de batch para embeddings (default 16) |
| `--document-id` | Restaurar un documento específico |

## 8. Rollback plan

### Si el upsert falla:

```sql
-- PG: milvus_primary_key se actualiza solo si upsert confirma
-- Si upsert falla, no se toca PG
```

### Si hay corrupción:

```bash
# Restaurar Milvus desde backup
python scripts/restore_milvus_entities.py --input docs/backup_milvus_pre_repair_2026-07-08.json
```

### Rollback siempre disponible:

```sql
-- PG rollback (no aplica porque solo UPDATE milvus_primary_key)
BEGIN;
UPDATE library_chunk_embeddings SET milvus_primary_key = ''
WHERE chunk_id IN (SELECT id FROM library_document_chunks WHERE document_id IN ('56ddcc3b-...', '43ba4f4b-...', '76f2adbc-...'));
COMMIT;
```

## 9. Validación post-repair

### Check 1: Conteos

| Métrica | Esperado | Cómo verificar |
|---|---|---|
| Milvus num_entities | 5102 | `c.num_entities` |
| PG embeddings indexed | 5102 | `SELECT count(*) FROM library_chunk_embeddings WHERE status='indexed'` |
| PG milvus_pk no nulos | 5102 | `SELECT count(*) FROM library_chunk_embeddings WHERE milvus_primary_key IS NOT NULL` |

### Check 2: PG↔Milvus match por documento

| Documento | PG embeddings | Milvus prod | Match |
|---|---|---|---|
| Likutey Halajot LM II 8 | 1205 | 1205 | 100% |
| La Potencia de la Plegaria | 646 | 646 | 100% |
| El Jardín de las Almas | 147 | 147 | 100% |
| Los otros 5 docs | 3104 | 3104 | 100% (sin cambios) |

### Check 3: Stale entities

```python
entities = c.query(expr='source_type == ""', output_fields=['pk'], limit=10000)
assert len(entities) == 0
```

### Check 4: Golden queries

Ejecutar 15 golden queries del corpus Breslov y verificar:
- 0 resultados sin PG text
- Todos los resultados tienen document_id + chunk_id + contenido

### Check 5: Content round-trip

Para una muestra de 20 chunks por documento:
```
Milvus content_preview == PG content[:1024]
```

## 10. Cronograma estimado

| Paso | Duración |
|---|---|
| Dry-run + backup | 5 min |
| Re-embed Likutey (1039) | ~8 min |
| Re-embed Potencia (643) | ~5 min |
| Re-embed Jardín (146) | ~2 min |
| Upsert Milvus (3 batches) | ~1 min |
| PG backfill | ~1 min |
| Validación | ~5 min |
| **Total** | **~25 min** |

## 11. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| LiteLLM timeout | Baja | Retraso | Batch size=16, timeout=60s |
| Rate limit OpenAI | Baja | Retraso | Batches secuenciales |
| Upsert falla parcial | Media | Inconsistencia | PG milvus_pk solo se actualiza tras éxito |
| Compactación durante repair | Baja | num_entities temporal | No afecta, validar post-repair |
| Milvus productivo degradado | Baja | Search afectado | Horario de baja actividad |

## 12. Autorización prevista (histórica)

El plan previo a la ejecución clasificó la reparación de esta forma:

- ✅ ES read-only para PG (SELECT + UPDATE milvus_primary_key)
- ❌ NO es read-only para Milvus (upsert de 1828 entidades)
- ✅ No cambia status documental
- ✅ No reingesta PDFs
- ✅ No recalcula embeddings existentes (solo los que Milvus perdió)
- ❌ Requiere autorización explícita del usuario

La plantilla requerida antes de ejecutar fue:

```text
Autorizo la ejecución del repair plan del 2026-07-08:
- Upsert 1828 entidades a tebaai_breslov_chunks_v1
- Normalización de source_type a 'book'
- Actualización de milvus_primary_key en PG

Firma: ______________________________
Fecha: ______________________________
```
