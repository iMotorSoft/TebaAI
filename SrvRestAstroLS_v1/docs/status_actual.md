# Status actual - TebaAI

Objetivo: `desarrollo`

Ultima actualizacion: 2026-06-29 (corpus de prueba y status documental)

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
- LiteLLM se usa para embeddings `text-embedding-3-small`; no existe modelo generativo ni RAG conversacional.

Referencias canonicas:

- `lat.md/global-configuration-facade-policy.md`;
- `lat.md/authentication-security-policy.md`;
- `lat.md/library-retrieval-models-policy.md`;
- `lat.md/postgres-driver-policy.md`;
- `lat.md/service-preflight-methodology.md`;
- `lat.md/page-mapping-failure-diagnosis.md`;
- `lat.md/breslov-test-corpus-policy.md`.

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
9. Evaluar OCR para el residuo de extraccion de Likutey y metadata de confianza media.
10. Diseñar cualquier RAG generativo mediante ADR, sin incorporarlo al endpoint de retrieval existente.
11. Eliminar `datetime.utcnow()` y usar claves JWT de test de al menos 32 bytes.

## Seguridad

- No guardar secretos ni credenciales de prueba en codigo o documentacion.
- Las variables `TEBAAI_E2E_ADMIN_EMAIL` y `TEBAAI_E2E_ADMIN_PASSWORD` son obligatorias para E2E autenticado.
- PostgreSQL, Milvus y LiteLLM son servicios externos; no gestionarlos automaticamente.
- No imprimir DSN, tokens ni API keys completos.

## Historial

- resumen tecnico previo: `status_historico_hasta_2026-06-28.md`;
- arquitectura viva: `../../lat.md/lat.md`;
- Git conserva el detalle exacto de cada fase.
