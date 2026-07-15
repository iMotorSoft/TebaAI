# ADR: detector estructural conservador para Likutey Halajot

Page-first sigue siendo la capa canónica de evidencia. Esta decisión incorpora
una tabla de clasificaciones por página, separada de ContentNodes, y sólo
promueve bloques delimitados por títulos locales visibles: índice, prefacios,
introducción, texto principal, apéndices, glosario y diagramas.

Los números impresos se extraen sólo junto al encabezado `LIKUTEY HALAJOT`.
Los `zone_hints` son detectores determinísticos de etiquetas visibles, no zonas
autoritativas ni relaciones. Si un futuro borde no tiene texto verificable, debe
permanecer `page_literal_only`; IA podrá producir candidatos auditables, nunca
promoción directa.

Rollback: borrar exclusivamente las filas con el detector run id indicado y
recrear las vistas; el source run `likutey_halajot_page_first_v1` no se toca.
