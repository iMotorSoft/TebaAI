# Editorial Scores — Relation QA Editorial Acid Batch

Evaluación por pregunta con puntaje 0–3 en cada criterio.
Máximo por pregunta: 24.

Clasificación:
- 21–24: PASS fuerte
- 17–20: PASS usable
- 13–16: WARN
- 0–12: FAIL

| ID | Pregunta | Conclusión | Fuentes | Evidencia | Warnings | Conceptos | Cobertura | UI/render | Método | Total | Estado | Observaciones |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | sangre y habla | 1 | 3 | 2 | 2 | 3 | 2 | 1 | 3 | 17 | PASS usable | AI synthesis falla consistente; respuesta editorial genérica |
| 2 | tristeza | 2 | 3 | 2 | 2 | 1 | 2 | 2 | 3 | 17 | PASS usable | AI funcionó pero respuesta pobre (solo 1 fuente referenciada) |
| 3 | miedo | 2 | 3 | 2 | 2 | 1 | 2 | 2 | 3 | 17 | PASS usable | AI funcionó en reintento; cobertura transversal mejorable |
| 4 | hitbodedut | 3 | 3 | 2 | 2 | 1 | 2 | 3 | 3 | 19 | PASS usable | Excelente distinción literal/temático; conceptos mal detectados |
| 5 | alegría-plegaria | 1 | 3 | 2 | 2 | 1 | 2 | 1 | 3 | 15 | WARN | AI falla consistente; respuesta solo lista fuentes |
| 6 | emuná | 2 | 3 | 2 | 2 | 1 | 2 | 2 | 3 | 17 | PASS usable | AI funcionó; detección conceptual limitada |
| 7 | ruaj-habla | 3 | 3 | 2 | 2 | 3 | 2 | 3 | 3 | 21 | PASS fuerte | AI funcionó; buena cobertura multilingüe |
| 8 | ojos-pulmones-luz | 2 | 3 | 2 | 2 | 1 | 2 | 3 | 3 | 18 | PASS usable | AI funcionó; respuesta honesta sobre límites |
| 9 | habla-respiración-profecía | 2 | 3 | 2 | 2 | 1 | 2 | 2 | 3 | 17 | PASS usable | AI funcionó en reintento |
| 10 | caída-renovación | 1 | 3 | 2 | 2 | 1 | 2 | 1 | 3 | 15 | WARN | AI falla consistente; respuesta genérica |

## Resumen

- **Promedio**: 17.3/24
- **PASS fuerte**: 1 (Q7)
- **PASS usable**: 7 (Q1, Q2, Q3, Q4, Q6, Q8, Q9)
- **WARN**: 2 (Q5, Q10)
- **FAIL**: 0

## Distribución por criterio

| Criterio | Promedio | Fortaleza |
|---|---|---|
| Conclusión | 1.9 | Mejorable: a menudo genérica cuando AI falla |
| Fuentes | 3.0 | Excelente: página/chunk/snippet siempre presentes |
| Evidencia | 2.0 | Buena: tipos variados, distingue literales |
| Warnings | 2.0 | Buenas: siempre presentes, protegen de sobreafirmación |
| Conceptos | 1.4 | Débil: variantes pobres, a veces detecta mal |
| Cobertura | 2.0 | Buena: 20 fuentes por consulta |
| UI/render | 2.1 | Variable: cuando AI funciona es excelente; cuando falla es genérica |
| Método | 3.0 | Excelente: PG+Milvus+FTS+vector siempre |

## Hallazgos principales

1. **AI synthesis falla ~30-50%**: Q1, Q5, Q10 consistentemente; otras con falla transitoria.
2. **Concept detection frágil**: detecta palabras de la pregunta en lugar de conceptos del dominio.
3. **Deterministic fallback genérico**: cuando AI falla, la respuesta es solo una lista de fuentes.
4. **Fuentes siempre auditables**: página, chunk, snippet, evidence type — excelente.
5. **Warnings siempre presentes**: protegen contra sobreafirmación doctrinal.
