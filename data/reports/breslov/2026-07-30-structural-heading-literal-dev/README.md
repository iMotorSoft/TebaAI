# Structural heading literal retrieval — DEV closure

Fecha: 2026-07-30

Rama: `feature/console-backend-core`

HEAD inicial: `e8b57e7f3e571372f9031e98e169dee9ba3df934`

Entorno: DEV (`127.0.0.1:7008`, `127.0.0.1:3008`)

## Resultado

**PASS — DEV ready, sin rollout productivo.**

`CONSTRUYENDO UN MISHKÁN` recupera por el flujo real de `/research`:

- pipeline: `simple_rag`;
- query shape: `structural_heading`;
- match: `structural_heading_exact`;
- obra: `Likutey Halajot`;
- archivo: `LIKUTEY HALAJOT (Interior Final).pdf`;
- página física: 51;
- página impresa: 33;
- sección visible: `4. CONSTRUYENDO UN MISHKÁN`;
- heading canónico almacenado: `4 ■ CONSTRUYENDO UN MISHKÁN`;
- heading chunk: `91aba034-7a02-4520-aa1c-3f29be2741be`;
- body chunk asociado: `d0ae8b80-0947-4503-a45f-11e4b9c7d0ff`;
- evidence ID: `ev-bf5ac6e2fbf46812`;
- estado: `complete`;
- respuesta: grounded y con el evidence ID permitido.

## Baseline

Antes del cambio, la forma exacta en mayúsculas se clasificó como
`short_proper_name`, terminó `partial`, sin evidencia primaria y con seis hits
ajenos al encabezado. Los resultados provenían principalmente de
`LIKUTEY HALAJOT LM II 8.pdf` (páginas 141, 143 y 294) y de paralelos temáticos.
La variante title case podía quedar `complete`, pero promovía contenido general
sobre el Mishkán, no la sección física 51 del archivo solicitado.

El selector real del endpoint y el flujo confirmado usan `simple_rag`; la
prueba `interpret → analyze` devolvió el mismo pipeline y la misma evidencia.

Evidencia: `baseline-api.json`, `confirmed-api.json`, `final-api.json`.

## Documento y cobertura

### Documento layout-aware que contiene los chunks

| Campo | Valor |
|---|---|
| document_id | `47768aac-704e-4296-9649-53b9ea037096` |
| document_code | `NULL` en esta ingesta layout-aware |
| título | `Likutey Halajot Explicado — Interior Final` |
| filename | `LIKUTEY HALAJOT (Interior Final).pdf` |
| SHA-256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| status | `test_candidate`, consultable read-only en DEV |
| idioma | `es` |
| scope | `breslov_primary` |
| ingestion profile | `layout_aware_likutey_halajot` |
| ingestion_run_id | no existe como columna documental en el esquema vigente |
| chunks | 2.652 |
| embeddings | 2.222 |
| embedding run focal | `370df7c7-8381-47fc-b611-b2b2ab3d309d` |

### Proyección page-first especializada del mismo PDF/SHA

| Campo | Valor |
|---|---|
| document_id | `37b5842d-517d-49d1-bab0-3584f409f355` |
| document_code | `likutey_halajot_interior_final` |
| título | `Likutey Halajot` |
| nodes | 268 |
| node página 51 | `cffc46ad-d47e-4ec2-8d0d-f85d4b7f0c70` |
| content unit | `8b0794a3-70e5-4b2f-ad08-0c72be740615` |
| page anchor | `d57966c7-09ee-425b-b974-d784c384f3ad` |

El node page-first conserva heading, bajada y cuerpo completo, pero su anchor no
tenía página impresa. El chunk layout-aware preserva correctamente `printed_page_label=33`.
La respuesta usa el chunk layout-aware como evidencia y reutiliza el título
editorial de la proyección canónica del mismo SHA.

## PostgreSQL

Capas inspeccionadas read-only:

- `library_documents`;
- `library_document_texts`;
- `library_document_chunks`;
- `library_chunk_embeddings`;
- `library_content_units_v2`;
- `library_content_nodes_v2`;
- `library_page_anchors_v2`;
- `library_likutey_halajot_search_ready_v2`;
- `library_likutey_halajot_investigative_search_v1`.

El heading está en el chunk 356 y la bajada en el chunk 357, ambos en PDF 51,
impresa 33, `main_explanation_es`, citable. El Markdown documental completo
también contiene la frase. La vista especializada page-first contiene la página
completa, aunque no separa este heading como fine zone.

Probe focal:

| Query | ILIKE | FTS | trigram |
|---|---:|---:|---:|
| `CONSTRUYENDO UN MISHKÁN` | 1, target sí | 0 | 0 |
| `construyendo un mishkán` | 1, target sí | 0 | 0 |
| `construyendo un mishkan` | 1, target sí | 14, target sí | 0 |
| `mishkán` | 20, target sí | 0 | 0 |
| `mishkan` | 20, target sí | 20, target sí | 0 |

El trigram no veía el heading porque los 2.652 chunks de esta ingesta anterior no
tienen `search_text_normalized`. La solución no modifica datos ni crea índice:
limita el fallback a bloques layout compactos de DEV.

Evidencia: `postgres-probe.json`, `postgres-search-modes.json`.

## Milvus

Tracking PostgreSQL:

- heading PK: `lkh_pg051_b004_main_explanation_es`;
- body PK: `lkh_pg051_b005_main_explanation_es`;
- colección: `tebaai_breslov_test_chunks_v1`;
- modelo: `openai_text_embedding_3_small`;
- dimensión: 1536;
- estado: `indexed` / `indexed_test`.

Resultados read-only:

| Query | Heading rank/score | Body rank/score |
|---|---:|---:|
| `CONSTRUYENDO UN MISHKÁN` | 1 / 0,84806 | 15 / 0,55534 |
| `Construyendo un Mishkán` | 1 / 0,79234 | 15 / 0,57732 |
| `Mishkán` | 1 / 0,52148 | 46 / 0,37713 |
| bajada completa | — | 1 / 0,99018 |

Ninguno de los dos PK está en `tebaai_breslov_chunks_v1`. `simple_rag` consulta
correctamente esa colección productiva; por eso Milvus no podía rescatar este
documento `test_candidate`. PostgreSQL estructural resuelve el caso sin mover
vectores, reindexar ni recalcular embeddings.

Evidencia: `milvus-probe.json`.

## Causa raíz

La causa fue la combinación de cinco capas:

1. mayúsculas españolas confundidas con nombre propio inglés;
2. literal genérico limitado a chunks `ready`;
3. heading y bajada separados en chunks contiguos;
4. vectores focales presentes sólo en Milvus test;
5. selección/ranking que permitía contexto semántico sobre Mishkán sin el título.

No fue ausencia de ingesta, scope, página, chunk, node ni vector.

## Corrección

- normalización estructural NFKC, casefold, controles, NBSP, Markdown,
  puntuación, número inicial y diacríticos;
- clasificación corpus-backed: la forma sola no produce
  `structural_heading`;
- lookup acotado sobre `section_title`, headings Markdown indexados y bloques
  layout cortos existentes;
- ranking estructural por encima de literal corporal y semántica;
- prohibición de primaria `semantic_only` para lookup estructural;
- asociación heading → siguiente body citable de misma página/tipo;
- rehidratación read-only de chunks `test_candidate` ya autorizados en DEV;
- página física e impresa separadas;
- metadata de heading, chunk asociado y evidence ID en API/UI;
- negativos editoriales en mayúsculas sin promoción temática;
- selección única para queries literales prioritarias, evitando que la IA cite
  un exacto contextual distinto del evidence primario.

ADR: `docs/adr/ADR-010-structural-heading-literal-retrieval.md`.

## Ranking vigente

```text
structural_heading_exact
> structural_heading_normalized
> structural_heading_accent_folded
> structural_heading_all_tokens_ordered
> structural_heading_all_tokens_proximity
> body_literal
> structural_heading_partial
> semantic_only
```

El fixture heading exacto con score semántico menor queda por encima de una
fuente temática con score vectorial alto.

## API final y rendimiento

`final-api.json`:

| Etapa | ms |
|---|---:|
| normalización estructural | 0,11 |
| heading lookup + clasificación | 184,42 |
| literal/FTS | 2.689,47 |
| embedding + Milvus | 573,87 |
| merge | 0,16 |
| rehidratación PostgreSQL | 8,85 |
| heading-body association | 0,03 |
| IA | 2.936,42 |
| total backend | 5.822,31 |

El batch de 16 headings tuvo 5.839–10.834 ms, promedio 6.957 ms, incluyendo IA.
No se escanean páginas completas por request.

## Batch estructural

- Likutey Halajot: 5/5;
- Kitzur Likutey Moharán: 3/3;
- La Potencia de la Plegaria: 3/3;
- Kokhavey Ohr EN: 3/3;
- headings hebreos canónicos disponibles: 2/2, honestamente `partial` por match
  de todos los tokens dentro de heading bilingüe.

Las 14 coincidencias exactas/accent-folded terminaron `complete`; las dos
hebreas conservaron heading, fuente, página y evidence ID como
`structural_heading_all_tokens_ordered`.

Variaciones cubiertas: mayúsculas, capitalización editorial, sin acento,
número inicial y forma parcial distintiva.

Evidencia: `heading-batch-api.json`.

## Negativos y regresiones

Negativos, 3/3 `no_evidence`, cero hits y cero primary:

- `CONSTRUYENDO UN TEMPLO INEXISTENTE`;
- `MISHKÁN ABSTRACTO INVENTADO`;
- `CAPÍTULO QUE NO EXISTE`.

Nombres propios:

- `Gedalia of Linitz`, `Gedalia`, `Linitz`, `Reb Noson`: 4/4 `complete` con
  `short_proper_name` y match exacto;
- Playwright confirmó Gedalia en admin, guest y móvil.

Multilingüe:

- ES/EN scorpion, sangre-habla y Azamra conservaron fuentes;
- hebreo `עקרב`, `אזמרה` y las tres variantes de
  `וּמִצְרַיִם נָסִים לִקְרָאתוֹ` conservaron prioridad literal;
- `מה הקשר בין דיבור לדם?` mantuvo su estado preexistente `partial` sin primary;
  no fue capturada como heading ni degradada por esta rama.

Evidencia: `api-regression.json`.

## Validaciones

### Backend

- focal principal + confirmación: 123 passed;
- gate focal pedido: 154 passed, 1.149 deselected, 20 warnings conocidos;
- suite completa final: 1.303 passed, 94 warnings conocidos, 0 failed.

Warnings conocidos: `datetime.utcnow()`, claves JWT cortas de tests y estilo de
query params Litestar; ninguno fue introducido por este gate.

### Frontend

- Vitest: 60 passed;
- `pnpm check`: 0 errores, 0 warnings, 0 hints;
- build: 8 páginas, PASS;
- Playwright Chromium final: 4/4 (structural admin/guest/mobile + proper-name
  admin/guest/mobile), sin mocks.

La UI muestra `Coincidencia exacta con título de sección`, obra, archivo,
páginas 51/33, sección, heading original, normalización, chunk asociado y
evidence ID. El viewport 390×844 terminó sin overflow y guest permaneció
read-only con administración denegada.

### Arquitectura y diff

- `lat check`: PASS (warning operativo: LAT sin key/init, no fallo);
- `git diff --check`: PASS.

## Guardrails

- PostgreSQL no reiniciado ni modificado;
- Milvus no reiniciado ni modificado;
- LiteLLM no reiniciado ni modificado;
- corpus no modificado;
- status documental no modificado;
- reingesta no realizada;
- embeddings no recalculados;
- migraciones no ejecutadas;
- producción, Nginx y `.bashrc` no modificados;
- usuarios y permisos no modificados;
- push no realizado.

Backend DEV y Astro DEV fueron reiniciados únicamente mediante sus launchers
canónicos y quedaron activos.
