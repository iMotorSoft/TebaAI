# Fidelidad de extracción hebrea — DEV — 2026-10-01

**TEBAAI_BRESLOV_HEBREW_EXTRACTION_FIDELITY_V1_PASS**

`DEV_HEBREW_EXTRACTION_FIX_PASS`: PASS.
Ambos PDFs originales completos fueron reingestados por upload → job → worker
normal en `breslov_e2e`, conservados como `test_candidate` y nunca publicados.
No se cambió el corpus productivo ni se desplegó producción. El gate RTL
productivo permanece abierto; el gate productivo principal permanece cerrado.

## CASO A — Un Día en la Vida de un Jasid de Breslov / PDF 187

- first_bad_stage: extracción raw de PyMuPDF.
- root_cause: 294 espacios sintéticos tras marcas hebreas/niqqud en 18 líneas; las cajas de los caracteres base se tocan o superponen. Los espacios reales entre palabras no tienen esa metadata.
- fix: retirar únicamente esos espacios cuando metadata sintética, contexto Unicode y geometría prueban la frontera artificial; aplicar sobre una única coincidencia de la línea fuente en Markdown. No unir letras o palabras mediante regex global.
- result: **PASS**. `יְהִ י רָ צוֹן מִלְּ פָ נֶיָך` → `יְהִי רָצוֹן מִלְּפָנֶיָך`. 196 páginas, 13 vacías preservadas, 296 chunks/embeddings/vectores; reconciliación sin faltantes, duplicados ni huérfanos. Texto canónico = página PG; hashes y previews Milvus corresponden a los chunks. API y DOM coinciden para el chunk `c781e1ae-2b96-5704-8aad-8d5de7c32bc6` de PDF 187. Chromium desktop/móvil y revisión visual: PASS.
- document_id: `10b21f2d-fbe7-51f0-a60a-4a9bd6f274f4`.
- job final: `a36d47cc-8322-4aad-bdf5-fdc67cf551b9`, intento 2, `completed_with_warnings`.
- fuente: `UN DÍA EN LA VIDA (KDP).pdf`; SHA256 `d98e4d4c96a36c701aa055e1a9b8ce230dec24f3b45f35455828f6fe30f69c13`.

## CASO B — La Potencia de la Plegaria / PDF 416

- first_bad_stage: extracción raw de PyMuPDF; PyMuPDF4LLM además pliega saltos entre filas.
- root_cause: columnas independientes de una tabla de equivalencias numéricas se concatenan sin conservar el gutter. El PDF muestra `6 = ו` y `1 = א` en celdas separadas; igualmente `400 = ת`, `80 = פ,ף`, `30 = ל`, `7 = ז`, `2 = ב`. No son letras/números de una misma palabra.
- fix: exigir una línea íntegra de al menos dos celdas número = letra y evidencia de separación geométrica en **todas** sus fronteras. Añadir delimitador explícito ` ; ` entre celdas y preservar filas con saltos de párrafo. 21 fronteras, 6 filas, sin invertir caracteres ni cambiar cifras/puntuación fuente.
- result: **PASS**. Texto canónico = página PG; chunk `b9d937c3-f5a6-5bcf-8643-ffe5fb2ad1b9` y vector correspondientes a PDF 416 coinciden. 416 páginas, 4 vacías preservadas, 908 chunks/embeddings/vectores; reconciliación sin faltantes, duplicados ni huérfanos. API/DOM y revisión visual desktop/móvil: PASS.
- document_id: `47205536-f4d3-5e84-9a1b-75aaac73ca41`.
- job final: `c490f9c6-4752-459c-ad08-9d6706cde0a1`, intento 3, `completed_with_warnings`.
- fuente: `LA POTENCIA DE LA PLEGARIA Interior Print.pdf`; SHA256 `8e5c2ca6c153f47e7ae31e0ba2f2b8fefaedb9916dd8d0d79d484e2c96990c46`.

## Evidencia nueva de render después de corregir la extracción

La primera captura de Relation QA con el canónico corregido mostró que, aunque
los delimitadores ya estaban en API/PG, el navegador podía asociar visualmente
cifras a la celda vecina en el run mixto. Evidencia conservada:
`b-citation-desktop-before-isolation.png`, `b-citation-mobile-before-isolation.png`.

Esto activó la excepción explícita del pedido: no aplicar fixes RTL salvo
**evidencia nueva**. Se hizo un cambio mínimo en la cita de Relation QA:
`sourceTextRuns` reconoce ecuaciones en texto que ya tiene delimitadores de
tabla y aísla cada run mediante `<bdi dir="auto">`. Incluye niqqud con su letra.
No se cambió CSS ni se agregaron controles Unicode al texto canónico; no se
reordenaron números/caracteres ni se alteró la API. Runs concatenados = source
exacto. Celdas de filas distintas también quedan aisladas cuando la API pliega
los saltos. Texto sin estructura demostrada no se segmenta en ecuaciones.
Las capturas finales `b-citation-desktop.png` y `b-citation-mobile.png` muestran
pares inequívocos (por ejemplo ו = 6, א = 1, ת = 400, פ,ף = 80).

## Capas A–G y navegador

Para cada caso: `*-extractor-raw.txt`, `*-pymupdf4llm.md`, `*-canonical.md`,
`*-markdown.md`, `*-chunk-final.txt`, `*-chunks.json`, `*-pg-after.json`,
`*-milvus.json`, `*-api.json`, `*-pdf.png` y fixtures de rawdict/geometría real en
`backend/tests/fixtures/hebrew_pdf_fidelity/`. `extraction-comparison.json`
conserva hashes originales y antes/después. `storage-comparison.json` prueba
igualdad canónico↔PG y metadatos/previews PG↔Milvus.

`browser.json`: Chromium real, login real y peticiones reales, 2/2 PASS, sin
errores de consola ni HTTP 5xx. Se comprueba identidad de documento/página/chunk,
API = excerpt de chunk PG, API = DOM de cita y API = DOM de respuesta editorial.
Desktop 1600×1000 y móvil 390×844, con capturas de respuesta/cita/evidencia.

La UI existente `/library/relation-qa/` usa primary por defecto. La prueba agrega
al request el scope autorizado `breslov_e2e` e inclusión de candidatos,
sin mock de respuestas ni modificación de datos. La síntesis IA se desactiva
explícitamente para comprobar extracción y respuesta determinística, fragmento
y cita. No se declara éxito de síntesis generativa ni retrieval vectorial en
esta ruta (PG para E2E); Milvus se valida separadamente mediante almacenamiento
y reconciliación reales. Preflight de embeddings real: 1536 dimensiones, sin
fallback (`embeddings-preflight-before-reingest.json`).

## Tests nuevos / Tests ejecutados / Backend / Frontend / Regression

Tests nuevos:
- Backend: 23 de fidelidad (fixtures A/B offline, preservación de caracteres, idempotencia, geometría, anclas duplicadas, tres entrypoints con páginas reales, PDF español/inglés comparado con el convertidor sin repairs, headers legacy/Layout); 5 de previews UTF-8; 1 de migración en tabla TEMP; 1 de worker dirigido sin recuperación ajena.
- Frontend: 7 de aislamiento de ecuaciones, filas plegadas, niqqud y secuencias/prosa legítimas intactas.

Tests ejecutados:
- **Backend: 200 PASS**, suite focalizada final en `backend-tests-final.txt` (32,19 s con cuota de CPU). Cubre fidelidad, UTF-8, page-first, evidencia, mapping/chunking, pipeline/normalizador hebreo, aislamiento/orquestación/publicación/cleanup y migración.
- **Frontend: 43 PASS**, `textDirection.test.ts`, `markdownRenderer.test.ts`, `sourceTextRuns.test.ts`, Vitest threads/1 worker; `frontend-tests-final.txt`.
- `pnpm check`: 0 errores, 0 warnings, 9 hints existentes.
- `pnpm build`: 9 páginas PASS.
- Chromium real: 2/2 casos PASS, desktop/móvil, respuesta/cita/evidencia, texto mixto.
- `git diff --check`: PASS. `lat check`: PASS (warnings de setup LAT, sin errores).

| Regression | Estado |
| --- | --- |
| Hebrew pure | PASS |
| Hebrew spaces | PASS |
| Hebrew + numbers | PASS |
| Mixed RTL/LTR | PASS |
| Citation | PASS |
| Español / inglés / cifras / puntuación | PASS |
| Chunking general / páginas / evidencia | PASS |

No se eliminan espacios hebreos globalmente ni se unen/separan secuencias
legítimas por letra+número; `ו1`, `1ו`, `ת80`, palabras distintas y puntuación
permanecen intactas fuera de la evidencia geométrica. No reverse ni inversión.

## Cambios auxiliares necesarios y fallos conservados

- Preview Milvus limitado por **bytes UTF-8** (VARCHAR 1024), sin recortar canónico/chunks. El intento inicial A falló por este límite; compensación oficial verificada antes de retry.
- Worker `--job-id --once` conserva protecciones scope/hash y no recupera/reclama jobs ajenos.
- Migración 042 de unicidad legacy por scope autorizada y aplicada solamente DEV, registrada por migrador normal. El antiguo índice colección/hash chocaba con un candidato B ya existente en primary; no se alteró su contenido. Test TEMP comprueba guard de duplicados por scope y de filas legacy no scoped. Evidencia: `dev-schema-applied.json`.
- B intento 2 falló por timeout de embeddings; Milvus cayó y la compensación no pudo conectar. El usuario reinició Milvus. Se repitió `ManifestCleanupService` manteniendo upload para retry: `b-compensation-recovered.json`, 1327 recursos, completed. Intento 3 completo; no filas/vectores fabricados manualmente.
- Corpus ready DEV: **10 documentos / 5106 chunks sin cambios**, snapshots/hashes `ready-baseline.json` y `ready-after.json`. Job E2E previo ajeno permanece queued. Producción no consultada ni escrita en esta fase.
- Header helper comparte análisis legacy solo cuando está disponible y se utiliza. Layout ignora hdr_info; el módulo instalado no expone IdentifyHeaders en su API superior. La guardia evita análisis inutilizados en runtimes que lo expongan. No se atribuye a este helper una mejora de velocidad en el runtime actual; extracción completa B tardó 1917 s bajo límites. El costo de Layout por página debe medirse antes de una reparación productiva amplia.
- Dos nuevos tests inicialmente fallaron por construir un stub de atributo ausente; corregidos (`raising=False`) y suite completa final 200 PASS. Registro anterior preservado. El test existente de heartbeat dependía de dos pulsos en 40 ms y falló bajo cuota de CPU; ahora mantiene la etapa pendiente hasta dos renovaciones reales con timeout de 5 s, y la suite completa final pasó. Primer runner frontend forks tuvo timeout; threads/1 worker pasó.

## Procesos y memoria

Se detectó y detuvo por SIGTERM la búsqueda amplia de PDFs PID 54465 que había
quedado ejecutándose 76 minutos. Fue un error dejarla activa. Recursos y revisión:
`resource-review.json`, `resource-io-sample.json`, `resource-bounded-run.json`.

Después: trabajo estrictamente secuencial. Cleanup/worker/tests: cgroups con
MemoryMax 1–1,5 GiB según etapa, CPUQuota 50%, IOWeight 10, nice 15, ionice clase 3;
worker TasksMax 64, bibliotecas numéricas a un hilo. Worker: pico observado
609628160 bytes (~581 MiB), salida 0. Chromium: una sesión, MemoryMax 1 GiB,
CPUQuota 100% de un núcleo, TasksMax 128. No tests/browser concurrentes con la
reingesta. No se modificó la configuración ni se reiniciaron PG/LiteLLM/Milvus
por parte del agente; el reinicio Milvus lo realizó el usuario. Backend DEV iniciado para QA detenido con launcher canónico (estado inicial: detenido); tail propio retirado. Frontend previamente activo permanece intacto. No quedan workers, tests ni Chromium de esta tarea.

## Archivos y Git

Backend: `pdf_hebrew_fidelity.py`, `extractors.py`, `page_first_pipeline.py`,
`page_first_gateway.py`, repositorio/runtime/CLI del worker, migración 042,
fixtures y tests citados. Frontend: `RelationQAPanel.svelte`, `sourceTextRuns.ts`
y su test. Docs: contrato de scope, status vigente y este reporte.

Branch: `feature/console-backend-core`.
HEAD inicial/final: `f8bd7e60750abd3be49c113d1ad55a0ec529a5d7`.
Commits: 0. Push: NO. Deploy PROD: NO.
Working tree: cambios sin commit y archivos nuevos del objetivo; directorio
RTL previo del usuario preservado. No cambio de rama ni stash/reset/clean.

## Fase productiva separada — preparada, NO ejecutada

Inventario exacto de fuentes/versiones afectadas → backup verificable de PG y
metadata/índice derivado → prueba de restauración y rollback → capacidad y
ventana de recursos → reparación/reingesta normal controlada por documento →
reconciliación PG/Milvus → validación real API/UI y citas → repetir gate RTL
productivo. Evaluar el índice legacy con el contrato de scope antes de una
migración productiva. La prueba DEV no autoriza reparar datos productivos ni
abrir el gate productivo principal. El único cierre de esta fase es el gate
DEV de fidelidad de extracción arriba indicado.
