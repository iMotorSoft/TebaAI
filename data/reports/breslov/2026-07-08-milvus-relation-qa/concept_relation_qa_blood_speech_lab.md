# Breslov Concept Relation QA Lab — Blood / Speech Lab Report

**Date:** 2026-07-08
**Rama:** `feature/console-backend-core`
**HEAD inicial:** `1547bf0`

> **Cierre post-restauración:** el lab se reejecutó después del repair y cleanup sobre 5102 chunks únicos. Obtuvo 56 hits vectoriales, 187 fragmentos y 0 evidencias sin PostgreSQL. La conclusión sigue válida y la limitación histórica de cobertura `3274/5102` queda resuelta. Véase `milvus_productive_baseline_restoration.md`.

## 1. Objective

Build a investigative **lab script** for cross-concept research queries (e.g., "¿Dónde está la conexión entre sangre y habla?") that answers with traceable evidence separating literal → cooccurrence → thematic → AI inference.

## 2. Tools Verified

| Herramienta | Estado |
|---|---|
| PostgreSQL (tebaai) | ✅ OK |
| Milvus test (`tebaai_breslov_test_chunks_v1`) | ✅ OK (10115 entities) |
| Milvus prod (`tebaai_breslov_chunks_v1`) | ✅ OK (3274 entities; snapshot inicial previo al repair) |
| LiteLLM health | ✅ OK (200) |
| Model `openai_gpt-5.4-nano` | ✅ Available |
| FTS PostgreSQL | ✅ OK (ILIKE) |
| Vector search | ✅ OK (via LiteLLM embeddings) |
| AI interpretation | ✅ OK (via LiteLLM chat completions) |

## 3. Script Created

`scripts/breslov_concept_relation_qa_lab.py` — 1247 lines.

### Modules

- `preflight()` — read-only connectivity check
- `expand_concepts()` — multilingual expansion (ES/EN/HE)
- `search_literal_fts()` — ILIKE search per concept
- `search_exact_cooccurrence()` — both concepts in same chunk
- `search_vector_relation()` — Milvus ANN search
- `enrich_evidence_from_pg()` — PG canonical text recovery
- `merge_results()` / `classify_evidence()` — dedup + classification
- `build_source_map()` — structured source map
- `call_interpretation_model()` — LiteLLM chat (openai_gpt-5.4-nano)
- `render_report()` — structured output

### Arguments

```
--concept-a          Primer concepto
--concept-b          Segundo concepto
--question / -q      Pregunta de investigación
--top-k              Resultados por búsqueda (default: 20)
--no-ai              Modo sin IA (PG + Milvus only)
--use-ai             Modo con interpretación LiteLLM
--skip-preflight     Saltar preflight check
```

## 4. Corpus

- **8 docs ready** (5102 chunks)
- **1 doc test_candidate** (Likutey Halajot Explicado — Interior Final, 47768aac, 2652 blocks, 2222 embeddings)
- Knowledge scope: `breslov_primary`

## 5. Test Loops

All five loops executed successfully:

| Loop | Lang | Mode | Result |
|---|---|---|---|
| 1 | ES | no-ai | ✅ 181 fragments, 61 same_chunk cooccurrence, 0 without PG |
| 2 | EN | no-ai | ✅ 185 fragments, 40 same_chunk cooccurrence, 0 without PG |
| 3 | ES | use-ai | ✅ 181 fragments, LiteLLM call 33k tokens |
| 4 | EN | use-ai | ✅ 185 fragments, LiteLLM call 34k tokens |
| 5 | HE | no-ai | ✅ 256 fragments, 74 same_chunk cooccurrence, 0 without PG |

## 6. Blood / Speech Results

### Apariciones de sangre (concept A)

| Libro | Página | Fragmento |
|---|---|---|
| Likutey Halajot Explicado — Interior Final | 87 | "revolcándote en tu sangre, y te dije, '¡En tu sangre vive!'" |
| La Potencia de la Plegaria | 100 | "luego se salpica la sangre del sacrificio" |
| KITZUR | 130 | "el derramamiento de sangre" |
| Kokhavey Ohr | 60 | "Do not stand by the blood of your brother" |
| Cruzando el Puente Angosto | 182 | "¿Por un poco de sangre en tu corazón?" |

### Apariciones de habla (concept B)

| Libro | Página | Fragmento |
|---|---|---|
| La Potencia de la Plegaria | 11 | "el habla, que estaba atrapada en Egipto" |
| Kokhavey Ohr | 29 | "Speech has great power to influence a person" |
| KITZUR | 145 | "Está prohibido hablar" / "permiso para hablar" |
| KITZUR | 362 | "el habla es el alma misma" |

### Relación sangre/habla

| Tipo | Resultado |
|---|---|
| Literal | No |
| Coocurrencia same_chunk | Sí (61 ES, 40 EN, 74 HE) |
| Coocurrencia same_page | Sí |
| Coocurrencia same_section | No |
| Temática | Sí (6 ES, 6 EN, 56 HE) |
| Inferida por IA | Sí |

**Conclusión:** No hay conexión literal directa entre sangre y habla en el corpus recuperado. Sí hay coocurrencia significativa (ambos conceptos en el mismo fragmento) en múltiples documentos. La IA infiere una posible conexión interpretativa — sangre como estado corporal y habla como expresión espiritual — pero sin base literal directa.

## 7. Auditoría de fuentes

| Check | Resultado |
|---|---|
| Todas resuelven a PG | ✅ Sí |
| Sin PG | 0 |
| Composite como fuente final | 0 |
| Content preview usado | No (siempre PG canonical text) |
| Productivo tocado | No |

## 8. Guardrails

- ✅ No productivo tocado (solo lectura Milvus + PG)
- ✅ No status cambiado
- ✅ No reingesta
- ✅ No embeddings nuevos
- ✅ No chunks modificados
- ✅ No OpenAI directo (solo LiteLLM)
- ✅ Likutey layout doc sigue test_candidate
- ✅ 8 ready intactos
- ✅ Frontend no tocado
- ✅ Team360 no tocado
- ✅ Servicios no reiniciados

## 9. Archivos creados

- `SrvRestAstroLS_v1/backend/scripts/breslov_concept_relation_qa_lab.py` (nuevo)
- `concept_relation_qa_blood_speech_lab.md` (este informe)

## 10. Limitaciones

1. **FTS ILIKE no es FTS nativo** — se usó `ILIKE` para evitar desambiguación entre búsqueda exacta y stemming. Esto es lento para grandes volúmenes.
2. **Milvus collection_code** — La colección productiva usa `collection_code='breslov'` mientras `knowledge_scope_code=breslov_primary`. Hay desajuste.
3. **Cooccurrence detection** — La detección de "mismo chunk" usa `ILIKE` sobre variantes. Hebrew matchea más por variantes cortas (דבר, דם) generando más coocurrencias pero también más falsos positivos.
4. **Explicit relation pattern** — Los patrones de relación explícita (conectado con, relacionado con, etc.) son heurísticos y pueden fallar con construcciones alternativas.
5. **Milvus Dense-only** — Milvus BM25 no se usó; solo dense vectors con métrica COSINE.

## 11. Próxima fase recomendada

El laboratorio funciona correctamente. Recomiendo:

**Breslov Investigative Relation QA Backend Endpoint** — migrar el script a un endpoint productivo POST `/library/relation-qa` con:
- Autenticación
- Rate limiting
- Cache de resultados
- Source map estructurado como JSON
- Integración con el frontend de biblioteca

Si hay fallas de calidad detectadas en la interpretación IA:

**Breslov Concept Relation Retrieval Refinement** — mejorar:
- FTS nativo PostgreSQL (websearch_to_tsquery)
- BM25 + dense hybrid retrieval
- Explicit relation pattern amplification
- Hebrew morphological normalization
