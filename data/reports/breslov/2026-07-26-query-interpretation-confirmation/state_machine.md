# Máquina de estados

- `idle → interpreting → awaiting_interpretation_confirmation`
- `awaiting_interpretation_confirmation → analyzing → completed`
- `awaiting_interpretation_confirmation → editing_interpretation → interpreting → awaiting_interpretation_confirmation`
- cualquier solicitud fallida pasa a `error`.

El modelo de turno conserva bloques `query_interpretation` implícitos en el turno: pending, superseded y analyzed se corresponden con el estado autoritativo del registro. Una versión superseded no puede analizarse.

No existe transición directa `awaiting_interpretation_confirmation → completed`.
