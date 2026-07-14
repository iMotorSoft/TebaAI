# ADR — LiteLLM note continuity fix

El cierre anterior no era suficiente: 29/29 HTTPStatusError ocultaban un modelo vacío. Se reutiliza el contrato de Relation QA con `openai_gpt-5.4-nano`, JSON estricto, retry de parseo y fallback citable. Relaciones sólo con confidence >=0.85, origen `ai_interpreted`; rollback: eliminar relaciones AI y restaurar metadata previa desde historial.
