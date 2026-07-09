# Recommendations — Book QA Hybrid Stability Diagnosis

## 1. Endpoint SQL-only

**Recomendación**: Avanzar con endpoint `POST /library/book-qa` SQL-only.

**Fundamento**: La fase SQL-only demostró 87/100 (PASS usable) sin dependencia de Milvus ni LiteLLM. Es la ruta más estable y predecible para producción.

## 2. Hybrid postergado

**Recomendación**: No implementar hybrid (SQL + Milvus) hasta que la inestabilidad de Milvus bajo carga esté resuelta.

## 3. LiteLLM antes de hybrid full

**Recomendación**: Antes de reintentar hybrid full:
- Monitorear logs de Prisma durante batches de embeddings
- Configurar rate limiting explícito en LiteLLM para embeddings
- Evaluar si `CheckResponsesCost` puede deshabilitarse o configurarse

## 4. Milvus antes de hybrid full

**Recomendación**: Antes de reintentar hybrid full:
- Diagnosticar por qué el container se cae bajo carga (memory? disk IO?)
- Aumentar recursos del container (memory limits)
- Probar con Milvus standalone configurado con más recursos
- Usar `batch_size=1` con delay como estándar para inserts

## 5. Batch size recomendado

Para cualquier operación batch que involucre LiteLLM embeddings + Milvus insert:
- **batch_size = 1**
- **delay entre páginas ≥ 0.5s**
- **timeout por embedding ≥ 60s**

## 6. Cache de embeddings

**Recomendación**: Implementar cache de embeddings en PostgreSQL (tabla `library_embedding_cache_v2`) para no re-embedder páginas ya procesadas si el batch se cae a medio camino.

## 7. Separar embedding generation de Milvus insert

**Recomendación**: Generar embeddings primero (guardar en PostgreSQL o archivo), y solo después insertar en Milvus en un paso separado. Esto permite:
- Reintentar embeddings fallidos sin perder progreso
- Insertar en Milvus cuando el servicio esté estable
- Validar embeddings antes de insertar

## 8. Monitoreo de Prisma

**Recomendación**: Durante batches grandes, monitorear `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/lab/litellm-server/` logs de Prisma.

## 9. Reconciliación productiva

**Recomendación**: No es necesaria. El corpus productivo (5102 chunks, 0 duplicados, 100% PG↔Milvus) está intacto y validado en fases previas.

## 10. Próximo paso

1. Implementar endpoint `/library/book-qa` SQL-only
2. Cache de embeddings offline
3. Hybrid opcional cuando infraestructura esté estable
