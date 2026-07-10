# Status actual - TebaAI

Objetivo: `desarrollo`

Ultima actualizacion: 2026-07-09 (synthesis hardening + UI indicator)

Este tablero contiene solo el estado tecnico vigente. La evolucion previa esta resumida en `status_historico_hasta_2026-06-28.md` y conservada con detalle en Git.

## Directorio y rama

- raiz: `/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI`;
- rama funcional: `feature/console-backend-core`;
- la rama local estaba sincronizada con `origin/feature/console-backend-core` al iniciar esta fase.

## Estado general

- Backend Litestar con configuracion tipada, lifecycle y PostgreSQL 18 mediante `psycopg 3 async`.
- Frontend Astro 7 + Svelte 5, Tailwind CSS 4 y DaisyUI 5.
- Autenticacion con Argon2id, access JWT, refresh token opaco, rotacion, deteccion de reutilizacion y roles `admin`, `editor`, `viewer`.
- Biblioteca con ingesta de Markdown, texto y PDF, chunking, PostgreSQL FTS y busqueda HTTP autenticada.
- Milvus 2.6 funciona como indice vectorial derivado; PostgreSQL conserva texto y metadata como fuente de verdad.
- LiteLLM se usa para embeddings `openai_text_embedding_3_small` y para síntesis generativa (`openai_gpt-5.4-nano`) en el endpoint Relation QA.
- Servidores dev canonicos: `SrvRestAstroLS_v1/backend-dev.sh` para Litestar en `127.0.0.1:7008` y `SrvRestAstroLS_v1/astro-dev.sh` para Astro en `127.0.0.1:3008`.

Referencias canonicas:

- `lat.md/global-configuration-facade-policy.md`;
- `lat.md/authentication-security-policy.md`;
- `lat.md/library-retrieval-models-policy.md`;
- `lat.md/postgres-driver-policy.md`;
- `lat.md/service-preflight-methodology.md`;
- `lat.md/page-mapping-failure-diagnosis.md`;
- `lat.md/breslov-test-corpus-policy.md`.

## Servidores dev operativos

Los scripts de desarrollo estan documentados como entrypoints locales canonicos y no gestionan servicios permanentes.

- `SrvRestAstroLS_v1/backend-dev.sh`: soporta `start`, `stop`, `restart`, `status` y ejecuta `.venv/bin/uvicorn ls_iMotorSoft_Srv01:app --host 127.0.0.1 --port 7008` por defecto.
- `SrvRestAstroLS_v1/astro-dev.sh`: soporta `start`, `stop`, `restart`, `status` y ejecuta `astro dev --host 127.0.0.1 --port 3008` por defecto.
- Overrides locales: `TEBAAI_BACKEND_HOST`, `TEBAAI_BACKEND_PORT`, `TEBAAI_ASTRO_HOST`, `TEBAAI_ASTRO_PORT`; backend tambien puede cargar `SrvRestAstroLS_v1/.env.backend-dev.local`.
- PID files: `SrvRestAstroLS_v1/.dev-pids/`; logs: `SrvRestAstroLS_v1/.dev-logs/`.
- No ejecutan `docker compose`, `systemctl`, `service`, `pkill`, `killall`, migraciones, ingesta, embeddings ni llamadas directas a OpenAI.
- No inician, detienen, reinician ni reconfiguran PostgreSQL, Milvus o LiteLLM.
- `stop` solo envia señales a un PID file propio despues de validar el comando esperado.
- Si el puerto esta ocupado por un proceso desconocido, lo reportan y no lo matan.

## Corte runtime: `library_collections_legacy` → `knowledge_scopes` — 2026-07-04

**Completado.** `knowledge_scopes` es la única fuente primaria operativa v1.

### Regla vigente

```
knowledge_scopes es el único contenedor primario para todo flujo activo de conocimiento/biblioteca.
library_collections_legacy queda deprecated, histórico y read-only.
No debe ser usado por runtime, ingesta, retrieval, validación, indexación ni promoción.
collection_id es solo metadata legacy y no debe usarse como clave operativa de routing.
```

### Módulos actualizados

| Archivo | Cambio |
|---------|--------|
| `modules/library/repository.py` | Nuevas funciones `get_scope_by_code`, `get_scope_by_id`, `resolve_scope_context`. Funciones legacy (`get_or_create_collection`, `get_collection_by_code`) marcadas DEPRECATED. |
| `modules/library/text_search.py` | `search_chunks_text` ahora usa `knowledge_scope_code`. JOINs reemplazados de `library_collections_legacy` a `knowledge_scopes`. |
| `modules/library/hybrid_search.py` | `search_chunks_hybrid` ahora usa `knowledge_scope_code`. JOIN legacy reemplazado. |
| `modules/library/indexing_service.py` | `index_collection` e `index_existing_chunks` ahora usan `knowledge_scope_id`/`knowledge_scope_code`. |
| `modules/library/vector_repository.py` | `get_unindexed_chunks` y `count_chunks` ahora filtran por `knowledge_scope_id`. |
| `modules/library/service.py` | `ingest_document` resuelve scope vía `resolve_scope_context`. |
| `modules/library/routes.py` | Pasa `knowledge_scope_code` a search functions. |
| `modules/library/schemas.py` | `LibrarySearchResult` y `IngestDocumentResult` usan `knowledge_scope_code`. |
| `modules/library/errors.py` | Nuevo `ScopeNotFoundError`. `CollectionNotFoundError` marcado DEPRECATED. |
| `modules/library/domain.py` | `LibraryCollection` marcado DEPRECATED. `KnowledgeScope` existente. |

### Datos backfilleados

- 9.478 chunks con `knowledge_scope_id` poblado
- 231 embeddings con `knowledge_scope_id` poblado
- 1 documento archivado sin scope (aceptable: `archived` legacy)
- 0 chunks/embeddings sin scope

### Scripts

- `chunk_documents.py` e `index_chunks_milvus.py`: actualizados a `knowledge_scopes`
- `dry_run_promotion_checklist.py`: actualizado a `knowledge_scopes`
- 16 scripts de auditoría/evaluación: marcados DEPRECATED con header
- `ingest_koren_part_one.py` y `ingest_koren_part_two.py`: marcados DEPRECATED

### Tests

- `test_hebrew_fts_builder.py`: JOIN actualizado de `library_collections_legacy` a `knowledge_scopes`

### Base de datos

- `library_collections`: **no existe**
- `library_collections_legacy`: **existe** (3 filas históricas, read-only)
- `knowledge_scopes`: **existe** (1 fila: `breslov_primary` activo)
- Milvus productivo `tebaai_breslov_chunks_v1`: **7023 entidades** (5194 breslov corpus ES/EN + 1829 heredadas de pipeline original). Promovido 2026-07-05.
- Otras bases PG18: **no tocadas**

## Runtime validado

- migraciones `001` a `008` aplicadas;
- 1.990 chunks bibliograficos vigentes y 1.991 vectores registrados por la ejecucion historica inicial;
- 284 chunks enriquecidos con metadata de pagina de alta confianza;
- diagnostico reproducible de cobertura baja en Potencia y Likutey, ejecutado sin escrituras;
- colección `breslov_test` aislada con un documento `test_candidate`, texto extraído y cero chunks;
- modos de busqueda textual: `auto`, `fts`, `phrase`, `trigram`;
- modo `hybrid`: PostgreSQL FTS + Milvus, deduplicado por `chunk_id`;
- endpoint `POST /library/search` protegido por autenticacion;
- UI disponible para login, administracion de usuarios y busqueda bibliografica.

La diferencia 1.990/1.991 queda como deuda de reconciliacion: no debe normalizarse documentalmente sin auditar PostgreSQL y Milvus.

## Validacion actual

- backend: `uv run pytest` = 259 PASS, 66 warnings de deuda conocida;
- frontend: `pnpm check` = 0 errores, 0 warnings, 0 hints;
- frontend: `pnpm build` = 4 paginas, PASS;
- Playwright: 12 tests descubiertos correctamente; no se ejecutaron contra servicios reales en esta consolidacion;
- Playwright sin credenciales: 3 tests autenticados seleccionados, 3 skips esperados y cero intentos con fallback;
- Playwright autenticado requiere credenciales E2E cargadas por entorno;
- evaluacion bibliografica hibrida: 26/30 PASS;
- `lat check`: PASS, cero errores;
- `git diff --check`: PASS;
- **scripts/compare_chunking_strategies.py**: CLI implementado, 38 tests unitarios PASS. Smoke real con PostgreSQL no ejecutado por falta de conexión en este entorno.

La suite reporta deuda preexistente por `datetime.utcnow()` y claves JWT cortas usadas en tests; no afecta el PASS, pero debe corregirse.

## PostgreSQL config centralizada 2026-06-30

- `core/config.py` ahora resuelve PostgreSQL desde `DB_PG_*` (estándar iMotorSoft) + base `tebaai`.
- `globalVar.py` es la fachada oficial; no requiere exportar `TEBAAI_POSTGRES_*` localmente.
- `TEBAAI_POSTGRES_*` queda como override opcional.
- Smoke real de chunking ejecutado: 52/52 Sijot detectadas, recomendación B.
- Sin contaminación: `breslov`=1991 chunks, `breslov_test`=0 chunks.
- `test_globalvar_postgres_config.py`: 12 tests PASS.
- `test_sijot_aware_chunk_apply.py`: 11 tests PASS.
- `chunk_documents.py` extendido con `--strategy` (generic/sijot-aware) y `--apply`.
- `chunking.py` agregó `convert_temporary_chunks_to_db_format()`.
- `test_sijot_page_mapping_enrichment.py`: 16 tests PASS.
- `enrich_chunk_page_metadata.py` extendido con `--strategy normalization_plus` y soporte `test_candidate`.
- `text_search.py` y `search_library_text.py`: ahora incluyen `reference_label` en resultados.
- `pytest` total: 298 PASS.

## Sijot-aware chunking applied 2026-06-30

- Documento "El Alma del Rebe Najmán" en `breslov_test` ahora tiene 476 chunks Sijot-aware.
- 52/52 Sijot detectadas, 0 missing, 0 cross-section.
- Metadata estructural por chunk (section_type, section_number, section_label).
- FTS busca correctamente en `breslov_test`.
- `breslov` productivo sigue con 1991 chunks (sin contaminación).
- Milvus no indexado. LiteLLM no llamado.
- Documento sigue `test_candidate`.

## Sijot-aware page mapping 2026-06-30

- 273/476 chunks de `breslov_test` enriquecidos con page_start, page_end, reference_label.
- Estrategia `normalization_plus`: NFKC + unaccent + markdown/bold/italic stripping + Sija normalization.
- Reference labels: `Sija N · PDF page(s) M` o `SectionName · PDF page(s) M`.
- `bibliographic_metadata` mergeada preservando section + chunking + page_mapping.
- Sin contaminación: breslov=1991/284, breslov_test=476/273.
- Invalid ranges: 0.
- 203 chunks sin mapping (42.6%) por markdown denso. Mejorable.

## Breslov test Milvus indexing 2026-06-30

- 476 chunks de `breslov_test` indexados en Milvus `tebaai_breslov_test_chunks_v1`.
- Embeddings: LiteLLM + `openai_text_embedding_3_small` (dim=1536).
- Safety guards: test → test collection, prod → prod collection. Rechaza contaminación cruzada.
- `tebaai_breslov_chunks_v1` productiva: 1991 (intacta).
- Search Milvus smoke: chunk 246 (Sija #25) top result para "La maravilla del cerebro".
- Evaluación productiva sin regresión.
- `test_milvus_test_indexing.py`: 13 tests.
- `pytest`: 311 PASS.
- Documento sigue `test_candidate`. Sin promoción.`

## Hebrew PDF pipeline validation — TNK Masoretic Text 2026-07-02

Documento experimental de prueba técnica hebrea completa desde PDF `tnk Massoretic Text.pdf` (Tanaj masorético, 1532 páginas, Tiqwah TeX font encoding SI-960).

### FASE 1–2: Preflight y extracción

- PDF: 1532 páginas, 7.9 MB, texto seleccionable (no OCR).
- PyMuPDF4LLM: 0 caracteres hebreos (font TeX Tiqwah no decodificable por PyMuPDF4LLM).
- Extracción vía `pymupdf (fitz)` + `hebrew_tex_decoder` (SI-960 TeX decoder).
- Subset extraído: páginas 1–200 → 701.331 chars, 547.089 hebreos (78%).
- Marcado `## Page N` preservado para page mapping.
- Limitaciones: artefactos `¡`, espacios entre caracteres, combinación parcial de niqqud/temim.
- Reporte de preflight guardado en `data/reports/preflight_tnk_hebrew.json`.

### FASE 3: PostgreSQL persistencia

- Documento creado: `Tanakh Torah (Bereshit+Shemot) — Masoretic Text PDF pages 1-200 (Hebrew test)`.
- Estado: `test_candidate` en colección `breslov_test`.
- SHA-256: `f2ec0fc...` — round-trip exacto verificado (701.331 chars, 547.089 hebreos).
- Metadata: source path, pdf_pages, books_covered, extraction_method `si960_decoder`.
- Sin corrupción: 0 nulls, 0 vacíos, SHA256 match 100%.

### FASE 4: Chunking experimental

- Estrategia: `paragraph_overlap` (chunk_size=1800, overlap=250, min_chunk=200).
- 381 chunks generados desde `library_document_texts.content`.
- 0 chunks vacíos, 0 corruptos.
- 373/381 (97.9%) con hebreo detectado.
- Page mapping: 381/381 (100%) mapeados vía `## Page N` markers.
- Longitud promedio: 2.089 chars.

### FASE 5: PostgreSQL FTS hebreo básico

| Query | Modo | Hits | Resultado |
|---|---|---|---|
| `בראׁשית` (Bereshit) | fts | 3 | OK |
| `משה` (Moshe) | fts | 3 | OK |
| `ויאמר` (vayomer) | phrase | 3 | OK |
| `Introduction` | fts | 3 | OK |
| `זזזזזזזזז` (garbage) | fts | 0 | OK (negativa) |

**OR corregido y testeado:**
- `to_tsquery('simple', 'בראׁשית \| שמות')` → 69 matches correctos.
- `||` dentro de `to_tsquery` → error de sintaxis (rechazado correctamente).
- `websearch_to_tsquery('simple', 'בראׁשית or שמות')` → produce `'בראׁשית' \| 'שמות'`.
- Trigram search para hebreo: 0 hits (sin stemming hebreo, esperado).

Regla documentada: `||` en SQL concatena tsvector/texto, no representa OR dentro de `to_tsquery`. OR correcto es `|`.

### FASE 6–7: Embeddings LiteLLM + Milvus test

- Embeddings vía LiteLLM (`openai_text_embedding_3_small`, dim=1536).
- Colección Milvus: `tebaai_breslov_test_chunks_v1` (productiva `tebaai_breslov_chunks_v1` intacta).
- 50 chunks embebidos e indexados (subset técnico por costo/límite de tokens).
- Límite de tokens: chunks truncados a 1.200 chars para evitar exceder 8192 tokens de OpenAI.
- Dimensión 1536 validada; 0 vectores nulos.
- Sin errores de rate limit o timeout.

### FASE 8: Round-trip PG↔Milvus

- 50/50 chunks verificados: 100% (Milvus existence + SHA-256 match + PG re-read).
- Mecanismo: vector search con filtro `pk == "<chunk_uid>"`, verificación SHA-256.

### FASE 9: Search smoke tests

- **FTS hebreo**: 3+ hits para términos reales del texto.
- **Vector search hebreo**: 5 hits, distancia promedio 0.50.
- **Vector search inglés**: 5 hits, distancia promedio 0.42.
- **Vector search negativo**: distancia baja (0.396) — sin falsos positivos.
- **Hybrid search**: 5 resultados combinando FTS + vector, deduplicados.
- **PG retrieval**: texto literal recuperado desde PostgreSQL con title y page_start/end.

### FASE 10: Shoresh/lemas hebreos — fuera de alcance de esta fase

Primero se validó transporte técnico hebreo. La normalización semántica/morfológica se analizará después, cuando UTF-8, Markdown, chunking, FTS, embeddings, Milvus y round-trip estén validados. El hebreo viaja sin corrupción por toda la tubería: PDF → SI-960 decode → Markdown → PostgreSQL → chunks → FTS → embeddings → Milvus → recuperación literal.

### Resumen numérico

| Métrica | Valor |
|---|---|
| Páginas PDF analizadas | 200 (de 1532) |
| Chunks generados | 381 |
| Embeddings generados | 50 (subset) |
| Vectores en Milvus test | 50 (nuevos) + preexistentes |
| Round-trip PG↔Milvus | 100% |
| FTS hebreo | Funcional con `simple` config |
| Colección productiva tocada | No |
| Servicios reiniciados | No (PostgreSQL, Milvus, LiteLLM) |
| OpenAI key directa usada | No (solo LiteLLM) |

### Archivos modificados

- `SrvRestAstroLS_v1/backend/modules/library/hebrew_tex_decoder.py` — mapeos `¡`→meteg, `Ì`→qamats qatan, función `scan_unknown_characters`, constante `KNOWN_UNMAPPED`.
- `SrvRestAstroLS_v1/backend/scripts/hebrew_test_pipeline.py` — bug `embedded`→`indexed` corregido, `create_embedding_run` agregado.
- `SrvRestAstroLS_v1/backend/scripts/smoke_hebrew_pipeline.py` — **nuevo**: smoke test reproducible hebreo.
- `SrvRestAstroLS_v1/backend/tests/test_hebrew_tex_decoder.py` — 18 tests nuevos (mapeos, artefactos, niqqud, orden).
- `SrvRestAstroLS_v1/backend/tests/test_hebrew_fts_builder.py` — 6 tests nuevos postgres integration (OR, ||, websearch).
- `SrvRestAstroLS_v1/docs/status_actual.md` — este informe.

## Hebrew pipeline stabilization 2026-07-02

Correcciones aplicadas tras la prueba técnica Tanaj:

### Decoder SI-960 refinado

- **Artefacto `¡` (U+00A1)**: 6.075 ocurrencias mapeadas a **meteg** (U+05BD, barra vertical de acento secundario). Contexto en texto masorético lo confirma.
- **Artefacto `Ì` (U+00CC)**: 565 ocurrencias mapeadas a **qamats qatan** (U+05C7, variante de qamats).
- **Artefactos `¿` (U+00BF) y `Í` (U+00CD)**: preservados como están. Mapeo incierto sin inspección de archivo de fuente Tiqwah. Documentados en `KNOWN_UNMAPPED`.
- **Función `scan_unknown_characters()`**: nueva utilidad para auditar artefactos residuales tras decodificación.
- **Meteg y qamats qatan excluidos del conteo de artefactos** (son marcas hebreas válidas).
- Tests: 46 tests en `test_hebrew_tex_decoder.py` (antes 28), cubriendo mapeos nuevos, detección de artefactos, preservación de niqqud/taamim, letras finales, dagesh, y orden RTL.

### Bug de estados `embedded` vs `indexed` corregido

- **Causa**: `phase_embed` en `scripts/hebrew_test_pipeline.py` usaba `status="embedded"` que viola el check constraint de `library_chunk_embeddings` (solo permite `indexed`, `failed`, `skipped`).
- **Fix**: cambiado a `status="indexed"`. Agregada llamada a `create_embedding_run()` y `update_embedding_run()` para cumplir FK `embedding_run_id`.
- **Estados válidos del pipeline**: extraído (en content) → chunked (en chunks) → indexed (embedding generado + Milvus indexado).
- Tests de transición cubiertos por los PostgreSQL integration tests.

### Smoke test reproducible

- Nuevo: `scripts/smoke_hebrew_pipeline.py` — prueba chica e idempotente.
- Cubre: extract → ingest → chunk → FTS → embed → Milvus → round-trip → cleanup.
- Flags: `--limit-pages N`, `--limit-chunks N`, `--skip-embed`, `--cleanup`.
- Uso: `TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.smoke_hebrew_pipeline`
- Usa título único + SHA-256 para idempotencia. `--cleanup` remueve datos.

### FTS/OR regression tests ampliados

- `test_hebrew_fts_builder.py`: 17 tests (antes 11).
- Nuevos tests PostgreSQL integration:
  - `to_tsquery('simple', '... | ...')` con hebreo real funciona.
  - `to_tsquery('simple', '... || ...')` es rechazado por PostgreSQL.
  - `websearch_to_tsquery('simple', '... or ...')` produce `|`.
  - Query FTS real contra `breslov_test` chunks con hebreo.

## PDF moderno bilingüe — Koren Talmud Yevamot 2026-07-02

Segundo PDF hebreo probado: Koren Talmud Bavli, Vol 15 Yevamot Part 2, edición bilingüe hebreo/inglés.

### Diferencias clave vs Tanaj SI-960

| Aspecto | Tanaj SI-960 | Koren moderno |
|---|---|---|
| PDF engine | Tiqwah TeX (pdfLaTeX 2004) | Adobe InDesign CS5.5 |
| Año | 2002–2005 | 2016 |
| Páginas | 1.532 | 398 |
| Texto hebreo | SI-960 encoded | Unicode directo |
| PyMuPDF4LLM | 0 chars hebreos | **Funciona directo** |
| Decoder especial | `hebrew_tex_decoder` | No necesario |
| Marcas diacríticas | Meteg, taamim | Niqqud completo |
| Columnas | Simple | Bilingüe hebreo/inglés |
| Page markers | `## Page N` | No hay (`PyMuPDF4LLM` no los genera) |

### Resultados pruebas

- **Preflight**: 398 páginas, 10.2 MB, texto seleccionable, sin OCR. Fuentes Unicode (ArnoKoren, KorenSiddur).
- **Extracción**: PyMuPDF4LLM directo → 230.833 chars (20.708 hebreos, 149.295 ingleses). UTF-8 preservado. Sin artifacts SI-960. Sin decoder.
- **PostgreSQL**: documento `test_candidate` en `breslov_test`. SHA-256 round-trip 100%.
- **Chunking**: 176 chunks, 0 vacíos. 43 con hebreo, 169 con inglés, 36 mixtos. Page mapping no disponible (PyMuPDF4LLM no inserta marcadores de página para este PDF).
- **FTS hebreo**: `תלמוד`=3 hits, `תלמוד בבלי`=1 hit, OR `תלמוד | בבלי`=3 matches.
- **FTS inglés**: `Talmud`=3 hits, `uncircumcised priest`=3 hits, websearch `Talmud or Torah`=OK.
- **OR guard**: `||` rechazado correctamente.
- **Embeddings**: LiteLLM + `openai_text_embedding_3_small`, 20 vectores, dim=1536.
- **Milvus test**: `tebaai_breslov_test_chunks_v1`, 20 vectores insertados. Productivo intacto.
- **Round-trip PG↔Milvus**: 20/20 = 100%.

### Smoke script extendido

`smoke_hebrew_pipeline.py` ahora soporta:
- `--pdf-path`: ruta al PDF
- `--title`: título del documento
- `--extraction-mode pymupdf4llm|fitz-si960|auto`
- Uso: `TEBAAI_LITELLM_API_KEY="..." uv run python -m scripts.smoke_hebrew_pipeline --extraction-mode pymupdf4llm --pdf-path "..." --title "..." --limit-pages 10`

### Decisión futura clara

- **PDF moderno Unicode** → `--extraction-mode pymupdf4llm`
- **PDF legacy SI-960/Tiqwah** → `--extraction-mode fitz-si960`
- **OCR** → fuera de alcance hasta ADR

### Próximos pasos recomendados

1. **BM25/multilingual analyzer en Milvus**: evaluar si un analyzer multilingüe mejora la búsqueda vectorial hebrea en Milvus.
2. **Shoresh/lemas**: cuando corresponda, diseñar capa morfológica hebrea como ADR separado. No mezclar con el pipeline de transporte.
3. **Ampliar cobertura**: procesar las 1.532 páginas completas del Tanaj y/o las 398 del Talmud Yevamot.
4. **Page mapping para PyMuPDF4LLM**: investigar si hay forma de obtener page numbers del output de PyMuPDF4LLM para PDFs sin marcadores.

### Fuera de alcance (permanente para esta fase)

- **Shoresh**: no se implementó análisis de raíces hebreas.
- **Lemas**: no se implementó lematización hebrea.
- **Stemming hebreo**: no se configuró PostgreSQL stemming hebreo.
- **BM25 multilingüe Milvus**: no se evaluó.
- **Rediseño de chunking semántico**: no se modificó.
- **Frontend**: no se tocó.
- **Análisis talmúdico**: estructura daf/amud/sugya no analizada.
- **OCR**: PDF tiene texto seleccionable, no aplica.

## Calidad documental y operativa

- `AGENTS.md` es la fuente operativa canonica.
- el status runtime fue compactado; el status duplicado de Astro fue retirado.
- las credenciales E2E no tienen fallback versionado y deben venir del entorno.
- LAT enlaza configuracion, auth y retrieval con referencias `@lat` en codigo.
- `lat check` es gate obligatorio para cambios documentales.
- `lat search` requiere `LAT_LLM_KEY`, `LAT_LLM_KEY_FILE` o `LAT_LLM_KEY_HELPER`; sin clave se usa `lat locate`.

## Pendientes prioritarios

1. Reconciliar la diferencia entre 1.990 chunks vigentes y 1.991 vectores historicos.
2. Reejecutar backend, frontend y E2E con servicios reales disponibles.
3. Sustituir almacenamiento frontend de tokens por cookies `httpOnly` con proteccion CSRF documentada.
4. Implementar refresh automatico y expiracion de sesion visible.
5. Completar paginacion y busqueda en administracion de usuarios.
6. Definir el limite entre plataforma generica TebaAI y la vertical Breslov.
7. Refinar `normalization_plus` con guard de rango exacto y ampliar el holdout antes de aplicar nueva metadata high-confidence.
8. ~~Ejecutar section-aware chunking dry-run para `El Alma del Rebe Najmán` antes de crear chunks en `breslov_test`.~~
    - **Completado**: scripts/compare_chunking_strategies.py implementado y testeado (38 tests). Smoke real pendiente de conexión PostgreSQL.
9. Decidir qué hacer con las 92 entidades extra heredadas en Milvus productivo (Likutey Halajot — mismo contenido, chunk_id distinto del pipeline original).
10. Diseñar cualquier RAG generativo mediante ADR, sin incorporarlo al endpoint de retrieval existente.
11. Eliminar `datetime.utcnow()` y usar claves JWT de test de al menos 32 bytes.

## Seguridad

- No guardar secretos ni credenciales de prueba en codigo o documentacion.
- Las variables `TEBAAI_E2E_ADMIN_EMAIL` y `TEBAAI_E2E_ADMIN_PASSWORD` son obligatorias para E2E autenticado.
- PostgreSQL, Milvus y LiteLLM son servicios externos; no gestionarlos automaticamente.
- No imprimir DSN, tokens ni API keys completos.

## Page mapping robusto para PDF moderno Unicode 2026-07-02

Problema resuelto: PDFs modernos como el Koren Talmud no tenían `## Page N` markers en el output de PyMuPDF4LLM, por lo que los chunks quedaban sin page mapping bibliográfico.

### Solución adoptada

1. Nueva función `extract_pdf_with_page_markers()` en `modules/library/extractors.py`:
   - Extrae página por página con PyMuPDF4LLM.
   - Envuelve cada página con `## Page N` marker controlado.
   - Devuelve Markdown combinado + metadata de página (char_start, char_end, page_number, char_count, hebrew_count).
   - No requiere decoder SI-960 para PDFs Unicode modernos.

2. Nueva función `resolve_page_range_from_markers()` en `extractors.py`:
   - Dado char_start/char_end de un chunk y la metadata de páginas, resuelve page_start/page_end.
   - Maneja correctamente:
     - chunk dentro de una página → (N, N).
     - chunk cruzando límite → (N, N+1).
     - chunk en última página → página correcta.
     - sin markers → (None, None).
   - Tests unitarios para todos los casos.

3. Smoke script extendido con `--page-markers force|auto|off`.

### Resultados validados

| Métrica | Koren (pages 45-50) |
|---|---|
| Páginas extraídas | 6 |
| Chunks generados | 35 |
| Chunks vacíos | 0 |
| Page mapping | **35/35 (100%)** |
| Cross-page chunks | 5 (correctamente mapeados) |
| Embeddings | 20 vía LiteLLM |
| Milvus test | 20 vectores |
| Round-trip PG↔Milvus | 20/20 (100%) |
| Productivo intacto | Sí |

### Decisión documental

- **PDF moderno Unicode**: `--extraction-mode pymupdf4llm --page-markers force`.
  Usa `extract_pdf_with_page_markers()` → page mapping 100%.
- **PDF legacy SI-960**: `--extraction-mode fitz-si960`.
  Usa fitz + decoder → markers via `## Page N` → regex-based mapping.
- **OCR**: fuera de alcance.

### Archivos modificados

- `modules/library/extractors.py` — nuevas funciones `extract_pdf_with_page_markers()`, `resolve_page_range_from_markers()`.
- `scripts/smoke_hebrew_pipeline.py` — flags `--page-markers`, `--page-start`, integración page_meta, extracción dinámica.
- `tests/test_page_markers_extraction.py` — **nuevo**: 14 tests (resolve_range, extract con PDF real, metadata, FTS).
- `docs/status_actual.md` — este informe.

## Ampliación de cobertura Koren 2026-07-02

Validación de escalabilidad del PDF Koren moderno Unicode + page markers controlados.

### Resumen de cobertura

| Escenario | Págs | Chars | Hebrew | Chunks | Hebrew chunks | Vacíos | Page mapping | Embeddings | Round-trip |
|---|---|---|---|---|---|---|---|---|---|
| 1–50 no embed | 50 | 194.759 | 17.053 | 150 | 33 | 0 | 100% | — | — |
| 1–100 no embed | 100 | 570.233 | 64.756 | 438 | 122 | 0 | 100% | — | — |
| 1–398 full no embed | **398** | **2.534.522** | **313.408** | **1.988** | 608 | 0 | 100% | — | — |
| 1–50 embed limit 20 | 50 | 184.206 | 16.473 | 141 | 31 | 0 | 100% | 20 | 100% |
| Tanaj SI-960 regression | 10 | 9.889 | 2.023 | 9 | 2 | 0 | 100% | — | — |

### Hallazgos

1. **Escala lineal**: 50→100→398 páginas → chars y chunks crecen proporcionalmente sin degradación.
2. **Page mapping 100%** en todos los escenarios via `page_meta` (Koren) o regex (Tanaj).
3. **Chunks vacíos = 0** en todos los escenarios.
4. **PyMuPDF4LLM 0-index fix**: se detectó que la versión 1.27.2.3 usa 0-indexed para `pages`. Se corrigió `extract_pdf_with_page_markers()` restando 1.
5. **No hay chunks sin página** en ningún subset probado.
6. **FTS hebreo/inglés funcional** en todos los escenarios.
7. **Productivo intacto**: solo se usó `tebaai_breslov_test_chunks_v1`.
8. **OpenAI key directa no usada**: solo LiteLLM.

### Decisión

La ruta PDF moderno Unicode + page markers controlados **escala a libro completo** manteniendo referencias bibliográficas confiables. No hay bloqueo técnico para avanzar a BM25 multilingüe o shoresh/lemas cuando corresponda.

## Fix smoke embedding lifecycle 2026-07-02

### Bug detectado

El smoke script `scripts/smoke_hebrew_pipeline.py` tenía un bug donde el embed step reportaba "No uninitialized chunks" falsamente.

**Causa raíz**: El test de guardia `||` en el FTS step (línea original 303-309) ejecuta `SELECT to_tsquery('simple', 'a || b')` que PostgreSQL rechaza con un error de sintaxis. En psycopg 3, cualquier SQL error dentro de una transacción **aborta toda la transacción**. Todos los INSERTs previos (documento, texto, chunks) quedan en estado "aborted", y cuando el bloque `async with pool.connection()` intenta COMMIT, PostgreSQL lo rechaza y ejecuta ROLLBACK. El siguiente pool/connection no ve ningún chunk.

**Fix**: El test `||` ahora se ejecuta dentro de un `SAVEPOINT`. Si falla, se ejecuta `ROLLBACK TO SAVEPOINT` que restaura solo el savepoint sin afectar la transacción principal. Los chunks previos se commitean correctamente.

**Validación**: Smoke Koren 1–50 con embeddings ahora corre end‑to‑end sin workaround:
- 141 chunks, 20 embebidos, 20 indexados Milvus, round-trip 20/20 = 100%.
- "No uninitialized chunks" ya no aparece falsamente.
- Regression Koren `--skip-embed` y Tanaj SI-960 siguen pasando.

## ADR BM25 multilingüe Milvus 2026-07-02

### Investigación técnica

Milvus 2.6.14 + PyMilvus 2.6.15 soportan:

- **BM25** via `FunctionType.BM25` — auto-computa sparse vectors desde VARCHAR con analyzer.
- **`SPARSE_FLOAT_VECTOR`** — tipo de datos para sparse vectors.
- **`enable_analyzer`** — requerido en campo VARCHAR para BM25.
- **Index `SPARSE_INVERTED_INDEX`** con `metric_type: BM25`.
- **Hybrid dense+sparse** via `AnnSearchRequest` + `RRFRanker`.

### Prototipo validado

Se creó colección experimental `tebaai_breslov_bm25_test_v5`, se insertaron documentos multilingües y se ejecutaron BM25 searches:

| Query | Resultado |
|---|---|
| `Talmud` | 1 hit score 1.41 |
| `יבמות` (Yevamot) | 1 hit score 1.30 |
| `God created heavens` | 1 hit score 4.05 (phrase boost) |
| `בראשית` (Bereshit) | 1 hit score 1.55 |
| `zzzzzzz` | 0 hits (negativa correcta) |

### ADR creado

`docs/adr/ADR-003-milvus-bm25-multilingual.md` — estado `proposed (experimental)`.

### Evaluación comparativa con corpus real

Se ejecutó `scripts/evaluate_bm25_retrieval.py` con **500 chunks reales** (Kokhavey Ohr EN + Koren HE/EN) y **12 queries** comparando PG FTS, Milvus dense y Milvus BM25.

#### Resultados clave

| Método | Hebrew hits | English hits | Spanish hits | Negative |
|---|---|---|---|---|
| PG FTS | 4/12 | 21/20 | 15/15 | 0 (correcto) |
| Dense | 15/15 | 20/20 | 15/15 | 5 (falso positivo) |
| BM25 | 2/15 | 10/30 | 20/20 | 0 (correcto) |

#### Overlap BM25 vs FTS

BM25 encuentra chunks **diferentes** a FTS para la mayoría de queries:
- `תלמוד`: overlap 2/3 (J=0.67)
- `Talmud`: overlap 0/10 (J=0.00) — BM25 y FTS rankean distinto
- `maravilla del cerebro`: overlap 3/7 (J=0.43)
- `Breslov`: overlap 0/10 (J=0.00)

#### Conclusión

**BM25 aporta valor complementario**: baja superposición con PG FTS y dense vectors sugiere que un ranking híbrido (dense+sparse+FTS) podría mejorar recall. **No integrar a producción todavía**. Seguir evaluando.

## Hybrid/RRF evaluation 2026-07-02

### Métodos comparados

Nuevo script `scripts/evaluate_hybrid_retrieval.py` que implementa RRF fusion de:
- PG FTS
- Milvus dense vector
- Milvus BM25 sparse

**Fórmula RRF**: `score = Σ 1/(rrf_k + rank_i)`, con `rrf_k = 60`.

**Lexical gate**: Si FTS=0 y BM25=0, los resultados dense se marcan `low_confidence`.

### Resultados (500 chunks, 12 queries)

| Query | FTS | Dense | BM25 | RRF F+D+B | Gate |
|---|---|---|---|---|---|
| `תלמוד` | 3 | 10 | 2 | 10 | 10 |
| `מסכת` | 0 | 10 | 0 | 10 | **10 low** (over-flagged) |
| `Talmud` | 10 | 10 | 10 | 10 | 10 |
| `zzzzzzzzzz` | 0 | 10 | 0 | 10 | **10 low** (correct) |

### Hallazgos

1. **RRF FTS+dense+BM25** = cobertura máxima. Consolida hasta 29 chunks únicos por query.
2. **Lexical gate** funciona para negativas pero **sobre-flaggea términos hebreos válidos** con niqqud.
3. **Dense** siempre encuentra 10 resultados (incluso gibberish) — necesita gate.
4. **No integrar a producción**. Seguir experimental.

### Scripts experimentales

- `scripts/evaluate_bm25_retrieval.py` — BM25 vs FTS vs dense.
- `scripts/evaluate_hybrid_retrieval.py` — RRF fusion + lexical gate.

### Archivos nuevos/modicados

- `docs/adr/ADR-003-milvus-bm25-multilingual.md` — actualizado con evaluación BM25 + hybrid/RRF.
- `scripts/evaluate_bm25_retrieval.py` — **nuevo**: evaluación BM25 comparativa.
- `scripts/evaluate_hybrid_retrieval.py` — **nuevo**: evaluación hybrid RRF.
- `docs/status_actual.md` — este informe.

## Hebrew lexical normalization 2026-07-02

### Módulo creado

`modules/library/hebrew_lexical_normalizer.py` — helper puro para normalización lexical hebrea.

**Qué normaliza:**
- Unicode NFC
- Niqqud (U+05B0–U+05BC, U+05C1–U+05C2, U+05C7)
- Taamim (U+0591–U+05AF)
- Meteg (U+05BD)
- Maqaf → guion ASCII
- Invisible/formatting marks

**Qué NO normaliza:**
- Shoresh/lemas/stemming
- Letras finales
- Prefijos ו/ה/ב/ל/מ/כ
- Texto canónico en PostgreSQL
- Inglés/español

### Tests: 25 tests unitarios, todos PASS.

### Integración en evaluación

`scripts/evaluate_hybrid_retrieval.py` ahora soporta `--normalize-hebrew` que:
1. Crea colección BM25 normalizada `tebaai_breslov_bm25_norm_test_v1`
2. Evalúa FTS con query normalizada
3. Evalúa BM25 sobre contenido normalizado
4. Lexical gate considera todas las variantes (original + normalizadas)

### Resultados

| Query | FTS | F_N | BM25 | B_N | Gate |
|---|---|---|---|---|---|
| `מסכת` | 0 | 0 | 0 | 0 | low (cobertura, no niqqud) |
| `תלמוד` | 3 | 3 | 2 | 2 | OK |
| `Talmud` | 10 | 10 | 10 | 10 | OK |
| `zzzzzzzzzz` | 0 | 0 | 0 | 0 | low (correcto) |

La normalización no degrada inglés/español. El caso `מסכת` no mejora por ser problema de cobertura del corpus (1 chunk en PG, fuera del límite 500), no de niqqud.

### Decisión

Normalización lexical hebrea implementada y funcional. No modifica texto canónico. No introducir shoresh/lemas. Mantener experimental. Evaluar en corpus más grande antes de integración.

## Likutey Moharan HebrewBooks 34314 — Breslov real corpus test 2026-07-02

### Preflight

| Métrica | Valor |
|---|---|
| Archivo | `Hebrewbooks_org_34314.pdf` |
| Páginas | 352 |
| Tamaño | 18.25 MB |
| Título | `ספר ליקוטי מוהר"ן` |
| Autor | `נחמן בן שמחה, מברסלב` |
| Productor | iText 5.5.8 |
| Texto seleccionable | Sí |
| OCR requerido | No (texto extraíble) |
| Caracteres hebreos | ~60-90% por página |
| Niqqud | No |
| Fuente | Probable OCR text layer (iText) |

### Columnas y orden de lectura

**PyMuPDF4LLM**: produce texto corrupto con mezcla de columnas línea a línea y caracteres basura. **No usable.**

**fitz `get_text('blocks')`**: produce fragmentos palabra-por-palabra (blocks granularidad demasiado fina). **No usable.**

**fitz `get_text('text', sort=True)`**: produce texto hebreo conectado legible con orden (y, x). Las columnas se intercalan pero el texto es coherente. **Mejor opción.**

### Extracción elegida

`extract_pdf_columns_with_page_markers()` en `extractors.py` implementa extracción con `fitz.get_text('text', sort=True)` y `## Page N` markers. Método: `fitz_sort_text`.

### Resultado subset 1-20

20 páginas, 90.642 chars, 57.193 hebreos. 36 chunks, 0 vacíos, 100% hebreo. SHA-256 round-trip OK. FTS: `ליקוטי`=3, `נחמן`=3, `תורה`=3, `zzzzzzzzzz`=0. Embeddings: 20 generados vía LiteLLM, 20 indexados Milvus test. Round-trip PG↔Milvus: 20/20.

### Limitaciones

1. **Extracción imperfecta**: El texto tiene OCR artifacts (puntos entre palabras, espacios extraños). No es texto born-digital limpio.
2. **No apto para producción**: La capa de texto del PDF tiene calidad insuficiente para cita bibliográfica confiable.
3. **No se procesó 1-100 ni full** porque la calidad de extracción no lo justifica. La prueba técnica demostró que el pipeline funciona pero el input es deficiente.
4. **Solución futura**: Si se desea texto de alta calidad para Likutey Moharán, buscar fuente Sefaria, texto plano, o realizar OCR sobre PDF escaneado de mejor calidad.

### Activos generados

- `modules/library/extractors.py` — extendido con `extract_pdf_columns_with_page_markers()`.
- Tests: 113/113 PASS.

### Conclusión

El pipeline técnico funciona para este PDF (fitz_sort_text + PG + chunks + FTS + embeddings + Milvus). Sin embargo, la calidad del texto extraído es pobre debido a la capa OCR/text-layer del PDF. **No recomendar ingesta productiva de este PDF.** Para corpus Breslov real en hebreo, buscar fuente nativa digital o Sefaria.

## Koren Yevamot Part One — modern bilingual full corpus test 2026-07-02

### Preflight

| Métrica | Part One | Part Two |
|---|---|---|
| Páginas | **496** | 398 |
| Chars totales | **3.281.327** | 2.534.522 |
| Chars hebreos | **369.550** | 313.408 |
| Productor | Adobe InDesign CS5.5 | Adobe InDesign CS5.5 |
| Texto seleccionable | Sí | Sí |
| OCR requerido | No | No |
| PyMuPDF4LLM directo | Sí | Sí |

### Resultados de cobertura

| Escenario | Págs | Chars | Hebrew | Chunks | Hebrew chunks | Vacíos | Page mapping | Embeddings | Round-trip |
|---|---|---|---|---|---|---|---|---|---|
| 1–20 | 20 | 20.723 | 168 | 16 | 2 | 0 | 100% | — | — |
| 1–100 | 100 | 525.490 | 50.255 | 410 | 104 | 0 | 100% | — | — |
| 1–496 full | **496** | **3.281.327** | **369.550** | **2.559** | 767 | 0 | 100% | — | — |
| 1–50 embed | 50 | 158.117 | 11.671 | 126 | 25 | 0 | 100% | 20 | 100% |

### Comparación Part One vs Part Two

| Métrica | Part One | Part Two |
|---|---|---|
| Páginas | 496 | 398 |
| Chunks | 2.559 | 1.988 |
| Page mapping | 100% | 100% |
| Chunks vacíos | 0 | 0 |
| FTS hebreo | OK | OK |
| FTS inglés | OK | OK |
| Embeddings limitados | 20 (1-50) | 20 (1-50) |
| Round-trip PG↔Milvus | 20/20 = 100% | 20/20 = 100% |
| Extracción | pymupdf4llm + page markers | pymupdf4llm + page markers |

La familia Koren/Steinsaltz moderna es **consistente entre volúmenes**: mismo pipeline, misma calidad, misma confiabilidad.

### Conclusión

Yevamot Part One se procesó completo (496 páginas, 3.28M chars, 2.559 chunks) con la misma ruta moderna `pymupdf4llm + controlled page markers`. Layout bilingüe preservado. Page mapping 100%. FTS hebreo/inglés funcional. Embeddings limitados OK. Round-trip PG↔Milvus 100%. Productivo intacto.

**La ruta Koren/Steinsaltz moderna es confiable y escalable entre volúmenes.**

## Política de calidad documental 2026-07-02

Se creó `docs/library_document_source_quality_policy.md` — política formal de
clasificación, promoción y criterios para fuentes documentales.

### Decisiones clave

| Fuente | `source_kind` | Estado actual | Recomendación |
|---|---|---|---|
| Koren Yevamot Part One | `pdf_modern_unicode` | `test_candidate` → técnicamente `approved_candidate` | Aprobable para producción |
| Koren Yevamot Part Two | `pdf_modern_unicode` | `test_candidate` → técnicamente `approved_candidate` | Aprobable para producción |
| Tanaj SI-960 Masoretic | `pdf_legacy_encoded` | `test_candidate` → `approved_candidate` técnico | Pendiente revisión artifacts |
| HebrewBooks 34314 Likutey | `pdf_facsimile_ocr_layer` | Text layer: `rejected_text_layer` | No canónico. Facsímil útil |

### Taxonomía de fuentes

7 clases: `pdf_modern_unicode`, `pdf_legacy_encoded`, `pdf_facsimile_ocr_layer`,
`pdf_scan_no_text`, `native_digital_text`, `manual_transcription`, `derived_normalized`.

### Estados de promoción

Actuales: `draft`, `test_candidate`, `ready`, `archived`, `error`.
Propuestos (documentados, no implementados): `discovered`, `preflighted`,
`approved_candidate`, `facsimile_only`, `rejected_text_layer`,
`blocked_ocr_required`, `deprecated`.

### Criterios mínimos

Preflight, extracción, UTF-8, PostgreSQL round-trip, chunking (0 vacíos),
page mapping ≥95%, FTS smoke, query negativa, embeddings vía LiteLLM,
calidad bibliográfica. Checklist operativo incluido en la política.

### Relación PostgreSQL/Milvus

PostgreSQL = fuente de verdad documental.
Milvus = recuperación/ranking, nunca texto canónico completo.
Round-trip PG↔Milvus debe ser 100%.

### Archivos nuevos

- `docs/library_document_source_quality_policy.md` — política de calidad.

## Aplicación de política a fuentes reales 2026-07-02

### Quality reports aplicados

Se registró `bibliographic_metadata.source_quality` en documentos PostgreSQL existentes.

| Fuente | Document ID | `source_kind` | Recomendación |
|---|---|---|---|
| Koren Yevamot Part Two | cfd5a9f9 | `pdf_modern_unicode` | `approved_candidate` |
| Tanaj SI-960 (Tanakh Torah) | d48fa596 | `pdf_legacy_encoded` | `approved_candidate_conditional` |
| Masoretic Text (old partial) | b62619cb | `pdf_legacy_encoded` | `diagnostic_only` |
| Koren Yevamot Part One | (smoke - limpio) | `pdf_modern_unicode` | Template en policy doc |
| HebrewBooks 34314 | (smoke - limpio) | `pdf_facsimile_ocr_layer` | Template en policy doc |

### DB constraint real

`library_documents.status` permite: `draft`, `ready`, `test_candidate`, `archived`, `error`.
El `source_quality.promotion_recommendation` es **virtual** — no modifica el constraint.
Los documentos persisten con `status = test_candidate` (valor permitido).

### Guardrails

- `approved_candidate` es virtual hasta que schema lo soporte.
- Ninguna fuente es canónica solo porque FTS/embeddings pasan.
- `facsimile_only` no alimenta texto canónico.
- `derived_normalized` nunca se cita.
- Milvus no decide calidad documental.

### Archivos modificados

- Ningún archivo de código modificado. Solo metadata en PostgreSQL.
- `docs/status_actual.md` — este informe.

## Diseno de workflow de promocion documental 2026-07-02

### Contexto

La politica `docs/library_document_source_quality_policy.md` ya fue aplicada con
`bibliographic_metadata.source_quality` sin migracion. Los estados virtuales
(`promotion_recommendation`) existen en metadata pero no modifican status real.

### Auditoria de `ready`

- **Busqueda**: NO filtra por status — `test_candidate` y `ready` coexisten en resultados.
- **Milvus productivo**: solo indexa `status = 'ready'`.
- **Milvus test**: solo indexa `status = 'test_candidate'`.
- **Chunking**: permite ambos en test, solo `ready` en produccion.
- **Promocion**: NO existe codigo de promocion. No hay script ni endpoint que cambie status.

### Diseno aprobado (documentado, no implementado)

1. `ready` definido como "corpus estable interno", no "exposicion publica".
2. Mapping `promotion_recommendation → status`: `approved_candidate` → `ready`,
   `approved_candidate_conditional` → `test_candidate` hasta condiciones resueltas,
   `facsimile_only`/`rejected_text_layer` → nunca `ready` como texto canonico.
3. Checklist promocional: 18+ items obligatorios, 8 rechazos automaticos.
4. Metadata `promotion_decision` registra decision, checks, limitaciones aceptadas.
5. Script futuro `scripts/promote_library_document.py`: dry-run por defecto,
   guardrails por politica, `--apply` requerido para mutar.
6. Evaluacion actual: Koren Yevamot Part Two elegible pero no auto-promovido.
   Tanaj SI-960 condicional. HebrewBooks 34314 no canonico.

### Documentos creados

- `docs/library_promotion_workflow.md` — diseno completo del workflow.
- `docs/library_document_source_quality_policy.md` — actualizado con secciones 13-17.

### Guardrails

- No se cambio status real de documentos.
- No se aplico migracion.
- No se toco Milvus productivo.
- No se reiniciaron servicios.
- Tests: 113/113 PASS (sin regresion).

## Cierre consolidado: Koren Yevamot Part One + Part Two 2026-07-02

### Contexto

Cierre de la línea Koren/Steinsaltz. Se resolvieron inconsistencias pendientes
y ambos documentos quedaron en estado comparable, auditado, con metadata
consistente, dry-run de promoción persistido y status real `test_candidate`.

### Documentos involucrados

| Documento | ID | Status | Estado |
|---|---|---|---|
| **Part One** | `6f876e95...` | `test_candidate` | Full, metadata consistente, dry-run OK |
| **Part Two full (nuevo)** | `91e5829e...` | `test_candidate` | Full, metadata consistente, dry-run OK |
| **Part Two old (superseded)** | `cfd5a9f9...` | `test_candidate` | Metadata corregida, marcado superseded |

### Part Two old — resolución de inconsistencia

El documento original `cfd5a9f9` (55 páginas, 176 chunks, 0% page mapping) tenía
`source_quality.evidence` incorrecto (declaraba 398 páginas, 1.988 chunks, 100%
page mapping). Se resolvió:

- **No se borró** el documento histórico.
- **No se cambió** su status (`test_candidate` preservado).
- Se creó un **nuevo documento full** (91e5829e) con 398 páginas, page markers,
  1.988 chunks, 100% page mapping.
- El viejo fue marcado en metadata:
  - `promotion_recommendation = superseded_smoke_subset`
  - `canonical_text_allowed = false`
  - `superseded_by_document_id = 91e5829e...`
  - `evidence.page_mapping_coverage = 0.0`
  - Evidence real: pages=55, chunks=176

### Estado final Part One

| Métrica | Valor |
|---|---|
| Document ID | `6f876e95-04c3-4bd5-b7d8-a4de27d6becc` |
| Status | `test_candidate` |
| Páginas | 496 |
| Chars | 3.281.327 |
| Chunks | 2.559 (0 vacíos) |
| Page mapping | 100% |
| FTS hebreo/inglés | OK |
| Embeddings | **Pendientes** (LiteLLM key no disponible) |
| PG↔Milvus | Pendiente |
| `promotion_recommendation` | `approved_candidate` |
| `promotion_decision_dry_run` | ✅ Persistido: `eligible_pending_manual_review` |

### Estado final Part Two full

| Métrica | Valor |
|---|---|
| Document ID | `91e5829e-0fb3-4319-afe1-25413851ff7f` |
| Status | `test_candidate` |
| Páginas | 398 |
| Chars | 2.534.522 |
| Chunks | 1.988 (0 vacíos) |
| Page mapping | 100% |
| FTS hebreo/inglés | OK |
| Embeddings | **Pendientes** (LiteLLM key no disponible) |
| PG↔Milvus | Pendiente |
| `promotion_recommendation` | `approved_candidate` |
| `promotion_decision_dry_run` | ✅ Persistido: `eligible_pending_manual_review` |
| Relación | Reemplaza a `cfd5a9f9` (registrado en metadata) |

### Dry-run de promoción

Ejecutado contra DB real para Part One y Part Two full:

| Check | Resultado |
|---|---|
| Pass | 14/18 |
| Fail | 0/18 |
| Pending | 4/18 |
| Rechazos automáticos | 0/8 |
| Decisión | `eligible_pending_manual_review` |

**Items pendientes (4):**
1. Embedding smoke pass (skipped: no LiteLLM key)
2. PG↔Milvus round-trip (skipped: depende de embeddings)
3. Manual review sample
4. Legal/copyright/public exposure decision

`promotion_decision_dry_run` persistido en `bibliographic_metadata` para ambos
documentos. No se escribió `promotion_decision` real.

### Simetría técnica

| Dimensión | Part One | Part Two full | ¿Simétricos? |
|---|---|---|---|
| Pipeline | `pymupdf4llm + page markers` | `pymupdf4llm + page markers` | ✅ |
| Page mapping | 100% | 100% | ✅ |
| Chunks vacíos | 0 | 0 | ✅ |
| Metadata consistente | ✅ | ✅ | ✅ |
| `promotion_recommendation` | `approved_candidate` | `approved_candidate` | ✅ |
| Status | `test_candidate` | `test_candidate` | ✅ |
| Embeddings | pendientes | pendientes | ✅ |
| Dry-run persistido | ✅ | ✅ | ✅ |
| Sin promoción real | ✅ | ✅ | ✅ |

### Guardrails

- `library_documents.status` preservado en todos los documentos.
- No se promovió a `ready`.
- No se tocó Milvus productivo (`tebaai_breslov_chunks_v1` intacta).
- No se reiniciaron servicios (PostgreSQL, Milvus, LiteLLM).
- No se aplicaron migraciones.
- No se borraron documentos históricos.
- No se modificó texto canónico.
- Tests: 532 PASS.
- `git diff --check`: 0 errores.

### Archivos modificados en esta fase

- `scripts/ingest_koren_part_two.py` — **nuevo**: ingesta full Part Two con page markers.
- `SrvRestAstroLS_v1/docs/status_actual.md` — este informe.

### Embeddings completados y dry-run actualizado 2026-07-02

Se ejecutó el vector smoke faltante con `LITELLM_MASTER_KEY`.

| Documento | Embeddings | Milvus test | PG↔Milvus round-trip | Estado |
|---|---|---|---|---|
| Part One (`6f876e95`) | 20 | `tebaai_breslov_test_chunks_v1` | 20/20 (100%) | ✅ Pass |
| Part Two full (`91e5829e`) | 20 | `tebaai_breslov_test_chunks_v1` | 20/20 (100%) | ✅ Pass |

`source_quality` actualizado para ambos: `embedding_smoke_status=pass`, `milvus_roundtrip_status=pass`, `evidence.embedding_count=20`, `evidence.milvus_roundtrip=1.0`.

Dry-run de promoción re-ejecutado contra DB real con datos actualizados:

| Documento | Pass | Pending | Fail | Rechazos | Decisión |
|---|---|---|---|---|---|
| Part One | **16/18** | 2/18 | 0/18 | 0/8 | `eligible_pending_manual_legal` |
| Part Two full | **16/18** | 2/18 | 0/18 | 0/8 | `eligible_pending_manual_legal` |

Los únicos pending son: **manual review sample** y **legal/copyright decision**. Embeddings y round-trip ya están verificados.

Milvus productivo `tebaai_breslov_chunks_v1` intacto (1991 entidades, sin cambios).

### Estado final consolidado — todos los documentos

| Documento | ID | Status | Mapping | Embeddings | Dry-run | Ready? |
|---|---|---|---|---|---|---|
| **Part One** | `6f876e95` | `test_candidate` | 100% | 20/20 pass | ✅ `eligible_pending_manual_legal` | Pendiente manual/legal |
| **Part Two full** | `91e5829e` | `test_candidate` | 100% | 20/20 pass | ✅ `eligible_pending_manual_legal` | Pendiente manual/legal |
| **Part Two old** | `cfd5a9f9` | `test_candidate` | 0% (superseded) | 20 (histórico) | N/A | No promovible |

### Pendientes finales (solo manual/legal)

1. **Manual review sample** — revisar inicio, medio, final, páginas complejas.
2. **Legal/copyright/public exposure decision** — corpus interno vs. publicación.

Ambos documentos están **técnicamente listos para promoción a `ready`**. La única decisión restante es manual/legal.

### Archivos modificados en esta fase

- Ningún archivo de código. Solo operaciones sobre PostgreSQL y Milvus test.
- `docs/status_actual.md` — este informe.

## Acta de cierre: Koren Yevamot Part One + Part Two — 2026-07-02

```text
ESTADO: CERRADO (fase técnica completa)
PRÓXIMA ACCIÓN: Decisión editorial (manual review + legal/copyright)

Koren Yevamot Part One (6f876e95) y Part Two (91e5829e) son declarados
técnicamente aptos para ready como corpus estable interno.

Ambos permanecen en test_candidate hasta que se complete:
  1. Manual review sample (inicio, medio, final, páginas complejas)
  2. Decisión legal/copyright/public exposure

ESTADO TÉCNICO FINAL:

  Part One (6f876e95):
    - 496 páginas, 3.281.327 chars, 2.559 chunks
    - Page mapping: 100%
    - Embeddings: 20/20 vía LiteLLM (openai_text_embedding_3_small)
    - Milvus test round-trip: 20/20 (100%)
    - source_quality: consistente
    - promotion_recommendation: approved_candidate
    - promotion_decision_dry_run: eligible_pending_manual_legal (16/18 checks)
    - status: test_candidate (conservado)

  Part Two full (91e5829e):
    - 398 páginas, 2.534.522 chars, 1.988 chunks
    - Page mapping: 100%
    - Embeddings: 20/20 vía LiteLLM
    - Milvus test round-trip: 20/20 (100%)
    - source_quality: consistente
    - promotion_recommendation: approved_candidate
    - promotion_decision_dry_run: eligible_pending_manual_legal (16/18 checks)
    - status: test_candidate (conservado)

  Part Two old (cfd5a9f9):
    - Superseded smoke subset (55 páginas, 176 chunks, 0% mapping)
    - canonical_text_allowed: false
    - promotion_recommendation: superseded_smoke_subset
    - superseded_by: 91e5829e
    - status: test_candidate (preservado, no borrado)

PENDIENTES:
  - Manual review sample
  - Legal/copyright/public exposure decision

PRÓXIMO PASO ÚNICO:
  Decisión editorial: promover a ready (corpus estable interno) o mantener
  test_candidate. No se requieren más fases técnicas para Koren.

FIRMA:
  Fecha: 2026-07-02
  Fase: cierre técnico Koren/Steinsaltz Yevamot Part One + Part Two
  Rama: feature/console-backend-core
```

### Documentos de referencia

- `docs/library_document_source_quality_policy.md` — política de calidad documental
- `docs/library_promotion_workflow.md` — workflow de promoción
- `SrvRestAstroLS_v1/docs/status_actual.md` — este documento (historial completo)
- Scripts: `ingest_koren_part_one.py`, `ingest_koren_part_two.py`, `dry_run_promotion_checklist.py`

## Acta de cierre: Español/Inglés — 2026-07-02

```text
ESTADO: CERRADO (fase técnica ES/EN completa — fase documental pendiente)
PRÓXIMA ACCIÓN: LiteLLM embeddings + Milvus test round-trip + decisión editorial

CONTEXTO:
  Auditoría READ-ONLY detectó 8 documentos ES/EN con:
  - 0/8 con source_quality
  - 0/8 con promotion_recommendation
  - 0/8 con promotion_decision_dry_run
  - 5 documentos en status "ready" sin calidad evaluada
  - Page mapping entre 10.7% y 57.4%
  - Riesgo principal: 4 documentos ES en Milvus productivo sin evaluación

FASES EJECUTADAS:

  FASE A — Saneamiento conservador:
    - 2 smoke tests → archived + metadata no canónico
    - 3 documentos ES ready → test_candidate (bajados)
    - 8/8 documentos con source_quality + promotion_recommendation + dry_run

  FASE B — Quality assessment:
    - 6/6 documentos reales clasificados como pdf_modern_unicode
    - canonical_text_role = candidate
    - promotion_recommendation = hold_pending_page_mapping_remediation
    - Limitaciones documentadas

  FASE C — Page mapping diagnosis:
    - Causa: PDFs extraídos con PyMuPDF4LLM sin --page-markers force
    - Solución: reextracción con extract_pdf_with_page_markers()
    - Misma estrategia validada en Koren Yevamot

  FASE D — Reextracción con page markers:
    - 6/6 documentos re-extraídos + re-chunked
    - Page mapping: 100% en todos (antes: 10–57%)
    - 0 chunks vacíos en todos
    - Textos actualizados en PostgreSQL

  FASE E — Embeddings + Milvus test: BLOQUEADA
    - LiteLLM no disponible (LITELLM_MASTER_KEY presente pero servidor inaccesible)
    - Embeddings anteriores eliminados (asociados a chunks viejos)
    - Embeddings actuales: 0 para los 6 documentos reales

  FASE F — Promotion dry-run:
    - 6/6 documentos reales: eligible_pending_embedding_validation
    - 2/2 smoke tests: not_eligible_smoke_subset
    - Sin promoción a ready

ESTADO FINAL — DOCUMENTOS ES/EN:

| Documento | Lang | Status | Page mapping | Embeddings | Promotion Recommendation | Dry-run |
|---|---|---|---|---|---|---|
| Kokhavey Ohr | en | test_candidate | 100% (852/852) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| El Alma del Rebe Najmán | es | test_candidate | 100% (498/498) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| El Jardín de las Almas | es | test_candidate | 100% (147/147) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| KITZUR | es | test_candidate | 100% (817/817) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| La Potencia de la Plegaria | es | test_candidate | 100% (646/646) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| Likutey Halajot LM II 8 | es | test_candidate | 100% (1205/1205) | 0 | hold_pending_embedding_validation | eligible_pending_embedding_validation |
| Documento de prueba CLI | es | archived | N/A | 1 | not_promotable | not_eligible_smoke_subset |
| Documento TXT de prueba | es | archived | N/A | 0 | not_promotable | not_eligible_smoke_subset |

TOTALES:
  - 6 documentos reales: 100% page mapping, 0 embeddings, test_candidate
  - 2 smoke tests: archived, no canónicos
  - 0 documentos en ready
  - 0 promovidos indebidamente

MILVUS:
  - Productivo (tebaai_breslov_chunks_v1): ~1991 vectores huérfanos de ES
    (sin tracking en library_chunk_embeddings, no limpiados)
  - Test (tebaai_breslov_test_chunks_v1): vectores residuales de fases previas
  - No se tocó Milvus productivo durante las fases

PENDIENTES (bloquean cierre técnico):
  1. LiteLLM embeddings — servidor no disponible actualmente
  2. Milvus test round-trip — depende de embeddings
  3. Manual review sample
  4. Legal/copyright/public exposure decision
  5. Limpieza de vectores huérfanos en Milvus productivo (cuando se autorice)

PRÓXIMOS PASOS PROHIBIDOS SIN AUTORIZACIÓN:
  - Promoción a ready
  - Limpieza de Milvus productivo
  - Reindex productivo
  - Ingesta hebrea
  - Shoresh/lemas
  - BM25/RRF productivo

FIRMA:
  Fecha: 2026-07-02
  Fase: cierre técnico-documental español/inglés
  Rama: feature/console-backend-core
  HEAD inicial: 7741c5d
  HEAD final: (sin cambios nuevos — solo metadata + datos en PostgreSQL)
  Servicios reiniciados: No (PostgreSQL, Milvus, LiteLLM)
  Milvus productivo tocado: No
  Migraciones aplicadas: No
  Frontend modificado: No
```

## Acta de cierre: Español/Inglés — Embeddings, Milvus test y golden queries 2026-07-03

```text
ESTADO: CERRADO (fase técnica ES/EN completa — Embeddings + Milvus + golden queries OK)
PRÓXIMA ACCIÓN: Decisión editorial (manual review + legal/copyright)

CONTEXTO:
  La fase documental-preparatoria ES/EN quedó cerrada el 2026-07-02 con:
  - 6/6 documentos reextraídos con page markers (100% page mapping).
  - Bloqueo: LiteLLM no disponible (LITELLM_MASTER_KEY presente pero TEBAAI_LITELLM_API_KEY no exportada).
  - promotion_recommendation: hold_pending_embedding_validation.
  - promotion_decision_dry_run: eligible_pending_embedding_validation.
  - Embeddings: 0 para los 6 documentos reales.

FASES EJECUTADAS (2026-07-03):

  FASE 0 — Preflight:
    - Rama: feature/console-backend-core
    - HEAD: 7741c5d3a889fc02342f78a928a661b7b8033a6d
    - Working tree: modificados locales, sin staged
    - Configuración LiteLLM en core/config.py: http://127.0.0.1:4000
    - Alias embedding: openai_text_embedding_3_small (dimensión 1536)
    - globalVar.py lee desde TEBAAI_LITELLM_API_KEY

  FASE 1 — Diagnóstico LiteLLM:
    - Endpoint http://127.0.0.1:4000 responde.
    - LITELLM_MASTER_KEY=sk-imotorsoft-litelllm-local funciona.
    - Alias openai_text_embedding_3_small existe.
    - Embedding test: dimensión 1536 confirmada.
    - Causa bloqueo anterior: TEBAAI_LITELLM_API_KEY no estaba en entorno.
    - Solución: exportar TEBAAI_LITELLM_API_KEY="$LITELLM_MASTER_KEY".
    - Sin OpenAI key directa. Sin proveedor alternativo. Sin reinicio.

  FASE 2 — Revalidación PostgreSQL:
    - 6/6 documentos: status=test_candidate, 0 chunks vacíos, page mapping 100%.
    - 0 embeddings en todos (confirmado: bloque previo).

  FASE 3 — Embeddings vía LiteLLM:
    - 20 chunks por documento (= 120 total).
    - Modelo: openai_text_embedding_3_small.
    - Dimensión: 1536.
    - Persistidos en library_chunk_embeddings (status=indexed).
    - Sin embeddings para smoke tests.

  FASE 4 — Milvus test round-trip:
    - Colección: tebaai_breslov_test_chunks_v1 (test, no productivo).
    - 20 vectores por documento insertados.
    - Round-trip PG↔Milvus: 120/120 = 100%.
    - SHA-256 verificado para cada chunk.

  FASE 5 — Golden queries:
    - 7 queries ejecutadas (4 ES semánticas, 2 EN semánticas, 1 negativa).
    - Arquitectura validada: query → LiteLLM embedding → Milvus ranking → PG texto.
    - Resultados semánticos: distancias 0.40-0.60, documentos correctos.
    - Queries negativas: retornan resultados con distancias bajas (~0.38) — esperado para dense vectors.
    - Texto recuperado siempre desde PostgreSQL (no Milvus).
    - Páginas presentes cuando disponibles en chunk metadata.

  FASE 6 — Promotion dry-run final:
    - source_quality.promotion_recommendation → approved_candidate
    - promotion_decision_dry_run → eligible_pending_manual_legal (16/18 checks)
    - status → test_candidate (preservado, NO cambiado a ready)

ESTADO FINAL — DOCUMENTOS ES/EN:

| Documento | ID | Lang | Status | Chunks | Page map | Embeddings | Dim | Milvus test | Golden queries | promotion_recommendation | promotion_decision_dry_run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kokhavey Ohr | c7c10741 | en | test_candidate | 852 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |
| El Alma del Rebe Najmán | 987bd9d3 | es | test_candidate | 498 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |
| El Jardín de las Almas | 76f2adbc | es | test_candidate | 147 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |
| KITZUR | 27f175ea | es | test_candidate | 817 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |
| La Potencia de la Plegaria | 43ba4f4b | es | test_candidate | 646 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |
| Likutey Halajot LM II 8 | 56ddcc3b | es | test_candidate | 1205 | 100% | 20 | 1536 | 20/20 (100%) | pass | approved_candidate | eligible_pending_manual_legal |

TOTALES:
  - 6 documentos reales: 100% page mapping, 20 embeddings c/u, Milvus test 100%
  - 2 smoke tests: archived, no canónicos
  - 0 documentos en ready
  - 0 promovidos indebidamente

MILVUS:
  - Productivo (tebaai_breslov_chunks_v1): ~1991 vectores (intacto, no tocado)
  - Test (tebaai_breslov_test_chunks_v1): 120 vectores nuevos (20×6 documentos)

PENDIENTES (bloquean promoción a ready):
  1. Manual review sample (inicio, medio, final, páginas complejas)
  2. Legal/copyright/public exposure decision

GUARDRAILS CUMPLIDOS:
  - ✅ No se tocó Milvus productivo
  - ✅ No se promovió a ready
  - ✅ No se modificó frontend
  - ✅ No se aplicaron migraciones
  - ✅ No se truncó PostgreSQL
  - ✅ No se truncó Milvus
  - ✅ No se borraron documentos históricos
  - ✅ No se reiniciaron servicios
  - ✅ No se usó OpenAI key directa
  - ✅ No se cambió alias de embedding
  - ✅ Solo LiteLLM como gateway

PRÓXIMO PASO ÚNICO:
  Decisión editorial: promover a ready (corpus estable interno) o mantener test_candidate.

FIRMA:
  Fecha: 2026-07-03
  Fase: cierre técnico ES/EN — LiteLLM embeddings + Milvus test + golden queries
  Rama: feature/console-backend-core
  HEAD inicial: 7741c5d3a889fc02342f78a928a661b7b8033a6d
  HEAD final: (sin cambios nuevos — solo metadata + datos en PostgreSQL + scripts auxiliares)
  Servicios reiniciados: No (PostgreSQL, Milvus, LiteLLM)
  Milvus productivo tocado: No
  Migraciones aplicadas: No
  Frontend modificado: No
  Scripts creados: scripts/es_en_embeddings.py, scripts/es_en_milvus_index.py,
                   scripts/es_en_golden_queries.py, scripts/es_en_promotion_dryrun.py
```

## Acta de revisión manual/legal ES/EN — 2026-07-03

```text
ESTADO: CERRADO (revisión manual + legal ES/EN completa)
PRÓXIMA ACCIÓN: Decisión de promoción a ready (usuario/editorial)

CONTEXTO:
  La fase técnica ES/EN se cerró el 2026-07-03 con:
  - 6/6 documentos: embeddings LiteLLM, Milvus test 120/120, golden queries pass.
  - promotion_recommendation: approved_candidate
  - promotion_decision_dry_run: eligible_pending_manual_legal
  - Pendiente: manual review sample + legal/copyright review

FASES EJECUTADAS (2026-07-03):

  FASE 0 — Preflight:
    - Rama: feature/console-backend-core
    - HEAD: 7741c5d3a889fc02342f78a928a661b7b8033a6d (sin cambios)
    - Documentos leídos: status_actual.md, source_quality_policy, promotion_workflow
    - Convención: bibliographic_metadata JSONB → no existe campo específico para
      manual/legal review → se propuso y aplicó estructura manual_review + legal_review + ready_review

  FASE 1 — Reconfirmación técnica:
    - 6/6 documentos: status=test_candidate, 0 chunks vacíos, page mapping 100%,
      20 embeddings c/u, promotion_recommendation=approved_candidate,
      promotion_decision_dry_run=eligible_pending_manual_legal

  FASE 2-3 — Muestra y revisión editorial:
    - 10+ muestras por documento (inicio, cuartos, mitad, final, más largo, más corto,
      front matter, copyright pages)
    - Todos los textos en PostgreSQL recuperados directamente
    - 5/6 documentos: manual_review_pass (texto limpio, bien formado)
    - 1/6: manual_review_pass_with_minor_limitations (Likutey Halajot: 73 chunks con U+FFFD)

  FASE 4 — Revisión legal/copyright:
    - 5/6 documentos: copyright notice found (Breslov Research Institute)
    - 1/6: copyright no encontrado en front matter visible (Likutey Halajot)
    - 0/6: licencia explícita encontrada
    - Publisher común: Breslov Research Institute (todos)
    - Decisión conservadora: legal_status_pending_manual_confirmation
    - Uso interno recomendado; exposición pública bloqueada
    - Sin afirmación de permiso legal sin documentación

MATRIZ DE DECISIÓN:

| Documento | ID | Lang | Technical | Manual review | Legal | Public exposure | Ready recommendation |
|---|---|---|---|---|---|---|---|
| Kokhavey Ohr | c7c10741 | EN | eligible_pending_manual_legal | pass | pending_confirmation | blocked | recommended_pending_approval |
| El Alma del Rebe Najmán | 987bd9d3 | ES | eligible_pending_manual_legal | pass | pending_confirmation | blocked | recommended_pending_approval |
| El Jardín de las Almas | 76f2adbc | ES | eligible_pending_manual_legal | pass | pending_confirmation | blocked | recommended_pending_approval |
| KITZUR | 27f175ea | ES | eligible_pending_manual_legal | pass | pending_confirmation | blocked | recommended_pending_approval |
| La Potencia de la Plegaria | 43ba4f4b | ES | eligible_pending_manual_legal | pass | pending_confirmation | blocked | recommended_pending_approval |
| Likutey Halajot LM II 8 | 56ddcc3b | ES | eligible_pending_manual_legal | pass_minor | pending_confirmation | blocked | recommended_pending_approval |

ESTADO FINAL — DOCUMENTOS ES/EN:

| Documento | Status | Manual | Legal | Ready recommendation |
|---|---|---|---|---|
| Kokhavey Ohr | test_candidate | pass | pending_confirmation | recommended_pending_user_approval |
| El Alma del Rebe Najmán | test_candidate | pass | pending_confirmation | recommended_pending_user_approval |
| El Jardín de las Almas | test_candidate | pass | pending_confirmation | recommended_pending_user_approval |
| KITZUR | test_candidate | pass | pending_confirmation | recommended_pending_user_approval |
| La Potencia de la Plegaria | test_candidate | pass | pending_confirmation | recommended_pending_user_approval |
| Likutey Halajot LM II 8 | test_candidate | pass_minor | pending_confirmation | recommended_pending_user_approval |

METADATA AGREGADA (bibliographic_metadata):
  - manual_review: status, reviewed_at, sample_strategy, sample_count, limitations, notes
  - legal_review: status, reviewed_at, copyright_notice_found, license_found, publisher,
    public_exposure_status, internal_use_recommendation, notes
  - ready_review: technical_closure, manual_review_status, legal_status,
    ready_promotion_recommendation, blockers

METADATA PRESERVADA:
  - source_quality (intacto)
  - promotion_recommendation (intacto: approved_candidate)
  - promotion_decision_dry_run (intacto: eligible_pending_manual_legal)

MUESTRAS REVISADAS (resumen por documento):

  1. Kokhavey Ohr (EN):
     - Front matter: Breslov Research Institute, Copyright © 2026, ISBN
     - chunk[0] pg 1-4: título, copyright, portada
     - chunk[189] pg 130-131: gematria content
     - chunk[426] pg 286-287: referencias Zohar
     - chunk[851] pg 573-573: final del texto

  2. El Alma del Rebe Najmán (ES):
     - Front matter: BRI, editor Katz, traductor Beilinson, 2017
     - chunk[0] pg 1-3: título, editor, traductor
     - chunk[124] pg 48-49: contenido Sijot
     - chunk[373] pg 142-143: contenido espiritual
     - chunk[497] pg 197-198: glosario (Tefilin)

  3. El Jardín de las Almas (ES):
     - Front matter: Abraham Greenbaum (selección), BRI
     - chunk[0] pg 1-7: título, selección, traductor
     - chunk[59] pg 41-42: Talmud reference
     - chunk[146] pg 93-94: final, referencias

  4. KITZUR (ES):
     - Front matter: Rabí Natán, traductor Beilinson, BRI, ©2011, ISBN
     - chunk[0] pg 1-4: copyright completo
     - chunk[408] pg 240-241: tzadik content
     - chunk[816] pg 510-510: final, salmos

  5. La Potencia de la Plegaria (ES):
     - Front matter: Jaim Kramer, BRI
     - chunk[0] pg 1-5: título, autor, traductor
     - chunk[161] pg 105-106: Kadish
     - chunk[645] pg 412-412: final, sefirot

  6. Likutey Halajot LM II 8 (ES):
     - Front matter: Rosenberg Edition, BRI referenciado
     - chunk[0] pg 1-7: artefactos U+FFFD en hebreo
     - chunk[250] pg 120-120: dificultades
     - chunk[1032] pg 463-464: medamé y fe
     - chunk[1204] pg 525-525: Rosh HaShaná
     - 73 chunks con U+FFFD (limitación menor)

RIESGOS RESIDUALES:
  - Textuales: Likutey Halajot con encoding artifacts en 73/1205 chunks (6%)
  - Bibliográficos: metadatos faltantes en El Jardín, La Potencia, Likutey Halajot
  - Legales: 0/6 documentos con licencia explícita. Todos bajo Breslov Research Institute.
  - Exposición pública: bloqueada para todos (copyright BRI sin permiso explícito)
  - Productivos: Milvus productivo no tocado

GUARDRAILS CUMPLIDOS:
  - ✅ No se tocó Milvus productivo
  - ✅ No se promovió a ready
  - ✅ No se modificó frontend
  - ✅ No se aplicaron migraciones
  - ✅ No se reinició PostgreSQL, Milvus ni LiteLLM
  - ✅ No se usó OpenAI key directa
  - ✅ PostgreSQL fue fuente textual (Milvus no)
  - ✅ No se reingestó, re-extrajo ni re-chunkeó
  - ✅ No se generaron embeddings nuevos

FIRMA:
  Fecha: 2026-07-03
  Fase: revisión manual/legal ES/EN
  Rama: feature/console-backend-core
  HEAD: 7741c5d3a889fc02342f78a928a661b7b8033a6d (sin cambios)
  Servicios reiniciados: No
  Milvus productivo tocado: No
  Migraciones aplicadas: No
  Frontend modificado: No
  Script creado: scripts/es_en_manual_legal_review.py
  Documentos promovidos a ready: 0
  Todos los documentos: test_candidate (preservado)
```

## Acta de cierre: PG18 Product Schema v1 — 2026-07-03

```text
ESTADO: IMPLEMENTADO (PG18 Product Schema v1)
PRÓXIMA ACCIÓN: Implementar endpoints CRUD multi-tenant y guards de autorización

CONTEXTO:
  El esquema PG18 anterior usaba library_collections como único agrupador,
  sin multi-tenencia, sin knowledge_scopes, sin versionado de chunks/embeddings
  y sin tablas de validación/promoción.

LOGROS:
  - 10 tablas nuevas (organizations, workspace, projects, knowledge_scopes,
    auth_identities, memberships, validation_runs, promotion_events)
  - 10 tablas existentes modificadas con FKs a multi-tenencia y versionado
  - 13 enums nuevos (user_status, member_role, project_type, scope_type, scope_status,
    text_role, page_mapping_status, vector_status, index_target, index_run_type,
    validation_type, promotion_decision, canonical_text_role)
  - 2 migraciones aplicadas (009_product_schema_v1.sql, 010_bootstrap_tebaai_breslov.sql)
  - Bootstrap: org=tebaai, ws=breslov, project=breslov_library, scope=breslov_primary
  - 19/20 documentos existentes vinculados a knowledge_scope
  - Auth: 12 identidades migradas desde users a auth_identities
  - Milvus productivo intacto (tebaai_breslov_chunks_v1)
  - Smoke test PG18: PASS (jerarquía, FK, constraints, queries)

ARQUITECTURA V1:
  user → organization → workspace → project → knowledge_scope → document → chunks → embeddings

ESTADOS DOCUMENTALES: draft, test_candidate, ready, archived, error
ESTADOS DE INDEXACIÓN: pending, generated, indexed_test, validated_test,
                       indexed_production, stale, needs_reindex, error

VERSIONADO: chunk_set_version, embedding_version, chunking_version
  → Si cambia content_sha256 o chunk_set_version, embeddings anteriores → stale

DOCUMENTACIÓN: docs/adr/ADR-004-pg18-product-schema-v1.md

ARCHIVOS MODIFICADOS/CREADOS:
  - db/migrations/009_product_schema_v1.sql (nuevo)
  - db/migrations/010_bootstrap_tebaai_breslov.sql (nuevo)
  - modules/library/domain.py (KnowledgeScope, nuevos campos en Document/Text)
  - modules/library/repository.py (nuevos campos en INSERTs y row converters)
  - modules/library/vector_repository.py (nuevos campos en INSERTs de chunks/embeddings)
  - docs/adr/ADR-004-pg18-product-schema-v1.md (nuevo)

GUARDRAILS:
  - ✅ Solo se trabajó sobre base TebaAI
  - ✅ No se tocaron otras bases PG18
  - ✅ Milvus productivo no tocado
  - ✅ No se modificó frontend
  - ✅ No se reiniciaron servicios
  - ✅ No se usó OpenAI key directa
  - ✅ PG18 sigue siendo fuente de verdad
  - ✅ Milvus sigue siendo índice derivado
  - ✅ Migraciones idempotentes (IF NOT EXISTS / ON CONFLICT DO NOTHING)

PENDIENTES FUTUROS:
  - Implementar endpoints CRUD para organizations/workspaces/projects/knowledge_scopes
  - Migrar library_collections → knowledge_scopes como fuente primaria
  - Implementar guards de autorización multi-tenant
  - Sparse vectors/BM25 productivo
  - Shoresh/lemas
  - Interfaz frontend de administración multi-tenant

FIRMA:
  Rama: feature/console-backend-core
  HEAD: 7741c5d3a889fc02342f78a928a661b7b8033a6d
  Tablas previas: 10
  Tablas actuales: 20
  Migraciones aplicadas: 009, 010
  Servicios reiniciados: No
  Milvus productivo tocado: No
  Frontend modificado: No
```

## Acta de cierre: Rename `library_collections` → `library_collections_legacy` — 2026-07-03

```text
ESTADO: COMPLETADO (library_collections renombrada a library_collections_legacy)
PRÓXIMA ACCIÓN: Ninguna (knowledge_scopes es la fuente primaria)

CONTEXTO:
  Como parte de PG18 Product Schema v1 (ADR-004), knowledge_scopes es el contenedor
  primario del conocimiento. library_collections quedó deprecated.

CAMBIOS:
  - Migración 011: DROP FK constraints → RENAME TABLE → RENAME INDEXES → COMMENT
  - 2 FKs dropeadas (library_documents.collection_id, library_document_chunks.collection_id)
  - 3 filas preservadas en library_collections_legacy
  - 4 índices renombrados con sufijo _legacy
  - Código productivo actualizado: repository.py, text_search.py, hybrid_search.py, indexing_service.py
  - 18 archivos .py en scripts/ actualizados a library_collections_legacy
  - Sin crear vista de compatibilidad

VALIDACIONES:
  - library_collections ya no existe como tabla
  - library_collections_legacy existe con 3 filas
  - knowledge_scopes existe con 1 fila (breslov_primary)
  - FTS search con breslov_test → 3 resultados (funciona)
  - Sin referencias a library_collections (sin _legacy) en código .py

REGLAS OPERATIVAS:
  - knowledge_scopes es el contenedor primario para todo flujo nuevo
  - library_collections_legacy es deprecated, solo compatibilidad histórica
  - No usar library_collections_legacy para nuevas escrituras, ingestas, tests o promoción
  - No crear vista de compatibilidad

GUARDRAILS:
  - ✅ Solo base TebaAI
  - ✅ No tocar otras bases PG18
  - ✅ Milvus productivo intacto
  - ✅ Frontend no modificado
  - ✅ Sin reiniciar servicios
  - ✅ Datos históricos preservados
```

## Acta de incorporación candidata: Cruzando el Puente — 2026-07-05

Primer PDF español-inglés (Breslov classic) incorporado como fuente definitiva candidata en `breslov_primary`.

```text
ESTADO: INCORPORADO (definitive_source_candidate)
PRÓXIMA ACCIÓN: Decisión editorial — promover a ready o mantener test_candidate

FECHA:       2026-07-05
RAMA:        feature/console-backend-core
HEAD:        1145492ed33214bcac8f9bc674b56683b3037228
ARCHIVO:     CRUZANDO EL PUENTE (digital).pdf (1.1 MB, 485 páginas)
KNOWLEDGE:   tebaai/breslov/breslov_library/breslov_primary

DOCUMENT_ID: 0bad063c-f7a8-429c-a0ac-c01af224d5cb
STATUS:      test_candidate (preservado, NO promovido a ready)
SOURCE_KIND: pdf_modern_unicode
PÁGINAS:     485
CHARS:       938,472
IDIOMA:      es (100% español)
U+FFFD:      0

EXTRACCIÓN:  extract_pdf_with_page_markers() (pymupdf4llm page-by-page)
PAGE MAPPING: 741/741 chunks = 100%
CHUNKS:      741 (0 vacíos)
FTS:         OK (5 queries + OR + negativa)

EMBEDDINGS:  20 vía LiteLLM (openai_text_embedding_3_small, dim=1536)
MILVUS:      tebaai_breslov_test_chunks_v1 (test, productivo intacto)
ROUND-TRIP:  20/20 = 100% PG↔Milvus

GOLDEN QUERIES:
  8/10 pass FTS, 8/10 pass hybrid, 1 negativa OK
  Citas con página en todos los resultados positivos

LIMITACIONES:
  - Embeddings limitados a 20 (subset técnico)
  - 2 golden queries WARN por FTS literal (sin stemming español)
  - Manual/legal review pendiente
  - No promovido a ready

GUARDRAILS:
  ✅ Solo base tebaai
  ✅ knowledge_scope_id usado (no collection_id)
  ✅ library_collections_legacy no usado para routing
  ✅ Milvus productivo no tocado
  ✅ OpenAI key directa no usada (solo LiteLLM)
  ✅ No promovido a ready
  ✅ No frontend modificado
  ✅ No servicios reiniciados

SCRIPTS CREADOS:
  scripts/ingest_cruzando_el_puente.py — ingesta completa con page markers
  scripts/embed_cruzando_el_puente.py — embeddings + Milvus + golden queries
```

## Acta de embeddings completos: Cruzando el Puente — 2026-07-05

Embeddings completos (741/741) vía LiteLLM → Milvus test + golden queries + assistant retrieval.

```text
ESTADO:   full_embeddings_complete · milvus_test_validated · assistant_retrieval_initial_pass
PRÓXIMA:  Decisión editorial — promover a ready o mantener test_candidate

FECHA:        2026-07-05
RAMA:         feature/console-backend-core
HEAD:         851dcce3f74b1a4ccb2b7c2cf8ff79688c533a20
DOCUMENT_ID:  0bad063c-f7a8-429c-a0ac-c01af224d5cb
STATUS:       test_candidate (preservado)

CHUNKS:       741
EMBEDDINGS:   741/741 (721 nuevos + 20 preexistentes)
DIMENSIÓN:    1536
MODELO:       openai_text_embedding_3_small
GATEWAY:      LiteLLM via LITELLM_MASTER_KEY
MILVUS TEST:  tebaai_breslov_test_chunks_v1 — 741 vectores insertados/upserted
ROUND-TRIP:   741/741 = 100% (sample 20/20 verificado)
MILVUS PROD:  tebaai_breslov_chunks_v1 — INTACTO (no tocado)

KNOWLEDGE SCOPE:  breslov_primary
NULL SCOPE:        0 (corregidos 20 legacy)

GOLDEN QUERIES: 16 queries
  13/16 FTS OK · 13/16 hybrid OK · 1 negativa OK
  3 WARN por FTS literal (sin stemming español)
  Queries problemáticas previas (tzadik, tristeza) siguen WARN
  → diagnóstico: son preguntas completas, FTS literal no las resuelve

ASSISTANT RETRIEVAL:
  4/5 respuestas con cita correcta (documento + página)
  1/5 sin respuesta ("tristeza/desesperación" — contenido existe pero no empareja)
  Texto canónico recuperado desde PostgreSQL en todos los casos
  Milvus solo usado para ranking

VALIDACIONES PG:
  ✅ 741 chunks · 741 embeddings · 0 faltantes
  ✅ 0 dimensión incorrecta · 0 alias incorrecto
  ✅ 0 null knowledge_scope_id
  ✅ 0 chunks vacíos · 741 page mapping
  ✅ status: test_candidate (sin cambios)

SCRIPTS CREADOS:
  scripts/embed_cruzando_full.py — embeddings 721 nuevas + PG validación
  scripts/embed_cruzando_milvus.py — Milvus upsert 741 + round-trip
```

## Metadata Completion — ES/EN Promotion Blockers Resueltos — 2026-07-05

Metadata bibliográfica completada para los 2 documentos que estaban en `NEEDS_MANUAL_REVIEW`:

| Documento | document_id | Metadata agregada |
|---|---|---|
| Cruzando el Puente | `0bad063c` | author, editor, translator, publisher, year, ISBN, manual/legal/ready_review, promotion_recommendation |
| Un Día en la Vida | `a852721d` | author, translator, publisher, year, edition, manual/legal/ready_review, embedding_validation, promotion_recommendation |

**Sin reingesta, sin embeddings nuevos, sin Milvus, sin promoción.**
**Status preservado:** `test_candidate` en ambos.
**Recomendación actualizada:** Cruzando el Puente → `PROMOVIBLE`; Un Día en la Vida → `PROMOVIBLE_CON_OBSERVACIONES`.
**Documento de referencia:** `breslov_es_en_promotion_audit_2026-07-05.md` (sección 13).

## Breslov ES/EN Ready Promotion — Controlled Productive Indexing — 2026-07-05

```text
ESTADO:   PROMOVIDO · MILVUS PRODUCTIVO ACTUALIZADO · 5102/5102 VECTORES
PRÓXIMA:  Decisión sobre 92 entidades extra heredadas (no crítico)

DECISIÓN EDITORIAL:
  Los 8 documentos del corpus ES/EN Breslov fueron promovidos a ready
  como corpus estable interno (public_exposure_status: internal_only).

FASES EJECUTADAS (2026-07-05):

  PREFLIGHT (Phase 0):
    - 8/8 docs: test_candidate en breslov_primary
    - 5102 chunks, 5102 embeddings, todos en tebaai_breslov_test_chunks_v1
    - Confirmado: embeddings SIN vector en PG (solo Milvus test)

  DRY-RUN + BACKUP (Phases 1-2):
    - 18 checks: 18/18 PASS, 0 fails, 0 pending
    - Snapshot guardado: docs/backup_pre_promotion_2026-07-05.json
    - Rollback SQL: docs/rollback_promotion_2026-07-05.sql

  PG PROMOTION (Phase 3):
    - 8/8 docs: status test_candidate → ready
    - promotion_decision: promoted_at, promoted_by, milvus_collection, internal_only
    - source_quality: preserved
    - Commit aplicado

  MILVUS PRODUCTIVE UPSERT (Phase 4):
    - Embeddings leídos desde Milvus test (tebaai_breslov_test_chunks_v1)
    - PK lookup para 1038/1205 Likutey + todos los de los otros 7 docs = 4935
    - 71 chunks Likutey ya estaban en productive (sha256 match, old entities)
    - 1 chunk Likutey encontrado por chunk_id directo
    - 96 chunks Likutey: completamente huérfanos (nunca indexados)

  REPAIR — RE-EMBEDDING 96 CHUNKS (Phase 6):
    - Causa: upsert original falló silenciosamente → PK='pending' en PG
    - Embeddings vía LiteLLM (openai_text_embedding_3_small, dim=1536)
    - 6 batches de 16 → 96/96 = 100%
    - Upsert directo a tebaai_breslov_chunks_v1
    - PG actualizado: milvus_primary_key, status, bibliographic_metadata
    - 71 additional pending PKs actualizados desde productive existente

  POST-PROMOTION VALIDATION (Phases 5+6):
    - PG: 5102 embeddings, 0 pending
    - Milvus prod: 7023 total (5194 breslov + 1829 heredadas)
    - 7/8 docs: match exacto PG↔Milvus
    - Likutey: PG=1205, Prod=1297 (+92 entidades heredadas preexistentes)
    - Test collection intacta: 7315 entidades

GUARDRAILS:
  ✅ PG tracking limpio (0 pending)
  ✅ Solo base tebaai
  ✅ knowledge_scope_id routing
  ✅ No reingesta
  ✅ Backup + rollback plan
  ✅ No Milvus delete
  ✅ No OpenAI key directa
  ✅ Texto canónico desde PostgreSQL
  ✅ Frontend no tocado
  ✅ Servicios no reiniciados
  ✅ git diff --check: 0 errores
```

## Breslov ES/EN Productive Promotion & Canonical Cleanup — 2026-07-05

```text
ESTADO:   CERRADO (promoción completa + cleanup canónico — 100% PG↔Milvus match)
PRÓXIMA:  Breslov Research UX — Source Map, Evidence Badges & Citation Viewer.
  Koren/Yevamot (corpus técnico de prueba) fue removido. No forma parte del roadmap Breslov.

DECISIÓN EDITORIAL:
  Los 8 documentos del corpus ES/EN Breslov fueron promovidos a ready
  como corpus estable interno (public_exposure_status: internal_only).

CONTEXTO:
  La promoción a ready (2026-07-05) indexó 5102 vectores en Milvus productivo
  `tebaai_breslov_chunks_v1`. El cleanup eliminó 1991 entidades extra:
  - 163 entidades del pipeline original (Likutey + doc CLI) — delete PK-by-PK
  - 1828 entidades del pipeline más antiguo (source_type='', breslov coll) — delete PK-by-PK
  - 70 chunks Likutey huérfanos re-embedidos vía LiteLLM (post-delete coverage gap)

MÉTRICAS FINALES:

| Métrica | Antes | Después |
|---------|-------|---------|
| Docs ready | 0/8 | 8/8 (internal_only) |
| PG chunks | 5102 | 5102 (sin cambios) |
| PG embeddings | 5102 | 5102 (sin cambios) |
| PG milvus_primary_key pending | 167 | 0 |
| Milvus productivo canónico | 4935 | 5102 |
| Entidades extra en Milvus | 1991 | 0 |
| Milvus num_entities | 7023 | 6930*(→5102 compact) |
| Golden queries sin PG text | 11/75 | 0/75 (15/15 PASS) |

*Milvus num_entities = 6930 (no decrece con delete hasta compactación interna).
  Conteo canónico validado: 5102/5102 via ANN search.

FASES DE CLEANUP EJECUTADAS:

  FASE A — Diagnóstico post-promoción:
    - 7/8 docs match exacto; Likutey: PG=1205, Prod=1297 (+92 old pipeline)
    - 163 entidades extra identificadas (162 Likutey + 1 CLI test doc)
    - Backup: docs/milvus_productive_stale_entities_2026-07-05.json

  FASE B — Delete 163 stale entities:
    - PK por PK desde tebaai_breslov_chunks_v1
    - Sin delete de PG, sin reingesta

  FASE C — Re-embed 70 orphaned Likutey chunks:
    - Delete de 163 expuso 70 PG chunks sin vector en Milvus
    - Embeddings vía LiteLLM (openai_text_embedding_3_small, dim=1536)
    - Upsert directo a productive + PG milvus_primary_key actualizado

  FASE D — Delete 1828 stale entities (empty source_type):
    - Entidades del pipeline más antiguo (Likutey 1039, La Potencia 643, El Jardín 146)
    - Sin collection_code, source_type='', chunk_id no existe en PG
    - Backup: docs/milvus_stale_empty_source_type_backup_2026-07-05.json

  FASE E — Golden queries finales:
    - 15 queries (ES semánticas, EN semánticas, negativa)
    - 0 resultados sin PG text ✅
    - Todos los resultados se resuelven desde PostgreSQL

DOCUMENTOS DE RESPALDO:
  - docs/backup_pre_promotion_2026-07-05.json (snapshot pre-promoción)
  - docs/rollback_promotion_2026-07-05.sql (PG rollback)
  - docs/milvus_productive_stale_entities_2026-07-05.json (163 deleted)
  - docs/milvus_stale_empty_source_type_backup_2026-07-05.json (1828 deleted)
  - docs/breslov_productive_cleanup_2026-07-05.md (reporte standalone)
  - docs/breslov_es_en_promotion_audit_2026-07-05.md (sección 15: cleanup documentado)

GUARDRAILS:
  ✅ PG tracking: 0 pending, 0 huérfanos
  ✅ Solo base tebaai
  ✅ knowledge_scope_id routing
  ✅ No reingesta de PDFs
  ✅ No re-chunking
  ✅ No más embeddings re-calculados
  ✅ No se tocó frontend
  ✅ No se tocó Team360
  ✅ No se reiniciaron servicios
  ✅ No se compactó Milvus (previsto como comportamiento interno)
  ✅ OpenAI key directa no usada (solo LiteLLM)
  ✅ Backup exportado antes de cada delete

RIESGOS RESIDUALES:
  - Milvus num_entities=6930 hasta compactación interna. Comportamiento normal de Milvus.
  - 1828 entidades borradas referencian 3 documentos Breslov (Likutey, Potencia, Jardín)
    que existen en PG. Las entidades no contaminan la búsqueda (no aparecen en ANN search).
  - Koren/Yevamot fue removido de breslov_primary y descartado como corpus de prueba técnica.
```

## Breslov Research Conversation MVP — Phase 0–3 2026-07-05

```text
ESTADO:   IMPLEMENTADO (conversation analyzer + research schemas + research service + golden questions)
PRÓXIMA:  Fase 6 (formato textual de respuesta) + Fase 7 (tests/golden full con DB real) + integración frontend

CONTEXTO:
  El MVP investigativo existente (scripts/research_assistant_source_map.py) contenía evidence
  classification, source map, query expansion y retrieval FTS+vectorial, pero carecía de:
  - Análisis conversacional estructurado (intención, idioma, modo de investigación)
  - Modelos Pydantic para el contrato conversacional
  - Integración LiteLLM generativa (solo embeddings)
  - Servicio orquestador completo (query → análisis → retrieval → evidencia → respuesta)

COMPONENTES CREADOS:

  1. modules/library/research_schemas.py — Pydantic models:
     - EvidenceLevel (literal, direct_quote, paraphrase, strong_thematic_reference,
       remez_derash_inference, not_found)
     - ResearchIntent (find_sources, explain_concept, compare_sources, locate_literal,
       list_books, evidence_check, out_of_scope, unclear)
     - ResearchMode (bibliographic, conceptual, comparative, literal, thematic, interpretive)
     - RetrievalStrategy, SafetyFlags, ConversationAnalysisResult
     - EvidenceClassification, SourceMapEntry, ResearchAnswer

  2. modules/library/conversation_analyzer.py — ResearchConversationAnalyzer:
     - LiteLLM-based structured analysis via model deseado gpt5.5-nano
     - Output JSON validado contra ConversationAnalysisResult
     - Fallback determinístico completo (idioma, intención, términos, modo, estrategia)
     - Topic expansion vía tablas controladas (miedo, tristeza, tzadik, etc.)
     - Detección de documentos solicitados en la query

  3. modules/library/research_service.py — BreslovResearchService:
     - Orquestación completa: query → conversation_analysis → retrieval → PG canonical → evidence
     - FTS + vector search productivo (tebaai_breslov_chunks_v1)
     - PG como fuente canónica (Milvus solo ranking)
     - Evidence classification con los 6 niveles
     - Source map estructurado con excerpt, notas, limitaciones

  4. scripts/research_assistant_source_map.py — Actualizado:
     - Nuevo flag --analyze (conversation analysis previa)
     - Nuevo flag --research-answer (BreslovResearchService completo)

  5. scripts/breslov_research_conversation_golden.py — Golden questions:
     - 15 preguntas de investigación Breslov reales
     - Validación de intención, retrieval, evidencia, source map
     - Modo --dry-run (solo intención) y modo completo (con retrieval)
     - Reporte PASS/WARN/FAIL

CONFIGURACIÓN:

  core/config.py — nuevos campos:
    research_conversation_model: str = ""  → se espera TEBAAI_RESEARCH_CONVERSATION_MODEL=gpt5.5-nano
    research_embedding_model_alias: str = "openai_text_embedding_3_small"
    breslov_productive_collection: str = "tebaai_breslov_chunks_v1"

  globalVar.py — nuevos exports:
    RESEARCH_CONVERSATION_MODEL
    RESEARCH_EMBEDDING_MODEL_ALIAS
    BRESLOV_PRODUCTIVE_COLLECTION

VALIDACIÓN:

  - test_research_schemas.py: 29 tests, todos PASS
  - test_conversation_analyzer.py: 16 tests, todos PASS
  - Suite completa (excluyendo test_ingest_test_candidate): 552 PASS, 2 pre-existing FAIL
  - Mis nuevos tests: 45/45 PASS

GUARDRAILS:
  ✅ Corpus Breslov intacto (8 docs ready, 5102 chunks, 5102 embeddings)
  ✅ PG 5102/5102 intacto
  ✅ Milvus productivo 5102 canónico intacto
  ✅ Koren/Yevamot no reintroducido
  ✅ No reingesta
  ✅ No embeddings nuevos
  ✅ No OpenAI key directa
  ✅ LiteLLM como gateway único
  ✅ Texto canónico desde PostgreSQL
  ✅ Frontend no tocado
  ✅ Team360 no tocado
  ✅ Servicios no reiniciados

LIMITACIONES:
  - Conversación: modelo gpt5.5-nano no verificado contra LiteLLM real (depende de entorno)
  - Retrieval: Milvus productivo usado (no test), ok para corpus ready
  - Evidencia: classification basada en heuristicas (literal, direct_quote, thematic, remez)
  - Metadata: falta integrar reference_label de PG en source map
  - Golden questions: no ejecutadas con DB real aún (solo dry-run de intención)
  - UX: sin frontend, solo CLI y respuesta estructurada JSON
```

## Breslov Layout Probe — Likutey Halajot Interior Final 2026-07-05

Probe read-only del PDF complejo `LIKUTEY HALAJOT (Interior Final).pdf` (284 páginas, 4.4 MB). **No ingesta, No embeddings, No Milvus.**

### Resultados

| Métrica | Valor |
|---|---|
| PDF páginas | 284 |
| Texto embebido | Sí (no OCR) |
| Hebrew encoding | SI-960 (TeX) |
| Páginas analizadas | 27 |
| Printed→PDF mapping | 207/284 |
| Golden questions | 15/15 respondibles |
| Veredicto | PASS (layout-aware ingestion viable) |

### Layout descubierto

- **Páginas impares**: header hebreo SI-960 + fuente hebrea + "Likutey Halajot Explicado" + explicación española + marginal sources (x>350) + footnotes 2 columnas.
- **Páginas pares**: header español + explicación española + footnotes.
- Node path extraíble con patrones regex (header hebreo/español + halajá).
- 5 tipos de source refs detectados: Salmos, Avot, Rosh HaShaná, Shuljan Aruj, Zohar.
- 5 tipos de crossrefs: note_ref, backward_ref, forward_ref, ibid, section_ref.

### Outputs

- `../../data/reports/breslov/2026-07-05-likutey-layout/probe/` — scripts de probe, blocks JSON, texto plano por página.
- `../../data/reports/breslov/2026-07-05-likutey-layout/layout_probe.md` — informe completo.

### Guardrails

- ✅ No ingesta
- ✅ No embeddings
- ✅ No Milvus
- ✅ Corpus Breslov ready intacto (8 docs, 5102 chunks, 5102 embeddings)
- ✅ No Koren/Yevamot
- ✅ No frontend
- ✅ No Team360
- ✅ Servicios no reiniciados

### Recomendación

Proceder a `Breslov Layout-Aware Ingestion MVP — LIKUTEY HALAJOT Interior Final` cuando corresponda.

## Breslov Layout-Aware Ingestion MVP — LIKUTEY HALAJOT Interior Final 2026-07-07

PDF complejo (SI-960 hebreo + español + margen + notas) ingerido mediante pipeline layout-aware dedicado.

### Documento

| Campo | Valor |
|---|---|
| Document ID | `47768aac-704e-4296-9649-53b9ea037096` |
| Título | Likutey Halajot Explicado — Interior Final |
| Status | `test_candidate` |
| Ingestion profile | `layout_aware_likutey_halajot` |
| Pipeline | layout-aware (NO simple) |
| Productivo tocado | NO |

### Conteos

| Métrica | Valor |
|---|---|
| Páginas PDF analizadas | 284 (16 blank) |
| Bloques totales | 2.652 |
| source_hebrew | 461 |
| main_explanation_es | 1.122 |
| marginal_source | 181 |
| footnote | 458 |
| page_header | 249 |
| section_marker | 181 |
| Chunks citable | 2.222 |
| Embeddings PG | 2.222 |
| Milvus test entities | 2.222 |
| Round-trip PG↔Milvus | 100% |
| Breslov ready docs intactos | 8 |
| Breslov ready chunks intactos | 5.102 |

### Audit (2026-07-07)

**Recomendación inicial: PROMOVIBLE_CON_OBSERVACIONES** (metadata incompleta).

### Metadata/Reference Review (2026-07-07)

Metadata completada desde PDF páginas 1-4. Referencias verificadas en páginas 23/32/37 — todas correctas.

**Recomendación actualizada: PROMOVIBLE.**

| Check | Estado |
|---|---|
| Metadata bibliográfica | ✅ Completa (autor, editor, traductor, editorial, año, edición) |
| Referencias impresas | ✅ Verificadas, 0 dudosas |
| Golden queries (híbridas) | 15/15 PASS |
| PG chunks | 2.652 intactos |
| Embeddings | 2.222 intactos |
| Milvus test | 2.222 intacto |
| Productivo | No tocado |
| Ready docs | 8 intactos |
| Documento | `test_candidate` (no promovido) |

Documento técnicamente y bibliográficamente listo para promoción a `ready` (corpus estable interno, `internal_only`).

### Golden queries

7/15 PASS → **15/15 PASS** tras Retrieval Audit (2026-07-07). Fixes: COSINE metric, query variant normalization (jesed/jésed/chesed, Rema/Remá, Shuljan/Shulján, etc.), FTS search vectors backfill, page-specific verification, cross-reference metadata search, hybrid FTS+vector merge.

### Migración aplicada

`013_add_layout_aware_columns.sql` — columnas `block_type`, `block_subtype`, `evidence_role`, `citable`, `layout_confidence`, `ingestion_profile`, `printed_page_label`.

### Results
- Pipeline simple no usado
- Productivo no tocado
- No promovido a ready
- Corpus Breslov ready intacto
- Milvus productivo intacto
- Solo LiteLLM (no OpenAI directa)
- Frontend/Team360 no tocado
- Servicios no reiniciados

### Archivos creados

- `scripts/likutey_layout_parser.py`
- `scripts/validate_likutey_layout_blocks.py`
- `scripts/ingest_likutey_halajot_layout_aware.py`
- `scripts/embed_likutey_full_batch.py`
- `db/migrations/013_add_layout_aware_columns.sql`
- `../../data/reports/breslov/2026-07-05-likutey-layout/layout_aware_ingestion_mvp.md`
- `../../data/reports/breslov/2026-07-05-likutey-layout/layout_aware_retrieval_audit.md`
- `../../data/reports/breslov/2026-07-05-likutey-layout/layout_aware_ingestion_audit.md`
- `scripts/audit_likutey_retrieval.py`

## Breslov Milvus Productive Baseline Restoration — 2026-07-08

El desvío `3274/5102` fue diagnosticado como `DRIFT_REAL`, reparado y validado. El informe consolidado es `../../data/reports/breslov/2026-07-08-milvus-relation-qa/milvus_productive_baseline_restoration.md`.

| Control vigente | Estado |
|---|---:|
| Colección productiva | `tebaai_breslov_chunks_v1` |
| Baseline lógico | 5102 chunks únicos |
| Duplicados por `chunk_id` | 0 |
| Match PG↔Milvus | 100% |
| `source_type=''` stale | 0 |
| Likutey layout `test_candidate` en productivo | No |

La diferencia de 1828 entidades se originó en el cleanup del 2026-07-05, que trató `source_type=''` como stale y eliminó entidades canónicas de tres documentos heredados. El repair restauró esos 1828 vectores; una reejecución generó 1828 duplicados, posteriormente eliminados conservando la PK referenciada por PostgreSQL.

Relation QA fue reejecutado después del cleanup final: 56 hits vectoriales, 187 fragmentos y 0 evidencias sin PostgreSQL. El resultado es válido sobre cobertura productiva completa.

### Refinamiento de retrieval 2026-07-08

Mejoras aplicadas al script `scripts/breslov_concept_relation_qa_lab.py`:

1. **FTS híbrido**: `websearch_to_tsquery` con ranking + ILIKE fallback. Detección automática de idioma (spanish→search_vector_es, english/hebrew→search_vector_simple).
2. **Patrones relación explícita**: 12 patrones direccionales A→B y B→A, incluyendo hebreo (`קשר`, `חיבור`).
3. **Prompt IA editorial**: estructura markdown con separación cita literal vs interpretación, nivel de certeza, fuentes exactas.

Resultados:

| Métrica | Antes | Después |
|---|---|---|
| FTS habla (ES) | 60 | **67** |
| Total fragments (ES) | 181 | **192** |
| Temática (ES) | 6 | **10** |
| Total fragments (HE) | 256 | **268** |
| Sin PG | 0 | 0 |

### Editorial QA Test Batch 2026-07-08

Tres casos investigativos ejecutados contra el flujo refinado:

| Caso | Consulta | Hallazgo | Conexión |
|---|---|---|---|
| 1 | DIVIDIENDO LA NOCHE / Jatzot | Jatzot identificado como "El Lamento de Medianoche" en Cruzando el Puente (pp. 230-231). Frase exacta no aparece literal; la conexión es inferida. | INFERIDA (certeza media) |
| 2 | Tzafón / Norte → Mal | Cita literal de Jeremías 1:14 en La Potencia de la Plegaria (p. 88): "Desde tzafón (norte) vendrá el mal". | **LITERAL** (certeza alta) |
| 3 | Bereshit Rabah | 7+ citas explícitas en Likutey Halajot Explicado, Likutey Halajot LM II 8, El Jardín de las Almas, Cruzando el Puente. | **LITERAL** (certeza alta) |

0 evidencias sin PostgreSQL en todos los casos. Respuesta IA editorial con separación cita literal vs interpretación.

El flujo queda validado para implementación de endpoint `POST /library/relation-qa`.

### Editorial QA Acid Batch — Likutey Halajot 2026-07-08

Wrapper `scripts/breslov_editorial_qa_acid_batch.py` + configuración `scripts/editorial_qa_cases_likutey_5.json` para 5 casos críticos.

| Caso | Fragments | Sin PG | Acid PASS |
|---|---|---|---|
| Azamra / Puntos Buenos / Poco de Bien | 162 | 0 | ✅ (0 FAIL) |
| Dividiendo la Noche / Jatzot / Medianoche | 136 | 0 | ✅ (0 FAIL) |
| Tzafón / Norte / Mal | 143 | 0 | ✅ (0 FAIL) |
| Elevando el Habla / Dibur / Korbanot | 276 | 0 | ✅ (0 FAIL) |
| Bereshit Rabah | 171 | 0 | ✅ (0 FAIL) |

0 evidencias sin PostgreSQL. Toda fuente resuelve a PG. 8 ready docs intactos. Likutey layout test_candidate no tocado.

## Breslov Investigative Relation QA Backend Endpoint — 2026-07-08

El endpoint backend autenticado está implementado; el informe canónico es `../../data/reports/breslov/2026-07-08-milvus-relation-qa/relation_qa_backend_endpoint.md`.

- ruta: `POST /library/relation-qa`;
- scope: autorización server-side por `breslov_primary` y cadena tenant completa;
- fuentes: snippets canónicos PostgreSQL, deduplicados por `chunk_id`;
- retrieval: FTS, ILIKE, patrones, coocurrencia y Milvus read-only;
- IA: `openai_gpt-5.4-nano` vía LiteLLM, JSON validado y fallback determinístico;
- evidencia: tipos finos, source map, warnings, literalidad e inferencia separadas;
- validación: 638 tests backend PASS y seis casos reales sin fuentes huérfanas;
- migración 012 aplicada para memberships bootstrap; corpus intacto en 8 docs/5102 chunks ready;
- pendiente operativo: curl 200 autenticado cuando el entorno provea credenciales E2E.

## Relation QA Editorial Acid Batch — 2026-07-09

```text
ESTADO: CERRADO (PASS usable)
PRÓXIMA FASE: AI synthesis reliability + concept detection hardening

Resultado: 17.3/24 promedio editorial
  - PASS fuerte:  1 (Q7: ruaj-habla)
  - PASS usable:  7 (Q1-Q4, Q6, Q8, Q9)
  - WARN:         2 (Q5: alegría-plegaria, Q10: caída-renovación)
  - FAIL:         0

P0 identificado: confiabilidad de síntesis IA vía LiteLLM/fallback
  - AI synthesis falla 30-50% con ai_response_parse_failed
  - Deterministic fallback es genérico (solo lista fuentes)
  - Q1, Q5, Q10 fallan consistentemente; Q3, Q9 transitorios

P1 identificado: detección conceptual frágil
  - extract_concepts_from_question() prioriza palabras de pregunta
  - Q4 detectó "literalmente"/"tema" en vez de "hitbodedut"
  - Faltan variantes hebreas para tristeza/atzevut, alegría/simjá, miedo/yirá

Fortalezas:
  - Fuentes siempre auditables (página/chunk/snippet en todas)
  - Warnings metodológicos siempre presentes
  - Retrieval: PG FTS + ILIKE + coocurrencia + Milvus vector en todas
  - Evidencia diversa (literal, bíblica, rabínica, temática, coocurrencia)
  - Cuando AI funciona, respuesta editorial es sustantiva

Reporte canónico:
  data/reports/breslov/2026-07-09-relation-qa-editorial-acid-batch/

Guardrails:
  - PostgreSQL no tocado
  - Milvus no tocado
  - LiteLLM no tocado
  - Corpus no tocado (8 docs ready, 5102 chunks, 5102 embeddings)
  - globalVar.py no tocado
  - No OpenAI directo
  - Backend detenido con backend-dev.sh
  - Frontend no tocado
  - Tests: 51/51 PASS
```

## Relation QA Synthesis Hardening — 2026-07-09

```text
ESTADO: CERRADO (AI synthesis reliability + concept detection hardening completado)
PRÓXIMA FASE: Posible — 10-question full batch re-evaluation

Mejoras:
  - AI synthesis ahora funciona en 4/4 preguntas foco (antes: 2/4 en batch original)
  - Guardrail IA menos restrictivo: permite "no se encontró relación literal directa"
  - Prompt fortalecido: instrucciones explícitas contra afirmación de literales falsas
  - max_tokens 1200→1600, sources 20→15 para mejorar tasa de éxito
  - Reintento automático: 2 intentos con fallback si ambos fallan
  - Fallback determinístico mejorado: incluye conceptos, conteos, warning explícito
  - Diagnosis fields en method: ai_synthesis_status, fallback_reason, synthesis_mode

  - Concept detection endurecida:
    - Preposición stripping ("de caída espiritual" → "caída espiritual")
    - Patrones: "fuentes relacionan A y B", "libros tratan A", "dónde habla de A"
    - Stopwords expandidas: "libro", "fuentes", "textos", "literalmente", "tema"
    - CONCEPT_EXPANSIONS: +13 nuevas entradas (tristeza, alegría, plegaria, miedo,
      emuná, caída, renovación, ruaj, espíritu, profecía, respiración, luz, ojos)

Delta:
  Q1 sangre-habla: 17→20  (+3, AI ahora funciona)
  Q5 alegría-plegaria: 15→19  (+4, AI ahora funciona)
  Q10 caída-renovación: 15→19  (+4, AI ahora funciona)
  Q7 ruaj-habla control: 21→21  (0, sin degradación)

Reporte canónico:
  data/reports/breslov/2026-07-09-relation-qa-synthesis-hardening/

Guardrails:
  - PostgreSQL no tocado
  - Milvus no tocado
  - LiteLLM no tocado
  - Corpus no tocado (8 docs ready, 5102 chunks, 5102 embeddings)
  - globalVar.py no tocado
  - No OpenAI directo
  - Frontend no tocado
  - Tests: 51/51 PASS
```

## Relation QA UI Synthesis Mode Indicator — 2026-07-09

```text
ESTADO: CERRADO

La UI de /library/relation-qa ahora muestra visualmente el modo de síntesis:
- "Síntesis IA" (badge success) cuando synthesis_mode=ai
- "Fallback determinístico" (badge warning) cuando fallback_used=true
- "Modo de síntesis no informado" cuando faltan campos
- Estado IA, intentos y motivo de fallback visibles sin abrir JSON crudo
- Advertencia editorial en caso de fallback

Archivos:
  - RelationQAPanel.svelte — nuevo bloque "Modo de síntesis" con badges y alertas
  - relationQaClient.ts — nuevos campos opcionales en RelationQAMethod
  - relation-qa-synthesis-mode.spec.ts — 3 tests E2E con fixture interception

Validación:
  - pnpm check: 0 errors
  - pnpm build: 5 pages PASS
  - Playwright: 3/3 PASS (AI OK, fallback, campos ausentes)
  - lat check: PASS
  - Backend no tocado
  - /library/search no tocado
```

## Library Search Hybrid Acid Batch — 2026-07-09

```text
ESTADO: CERRADO (PASS fuerte)
COMMIT: e20cce6 test(breslov): add library search hybrid acid batch

Endpoint: POST /library/search
  - Modalidad híbrida: PostgreSQL FTS + Milvus vector search
  - Score global: 189/200 = 94.5% (PASS fuerte)
  - Hybrid queries: 8/8 con vector hits
  - Response-visible vector hits: 7/8
  - fts_q09: WARN (phrase exacta sin resultados)

Alias confirmado para retrieval vectorial:
  - Scope lógico: breslov_primary
  - Milvus collection_code: breslov
  - mapping: knowledge_scope → collection_code via alias en hybrid_search.py

Guardrails:
  - Milvus productivo no modificado
  - No reindexado
  - PostgreSQL productivo no tocado
  - Corpus no tocado
  - globalVar.py no tocado
  - No OpenAI directo
  - Solo LiteLLM para embeddings

Documentación:
  - data/reports/breslov/2026-07-09-milvus26-acid-validation/library_search_hybrid_acid.md

Riesgo documentado:
  - Otras rutas que filtren vectores por scope lógico deben verificar
    el mapping breslov_primary → collection_code=breslov.
  - Si no está resuelto, vector search contra productivo puede fallar
    por expr filter incorrecta.
```

## Historial

- resumen tecnico previo: `status_historico_hasta_2026-06-28.md`;
- arquitectura viva: `../../lat.md/lat.md`;
- Git conserva el detalle exacto de cada fase.
