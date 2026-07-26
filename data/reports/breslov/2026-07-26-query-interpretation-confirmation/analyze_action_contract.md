# Acción Analizar

El cliente envía `phase=analyze`, `interpretation_id`, `conversation_id`, filtros actuales e `idempotency_key`.

El servidor:

1. valida usuario, conversación, expiración y estado;
2. ignora la consulta modificada en el payload;
3. reconstruye intent y subject desde el registro;
4. ejecuta retrieval una sola vez;
5. cachea el resultado para llamadas idénticas o concurrentes;
6. vincula `approved_interpretation` al resultado.

La UI deshabilita doble envío y cambia a `analyzing`.
