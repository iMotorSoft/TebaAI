# Kitzur Level 3 — Size / Orchestrator / Runtime Model Diagnostics

Fecha: 2026-07-12. Método: terminal, Ingesta V2, sólo lectura.

## Resumen ejecutivo

Diagnóstico principal:

- **ORCHESTRATOR_CONFIRMED**
- **ORCHESTRATOR_OR_QUERY_DECOMPOSITION_LIMIT**
- **PIPELINE_DESIGN_LIMIT**
- **AGENT_RUNTIME_MODEL_CONFUSION** (riesgo corregido en este informe)

La evidencia española del Kitzur existe y las búsquedas atómicas la recuperan. Book QA V2 no es un RAG generativo: es un endpoint SQL-only que clasifica una pregunta, extrae keywords y devuelve páginas/snippets, con un warning explícito de que la síntesis queda para el lector. Por eso el 29/175 de preguntas largas no mide un modelo runtime ni prueba ausencia de texto; mide una interfaz de recuperación que no descompone de forma fiable una pregunta multi-claim.

No se confirmó `SIZE_CONFIRMED`, `RETRIEVAL_TOPK_LIMIT`, `TRUNCATION_CONFIRMED`, `CORPUS_SCOPE_CONFUSION` ni `SYNTHESIS_MODEL_FAILURE`.

## Infraestructura

| Componente | Estado | Observación |
|---|---|---|
| PostgreSQL | PASS | Validación V2 read-only: run completado, 512 páginas, 506 con texto. |
| Milvus | PASS | Probe híbrido anterior de Kitzur realizó búsqueda y rehidratación PG sin escritura. |
| LiteLLM | PASS | Gateway alcanzable y usado por el probe híbrido para embeddings; no fue llamado por Book QA V2. |
| Backend 7008 | PASS | Launcher canónico `backend-dev.sh`; `/health` devolvió 200. |

## Modelos

| Plano | Modelo | Fuente de detección | Observación |
|---|---|---|---|
| Agente ejecutor | `unknown` | El contexto de esta sesión no expone alias verificable | No es runtime backend. |
| Agent tooling | Codex | Entorno de ejecución | No se usa como control de síntesis backend. |
| Backend runtime generativo | `openai_gpt-5.4-nano` | `core.config.get_settings().research_conversation_model` | Configurado para Relation QA, no invocado por Book QA V2. |
| Embeddings runtime | `openai_text_embedding_3_small` | `core/config.py`, `globalVar.py` | Vía LiteLLM; usado por la prueba híbrida, no reindexado. |

No hay evidencia configuracional de que `gpt5.6-terra-medium`, `gpt5.5-high` o `ds4-flash` sean modelos runtime de TebaAI. Atribuirles el 29/175 habría sido una confusión entre agente ejecutor y runtime.

## Corpus / scope

| Herramienta | Corpus/scope usado | Explícito o default | Observación |
|---|---|---|---|
| Book QA V2, modo largo | run `492acd8d-06bd-42ac-a511-f3ec52f97bb3`, `breslov_test` | explícito | Kitzur Ingesta V2, documento resuelto por el run. |
| Book QA V2, claims | mismo run y `breslov_test` | explícito | 65 consultas atómicas; no hubo caída a `breslov_primary`. |
| Page direct | `library_pages_v2` filtrada por el mismo run | explícito | Fuente textual final PostgreSQL. |
| Probe híbrido previo | `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1` | explícito | Colección de páginas test aislada. |

El schema mantiene `scope_code="breslov_test"` como default de Book QA V2, por lo que una llamada sin scope sería riesgosa. Esta medición no usó el default. El Kitzur no fue presentado como contenido de `breslov_primary`.

## Comparación general de las 7 preguntas

| Pregunta | Modo largo | Modo claims | Modo página | Diagnóstico |
| -------- | ---------- | ----------- | ----------- | ----------- |
| Teshuvá | PARTIAL: 20 páginas, cobertura incompleta | PARTIAL: 8/9 claims | PASS: páginas esperadas con texto | Recuperación genérica; requiere matriz para consolidar. |
| Pureza sexual | FAIL: 0 fuentes | PASS: 10/10 claims | PASS | Falta descomposición del orquestador. |
| Plegaria perfecta | FAIL: 0 fuentes | PASS: 8/8 claims | PASS | Falta descomposición del orquestador. |
| Hitbodedut | FAIL: 0 fuentes | PASS: 9/9 claims | PASS | Falta descomposición del orquestador. |
| Shabat | FAIL: 0 fuentes | PASS: 10/10 claims | PASS | Falta descomposición del orquestador. |
| Punto bueno | FAIL: 0 fuentes | PARTIAL: 6/8 claims | PASS | Dos formulaciones requieren variantes/curaduría. |
| Temor y ángeles | FAIL: 0 fuentes | PASS: 11/11 claims | PASS | Falta descomposición del orquestador. |

Los PASS de página son disponibilidad textual en las ventanas esperadas, verificada con variantes españolas en el informe Level 3 anterior. La métrica `page_phrase_hits` de abajo es más estricta: exige que la formulación de claim coincida literalmente, no que el pasaje equivalente exista.

## Métricas por pregunta

Regla de tokens: estimación `chars / 4`. `chunks recuperados` son fuentes/páginas de Book QA V2 (Ingesta V2 opera por página), no embeddings. Book QA no envía contexto a un modelo; por eso los campos de modelo/contexto final son `not_applicable` y no se infiere truncamiento.

### Pregunta 1 — Teshuvá

| Campo | Valor |
|---|---|
| query_type | long / decomposed_claim / page_direct |
| query_chars / approx_query_tokens | 182 / 46 |
| corpus/scope/documento | `breslov_test` / run `492acd8d…` / documento resuelto por run |
| top_k | 20, explícito |
| chunks recuperados / páginas únicas (largo) | 20 / 20 |
| input_context_chars / approx tokens | 13.068 / 3.267 (snippets devueltos, no prompt) |
| hubo truncamiento / final_context_chars_sent_to_model | unknown / not_applicable |
| claims esperados / con evidencia / sin evidencia | 9 / 8 / 1 (`correr y retornar`) |
| page_phrase_hits / páginas directas | 5 / 11; todas las ventanas existían |
| estado | PARTIAL |
| agent_execution_model / tooling | unknown / Codex |
| backend_runtime_model / provider | `openai_gpt-5.4-nano` configurado / LiteLLM; no invocado |
| prompt_chars / respuesta modelo | 0 / not_applicable |
| claims requested / answered / con cita / sin cita | 9 / 8 / 8 / 1 |

### Pregunta 2 — Pureza sexual

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 206 / 52 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 10 / 10 / 0 |
| page_phrase_hits/páginas directas | 8 / 8 |
| estado | PASS (claims y páginas); FAIL sólo modo largo |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 10 / 10 / 10 / 0 |

### Pregunta 3 — Plegaria perfecta

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 180 / 45 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 8 / 8 / 0 |
| page_phrase_hits/páginas directas | 9 / 10 |
| estado | PASS (claims y páginas); FAIL sólo modo largo |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 8 / 8 / 8 / 0 |

### Pregunta 4 — Hitbodedut

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 190 / 48 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 9 / 9 / 0 |
| page_phrase_hits/páginas directas | 5 / 8 |
| estado | PASS (claims y páginas); FAIL sólo modo largo |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 9 / 9 / 9 / 0 |

### Pregunta 5 — Shabat

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 168 / 42 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 10 / 10 / 0 |
| page_phrase_hits/páginas directas | 7 / 9 |
| estado | PASS (claims y páginas); FAIL sólo modo largo |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 10 / 10 / 10 / 0 |

### Pregunta 6 — Punto bueno / nekudá tová

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 163 / 41 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 8 / 6 / 2 |
| page_phrase_hits/páginas directas | 5 / 5 |
| estado | PARTIAL: requiere expansión de variantes para dos claims |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 8 / 6 / 6 / 2 |

### Pregunta 7 — Temor perfecto y ángeles

| Campo | Valor |
|---|---|
| query_type; query_chars/tokens | long + claims + page_direct; 198 / 50 |
| corpus/scope/documento; top_k | `breslov_test`, run explícito; 20 |
| largo: fuentes/páginas/contexto | 0 / 0 / 0 |
| truncation/model response | unknown; not_applicable |
| claims esperados/con evidencia/sin evidencia | 11 / 11 / 0 |
| page_phrase_hits/páginas directas | 5 / 6 |
| estado | PASS (claims y páginas); FAIL sólo modo largo |
| agente/runtime/provider | unknown/Codex; `openai_gpt-5.4-nano` configurado/LiteLLM, no invocado |
| prompt/final context/model response | 0 / 0 / not_applicable |
| claims requested/answered/con cita/sin cita | 11 / 11 / 11 / 0 |

Datos reproducibles de estas llamadas: [`metrics.json`](metrics.json). El runner es read-only y siempre envía `run_id` y `scope_code`: [`run_readonly_diagnostic.py`](run_readonly_diagnostic.py).

## Prueba comparativa mínima

Se eligió Teshuvá. No existe contrato Book QA para recibir una matriz y sintetizarla: `allow_ai_synthesis` produce el warning `ai_synthesis_disabled_in_sql_only_endpoint`. Por política, no se hizo una llamada genérica directa al modelo ni se usó el modelo del agente como sustituto del runtime.

| Variante | Recupera evidencia | Mantiene citas | Responde todos los claims | Diagnóstico |
|---|---:|---:|---:|---|
| 1. Pregunta larga a Book QA | Parcial: 20 páginas genéricas | Parcial | No: 8/9 | Recuperación por keywords, sin síntesis. |
| 2. Claims separados | Sí: 8/9 | Sí, por página | Parcial | La evidencia se recupera cuando se descompone. |
| 3. Matriz + modelo runtime | not_applicable | not_applicable | not_applicable | No hay endpoint/contrato de matriz para Kitzur; no se puede diagnosticar `SYNTHESIS_MODEL_FAILURE`. |
| 4. Síntesis determinística desde matriz | Sí | Sí | Sí, salvo claim EHIéH no consolidado como cita final | El informe Level 3 anterior es el control determinístico; evidencia existe. |

## Causa probable

- **No es tamaño bruto confirmado:** las preguntas tienen sólo 163–206 caracteres (41–52 tokens estimados), y una pregunta de 182 caracteres devolvió 20 páginas. La variación no sigue linealmente el tamaño.
- **Sí es descomposición/orquestación:** el servicio toma palabras de 4+ caracteres, genera grupos de sinónimos y puntúa páginas. No genera un plan de claims ni exige cobertura por claim. Para 6 de 7 preguntas largas produjo cero fuentes; con las mismas condiciones de scope/run/top_k, los claims recuperaron evidencia.
- **No es top_k:** el límite fue 20; seis preguntas terminaron con cero antes de llegar al límite. Teshuvá alcanzó 20, pero los resultados fueron de cobertura heterogénea, no una síntesis completa. Esto es un problema de ranking/cobertura, no una prueba de que deba subirse top_k.
- **No se confirmó truncamiento:** Book QA sólo devuelve snippets de 400/700 caracteres y no construye ni envía prompt a un modelo. No hay `final_context_chars_sent_to_model` que medir.
- **No hay confusión medida de corpus:** todas las llamadas pasaron scope y run explícitos. El default `breslov_test` existe, pero no intervino en esta prueba.
- **No se puede atribuir fallo al runtime:** Book QA no llamó `openai_gpt-5.4-nano`; por lo tanto `SYNTHESIS_MODEL_FAILURE` es `INCONCLUSIVE`, no confirmado.

## Recomendación

Declaración técnica: **Book QA V2 es suficiente para preguntas puntuales, pero no debe ser el motor único para Nivel 3. Nivel 3 requiere un orquestador de síntesis multi-claim.**

Diseñar, sin implementar aún, `synthesis_qa_v1` con:

1. `decompose_question_to_claims` con scope/run/document explícitos.
2. `retrieve_evidence_per_claim` (lexical primero, vectorial sólo como descubrimiento).
3. `verify_page_text` en PostgreSQL.
4. `build_evidence_matrix` con claim, página, cita, idioma, tipo de evidencia y cobertura.
5. `synthesize_answer_from_matrix` mediante un contrato de IA aprobado; registrar alias runtime efectivo, tokens, contexto, truncamiento y citas permitidas.
6. `emit_citable_report` y fallback determinístico si la síntesis no es válida.

El primer gate debe ser cobertura por claim, no un score único de la pregunta completa. Un segundo gate debe impedir que contexto compuesto o una inferencia se presenten como cita literal.

## Resultado final

| Diagnóstico | Confirmado | Evidencia |
|---|---:|---|
| Ingesta V2 correcta | Sí | Run completado; 512/506 páginas y evidencia directa. |
| Corpus/scope explícito | Sí | Todas las llamadas pasaron `run_id` y `scope_code`. |
| Modelo agente separado de runtime | Sí | Agente `unknown`/Codex; runtime configurado `openai_gpt-5.4-nano`. |
| Modelo runtime detectado | Sí, configurado | Settings efectivos; no fue invocado por Book QA. |
| Book QA V2 apto para preguntas cortas | Sí | 6–11/8–11 claims recuperados en la mayoría de preguntas. |
| Book QA V2 apto para Nivel 3 | No | 6/7 largas devolvieron cero fuentes; no hay síntesis. |
| Se requiere `synthesis_qa_v1` | Sí | Claims y páginas pasan mientras el modo largo falla. |
