# TebaAI — Breslov Two Books Chunking Strategy

Fecha: 2026-06-30.
Estado: completed.

## Objetivo

Comparar estrategias de chunking sobre Markdown persistido para Kokhavey Ohr (en) y KITZUR (es).

## Fuente

Markdown canónico extraído con PyMuPDF4LLM desde `library_document_texts.content`.

## Kokhavey Ohr

| Atributo | Valor |
|----------|-------|
| Idioma | Inglés |
| Chars Markdown | 1,136,153 |
| H2 headings | 172 |
| H1/H3 | 0 |
| Chapter/Lección patterns | 0 |

| Estrategia | Chunks | Avg chars | Section meta | Crossing |
|-----------|------:|----------:|-------------:|--------:|
| generic | 848 | 1583.8 | 0% | 0 |
| **heading-aware** | **903** | **1455.1** | **100%** | **0** |
| chapter-aware | 848 | 1583.8 | 0% | 0 |
| section-aware | 903 | 1455.1 | 100% | 0 |

**Recomendación**: heading-aware (o section-aware). La estructura usa H2 como secciones temáticas sin numeración.

**Metadata candidata**:
```json
{"section": {"section_type": "heading", "section_label": "H2 text", "section_source": "markdown_heading"}}
```

## KITZUR

| Atributo | Valor |
|----------|-------|
| Idioma | Español |
| Chars Markdown | 1,003,612 |
| H2 headings | 672 |
| Lección patterns | 946 (473 unique) |
| Chapter/Capítulo | 0 |

| Estrategia | Chunks | Avg chars | Section meta | Crossing |
|-----------|------:|----------:|-------------:|--------:|
| generic | 814 | 1478.5 | 0% | 0 |
| heading-aware | 1021 | 1065.0 | 100% | 0 |
| chapter-aware | 814 | 1478.5 | 0% | 0 |
| **lesson-aware** | **651** | **1590.1** | **100%** | **0** |
| section-aware | 1021 | 1065.0 | 100% | 0 |

**Recomendación**: lesson-aware (estructura clara de 473 lecciones numeradas).

**Metadata candidata**:
```json
{"section": {"section_type": "lesson", "section_number": N, "section_label": "Lección N", "section_source": "markdown_heading"}}
```

## Comando usado

```bash
uv run python -m scripts.compare_markdown_chunking_strategies \\
  --collection breslov_test --document-title "Kokhavey Ohr" \\
  --strategies generic,heading-aware,chapter-aware,section-aware

uv run python -m scripts.compare_markdown_chunking_strategies \\
  --collection breslov_test --document-title "KITZUR" \\
  --strategies generic,heading-aware,chapter-aware,lesson-aware,section-aware
```

## Tests

- `test_markdown_chunking_strategy_comparison.py`: 14 tests (detection, chunking, metrics, safety).
- `pytest`: 365 PASS.

## Próxima fase

Aplicar chunking estructural individual por libro en breslov_test.
