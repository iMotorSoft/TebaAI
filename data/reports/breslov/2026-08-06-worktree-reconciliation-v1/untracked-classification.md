# Clasificación de archivos untracked — 2026-08-06

Categorías: A=legítimo de fase cerrada sin commitear, B=config DEV/PRO, C=branding/assets, D=test, E=documentación, F=reporte reproducible, G=herramienta/probe read-only, H=runtime/temporal, I=cambio preexistente ajeno, J=dudoso.

## Assets frontend (C)

| ruta | estado | propósito | fase de origen | secretos | commitear |
|---|---|---|---|---|---|
| `SrvRestAstroLS_v1/astro/public/favicon.svg` | untracked | Favicon SVG (628 B) | 2026-07-28 assets sociales | no | sí |
| `SrvRestAstroLS_v1/astro/public/favicon-32x32.png` | untracked | Favicon 32 px (835 B) | ídem | no | sí |
| `SrvRestAstroLS_v1/astro/public/favicon-16x16.png` | untracked | Favicon 16 px (455 B) | ídem | no | sí |
| `SrvRestAstroLS_v1/astro/public/apple-touch-icon.png` | untracked | Apple touch icon 180 px (4.5 KB) | ídem | no | sí |
| `SrvRestAstroLS_v1/astro/public/images/breslov-social-card.png` | untracked | Tarjeta social Open Graph 1200×630 PNG | ídem | no | sí |
| `SrvRestAstroLS_v1/astro/scripts/render-social-assets.cjs` | untracked | Generador Playwright de la tarjeta social (reproducible, sin secretos) | ídem | no | sí |

Verificaciones: los 4 favicons están referenciados por `PublicLayout.astro` (diff commiteado), la tarjeta social es referenciada por layout (`socialImage` → `breslov-social-card.png`). Sin archivos duplicados ni assets sin uso.

## Probes read-only (G)

| ruta | estado | propósito | secretos | commitear |
|---|---|---|---|---|
| `SrvRestAstroLS_v1/backend/scripts/milvus_v2_isolated_status_probe.py` | untracked | Estado Milvus aislado; nunca llama `Collection.load()`; solo `Collection` metadata + `utility`. | no | sí |
| `SrvRestAstroLS_v1/backend/scripts/milvus_operational_closure_probe.py` | untracked | Probe de cierre operativo Milvus; `col.load()` solo bajo flag explícito `--safe-load`; sin insert/delete/drop. | no | sí |

## Reportes reproducibles (F) — 282 archivos en `data/reports/breslov/`

| directorio | archivos | fase de origen |
|---|---|---|
| `2026-07-09-kitzur-v2-lesson-index-recovery/` | 21 (raw/rendered/summary) | recuperación índice lecciones Kitzur v2 |
| `2026-07-09-kitzur-v2-level1-hardening/` | 21 | hardening nivel 1 |
| `2026-07-09-kitzur-v2-level2-hardening/` | 42 | hardening nivel 2 |
| `2026-07-12-kitzur-level3-full-stack-synthesis-qa-v1/` | 17 | QA full-stack síntesis nivel 3 |
| `2026-07-12-kitzur-level3-size-model-diagnostics/` | 3 | diagnóstico tamaño de modelo |
| `2026-07-12-kitzur-level3-synthesis-terminal/` | 19 | síntesis nivel 3 terminal |
| `2026-07-12-kitzur-level4-synthesis-qa-v1/` | 6 | QA síntesis nivel 4 |
| `2026-07-12-milvus-v2-isolated-status/` | 6 | estado Milvus v2 aislado |
| `2026-07-12-vector-store-decision/` | 27 | decisión vector store |
| `2026-07-13-likutey-moharan-ii-layout-profile-closure/` | 31 | cierre perfil layout LM II |
| `2026-07-16-research-workspace-v1/` (parcial) | 1 JSON + screenshots | workspace investigación v1 |
| `2026-07-20-likutey-moharan-i-ingestion-audit/` | 2 | auditoría ingesta LM I |
| `2026-07-26-query-interpretation-confirmation/screenshots/` | 2 png | confirmación de interpretación |
| `2026-07-31-exact-editorial-evidence-ranking-v1-dev/` | 1 README | ranking evidencia exacta |
| `2026-07-31-likutey-halajot-embedding-retrieval-completion-v2-dev/` | 1 README | completado embeddings LH v2 |

+ 84 capturas PNG dentro de esos directorios (14 MB total). Escaneo de secretos: solo falsos positivos ("tokens" de LLM, "secretos de la Torá"). Evidencia de fases cerradas, coherente con la práctica del repo (`data/reports/breslov/` ya trackeado).

## Runtime excluido (H) — 13 archivos

| ruta | razón |
|---|---|
| `SrvRestAstroLS_v1/backend/data/reports/breslov/2026-07-09-book-qa-v2-endpoint-sql/raw_Q*.json` (10) | salida cruda de probe HTTP |
| `SrvRestAstroLS_v1/backend/data/reports/breslov/2026-07-09-book-qa-v2-endpoint-sql/http_acid_summary.json` | salida cruda de probe |
| `SrvRestAstroLS_v1/backend/data/reports/breslov/2026-07-09-kitzur-v2-lesson-index-recovery/lesson_index_dry_run.json` | salida cruda dry-run |
| `SrvRestAstroLS_v1/backend/data/reports/breslov/2026-07-09-kitzur-v2-lesson-index-recovery/lesson_index_execute.json` | salida cruda de ejecución |

`SrvRestAstroLS_v1/backend/data/` es salida runtime del backend; el directorio canónico de reportes es `data/reports/breslov/`. Se excluye sin borrar (se conserva en disco).
