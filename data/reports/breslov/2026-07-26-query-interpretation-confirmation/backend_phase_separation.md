# Separación backend

Se eligió un endpoint con modo explícito para preservar consumidores legacy:

- `phase=interpret`: `prepare_query` + contrato visible, sin adquirir pool PostgreSQL;
- `phase=analyze`: valida el ID, reconstruye `PreparedQuery` desde el registro servidor y ejecuta el pipeline existente;
- `phase=legacy`: compatibilidad para consumidores previos; `/research` no lo usa.

La preparación aprobada se pasa a `run(..., prepared=...)`, evitando reinterpretar o volver a llamar IA antes del retrieval.
