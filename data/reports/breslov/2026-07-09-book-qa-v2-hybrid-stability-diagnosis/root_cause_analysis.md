# Root Cause Analysis — Book QA Hybrid Stability

## Hipótesis A — Milvus primario

**Evidencia a favor**:
- Milvus container cayó repetidamente durante inserts batch (híbrido 100 páginas requirió batch_size=1 con delay)
- Load de collection productiva `tebaai_breslov_chunks_v1` excede timeout de 5s (colección grande)
- Errores de conexión `StatusCode.UNAVAILABLE` durante inserts

**Evidencia en contra**:
- Milvus responde health checks (9091/healthz = 200)
- Dummy inserts sin embeddings funcionan correctamente (confirmado en probes previos)
- `utility.list_collections()` funciona rápido
- Las otras collections (test, dummy) cargan sin problema

**Veredicto**: Milvus es estable para reads y small writes, pero inestable bajo carga continua de inserts con embeddings. El container se cae cuando se satura.

## Hipótesis B — LiteLLM/Prisma primario

**Evidencia a favor**:
- Logs de LiteLLM mostraron `Prisma DB reconnect`, `db_health_watchdog_connection_error`, `prisma-query-engine PID exited`
- Estos errores aparecen durante operaciones batch de embeddings

**Evidencia en contra**:
- LiteLLM responde HTTP 200 en puerto 4000
- Embeddings individuales funcionan correctamente (probado en el probe de la fase hybrid)
- El proxy LiteLLM sirve requests sin problema

**Veredicto**: LiteLLM/Prisma tiene inestabilidad periódica que puede afectar batches largos de embeddings. El `CheckResponsesCost` job interno falla y gatifica reconexión de Prisma, lo que puede causar timeouts en medio de un batch.

## Hipótesis C — Interacción LiteLLM + Milvus

**Evidencia**:
- El flujo del index script hace: embed (LiteLLM) → insert (Milvus) por cada página secuencialmente
- Si LiteLLM se cae durante un batch, el script reintenta (con timeout de 60s) y si falla consistentemente, el proceso se detiene
- Si Milvus se cae durante un insert, toda la operación falla
- La combinación de ambos siendo llamados secuencialmente multiplica la probabilidad de fallo

**Veredicto**: La interacción sin aislamiento entre los dos servicios agrava la inestabilidad. Un fallo en cualquiera de los dos detiene todo el proceso.

## Hipótesis D — Batch size / rate limit

**Evidencia**:
- Con batch_size=20: falló después de ~40 embeddings (Milvus container cayó)
- Con batch_size=10: falló después de ~75 inserts
- Con batch_size=5 con 0.3s delay: 506 páginas completadas exitosamente en el probe anterior
- Con batch_size=1 con 0.5s delay: 100 páginas completadas exitosamente

**Veredicto**: **Confirmado**. Batch size y rate están directamente correlacionados con la estabilidad. Batch pequeño + delay = estable.

## Hipótesis E — Datos parciales/duplicados anteriores

**Evidencia**:
- Revisión previa del corpus productivo mostró 5102 entidades lógicas, 0 duplicados, 100% PG↔Milvus
- Collection test híbrida se creó y se llenó con 100 páginas sin duplicados
- No hay evidencia de datos parciales/duplicados

**Veredicto**: Descartada.

## Conclusión

La inestabilidad observada tiene **causa múltiple**:
1. **Milvus container se cae bajo carga continua** (principal causa de fallos en batch)
2. **LiteLLM/Prisma tiene inestabilidad periódica** que puede causar timeouts en embeddings batch
3. **La combinación secuencial** de ambos servicios multiplica el riesgo
4. **Batch pequeño + delay entre operaciones** mitiga el problema

No hay evidencia de que el problema sea exclusivamente Milvus ni exclusivamente LiteLLM. Ambos servicios son estables para operaciones individuales pero no para batches grandes sin rate limiting.
