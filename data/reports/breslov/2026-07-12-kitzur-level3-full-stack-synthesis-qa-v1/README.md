# Kitzur Level 3 — Full Stack Synthesis QA V1

## Resumen ejecutivo

Diagnóstico principal: **FULL_STACK_PARTIAL** con `ORCHESTRATION_GAP`, no un fallo de corpus.

El prototipo `scripts/library_synthesis_qa_v1_batch.py` procesó las siete preguntas como matrices de claims sobre un run V2 explícito. Las siete matrices tuvieron cobertura suficiente por SQL/page-direct; Book QA V2 aportó descubrimiento adicional salvo Shabat; la síntesis vía LiteLLM respondió con citas de IDs permitidos en las siete respuestas. El fallback determinístico quedó disponible y no hizo falta en esta corrida.

La etiqueta es PARTIAL porque FTS y Relation QA aún no aceptan `run_id` de Ingesta V2 y el probe semántico de páginas no completó: Milvus respondió `collection not loaded` durante `search`. No se cargó, reindexó ni reparó la colección para alterar ese resultado.

## Infraestructura

| Componente | Estado | Observación |
|---|---|---|
| PostgreSQL | PASS | Fuente final de citas por `library_pages_v2`; sólo SELECT. |
| Milvus | PARTIAL | Probe V2 intentado contra `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1`; error `collection not loaded`. |
| LiteLLM | PASS | Síntesis de 7/7 respuestas mediante el gateway. |
| Backend 7008 | PASS | Health HTTP 200 mediante launcher canónico. |

## Modelos

| Plano | Modelo | Fuente | Observación |
|---|---|---|---|
| Agente ejecutor | unknown | sesión Codex | No es runtime backend. |
| Backend runtime | `openai_gpt-5.4-nano` | `core.config.get_settings()` | Usado vía LiteLLM para la síntesis controlada. |
| Embeddings | `openai_text_embedding_3_small` | configuración efectiva | El probe vectorial usa este alias; no se generaron embeddings. |

## Herramientas usadas

| Herramienta | Usada | Resultado |
|---|---:|---|
| SQL directo | Sí | Evidencia canónica por página para 7/7. |
| Page lookup | Sí | Citas finales verificadas en PostgreSQL. |
| FTS / phrase / trigram | No aplicable al run V2 | Contrato actual no recibe `run_id`; no se mezcló scope V1. |
| Milvus / híbrido | Intentado | `collection not loaded`; registrado sin reparación. |
| Relation QA | No aplicable al run V2 | Contrato actual resuelve knowledge scope, no documento/run V2. |
| Book QA V2 | Sí | Descubrimiento por claim; 0 hits para Shabat, cubierto por page lookup. |
| IA synthesis | Sí | 7/7 respuestas con citas de matriz permitidas. |
| Fallback determinístico | Sí | Implementado; no usado en esta corrida. |

## Comparación general

| Pregunta | SQL/page | Book QA | Milvus/híbrido | Relation QA | IA | Fallback | Final |
|---|---:|---:|---:|---:|---:|---:|---|
| Teshuvá | 15 | 19 | no disponible | N/A V2 | sí | no | PASS |
| Pureza sexual | 7 | 22 | no disponible | N/A V2 | sí | no | PASS |
| Plegaria perfecta | 13 | 32 | no disponible | N/A V2 | sí | no | PASS |
| Hitbodedut | 6 | 16 | no disponible | N/A V2 | sí | no | PASS |
| Shabat | 6 | 0 | no disponible | N/A V2 | sí | no | PASS |
| Punto bueno | 10 | 24 | no disponible | N/A V2 | sí | no | PASS |
| Temor y ángeles | 15 | 24 | no disponible | N/A V2 | sí | no | PASS |

Los conteos SQL son candidatos de página antes de elegir la primera cita por claim; los conteos Book QA son resultados de descubrimiento, no citas automáticas.

## Resultados por pregunta

La matriz completa es [`evidence_matrix.json`](evidence_matrix.json); las respuestas, diagnósticos, métodos y métricas están en [`results.jsonl`](results.jsonl). Cada fila de matriz conserva `claim`, página, quote, idioma, `page_direct`, tipo `literal` y estado.

| Pregunta | Claims | Cobertura | Síntesis |
|---|---:|---|---|
| Teshuvá | 7 | 7 PASS | Humildad/silencio, confesión, juicio, vergüenza, retorno y Keter/EHIéH se anclaron a las páginas 20–205. |
| Pureza sexual | 5 | 5 PASS | Lenguaje Sagrado, tzitzit, pensamientos, plegaria/voz y profecía/sustento. |
| Plegaria perfecta | 5 | 5 PASS | Verdad, Tzadikim, alegría, obstáculos y paz. |
| Hitbodedut | 5 | 5 PASS | Juicio, temores, luz, noche/lugar, fuente e idioma cotidiano. |
| Shabat | 4 | 4 PASS | Fe/bendición, daat, comida/alma y alegría/libertad. |
| Punto bueno | 5 | 5 PASS | Búsqueda, impureza/retorno, alegría/plegaria, líder y mérito. |
| Temor y ángeles | 5 | 5 PASS | Tres deseos, festividades, temor/plegaria, ángeles y líderes. |

## Matriz de evidencia y regla de citas

1. El batch recibe `--run-id` y `--scope-code` obligatorios; no resuelve un corpus implícito.
2. Para cada claim, `page_direct` busca variantes sólo dentro de las páginas oracle del run V2 y extrae una ventana textual.
3. Sólo esa evidencia PostgreSQL es aceptada para la matriz final.
4. La IA recibe exclusivamente una evidencia aceptada por claim, con `source_id` y página.
5. La salida IA se rechaza si no contiene citas o cita IDs fuera de la matriz; entonces se entrega la síntesis determinística con `NO_CONFIRMADO` cuando aplique.

Los insumos y salidas reproducibles quedan en [`raw_requests/`](raw_requests) y [`raw_responses/`](raw_responses).

## Fallos y descartes

| Capa | Candidato/resultado | Motivo |
|---|---|---|
| Hybrid V2 | colección de páginas test | Milvus respondió `collection not loaded`; no se modificó estado de la colección. |
| FTS/hybrid estándar | chunks V1 | No acepta `run_id` V2; usarlo habría mezclado contratos/corpus. |
| Relation QA | endpoint actual | No acepta `run_id` ni `document_id` V2; no se forzó scope productivo. |
| Book QA para Shabat | 0 hits | El page lookup verificó la evidencia; Book QA queda como herramienta auxiliar, no autoridad única. |

## Diagnóstico técnico

El prototipo confirma que la limitación observada no es la disponibilidad textual: con claims explícitos, SQL/page V2 cubre las siete preguntas. También confirma que Book QA V2 es útil como un recuperador auxiliar, pero no como orquestador de síntesis. La mejora de producto proviene de la coordinación `claim → página verificada → matriz → síntesis citada`, no de ocultar los métodos internos al investigador.

No se concluye que Milvus o Relation QA carezcan de valor: sus contratos aún no están conectados al `run_id` V2 del Kitzur. Ése es un gap de integración, no una prueba negativa de recuperación semántica.

## Recomendación

Evolucionar este batch hacia un módulo/endpoint `synthesis_qa_v1` tras un ADR específico para la nueva superficie generativa. El diseño debe conservar:

1. `decompose_question_to_claims` determinístico y luego configurable;
2. `retrieve_evidence_per_claim` con adapters V2 para SQL/page, FTS, Milvus y Relation QA;
3. `verify_page_text` obligatorio en PostgreSQL;
4. `build_evidence_matrix` con claim, página, localizador, tipo y método;
5. `synthesize_answer_from_matrix` por LiteLLM con citas cerradas;
6. fallback determinístico y diagnósticos por capa.

La siguiente implementación debe añadir `run_id`/`document_id` V2 a FTS, vectorial y Relation QA antes de declarar `FULL_STACK_PASS`; no debe usar el corpus productivo como sustituto del candidato Kitzur.

## Resultado final

| Criterio | Estado |
|---|---|
| Ingesta V2 correcta | PASS |
| Scope explícito | PASS |
| Full-stack probado | PARTIAL |
| Synthesis QA V1 viable | PASS como batch prototipo |
| Matriz y citas verificadas | PASS |
| Síntesis IA desde matriz | PASS |
| Fallback determinístico | PASS |
| Falta desarrollo adicional | Sí: adapters V2 para FTS/Milvus/Relation QA y ADR/endpoint. |
