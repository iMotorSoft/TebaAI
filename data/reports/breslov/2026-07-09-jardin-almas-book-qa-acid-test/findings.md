# Findings — Book QA Acid Test: El Jardín de las Almas

## Resumen

Relation QA (`POST /library/relation-qa`) **no es adecuado** para preguntas de QA textual libro-específico. Está diseñado para relaciones conceptuales transversales entre libros, no para recuperación de fragmentos concretos dentro de un libro específico.

## El libro sí existe en el corpus

"El Jardín de las Almas" está en el corpus productivo (`ready`) y aparece en resultados cuando se usa la consulta correcta (`concept_a=Jardín, concept_b=Almas` devuelve 11+ chunks del libro). Sin embargo, para preguntas textuales específicas, el retrieval de Relation QA no encuentra el fragmento correcto.

## Causas de falla

### 1. Sin scoping por documento (P0)
Relation QA no acepta un parámetro para restringir la búsqueda a un libro/documento específico. Busca en todo el scope `breslov_primary`. Esto hace que preguntas como "¿Qué dice el Jardín de las Almas sobre X?" compitan con otros libros.

### 2. Fragmentos largos y específicos no matchean
Preguntas que contienen frases largas y específicas ("Shlomo Efraim", "talón del Otro Lado") usan FTS websearch que puede no encontrar coincidencias si la frase exacta no aparece en los chunks. El chunking del libro podría no preservar el contexto nominal completo.

### 3. Concept detection ignora el título del libro
Cuando la pregunta incluye el título del libro ("El Jardín de las Almas"), el extractor de conceptos debería usarlo para scoping, pero en cambio extrae palabras como "Jardín" y "Almas" como conceptos individuales, o peor, extrae términos no relacionados.

### 4. Page mapping correcto pero no accesible vía Relation QA
El page mapping del libro está en 100% según datos previos, pero Relation QA no prioriza páginas específicas ni tiene un mecanismo para "buscar en página N del libro X".

## Métricas finales

| Métrica | Valor |
|---|---|
| Promedio global | 11.9/20 (WARN) |
| Nivel 1 (trivial) | 12.7/20 |
| Nivel 2 (comprensión) | 12.0/20 |
| Nivel 3 (síntesis) | 11.3/20 |
| Nivel 4 (compleja) | 11.0/20 |
| Book OK | 5/10 |
| Page OK | 1/10 |
| Fragment OK | 0/10 |
