# TebaAI — Breslov Two Books Preflight

Fecha: 2026-06-30.
Estado: completed.

## Objetivo

Preflight read-only de dos nuevos PDFs candidatos para ingesta en `breslov_test`.

## PDFs evaluados

El preflight revisó calidad textual, estructura y necesidad de OCR de ambos PDFs.

| Archivo | Idioma | Páginas | Caracteres | Palabras | OCR | Estructura |
|---------|--------|-------:|----------:|---------:|:---:|-----------|
| Kokhavey Ohr | en | 576 | 1,127,970 | 207,947 | No | Chapter-based |
| KITZUR | es | 512 | 1,107,728 | 175,706 | No | Lesson-based (96) |

## Kokhavey Ohr

Kokhavey Ohr quedó como candidato inglés de alta calidad textual.

- Inglés, creado con Adobe InDesign 15.0.
- Tema: enseñanzas de Rabí Najmán sobre "estrellas de luz".
- Chapters detectados (4+), estructura narrativa/enseñanza.
- 962 heading candidates, 748 footnote signals.
- Sin TOC explícito, sin outline/bookmarks.
- Texto de alta calidad (InDesign source).
- **Estrategia**: chapter-aware como primaria, heading-aware como fallback.
- **Metadata candidata**: Breslov Research Institute, English.

## KITZUR

KITZUR quedó como candidato español con estructura de lecciones clara.

- Español, creado con PageMaker 7.0, autor "Enrique" (Enrique Kramer, traductor).
- Tema: resumen (Kitzur) de Likutey Moharán.
- **96 Lecciones** detectadas — estructura muy clara.
- 1189 heading candidates, 992 footnote signals.
- Sin TOC explícito, sin outline/bookmarks.
- Texto de alta calidad (PageMaker source).
- **Estrategia**: lesson-aware como primaria, section-aware como fallback.
- **Metadata candidata**: Rabí Natán de Breslov (autor original), Enrique Kramer (traductor).

## Comparación

La comparación confirma que ambos PDFs son aptos para `breslov_test`.

| Aspecto | Kokhavey Ohr | KITZUR |
|---------|-------------|--------|
| Calidad texto | Alta (InDesign) | Alta (PageMaker) |
| Estructura | Chapters (4+) | Lecciones (96) |
| OCR necesario | No | No |
| Riesgo layout | Bajo | Bajo |
| Apto breslov_test | Sí | Sí |
| Estrategia recomendada | chapter-aware | lesson-aware |

## Metadata propuesta

La metadata propuesta registra estado test y estrategia estructural candidata.

### Kokhavey Ohr

Kokhavey Ohr usa metadata candidata para una estructura chapter-aware.

```json
{"title": "Kokhavey Ohr", "language": "en", "domain": "breslov", "corpus": "breslov_test", "status": "test_candidate", "format": "pdf", "structure_strategy_candidate": "chapter-aware", "requires_ocr": false, "preflight_status": "candidate"}
```

### KITZUR

KITZUR usa metadata candidata para una estructura lesson-aware.

```json
{"title": "Kitzur Likutey Moharán", "language": "es", "domain": "breslov", "corpus": "breslov_test", "status": "test_candidate", "format": "pdf", "structure_strategy_candidate": "lesson-aware", "requires_ocr": false, "preflight_status": "candidate"}
```

## Riesgos

Los riesgos se limitan a ausencia de TOC y consistencia de headings.

- Sin TOC explícito ni outline en ambos — chunking section-aware tendrá que basarse en detección de headings.
- Kokhavey Ohr no tiene "Chapter" en todas las páginas — puede requerir heading-aware como fallback.
- KITZUR tiene 96 lecciones — el chunking lesson-aware funcionará bien si los headers de lección son consistentes.

## Próxima fase recomendada

Ingestar ambos libros como test_candidate en breslov_test y aplicar chunking según estrategia recomendada.
