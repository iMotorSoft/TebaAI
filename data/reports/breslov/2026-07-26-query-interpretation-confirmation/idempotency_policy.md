# Idempotencia

`interpretation_id` es la clave autoritativa de una aprobación. El primer `analyze` cambia el registro a `analyzing`; llamadas concurrentes esperan el mismo evento. Al completar, el resultado se conserva y las repeticiones reciben una copia del mismo resultado.

El cliente envía además `idempotency_key=analysis:{interpretation_id}` para auditoría. Cambiar esa key no permite ejecutar dos veces la misma interpretación.
