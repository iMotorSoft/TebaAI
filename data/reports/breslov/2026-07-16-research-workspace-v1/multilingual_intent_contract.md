# Contrato de intents multilingüe

La pregunta original es inmutable. El preprocesador identifica scripts, normalización Unicode y espaciado PDF; la interpretación clasifica estructura; el backend genera y ejecuta el retrieval.

Intents permitidos:

- `literal_lookup`: frase concreta; literal exacto y normalizado antes de FTS/trigram.
- `concept_lookup`: término o concepto; exacto, niqqud removido y prefijos controlados.
- `relation_query`: dos sujetos; exige recuperación individual y prioriza coaparición.
- `reference_lookup`: persona, obra o referencia nominal.
- `translation_or_explanation`: retrieval literal obligatorio antes de explicar.
- `follow_up`: reutiliza sólo sujetos validados de hasta 15 preguntas previas.
- `book_scope_query`: aplica una obra de la allowlist.
- `source_request`: recupera evidencia principal del sujeto previo validado.
- `comparison_query`: comparación explícita.
- `unknown`: entrada sin estructura segura.

Invariantes:

- ninguna salida de IA prueba existencia;
- las obras se reducen a `kitzur`, `lmi`, `lmii`, `lh`, `lm_xv` y `potencia_plegaria`;
- los sujetos deben estar anclados en segmentos del usuario o contexto validado;
- exacto precede a variante; hebreo precede a traducción secundaria;
- no se aceptan campos extra ni enums desconocidos;
- fallos HTTP, timeout, JSON o schema activan fallback, no un error de producto.
