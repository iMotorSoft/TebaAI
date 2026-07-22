# Reporte: Limpieza de fragmentos, clasificación de capa editorial y diferenciación entre coincidencia literal y cita de autor

**Fecha:** 2026-07-21
**Rama:** `feature/console-backend-core`
**HEAD inicial:** `7e25c95c7070e0c6728795f2d2d96919b4a42a57`
**Caso focal:** consulta «servir a HaShem por la noche»

## Problemas resueltos

1. **Fragmento corrupto (mojibake + controles + artefactos PDF)** — el fragmento visible comenzaba con bytes corruptos (0x98 0x83 0x89...) que representaban hebreo mal decodificado, caracteres de control C0/C1 y marcadores PDF `<#>`.
2. **Capa editorial no clasificada** — `source_layer = "unknown"` sin evidencia estructural para confirmar.
3. **Atribución al autor ambigua** — no se diferenciaba entre «coincidencia literal en la edición» y «cita textual del autor».
4. **Síntesis duplicada** — la síntesis investigativa podía renderizarse dos veces.
5. **Singular/plural incorrecto** — «1 evidencias», «1 relaciones».
6. **Matriz con obras en cero** — se mostraban obras sin resultados.
7. **Fragmentos duplicados** — posible duplicación de cards.

## Solución implementada

### Módulo nuevo: `text_quality.py`

- `analyze_text_quality(text)` → análisis determinístico de calidad
- `sanitize_evidence_snippet()` → produce `display_snippet` limpio preservando `raw_snippet`
- `match_centered_window()` → ventana contextual centrada en el match
- `build_summary()` → resumen con singular/plural correcto
- `singular_plural()` → helper genérico

### Modificaciones: `investigative_qa_v1.py`

- Nuevo tipo `AuthorQuoteStatus` y mapa `AUTHOR_QUOTE_MAP`
- Nuevos campos en `Hit`: `author_quote_status`, `attribution_label`, `raw_snippet`, `snippet_sanitized`, `sanitization_reason_codes`
- `classify()`: aplica `sanitize_evidence_snippet()` al snippet; deriva `author_quote_status` desde `source_layer`
- `render()`: usa `display_snippet`, agrega capa y atribución, muestra warning de sanitización
- `_deterministic_claims()`: incluye `attribution_label` en el claim
- Summary: usa `build_summary()` con singular/plural
- Matrix: filtra solo obras con hits
- Warnings: agrega `evidence_snippet_sanitized:ID` cuando aplica

### Modificaciones: Frontend

- `investigativeQaClient.ts`: nuevos campos en Hit type
- `researchLabels.ts`: `attributionLabels` export
- `SourcePanel.svelte`: muestra atribución y warning de sanitización

## Resultados del caso focal

| Aspecto | Antes | Después |
|---|---|---|
| Snippet visible | `\x98\x83\x89\x8a\x82 \x87\x86...` (mojibake) | «merece saber con todo el corazón...» |
| source_layer | `unknown` | `unknown` (no hay zona metadata) |
| author_quote_status | — | `not_confirmed` |
| attribution_label | — | «No confirmada como formulación textual del autor original» |
| Summary | «1 evidencias principales · 1 relaciones contextuales» | «1 evidencia principal · 1 relación contextual» |
| Matrix | 6 filas (4 con 0 hits) | 1 fila (solo lh) |
| Raw snippet | — | preservado con corrupción original |
| Warnings sanitización | — | `evidence_snippet_sanitized:lh-37c67830012c` |

## Validación

- Backend: 1003 tests PASS
- Frontend: `pnpm check` 0 errores, 0 warnings
- Build: `pnpm build` 7 páginas PASS
- `git diff --check`: PASS
- Edge cases: 10/10 PASS (texto limpio, hebreo, corrupción, resumen, sing/plural, artefactos PDF, controles, calidad, vacío, largo)
