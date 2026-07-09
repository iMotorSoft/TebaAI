# Diagnosis — Relation QA Synthesis Hardening

## Causa raíz por pregunta

| ID | Pregunta | Causa raíz antes | Causa raíz después | Fix aplicado |
|---:|---|---|---|---|
| 1 | sangre y habla | AI guardrail rechazó respuesta que decía "se encontró conexión...no literal" | AI ok (1 attempt) | Guardrail permite negación explícita "no se encontró" |
| 5 | alegría-plegaria | AI generaba source_ids no válidos (no en allowed set) | AI ok (1 attempt) | Reducir fuentes a 15 (de 20) + prompt más estricto |
| 10 | caída-renovación | AI devolvía JSON no válido (truncado por max_tokens) | AI ok (1 attempt) | max_tokens 1200→1600 + concepto "de caída espiritual"→"caída espiritual" |
| 7 | ruaj-habla (control) | AI ok | AI ok (1 attempt) | Sin cambios necesarios |

## Fixes aplicados

### relation_qa_ai.py
1. **Guardrail menos restrictivo** (línea 53-68): Permite frases que niegan explícitamente relación literal ("no se encontró una relación literal directa", "sin relación literal").
2. **Prompt fortalecido** (línea 122-146): Instrucciones más explícitas sobre no afirmar relaciones literales cuando no existen.
3. **max_tokens 1200→1600** (línea 149): Evita truncamiento de respuesta JSON del modelo.
4. **Sources reducidos 20→15** (línea 120): Menos fuentes = menos confusión para el modelo en source_ids.

### relation_qa_evidence.py
5. **Preposición stripping** (`_strip_prepositions`): Elimina "de", "del", "la", "el", "los" al inicio de conceptos extraídos (ej: "de caída espiritual" → "caída espiritual").
6. **Nuevos patrones de extracción** (en `extract_concepts_from_question`): "fuentes relacionan A y B", "textos conectan A y B", "libros tratan A", "dónde habla de A", "habla de A y B".
7. **Stopwords expandidas**: Agregadas "libro", "libros", "fuentes", "textos", "habla", "trata", "literalmente", "tema", "concepto" como términos a ignorar.
8. **CONCEPT_EXPANSIONS expandido**: tristeza/atzevut, alegría/simjá, plegaria/tefilá, miedo/yirá, emuná/fe, caída/yeridá, renovación/hitjadshut, ruaj/espíritu, profecía/nevuá, respiración/neshimá, luz/or, ojos/ayin, pulmones/reáj.

### relation_qa_service.py
9. **Fallback determinístico mejorado** (`_deterministic_answer`): Incluye nombres de conceptos, conteo de coocurrencias, menciones literales, y advertencia explícita.
10. **Campos de diagnosis en method**: `ai_synthesis_status`, `ai_synthesis_attempts`, `fallback_used`, `fallback_reason`, `synthesis_mode`.
11. **Reintento automático**: 2 intentos máximos para AI synthesis.
12. **Warning adicional** en fallback: "deterministic_fallback: la síntesis editorial automática no pudo completarse...".

### relation_qa_schemas.py
13. **Nuevos campos en RelationQAMethod**: `ai_synthesis_status`, `ai_synthesis_attempts`, `fallback_used`, `fallback_reason`, `synthesis_mode`.
