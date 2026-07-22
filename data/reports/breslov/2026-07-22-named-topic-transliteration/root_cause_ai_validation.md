# Causa raíz — validación IA

El `ai_interpretation_fallback:ValidationError` histórico no reapareció en los probes vivos del HEAD `379ad8b`: LiteLLM produjo JSON válido para los 12 casos finales.

El failure mode se aisló con una respuesta de modelo incompleta: `QuerySubject` exigía `kind`, `raw`, `normalized`, `language`, `script` y `variants`; un objeto parcial como `{"raw":"tisha"}` falla en Pydantic y antes caía a un fallback que tampoco conocía el tema compuesto. El warning conservaba sólo el nombre de excepción, por lo cual no existe evidencia suficiente para atribuir un campo histórico exacto.

Corrección: el prompt permite `kind=named_topic` pero prohíbe canonical IDs; el backend reconstruye el sujeto y su canonical exclusivamente desde el glosario. Cualquier `ValidationError`, timeout o JSON inválido sigue usando fallback, ahora con el span completo y canonical controlado.
