# ADR — Corpus, Vector Layer and Synthesis QA V2

## Estado

Accepted (2026-07-12)

## Contexto

El corpus Breslov V2 (Kitzur Likutey Moharán) fue ingerido mediante Ingesta V2 como páginas
en `library_pages_v2` (512 páginas, run_id 492acd8d). Los derivados vectoriales se backfillearon
originalmente con `collection_code=breslov_test` en lugar de `breslov_primary`, lo que impedía
que `VectorSearchBackend` con filtro `knowledge_scope_code=breslov_primary` encontrara resultados.

Además, la unidad canónica de evidencia no estaba documentada, el formato de citas no estaba
estandarizado, y las relaciones inferidas en Nivel 4 no tenían integración con Relation QA.

## Decisión

1. **Drop and rebuild de derivados vectoriales**: se eliminaron y recrearon `library_vector_embeddings_v2_dev`
   (pgvector) y `tebaai_breslov_chunks_v2_dev` (Milvus) con metadata correcta.
2. **Página como unidad canónica de evidencia**: para el Kitzur V2, la unidad principal es la página
   (`library_pages_v2`), no el chunk. No hay chunking V2 del Kitzur en `library_document_chunks`.
3. **DUAL_BACKEND_AUTO** confirmado: Milvus preferido por latencia, pgvector como fallback operativo,
   SQL/page y FTS para verificación textual final.

## Unidad canónica de evidencia

Para el corpus Kitzur V2:

```text
libro → página → fragmento textual
```

No hay chunking semántico intermedio. La búsqueda se hace a nivel de página.

## Metadata obligatoria en vectores derivados

| Campo | Tipo | Obligatorio |
|---|---|---|
| chunk_id / pk | VARCHAR(64) | Sí |
| document_id | UUID | Sí |
| knowledge_scope_code | VARCHAR(64) | Sí |
| collection_code | VARCHAR(64) | Sí |
| run_id | UUID | Sí |
| language | VARCHAR(8) | Sí |
| page | INTEGER | Sí |
| embedding_model | VARCHAR(128) | Sí |
| embedding_version | VARCHAR(32) | Sí |
| text_hash | VARCHAR(64) | Sí |
| text_preview | VARCHAR(1024) | Sí |
| embedding | vector(1536) | Sí |

## Vector backend

- **Primario**: Milvus 2.6 (HNSW/COSINE, colección `tebaai_breslov_chunks_v2_dev`)
- **Fallback**: pgvector 0.8.2 (HNSW/COSINE, tabla `library_vector_embeddings_v2_dev`)
- **Auto**: Milvus ready → Milvus; Milvus error → pgvector; ambos error → SQL + FTS
- **Disabled**: sin vector search, solo SQL/page textual

## run_id policy

Todo vector derivado debe tener `run_id` poblado desde `library_ingestion_runs_v2`.
Si no existe, no se backfillea.

## Citation policy

Formato canónico para citas en síntesis:

```text
[claim_id p. N]
```

Ejemplo:

```text
La humildad anula el orgullo [B1 p. 22].
El Tzadik enseña la verdad [G3 p. 53].
```

La IA synthesis no puede inventar citas. Solo puede usar citas presentes en la matriz
de evidencia. El fallback determinístico usa el mismo formato.

## Relation QA policy

Relation QA no está integrado en el pipeline Level 4 actual. Las relaciones se clasifican como:

- **literal**: mismo claim o co-ocurrencia exacta en página
- **same_page**: claims aparecen en misma página
- **thematic**: conexión conceptual, no literal
- **INFERRED**: relación inferida desde evidencia separada de cada claim

Para relaciones INFERRED, se recomienda integrar Relation QA en fase posterior.

## Rebuild policy

Para reconstruir derivados vectoriales V2 dev:

```bash
python scripts/vector_store_v2_backfill.py \
  --run-id <UUID> \
  --scope breslov_primary \
  --collection-code breslov_primary \
  --backend both \
  --drop-derived \
  --force \
  --json-out <path>
```

El script es idempotente: `ON CONFLICT DO UPDATE` en pgvector, `upsert` en Milvus.

## Rollback

Si se necesita revertir:

1. pgvector: `DROP TABLE library_vector_embeddings_v2_dev CASCADE`
2. Milvus: `utility.drop_collection("tebaai_breslov_chunks_v2_dev")`
3. Re-ejecutar backfill con `--force` pero sin `--drop-derived` (recrea desde cero)

## Validaciones

1. `count(pgvector) == count(Milvus) == pages_with_text`
2. `metadata correcta`: scope, collection_code, run_id, document_id, language
3. `búsqueda real`: query embedding devuelve hits con score > 0
4. `filtros V2`: scope filter funciona en ambos backends
5. `synthesis Nivel 4`: 29/29 claims PASS, relations matrix generada
