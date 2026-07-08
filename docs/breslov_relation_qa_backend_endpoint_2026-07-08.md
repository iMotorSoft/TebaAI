# Breslov Investigative Relation QA Backend Endpoint — 2026-07-08

Este informe documenta el contrato, implementación y validación del endpoint editorial `POST /library/relation-qa` para investigadores Breslov.

## Objetivo y estado

La API expone Relation QA como JSON auditable, con fuentes canónicas, clasificación editorial, advertencias y síntesis IA opcional.

Estado: backend implementado; tests y seis casos de servicio real validados. El curl autenticado 200 requiere credenciales E2E provistas por entorno; el curl sin token confirmó 401.

## Preflight

El preflight real verificó servicios, corpus, modelos y aislamiento antes de editar código.

| Control | Resultado |
|---|---:|
| Rama | `feature/console-backend-core` |
| HEAD inicial | `1547bf0` |
| PG documentos ready | 8 |
| PG chunks ready | 5102 |
| Milvus entidades / chunks únicos | 5102 / 5102 |
| Duplicados / stale | 0 / 0 |
| Diferencia PG↔Milvus | 0 / 0 |
| Likutey layout test candidate en productivo | No |
| Embedding alias / dimensión | `openai_text_embedding_3_small` / 1536 |
| GPT-5.4 nano vía LiteLLM | Disponible, llamada mínima 200 |

## Contrato request

El request controla corpus, profundidad, IA y formato sin aceptar identificadores tenant como prueba de autorización.

```json
{
  "question": "¿Dónde está la conexión entre sangre y habla?",
  "concept_a": "sangre",
  "concept_b": "habla",
  "language": "es",
  "top_k": 20,
  "use_ai": true,
  "include_test_candidates": false,
  "knowledge_scope_code": "breslov_primary",
  "evidence_depth": "standard",
  "return_markdown": true,
  "debug": false
}
```

`question` es obligatorio; `top_k` admite 1–50. El idioma es `es`, `en`, `he` o `auto`. Los conceptos faltantes se extraen con reglas determinísticas acotadas.

`include_test_candidates=true` habilita lectura investigativa y marca `document_status`. No promueve ni indexa candidatos. `debug` solo se devuelve a rol `admin`.

## Contrato response

La respuesta separa conclusión, conteos de evidencia, source map, warnings, método efectivo y debug autorizado.

```json
{
  "question": "...",
  "language": "es",
  "knowledge_scope_code": "breslov_primary",
  "concepts": {},
  "answer": {
    "short_conclusion": "...",
    "editorial_answer_markdown": "...",
    "literal_relation_found": false,
    "ai_inference_used": true,
    "editorial_certainty": "low"
  },
  "evidence_summary": {},
  "sources": [],
  "source_map": [],
  "warnings": [],
  "method": {},
  "debug": null
}
```

`literal_relation_found` se calcula en código y nunca se delega al modelo. Una respuesta IA inválida conserva las fuentes y usa fallback determinístico con warning.

## Evidence types

El clasificador combina señal textual, metadata layout-aware, roles editoriales y relación entre conceptos.

- literal: `literal_phrase`, `literal_relation`, `explicit_reference`;
- fuentes: `biblical_citation`, `rabbinic_source`, `breslov_text`, `source_hebrew`;
- edición: `editorial_explanation`, `footnote_reference`, `marginal_source`, `internal_cross_reference`, `paraphrase`;
- relación: `cooccurrence_same_chunk`, `cooccurrence_same_page`, `cooccurrence_same_section`, `thematic_relation`;
- interpretación: `derash_interpretation`, `remez_hint`, `ai_inference`;
- cautela: `ambiguous`, `not_found`, `excluded_false_positive`.

La ambigüedad hebrea `דבר` se marca cuando no aparece acompañada por `דיבור` o `דבור`.

## Source object

Cada fuente está deduplicada por `chunk_id` y contiene texto rehidratado desde PostgreSQL.

Los campos incluyen identidad documental, `document_status`, página, sección, capítulo, `node_path`, `block_type`, idioma, evidence types, rol editorial, método, score, citabilidad, snippet, referencias y cross-references.

`content_preview` de Milvus no participa en la fuente final. `composite_page_context` nunca puede tener `is_final_citation=true`.

## Pipeline

El servicio ejecuta retrieval antes de cualquier síntesis.

1. expansión determinística de variantes;
2. PostgreSQL `websearch_to_tsquery`;
3. fallback ILIKE con protección para transliteraciones cortas;
4. patrones relacionales ES/EN/HE;
5. coocurrencia exacta;
6. Milvus dense search read-only;
7. rehidratación PG por scope y lifecycle;
8. deduplicación, clasificación y ranking;
9. source map y warnings;
10. GPT-5.4 nano opcional vía LiteLLM;
11. validación de JSON y source IDs;
12. response mapper.

## Auth y migración 012

La ruta usa el mismo guard autenticado y la misma resolución tenant/scope de `/library/search`.

La migración idempotente `012_backfill_default_tenant_memberships.sql` era necesaria: existían memberships de organización, pero no de workspace/proyecto. Se aplicó solo 012 y se verificaron 12/12/12 memberships activos.

La aplicación no cambió documentos ni chunks: 8 ready, 5102 ready chunks y 10 test candidates permanecieron intactos.

## Tests

Los tests focalizados cubren contrato, clasificación, fuentes, IA, auth y regresiones del módulo library.

| Suite | Resultado |
|---|---:|
| Relation QA unit + HTTP | 42 PASS |
| Suite backend completa | 638 PASS, 79 warnings conocidos |
| HTTP sin Authorization | 401 PASS |
| Servicio real sangre/habla con IA | PASS |
| Loop real de seis casos | 5 PASS + 1 fallback seguro; reintento Bereshit PASS |

## Casos editoriales

Los seis casos resolvieron todas sus fuentes a PostgreSQL y no usaron previews ni composite final.

| Caso | Fuentes | Literal | IA | Certeza | Resultado |
|---|---:|---:|---:|---|---|
| Sangre / habla | 20 | No | Sí | low | PASS |
| Azamra / puntos buenos | 20 | No | Sí | low | PASS |
| Dividiendo la noche / jatzot | 20 | No | Sí | low | PASS |
| Tzafón / norte / mal | 20 | No | Sí | low | PASS |
| Elevando el habla / dibur | 20 | No | Sí | low | PASS |
| Bereshit Rabah | 20 | No | Sí en reintento | low | WARN no bloqueante |

Bereshit Rabah activó una vez el fallback por salida IA no aceptada; un reintento produjo JSON y source IDs válidos. El fallback no inventó conclusión ni descartó fuentes.

## Guardrails verificados

La implementación no contiene paths de escritura de corpus o índices.

- PostgreSQL es la única fuente del snippet final;
- Milvus solo devuelve identidad y score;
- no hubo reingesta, promoción, compactación ni embeddings de corpus;
- solo se generaron embeddings normales de query;
- no se usó OpenAI directo;
- no se tocó frontend ni Team360;
- no se reiniciaron PostgreSQL, Milvus ni LiteLLM;
- Likutey layout permanece `test_candidate`;
- no se usa `collection_id` ni `library_collections_legacy` para routing.

## Limitaciones

El endpoint está listo para backend, con deuda de hardening explícita.

- el clasificador heurístico requiere evaluación continua ante nuevos layouts;
- `include_test_candidates` debe reservarse a investigación editorial;
- PyMilvus ORM emite advertencias de deprecación para 3.1;
- no hay rate limiting, caché ni telemetría de costo por request;
- no existe UI;
- el curl 200 autenticado depende de credenciales E2E externas al repositorio.
- la suite conserva warnings previos por `datetime.utcnow()` y claves JWT cortas de test.

## Próxima fase

La siguiente fase recomendada es **Breslov Relation QA Endpoint Hardening**.

Debe incorporar rate limiting, caché, correlation IDs, telemetría sanitizada, presupuesto de tokens, timeouts diferenciados y una regresión editorial reproducible sobre el endpoint HTTP.
