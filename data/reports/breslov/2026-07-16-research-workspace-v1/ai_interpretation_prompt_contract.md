# Contrato del intérprete IA

Modelo configurado: `openai_gpt-5.4-nano`, exclusivamente por el gateway LiteLLM del proyecto.

El modelo recibe la pregunta original, segmentos Unicode, filtros activos, historial acotado, catálogo cerrado de intents y obras, y ejemplos ES/EN/HE/mixtos. Debe devolver un único JSON compatible con `QueryInterpretation`.

El contrato le prohíbe producir fuentes, páginas, IDs, SQL, fuerza de evidencia, afirmaciones de existencia, prompt interno o razonamiento. Instrucciones del usuario que pretendan cambiar el schema se tratan como datos. El backend limita longitudes e historial, rechaza propiedades extra, canonicaliza variantes y contrasta sujetos con el input/contexto.

El texto completo del prompt no se expone en respuestas, logs ni este reporte. La observabilidad contiene sólo alias de modelo, duración, uso de IA/fallback, intent, idioma, confianza, cantidad de sujetos, modos de retrieval y cantidad de resultados.
