# ADR — Content Node Investigative Model

## Contexto y problema

Página y chunk no alcanzan: la página ancla evidencia, pero mezcla voces; el
chunk recupera semántica, pero puede cruzar secciones o roles. Investigación
exige separar literal, traducción, nota, fuente citada y relación.

## Decisión

Adoptar `ContentUnit → ContentNode → LiteralSpan/SemanticUnit`, con
`PageAnchor`, relaciones tipadas y autoridad explícita. El árbol no admite
ciclos. Todo nodo citable exige ancla. Satélites requieren relación a primario.
PostgreSQL es la verdad; Milvus/pgvector son derivados.

## Cobertura

Kitzur puede usar libro/capítulo/página y nodo primario. LM I/II usa nodos
hebreo, traducción, notas y relación `parallel_translation`. Likutey Halajot
usa discurso/sección, comentario de Rabí Natán, anexo y `applies`/`derives_from`.
Las obras pedagógicas se etiquetan secundarias y sus fuentes Breslov como citas,
no voz primaria. Relaciones distinguen literal, traducción, fuente citada,
editorial, semántica e inferida. La expansión ES/HE/EN incluye alias y
transliteración.

## Consecuencias, rollback y validación

La compatibilidad V2 se conserva. Rollback: eliminar tablas/vista de migración
015; no afecta datos previos. Validado con 70 tests y `/health` 200. La
limitación aceptada es no inferir zonas visuales sin perfil editorial verificado.
