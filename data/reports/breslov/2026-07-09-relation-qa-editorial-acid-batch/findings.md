# Findings — Relation QA Editorial Acid Batch

Fecha: 2026-07-09
Branch: `feature/console-backend-core`
HEAD: `f13882280e8206eab5b47c7c99d7e9363b8968b9`
Endpoint: `POST /library/relation-qa`

---

## Hallazgos positivos

### H1. Auditabilidad excelente de fuentes
Cada fuente en todas las 10 preguntas incluye: título del documento, número de página, chunk_id, tipo de evidencia, score y snippet. Un investigador puede localizar exactamente el fragmento citado. Score: 3/3 en el criterio Fuentes.

### H2. Warnings metodológicos siempre presentes
Todas las respuestas incluyen advertencias como `no_literal_relation`, `cooccurrence_only`, y `ai_inference`. Esto protege al usuario de sobreafirmar relaciones doctrinales. Score: 2-3/3.

### H3. Diversidad de métodos de retrieval
Todas las consultas usan 4 métodos: PostgreSQL FTS websearch, ILIKE fallback, coocurrencia PostgreSQL, y vectorial Milvus cosine similarity. Score: 3/3.

### H4. Evidencia multilingüe
Conceptos como "sangre" incluyen variantes en español, inglés y hebreo (sangre, blood, דם, dam). La expansión hebrea permite recuperar fragmentos en el idioma original.

### H5. Distinción literal/temática cuando AI funciona
Q4 (hitbodedut), Q7 (ruaj-habla) y Q8 (ojos-pulmones-luz) muestran respuestas editoriales que distinguen claramente entre evidencia literal y temática/inferida.

---

## Fallas editoriales

### F1. Respuesta editorial genérica cuando AI falla (P0)
**Evidencia**: Q1, Q5, Q10 muestran respuesta editorial que es idéntica a la conclusión corta o lista fuentes sin síntesis.
**Impacto**: El investigador no obtiene análisis editorial, solo un volcado de fuentes.
**Frecuencia**: 30-50% de las consultas.

### F2. Respuesta editorial pobre incluso cuando AI funciona
**Evidencia**: Q2 (tristeza) solo referencia 1 fuente en la síntesis editorial, a pesar de tener 20 fuentes recuperadas.
**Impacto**: La síntesis es demasiado superficial para un investigador serio.

---

## Fallas de retrieval

### F3. Conceptos detectados incorrectamente (P1)
**Evidencia**: Q4 detecta conceptos "literalmente" y "tema" (extraídos de la pregunta) en lugar de "hitbodedut". Q3 detecta conceptos pobres ("miedo" sin variantes hebreas como "yirá").
**Causa raíz**: `extract_concepts_from_question()` en `relation_qa_evidence.py` prioriza palabras de la pregunta sobre el mapeo conceptual del dominio.
**Impacto**: El usuario ve conceptos irrelevantes en la UI.

### F4. Falta de variantes conceptuales en preguntas específicas
**Evidencia**: Q2 busca "tristeza" sin variantes hebreas (atzevut, עצבות, melancolía). Q5 busca "alegría" sin incluir "simjá" como variante hebrea prioritaria.
**Impacto**: Pérdida de recall en fragmentos hebreos donde el concepto aparece en su forma original.

---

## Fallas de síntesis

### F5. AI synthesis inconsistente (P0)
**Evidencia**: De 10 consultas, 5 fallaron AI en el primer intento (Q1, Q3, Q5, Q9, Q10). En reintento, Q3 y Q9 tuvieron éxito, pero Q1, Q5, Q10 persistieron fallando.
**Causa probable**: LiteLLM puede tener rate limiting o timeouts. El parseo de respuesta JSON del modelo también puede fallar si el LLM devuelve source_ids no válidos.
**Impacto**: El usuario obtiene calidad inconsistentemente.

### F6. Validación de AI muy restrictiva
**Evidencia**: El `validate_editorial_ai_result()` en `relation_qa_ai.py` rechaza respuestas si los source_ids no son un subconjunto exacto de los permitidos. Esto puede causar falsos positivos de validación cuando el LLM referencia correctamente la fuente pero con un formato ligeramente diferente.
**Impacto**: AI parse failures innecesarios.

---

## Fallas de UI/render

### F7. Markdown no parseado en UI
**Evidencia**: `editorial_answer_markdown` se renderiza con `whitespace-pre-line` en lugar de un parser markdown real. Los títulos y negritas no se renderizan.
**Impacto**: La respuesta editorial se ve plana en la UI, sin jerarquía visual.

### F8. Sin colapso de fuentes por defecto
**Evidencia**: Las 20 fuentes siempre se muestran expandidas. Para un investigador que quiere la síntesis primero, esto es abrumador.

---

## Riesgos de sobreafirmación

### R1. Deterministic fallback no advierte su propia limitación
Cuando AI falla, el fallback determinístico no incluye un warning explícito como "Esta respuesta es automática y no incluye análisis editorial.". El único indicio es que el `editorial_answer_markdown` se ve diferente.

### R2. Conceptos sin contexto teológico
Conceptos como "ruaj" (viento/espíritu) se presentan sin aclarar que tienen múltiples significados en el corpus Breslov. Un usuario no especializado podría interpretar incorrectamente.

---

## Preguntas que requieren revisión humana

| ID | Pregunta | Motivo |
|---|---|---|
| 1 | sangre y habla | AI falla consistentemente; la conexión conceptual existe pero requiere interpretación cuidadosa |
| 5 | alegría y plegaria | AI falla; conceptos comunes que el endpoint debería poder relacionar |
| 8 | ojos, pulmones y luz | No hay relación conjunta en corpus; respuesta honesta pero insatisfactoria |
| 10 | caída espiritual y renovación | AI falla; tema genérico que da respuestas genéricas |
