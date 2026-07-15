# ADR: Likutey Halajot begins page-first

## Contexto

Likutey Halajot no comparte necesariamente la estructura de LM II. Clasificar
por rangos heredados o por proximidad contaminaría las búsquedas.

## Decisión

Se creó un documento candidato y un run page-first. Cada página con texto se
guarda como `citable_page_text`, `unclassified`, `unlinked_citable` y
`needs_structural_classification`; ninguna lección, simán, halajá, nota o zona
se infiere por defecto. Las páginas sin texto tienen PageAnchor y se presentan
como `blank_page` en la vista de estado final.

## Consecuencias

La búsqueda por PDF y literal está lista. La búsqueda por página impresa,
unidad, nota, marcador o zona requiere una fase posterior de detección
determinística evidence-gated. Los candidatos IA, si se generan, deberán pasar
por validador y staging; no serán corpus ni clasificación autoritativa.

## Rollback

El run se identifica por `likutey_halajot_page_first_v1`; sus derivados pueden
retirarse por ese identificador sin afectar LM II, Kitzur ni el PDF fuente.
