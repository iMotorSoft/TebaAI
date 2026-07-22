# Seguridad

- canonical IDs provienen sólo del JSON validado;
- schema `extra=forbid`;
- no SQL, prompts ni citations de modelo ingresan a retrieval;
- parámetros SQL siguen parametrizados;
- inputs HTML, prompt injection, SQL text, bidi y strings largas cubiertos;
- originales se renderizan mediante contratos sanitizados existentes;
- no se imprimieron ni versionaron credenciales, tokens, cookies o storage state;
- LiteLLM sigue siendo el único gateway de modelo.
