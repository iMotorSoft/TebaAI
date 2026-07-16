# ADR — Breslov Conversational Investigative QA V1

El asistente usa IA desde el primer turno como intérprete estructurado y renderer de contexto cerrado, mediante el alias configurado `openai_gpt-5.4-nano` vía LiteLLM. SQL/vistas son la autoridad. El plan es allowlisted, no contiene SQL generado por IA y excluye auditoría por defecto. Todo renderer IA pasa grounding de IDs y páginas; si LiteLLM falla o el grounding rechaza, se entrega renderer determinístico. Terminal es la primera superficie sobre HTTP. V1 no usa fuentes externas, OCR, embeddings ni Milvus; las referencias nominales se muestran sólo como apariciones literales.

Alternativas descartadas: chatbot generativo libre, SQL creado por IA, render sin grounding, UI antes del contrato, Milvus obligatorio y convertir referencias nominales en relaciones.

Validación posterior: LiteLLM respondió realmente con `openai_gpt-5.4-nano`; el golden batch HTTP aceptó 15 renderings IA grounded y aplicó fallback determinístico seguro en 2 casos.
