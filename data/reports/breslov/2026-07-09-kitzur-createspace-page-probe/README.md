# KITZUR CreateSpace — Page Probe for Ingestion V2

## Resultado

| Métrica | Valor |
|---|---|
| PDF pages | 512 |
| Pages with text | 506 (99%) |
| Empty pages | 6 |
| Total chars | 1,086,231 |
| Avg chars/page | 2,147 |
| Embedded text | Sí |
| Requires OCR | No |
| Page markers | PASS |
| Printed numbers detected | 1,263 (494 pages) |
| Section candidates | 4+ |
| pymupdf4llm | OK pero sin markers nativos |

## Veredicto

**PDF apto para ingesta V2.** Extracción vía `fitz.get_text('text')` con page markers controlados (`## Page N`) es viable y confiable.

## Riesgos

- 6 páginas vacías (probablemente páginas de separación/portada)
- Sección detection heurística limitada (solo 4 candidatos con ALL-CAPS)
- 18 páginas sin números impresos detectados (probablemente front/back matter)
- pymupdf4llm no genera page markers nativos para este PDF
