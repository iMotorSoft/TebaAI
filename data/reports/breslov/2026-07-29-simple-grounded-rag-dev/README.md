# Simple Grounded RAG — DEV gate

Fecha: 2026-07-29.

Rama: `feature/console-backend-core`.

HEAD inicial: `ed5f161127598e39c595aedc1e89345564458fac`.

## Baseline avanzado sanitizado

El baseline se ejecutó directamente contra el servicio vigente con PostgreSQL y
LiteLLM reales, sin escrituras ni cambios de infraestructura.

| Consulta | Estado | Interpretación efectiva | Hits | Vector | Fallback | Duración ms |
| --- | --- | --- | ---: | --- | --- | ---: |
| Relación sangre y habla | no_evidence | sangre | 18 | no | sí | 23174 |
| salmo 19 | ok | Psalms 19 | 15 | no | sí | 9103 |
| escorpión, relaciones | ok | Escorpión | 7 | no | sí | 6022 |
| azamra | ok | Azamra | 15 | no | sí | 5654 |
| Rebe Najmán sobre tristeza | ok | Rebe Najmán | 18 | no | sí | 5077 |
| alegría y emuná | ok | Emuná | 15 | no | sí | 5554 |
| cómo se rectifica el miedo | no_evidence | sin conceptos | 0 | no | sí | 6425 |
| qué es hitbodedut | ok | Hitbodedut | 18 | no | sí | 5074 |

Hallazgos:

- el camino no ejecutó Milvus;
- la clasificación previa redujo preguntas relacionales;
- un fallo interpretativo podía producir vacío real aparente;
- todos los casos usaron redacción determinística de fallback.

No se incluyen tokens, credenciales, cookies, DSN ni payloads de autenticación.

## Smoke simple RAG

`Relación sangre y habla`:

- `original_query` preservada;
- embedding de la pregunta completa;
- Milvus: 30 hits;
- literal PostgreSQL: 30 hits;
- Markdown canónico seleccionado: 12 chunks;
- evidencia de La Potencia de la Plegaria: chunk con `page_start=207` y
  marcador Markdown `Page 208`;
- síntesis: `openai_gpt-5.4-nano`;
- relación: mediada;
- evidence IDs validados;
- estado: `complete`;
- latencia observada: 11.5 s total, con ~4.9 s literal y ~6.5 s síntesis.

## Guardrails

- PostgreSQL no reiniciado ni modificado;
- Milvus no reiniciado ni modificado;
- LiteLLM no reiniciado ni modificado;
- corpus no modificado;
- embeddings del corpus no recalculados;
- migraciones no ejecutadas;
- producción no modificada;
- push no realizado.

## Batch y comparación A/B

Archivo reproducible: `ab_batch.json`.

- preguntas: 22;
- simple RAG válido y con pregunta original preservada: 22/22;
- simple RAG con evidencia PostgreSQL: 22/22;
- estados simple: 20 `complete`, 2 `degraded`;
- degradaciones: síntesis rechazada por evidence IDs inválidos; las fuentes
  canónicas permanecieron visibles;
- advanced válido: 22/22;
- advanced con evidencia primaria: 18/22;
- falsos negativos advanced: sangre–habla, `Likutey Moharán`,
  `Mundo Venidero` y la consulta hebrea `מהי התבודדות`;
- p50 simple: 8763 ms; máximo: 13789 ms;
- p50 advanced: 6772 ms; máximo: 12520 ms.

Los cuatro casos críticos recuperaron evidencia con Milvus y literal en estado
`ok`. Sangre–habla incluyó el chunk de La Potencia con `page_start=207` y el
marcador canónico de página 208. Azamra recuperó La Potencia p. 74. Escorpión
recuperó contextos explícitos. Salmo 19 respondió con fuentes recuperadas sin
depender del parser bíblico.

Decisión del A/B: `simple_rag` es el default DEV. Es algo más lento por ejecutar
embedding, dos ramas de retrieval y síntesis grounded, pero eliminó los cuatro
falsos negativos prácticos del pipeline avanzado y mantuvo fallback auditable.

## Validaciones acumuladas

- backend focalizado solicitado: 309 PASS, 925 deselected;
- backend completo: 1234 PASS, 94 warnings preexistentes de deprecación,
  claves JWT cortas de fixtures y parámetros Litestar inferidos;
- frontend Vitest: 59 PASS;
- Astro check: cero errores, warnings e hints;
- Astro build: 8 páginas PASS;
- Playwright Chromium DEV: 4 PASS (admin, guest read-only, mobile/RTL y
  degradación visible);
- `lat check`: PASS;
- `git diff --check`: PASS.
