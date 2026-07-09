# Recommendations — Book QA Acid Test: El Jardín de las Almas

## P0 — Crear endpoint book-scoped QA

Relation QA necesita un parámetro opcional para restringir la búsqueda a un documento/libro específico.

**Sugerencia**: Agregar campo `document_id` o `book_title` opcional en `RelationQARequest`. Si se provee, el retrieval filtra por ese documento en PostgreSQL y Milvus.

**Estimación**: 4-8 horas (schema + retrieval + tests).

## P1 — Mejorar concept detection para incluir título de libro

Cuando la pregunta menciona un título de libro conocido ("El Jardín de las Almas", "KITZUR", etc.), el extractor de conceptos debería reconocerlo y usarlo como filtro de documento, no como concepto de búsqueda.

**Sugerencia**: Agregar detección de títulos de libros conocidos en `extract_concepts_from_question()`.

**Estimación**: 2-3 horas.

## P2 — Batch de prueba libro-específico con `/library/search`

Re-ejecutar las 10 preguntas usando `/library/search` (que puede hacer FTS sobre el corpus) en lugar de Relation QA, para comparar la tasa de recuperación de fragmentos exactos.

**Sugerencia**: Adaptar `book_qa_acid_batch.py` para usar search en lugar de relation-qa, con flag `--mode search|relation-qa`.

**Estimación**: 2 horas.

## P2 — Agregar modo "book QA" en CLI editorial

Extender `relation_qa_editorial_cli.py` con flag `--book "El Jardín de las Almas"` que restrinja la búsqueda a ese documento específico (una vez que el endpoint lo soporte).

**Estimación**: 1 hora.
