# Breslov Research workspace v1

Estado técnico de recuperación: `LANGUAGE_PRIORITY_AND_SOURCE_LAYER_FULL_PASS`, listo para `READY_FOR_MANUAL_SOURCE_LAYER_REVIEW`.

Estado general: `SOURCE_LAYER_FOLLOWUP_ANSWER_BLOCKED`. La recuperación, trazabilidad y clasificación son correctas, pero la respuesta narrativa del follow-up sobre si el fragmento es lección, cita o nota reutiliza contenido del turno anterior y no responde directamente. Por este motivo este directorio preserva un checkpoint validado, no un `FULL_PASS` general.

La fase implementa `/research` como workspace privado editorial: navegación de sesión, respuesta Markdown sanitizada, evidencia estructurada, matrices, fuentes seleccionables, filtros y drawers responsive. El backend y Astro se mantuvieron en PTY persistentes durante implementación y pruebas.

La revisión manual inicial descubrió una asociación incorrecta entre el claim sangre-habla y el primer hit literal. La causa, el contrato corregido y los batches están documentados en `manual_traceability_issue.md`, `traceability_contract.md`, `traceability_golden_batch.json` y `noise_negative_results.json`.

La segunda revisión manual descubrió fragmentación visual del hebreo. La comparación backend→DOM, análisis Unicode, contrato bidi, batch real 10/10, resultados E2E y checklist humano están en los artefactos `hebrew_*` de este directorio. El cierre automatizado del 2026-07-18 conserva el texto canónico y usa una proyección NFC derivada de geometría sólo para presentación.

El checkpoint del 2026-07-19 aprobó backend focalizado, batches conversacionales, Playwright Chromium completo, hidratación focal, `lat check`, `git diff --check` y revisión de credenciales sin secretos hardcodeados. La corrección separa el idioma del sujeto del usuario de los aliases secundarios usados sólo para retrieval. Los E2E multi-turno verifican estabilidad de evidencia, no todavía la formulación directa del follow-up de capa.

Limitaciones vigentes: el endpoint v1 conserva identificadores de conversación nulos; el contexto de seguimiento se resuelve en backend a partir del historial acotado y el frontend no resuelve pronombres ni extrae IDs desde Markdown. Además, `SOURCE_LAYER_FOLLOWUP_ANSWER_BLOCKED` debe corregirse en un commit separado para que la narración use la capa del turno actual y conteste primero sí/no/no confirmado.
