# Relation QA Synthesis Hardening — 2026-07-09

Mejora de confiabilidad de síntesis IA y endurecimiento de detección de conceptos para `POST /library/relation-qa`.

## Resultado

| Pregunta | Antes | Después | Delta |
|---|---|---|---|
| Q1 sangre y habla | AI fallback (17) | AI ok (20) | +3 |
| Q5 alegría-plegaria | AI fallback (15) | AI ok (19) | +4 |
| Q10 caída-renovación | AI fallback (15) | AI ok (19) | +4 |
| Q7 ruaj-habla (control) | AI ok (21) | AI ok (21) | 0 |

**Delta total**: +11 puntos. **4/4 preguntas con AI synthesis funcional.**

## Cambios

| Archivo | Cambio |
|---|---|
| `relation_qa_ai.py` | Guardrail menos restrictivo, prompt fortalecido, max_tokens 1200→1600, sources 20→15 |
| `relation_qa_evidence.py` | Preposition stripping, nuevos patrones extracción, CONCEPT_EXPANSIONS expandido |
| `relation_qa_service.py` | Fallback mejorado, diagnosis fields, retry automático |
| `relation_qa_schemas.py` | Nuevos campos: ai_synthesis_status, fallback_reason, synthesis_mode |

## Servicios

- PostgreSQL: no tocado
- Milvus: no tocado
- LiteLLM: no tocado
- Corpus: no tocado
- Tests: 51/51 PASS
