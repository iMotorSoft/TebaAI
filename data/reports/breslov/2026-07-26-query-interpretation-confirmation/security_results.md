# Seguridad

- `interpretation_id` es UUID opaco y se resuelve sólo en servidor.
- Cada registro queda ligado a `sub` autenticado y `conversation_id`.
- IDs inexistentes o de otro usuario se responden como no encontrados.
- Conversación incorrecta, expiración y estado superseded se rechazan.
- Analyze usa `original_query`, interpretación y named topic almacenados; no confía en campos manipulados del cliente.
- No se reciben evidence IDs, SQL ni planes de retrieval desde UI.
- Works, languages y límites conservan validación allowlisted.
- El cliente escapa/sanea texto visible y no usa HTML para la interpretación.
- No se registran prompts, cookies, tokens, credenciales ni chain of thought.
- El scan no encontró secretos nuevos. Dos literales preexistentes pertenecen a documentación histórica y fixture de test y no fueron modificados.

Limitación registrada: el store es in-process porque el runtime canónico actual usa un worker. Una futura topología multi-worker deberá mover este estado a PostgreSQL antes de habilitarla.
