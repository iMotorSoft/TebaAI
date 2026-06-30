# TebaAI — El Alma del Rebe Najmán Sijot-aware Page Mapping

Fecha: 2026-06-30.
Estado: applied.

## Contexto

Los 476 chunks Sijot-aware de "El Alma del Rebe Najmán" en `breslov_test` fueron enriquecidos con page mapping real desde el PDF local.

## Estrategia

- **normalization_plus**: NFKC + lowercase + unaccent + markdown stripping + Sija heading normalization + dash/quote normalization.
- Matching por anclas múltiples (inicio, medio, fin, saltos de tercio).
- Solo confidente `high` (start/end anchors coinciden en misma página o adyacentes con `>= 60%` hits).

## Documento fuente

| Atributo | Valor |
|----------|-------|
| PDF | `/media/issajar/DEVELOP/Download/Tora/Breslov/EL ALMA DEL REBE - KINDLE.pdf` |
| Páginas físicas | 200 |
| Colección | `breslov_test` |
| Chunks | 476 |

## Métricas dry-run

| Métrica | Valor |
|---------|-------|
| Estrategia | `normalization_plus` |
| Chunks evaluados | 476 |
| High-confidence | 273 (57.4%) |
| Ambiguous | 0 |
| Invalid ranges | 0 |

## Métricas apply

| Métrica | Valor |
|---------|-------|
| Chunks actualizados | 273 |
| Con page_start/page_end | 273 |
| Con reference_label | 273 |
| Invalid ranges | 0 |
| breslov productivo | 1991 (sin cambios) |

## Metadata preservada

- `bibliographic_metadata.section` — preservada desde `ch.metadata.section`
- `bibliographic_metadata.chunking` — preservada desde `ch.metadata.chunking`
- `bibliographic_metadata.page_mapping` — agregada por el enrichment

## Reference labels

- Secciones Sija: `Sija N · PDF page(s) M`
- Otras secciones: `SectionName · PDF page(s) M`
- Sin sección: `PDF page(s) M`

## FTS smoke

Las búsquedas ahora muestran `reference_label` y `page_start/end` en los resultados.

## Tests

- `test_sijot_page_mapping_enrichment.py`: 16 tests (normalization_plus, anchors, safety).
- `pytest` total: 298 PASS (antes 282).

## Limitaciones

- 203/476 chunks sin page mapping (42.6%) — chunks con contenido markdown denso no superan threshold.
- Cobertura mejorable con refinamiento de normalization_plus.
- Documento sigue `test_candidate`.
- Milvus no indexado.
- Sin embeddings. Sin RAG.

## Comando usado

```bash
uv run python -m scripts.enrich_chunk_page_metadata \\
  --collection breslov_test \\
  --document-title "El Alma del Rebe Najmán" \\
  --strategy normalization_plus --apply
```
