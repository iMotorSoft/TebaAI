# Matriz de validación de claims

| Claim público | Evidencia de implementación | Test o evidencia | Estado | Texto autorizado |
| --- | --- | --- | --- | --- |
| Consulta conversacional | `ResearchWorkspace.svelte` conserva turnos y follow-ups | suites `research*.spec.ts` | Disponible | Formular preguntas relacionadas conservando fuentes y evidencias anteriores |
| Español, inglés y hebreo | filtros `es/he/en`, interpretación y pruebas multilingües | `research-multilingual.spec.ts`, status actual | Disponible | Consultar obras en español, inglés y hebreo |
| RTL hebreo | `lang`, `dir`, helpers de dirección | `research-hebrew.spec.ts` y home Axe | Disponible | Los fragmentos hebreos respetan RTL |
| Obra, páginas y sección | campos `work_title`, `physical_pdf_page`, `printed_page`, `section` | `investigativeQaClient.test.ts` y suites de trazabilidad | Disponible cuando hay metadata | Referencias de obra, página y sección; faltantes informados |
| Cita y contexto | texto de evidencia y panel de fuente | `research-traceability.spec.ts` | Disponible | Recuperar citas en su contexto disponible |
| Capas editoriales | `source_layer` allowlisted y labels públicas | `research-source-layer.spec.ts` | Disponible | Distinguir original, cita, traducción, comentario y nota |
| Traducción vinculada | evidencia paralela sólo con vínculo validado | status actual y source-layer tests | Condicional | Traducción vinculada, cuando existe |
| Comparación entre obras | intent de comparación, matriz y relevancia | `research.spec.ts` y backend vigente | Disponible con límites | Organizar coincidencias y relaciones temáticas con sus límites |
| Seguimiento | historial de turnos enviado como contexto | suites multilingües y de trazabilidad | Disponible | Continuar mediante preguntas relacionadas |
| Tolerancia ortográfica | HEAD inicial incluye commits dedicados y tests | Vitest/backend vigente | Disponible, no promovido en hero | Omitido del mensaje principal |
| Autoridad doctrinal | No existe ni se pretende | revisión editorial | Excluido | No determina conclusiones doctrinales |
