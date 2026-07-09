# Recommendations — Relation QA Editorial Acid Batch

Clasificación:
- **P0**: Bloquea uso investigativo
- **P1**: Mejora importante pero no bloqueante
- **P2**: Pulido

---

## Recomendaciones P0

### P0-1: Diagnosticar y estabilizar AI synthesis

**Problema**: `ai_response_parse_failed` en 30-50% de consultas.

**Análisis**: Q1, Q5, Q10 fallan consistentemente. Otras fallan transitoriamente (se resuelven en reintento).

**Acciones**:
1. Verificar logs de LiteLLM para rate limiting o timeouts en el modelo `openai_gpt-5.4-nano`.
2. Aumentar `litellm_timeout_seconds` de 60 a 120 en `core/config.py`.
3. Agregar un reintento automático (2 intentos) en `build_editorial_answer_with_ai()` (`relation_qa_ai.py`) si el primer parseo falla.
4. Implementar un fallback AI más robusto: si el LLM devuelve JSON inválido, usar una segunda llamada con instrucciones más estrictas.

**Estimación**: 2-4 horas (debug + ajuste de código).

### P0-2: Mejorar deterministic fallback editorial

**Problema**: Cuando AI falla, la respuesta editorial es idéntica a la conclusión corta o solo lista fuentes sin síntesis.

**Acción**: Mejorar `_deterministic_answer()` en `relation_qa_service.py` para generar un resumen estructurado:
- Agrupar fuentes por tipo de evidencia
- Indicar qué conceptos aparecen literalmente y cuáles solo por coocurrencia
- Marcar explícitamente que "esta respuesta es automática y no incluye análisis editorial"

**Estimación**: 1-2 horas.

### P0-3: Mejorar detección de conceptos

**Problema**: `extract_concepts_from_question()` prioriza palabras de la pregunta sobre el mapeo conceptual del dominio. Detecta "literalmente" y "tema" en lugar de "hitbodedut".

**Acción**: 
1. Hacer que `extract_concepts_from_question()` primero busque en `CONCEPT_EXPANSIONS` (mapeo canónico) antes de extraer palabras genéricas.
2. Si el usuario proporciona `concept_a`/`concept_b` explícitos, respetarlos siempre.
3. Para preguntas sin conceptos explícitos, usar heurística: ignorar palabras como "dónde", "qué", "cómo", "aparece", "citado", "literalmente", "tema" como posibles conceptos.

**Estimación**: 2-3 horas.

---

## Recomendaciones P1

### P1-1: Expandir variantes conceptuales por dominio

**Problema**: Variantes faltantes para preguntas específicas:
- "tristeza" → falta "atzevut", "עצבות"
- "alegría" → falta "simjá", "שמחה"
- "miedo" → falta "yirá", "יראה"
- "emuná" → falta "fe", "creencia"

**Acción**: Agregar estas variantes a `CONCEPT_EXPANSIONS` en `relation_qa_evidence.py`.

**Estimación**: 30 minutos.

### P1-2: Agregar reintento automático en AI synthesis

**Problema**: Fallas transitorias de LiteLLM resueltas en reintento manual.

**Acción**: En `build_editorial_answer_with_ai()`, agregar un reintento con backoff (máx 2 intentos) si el primer parseo falla o hay timeout.

**Estimación**: 1 hora.

### P1-3: Mejorar validación de AI para reducir falsos positivos

**Problema**: `validate_editorial_ai_result()` rechaza respuestas si los source_ids no coinciden exactamente.

**Acción**: Normalizar source_ids antes de comparar (trim, lowercase). Considerar fuzzy matching para IDs muy similares.

**Estimación**: 1 hora.

---

## Recomendaciones P2

### P2-1: Renderizar markdown en UI

**Problema**: `editorial_answer_markdown` se muestra con `whitespace-pre-line` en vez de parseado.

**Acción**: Usar una librería markdown ligera (marked, markdown-it) o un componente Svelte markdown para renderizar correctamente títulos, listas y negritas.

**Archivo**: `SrvRestAstroLS_v1/astro/src/components/library/RelationQAPanel.svelte` línea 238-245.

**Estimación**: 1-2 horas.

### P2-2: Colapsar fuentes por defecto

**Problema**: 20 fuentes siempre expandidas saturan la UI.

**Acción**: Empezar con fuentes colapsadas (solo título + tipo + página) y expandir con clic. Mantener las primeras 3-5 fuentes más relevantes visibles.

**Archivo**: `RelationQAPanel.svelte`.

**Estimación**: 1-2 horas.

### P2-3: Indicador de "AI falló" en UI

**Problema**: Cuando AI falla, no hay indicador visual claro.

**Acción**: Si `warnings` incluye `ai_response_parse_failed`, mostrar un banner "Respuesta automática - sin análisis editorial" con color warning.

**Archivo**: `RelationQAPanel.svelte`.

**Estimación**: 30 minutos.

### P2-4: Agregar variantes hebreas faltantes

**Problema**: Variantes hebreas faltantes para conceptos comunes.

**Acción**: Revisar `CONCEPT_EXPANSIONS` y agregar:
- tristeza → atzevut, עצבות, marah, מרה
- alegría → simjá, שמחה, gilah, גילה
- miedo → yirá, יראה, pachad, פחד
- emuná → emuná, אמונה, fe, creencia

**Estimación**: 30 minutos.

---

## Priorización

| Prioridad | Acción | Esfuerzo | Impacto |
|---|---|---|---|
| P0-1 | Diagnosticar AI synthesis | 2-4h | Alto: estabiliza respuestas editoriales |
| P0-2 | Mejorar fallback determinístico | 1-2h | Alto: calidad mínima garantizada |
| P0-3 | Mejorar detección conceptos | 2-3h | Alto: UX conceptual |
| P1-1 | Expandir variantes conceptuales | 0.5h | Medio: recall |
| P1-2 | Reintento AI synthesis | 1h | Medio: reduce transitorios |
| P1-3 | Validación AI menos restrictiva | 1h | Medio: reduce falsos positivos |
| P2-1 | Renderizar markdown UI | 1-2h | Bajo: legibilidad |
| P2-2 | Colapsar fuentes | 1-2h | Bajo: UX |
| P2-3 | Indicador AI falló | 0.5h | Bajo: UX |
| P2-4 | Variantes hebreas | 0.5h | Medio: recall |

**Total estimado**: 10-16 horas.
