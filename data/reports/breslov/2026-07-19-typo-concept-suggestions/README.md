# Typo Tolerance and Concept Suggestions — 2026-07-19

## Resumen

Implementación de una capa general, auditable y prudente de tolerancia ortográfica,
sugerencias de corrección, alias controlados, transliteraciones, variantes lingüísticas
y conceptos relacionados para el endpoint investigative-qa de Breslov Research.

## Causa raíz

El pipeline de investigative-qa no tenía tolerancia ortográfica. Una consulta "Hitbodedud"
(error de una letra vs "Hitbodedut") no encontraba resultados porque el sistema no tenía:
- Distancia de edición entre el término consultado y los términos del catálogo
- Normalización determinística de diacríticos/apóstrofos
- Catálogo de sinónimos/transliteraciones/alias
- Capa de sugerencias entre la consulta y el retrieval

## Solución

### Nuevos módulos backend

1. **`concept_catalog.py`**: Catálogo centralizado de 15 conceptos Breslov con:
   - canonical_label, hebrew, aliases, transliterations, translations, related_concepts
   - Índice `FORM_INDEX` para lookup eficiente por cualquier forma
   - Cada entrada con tipos de relación: exact_alias, transliteration, translation, etc.

2. **`query_resolution.py`**: Capa de resolución de consultas con:
   - Normalización determinística (lowercase, NFC, diacríticos latinos, trim)
   - Damerau-Levenshtein distance para detección de typos
   - Autoapply por confianza (typo distancia 1 en términos >= 6 chars → autocorrección)
   - Catálogo de 15 conceptos con 100+ formas buscables
   - Contrato de sugerencias con alternativas y conceptos relacionados

### Modificaciones

3. **`investigative_qa_v1.py`**: Integración de query_resolution en `run()`:
   - Resolución de consulta después de `_retrieval_inputs()`
   - Autoapply reemplaza concepts del plan de retrieval con el término corregido
   - `query_resolution` en response con original, sugerencia, alternativas, relacionados
   - Warnings informativos sobre corrección aplicada

4. **`investigativeQaClient.ts`**: Tipos `QueryResolution`, `SuggestionAlternative`, `RelatedConcept`

5. **`ResearchWorkspace.svelte`**: Tarjeta de sugerencia en UI con:
   - Mensaje de corrección: "No encontré coincidencia exacta para X. Busqué Y."
   - Variantes del término (transliteraciones, forma hebrea)
   - Conceptos relacionados separados

### Tests

6. **`test_query_resolution.py`**: 28 tests unitarios para catálogo, normalización, resolución

### Casos probados

| Entrada | Resultado |
|---------|-----------|
| Hitbodedud | → Hitbodedut (typo, autoapply, 6 hits) |
| Hitbodedut | → exact_match |
| Hisbodedus | → transliteration_match → hitbodedut |
| Emunah | → transliteration → emuna |
| Tzadick | → typo → tzadik |
| Simcha | → transliteration → simja |
| Likutei Moharan | → transliteration → likutey_moharan |
| Rabi Natan | → alias → rabi_natan |
| xyzunknown | → no suggestion |
| Breslev | → no suggestion (concept not in catalog) |
| el (corto) | → no suggestion |

## Archivos

| Archivo | Cambio |
|---------|--------|
| `backend/modules/library/concept_catalog.py` | Nuevo |
| `backend/modules/library/query_resolution.py` | Nuevo |
| `backend/tests/test_query_resolution.py` | Nuevo |
| `backend/modules/library/investigative_qa_v1.py` | Modificado |
| `astro/src/components/research/investigativeQaClient.ts` | Modificado |
| `astro/src/components/research/ResearchWorkspace.svelte` | Modificado |

## Tests

- Backend: 974 passed (28 nuevos + 946 existentes)
- Playwright: 55 passed
- pnpm check: 0 errors
- pnpm build: 7 pages
- LAT check: PASS
- git diff --check: PASS

## Estados

- `TYPO_TOLERANCE_AND_CONCEPT_SUGGESTIONS_FULL_PASS` ✅
- `READY_FOR_MANUAL_SUGGESTION_REVIEW` ✅
