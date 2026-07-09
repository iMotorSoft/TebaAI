# Delta Scores — Relation QA Synthesis Hardening

| ID | Pregunta | Antes | Después | Delta | Estado final | Observación |
|---:|---|---:|---:|---:|---|---|
| 1 | sangre y habla | 17 | 20 | +3 | PASS usable | AI synthesis fija: guardrail + prompt |
| 5 | alegría-plegaria | 15 | 19 | +4 | PASS usable | AI synthesis fija: source count 15 + max_tokens 1600 |
| 10 | caída-renovación | 15 | 19 | +4 | PASS usable | AI synthesis fija: concept fix + max_tokens 1600 |
| 7 | ruaj-habla control | 21 | 21 | 0 | PASS fuerte | Control se mantiene; no degradado |

**Delta total: +11 puntos (promedio +2.75 por pregunta foco)**

## Síntesis de mejoras

1. **AI synthesis ahora funciona en 4/4 preguntas** (antes 2/4 en el batch original)
2. **Fallback determinístico mejorado**: incluye nombres de concepto, conteo de evidencia, warning explícito
3. **Concept detection mejorada**: preposiciones limpiadas, patrones "fuentes relacionan A y B", variantes expandidas
4. **Diagnóstico transparente**: method ahora incluye `ai_synthesis_status`, `fallback_reason`, `synthesis_mode`, `ai_synthesis_attempts`
