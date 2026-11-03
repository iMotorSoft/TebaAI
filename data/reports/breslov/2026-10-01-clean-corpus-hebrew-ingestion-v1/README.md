# Corpus limpio Breslov / validación integral hebrea — gate abierto

## Estado vigente — 2026-10-11

**BLOCKED por fidelidad de C, no por autorización de reset.** La autorización ampliada permitió el reset total DEV; los resultados y manifests conservados prueban corpus cero y preservación de plataforma. A/B/C se ingirieron y publicaron posteriormente por UI. Estado medido: 3 documentos, 896 páginas, 2146 chunks/vectores. A/B tienen PASS acotado a muestras críticas; C tiene corrupción de extracción pendiente. Producción no modificada; sin commit/push.

Continuación, cambios nuevos, validaciones y causa de texto oculto bajo rectángulos blancos: [c-continuation.md](c-continuation.md). La recuperación Unicode por font hash es un prototipo no integrado; no se reingestó C con un fix incompleto. **El gate integral no tiene PASS.**

---

## Snapshot histórico: preflight anterior a la autorización ampliada

Lo que sigue registra el bloqueo inicial y NO describe el estado actual del corpus.

Veredicto: **CLEAN_CORPUS_HEBREW_BLOCKED**.

Inventario ejecutado en esta sesión, 2026-10-11 según reloj del runtime. El nombre del directorio referencia el baseline de fidelidad de 2026-10-01, no una ejecución histórica completada.

No se ejecutó reset, ingesta, publicación ni QA visual. No se reutiliza el PASS anterior para aprobar este experimento. **Production modified: NO**.

## Bloqueo de seguridad antes del reset

La autorización cubre exclusivamente contenido documental Breslov DEV y exige STOP ante riesgo de afectar datos ajenos. El modelo actual no permite identificar ese conjunto simplemente por scope o collection:

- `breslov_primary` tiene 25 documentos, incluidos `Masoretic Text (Hebrew test)`, `Tanakh Torah (Bereshit+Shemot) — Masoretic Text PDF pages 1-200 (Hebrew test)` y `HebrewBooks 34314 (subset 1-15)`. Su pertenencia al scope no prueba que sean contenido Breslov autorizado para eliminación.
- `breslov_test` contiene también tres documentos Koren/Yevamot archivados y sin scope. No se eliminarán por compartir colección.
- 512 páginas tienen document_id ausente del inventario actual de library_documents. No se atribuyen a Breslov por inferencia.
- Vectores históricos en `tebaai_breslov_chunks_v2_dev` (506) y `tebaai_breslov_test_chunks_v1` (2302) referencian documentos ausentes. La colección BookQA Kitzur tiene 100 registros sin document_id en su esquema. Falta cerrar procedencia y relación con el conjunto autorizado.
- `ManifestCleanupService` es compensación por job/attempt, no reset integral: no elimina documentos ready, jobs/attempts ni todas las estructuras históricas. No debe ejecutarse masivamente como sustituto del reset.

No se diseñó ni ejecutó un DELETE genérico por nombre, título, scope o prefijo de colección. Ningún archivo fuente externo fue eliminado. La siguiente etapa necesita una clasificación explícita de registros ajenos/ambiguos y un manifest exacto de reset con dependencias y rollback. No se requiere ampliar la autorización a producción.

## Preflight e inventario

PostgreSQL resuelto mediante backend/globalVar.py. Configuración observada: development, no producción, host localhost, base tebaai. Servidor alcanzado: PostgreSQL 18.4, dirección interna Docker 172.18.0.2/32, puerto 5432. Todas las consultas se ejecutaron con transacción READ ONLY. Milvus: endpoint local 127.0.0.1:19530; sin URI override.

Backend y Astro DEV estaban detenidos. No se iniciaron servidores ni workers. Configuración del proceso de observación: worker_scope=breslov_e2e, primary ingestion deshabilitada, storage primario vacío. Esto no prueba la configuración de un futuro proceso de aplicación. Credenciales ADMIN E2E presentes; EDITOR/VIEWER dedicadas ausentes; no se imprimieron valores ni se crearon usuarios.

| Componente | Inventario actual | Eliminar en reset | Conservar |
|---|---:|---|---|
| Documents totales | 31 | Solo IDs documentalmente autorizados; pendiente | Registros ajenos/ambiguos |
| Documents primary | 25: 10 ready, 14 candidate, 1 archived | Pendiente clasificación | Contenido no Breslov |
| Documents E2E | 2 candidate | Asociados a A/B, previstos | Ningún dato ajeno |
| Documents sin scope | 4 archived | No por heurística | Koren y fixture general |
| Pages totales | 1864 | Solo conjunto probado | Ajeno/ambiguo |
| Pages primary / E2E / sin documento actual | 740 / 612 / 512 | Pendiente | Sin atribución probada |
| Chunks primary / E2E | 5964 / 1204 | Solo conjunto probado | Ajeno/ambiguo |
| Jobs primary / E2E | 16 / 69 | Solo conjunto probado | Ajeno |
| Jobs sin scope resuelto por JOIN | 1 de 86 totales | Pendiente atribución | No borrar por defecto |
| Attempts totales | 50 | Asociados al manifest autorizado | Ajeno |
| Users | 79 | NO | YES |
| Roles | 3 admin, 6 editor, 70 viewer | NO | YES |
| Configuración | Sin cambios | NO | YES |
| Schema/migrations | 42 migraciones, sin cambios | NO | YES |
| Colecciones/esquemas Milvus | Sin cambios | NO | YES |
| Uploads registrados | 74; 0 archivos existentes en temp_path registrado | Solo archivos administrados y probados | Fuentes originales externas |

Los conteos globales no son un inventario definitivo de filas autorizadas a borrar. Además existen tablas estructurales, referencias, relaciones, embedding runs, manifests, transiciones y eventos de publicación; sus columnas/FKs quedaron registradas, pero su selección exacta está pendiente. No se inspeccionó todo el storage derivado externo: inventario storage parcial, sin búsquedas amplias.

### Milvus

| Colección | Vectores vivos consultados | row_count reportado | Observación |
|---|---:|---:|---|
| tebaai_breslov_chunks_v1 | 5374 | 5374 | breslov=5106, breslov_primary=268 |
| tebaai_content_manager_e2e_v1 | 1204 | 1204 | breslov_e2e=1204 |
| tebaai_breslov_chunks_v2_dev | 506 | 506 | Documento ausente en PG actual |
| tebaai_breslov_test_chunks_v1 | 7359 | 10115 | primary=7158, test=201; 2302 con documento ausente |
| tebaai_breslov_bookqa_v2_kitzur_test_pages_v1 | 100 | 100 | Esquema sin document_id; atribución pendiente |
| tebaai_breslov_bm25_test_v2 | NO COMPROBADO | 0 | No cargada; no se alteró estado de carga |
| tebaai_breslov_bm25_test_v3 | 0 | 0 | Vacía en consulta |

No se suman colecciones como si fuesen un único índice, ni se considera row_count prueba suficiente de vectores vivos. Colecciones Team360/JAI: no mutadas ni consultadas para contenido.

La primera consulta a una colección histórica falló por asumir document_id. Se corrigió la observación inspeccionando los schemas reales antes de consultar campos. El fallo de colección BM25 no cargada queda registrado en el JSON como inventory_error. No hubo mutaciones para resolverlo.

## Reset y corpus cero

- Documents before: 31 totales, conjunto autorizado pendiente.
- Chunks before: 7168 totales.
- Vectors before: tabla por colección arriba.
- Documents/chunks/vectors after reset: **N/A; reset NO ejecutado**.
- Users/roles/config/schema: sin cambios por esta sesión.
- Auth works: NO VALIDADO (servidores detenidos).
- DEV_BRESLOV_CORPUS_ZERO_PASS: **NO**.

## Tres fuentes reales verificadas

C seleccionada como fuente candidata representativa por los antecedentes de headings, referencias, notas y texto mixto de esta edición. Diversidad visual nueva todavía no validada. La autorización editorial/legal del usuario se registra para esta prueba DEV; no se usa como permiso productivo.

| Libro | Archivo | SHA-256 | Páginas físicas |
|---|---|---|---:|
| A — Un Día en la Vida de un Jasid de Breslov | UN DÍA EN LA VIDA (KDP).pdf | d98e4d4c96a36c701aa055e1a9b8ce230dec24f3b45f35455828f6fe30f69c13 | 196 |
| B — La Potencia de la Plegaria | LA POTENCIA DE LA PLEGARIA Interior Print.pdf | 8e5c2ca6c153f47e7ae31e0ba2f2b8fefaedb9916dd8d0d79d484e2c96990c46 | 416 |
| C — Likutey Halajot — Interior Final | LIKUTEY HALAJOT (Interior Final).pdf | 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a | 284 |

Fuente: /media/issajar/DEVELOP/Download/Tora/Breslov/. Los PDFs se abrieron solo para metadatos y conteo físico; hashes calculados sobre archivos completos. No extracción manual ni ingesta alternativa.

document_id/job_id/attempt/publication/chunks/vectors nuevos: N/A para A/B/C. Los IDs previos del inventario NO son resultados de este experimento.

## Gates pendientes

Todos los gates de ingesta UI, procesamiento automático, publicación ready, reconciliación final, literal/semantic retrieval, negativa, cross-document, citas/páginas, chunking/regresión español, diversidad C y visualización desktop/mobile/niqqud/números/puntuación/mixto: **NO EJECUTADOS**.

No se declara ausencia de letras invertidas, palabras rotas, espacios sintéticos ni joins ambiguos en la experiencia final: no se observó en este experimento. No se capturaron screenshots nuevos. El PASS anterior no sustituye la comparación visual nueva con los PDFs.

## Intervención y validaciones

SQL por ingesta, Milvus manual por ingesta, embeddings manuales, worker específico por documento y publicación manual: no ejecutados; tampoco se demostró el flujo sin intervención. SQL de esta sesión: exclusivamente inventario READ ONLY. Milvus: list/schema/stats/query únicamente.

Backend/frontend suites/check/build/browser: no ejecutados, código sin cambios. git diff --check: PASS inicial y final. Revisión final: únicamente evidencia nueva de esta fase; archivos ajenos preservados.

## Git

- Branch: feature/console-backend-core.
- HEAD inicial/final: 1fa9290bdc7840e7277a998aa3ca66345c6080ee.
- Fix presente en HEAD.
- Ahead 1 frente a referencia local origin/feature/console-backend-core; sin fetch, estado actual GitHub no verificado.
- Código cambiado: NO. Commits: 0. Push: NO.
- Nuevos archivos: este reporte y cinco JSON de inventario/fuentes.
- Untracked ajenos preservados: browser-error.png del reporte de fidelidad y directorio previo hebrew-rtl-rendering-v1.

## Respuestas de negocio

| Pregunta | Resultado de esta ejecución |
|---|---|
| ¿Partimos realmente de corpus vacío? | NO |
| ¿A se ingresó desde UI? | NO |
| ¿B se ingresó desde UI? | NO |
| ¿Un Likutey Halajot real se ingresó desde UI? | NO |
| ¿Los tres se procesaron sin intervención técnica? | NO; no ejecutado |
| ¿Los tres quedaron correctamente indexados? | NO; no ejecutado |
| ¿PDF 187 quedó corregido desde esta extracción nueva? | NO demostrado |
| ¿PDF 416 quedó corregido desde esta extracción nueva? | NO demostrado |
| ¿Likutey conservó su diversidad estructural? | NO demostrado |
| ¿Hebreo puro, niqqud, números y español se leen perfectamente? | NO demostrado |
| ¿Las citas hebreas se leen perfectamente? | NO demostrado |
| ¿Páginas citadas corresponden al PDF? | NO demostrado |
| ¿Consultas recuperan libros correctos? | NO demostrado |
| ¿Pregunta sin evidencia evita alucinación? | NO demostrado |
| ¿Corpus final contiene solamente los tres libros? | NO |

**TEBAAI_BRESLOV_CLEAN_CORPUS_HEBREW_INGESTION_V1_PASS: NO**.

Próximo paso: resolver explícitamente la frontera de reset para documentos no Breslov que comparten scope y datos históricos sin propietario actual. Luego implementar/testear un cleanup por manifest exacto, respaldado y acotado, antes de cualquier eliminación. Continuar A → B → C mediante UI solamente después de corpus cero probado.
