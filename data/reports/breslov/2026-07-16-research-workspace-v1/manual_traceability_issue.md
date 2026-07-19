# Defecto manual de trazabilidad

## Síntoma reproducido

Consulta: `la relacion entre sangre y el habla`.

La respuesta anterior recuperó 141 hits. El primer hit (`kitzur-0-938383`) era el fragmento del shamir, herramientas de hierro y derramamiento de sangre. Sólo coincidía con `sangre`, pero la UI lo presentaba como fuente inicial fuerte. Los IDs elegidos por los claims estaban en posiciones posteriores: 3, 4, 7 y 8 (índices humanos).

## Causa raíz

1. El backend asignaba `strong` a toda cita literal sin medir relevancia para una pregunta relacional.
2. Los claims IA incluían `evidence_ids`, pero el response no exponía una primaria ordenada y el frontend descartaba los claims al normalizar.
3. El frontend seleccionaba siempre `hits[0]`.
4. El límite se aplicaba por término y obra; 12 expansiones podían producir más de 10 hits finales por obra.
5. La interpretación IA incorporó términos ajenos al corpus —fisiología, hemoglobina e hipoxia— como autoridad de retrieval.
6. Los IDs usaban `hash()` y posición, por lo que no eran estables entre procesos.

## Corrección

- Conceptos y expansiones de retrieval derivados de la consulta y allowlists del backend.
- Deduplicación por obra y contenido, IDs SHA-256 estables y límite aplicado al resultado final.
- `claims`, `primary_evidence_ids`, `relation_relevance`, `literal_strength` y fuerza relacional separados.
- Claims relacionales sólo admiten evidencias que recuperaron ambos conceptos.
- La UI selecciona exclusivamente la primaria explícita o un fallback estructurado relacional.
- Coincidencias de un solo término quedan en “Otras coincidencias literales”.

El identificador histórico `kitzur-3-449169` no era durable porque incluía posición y `hash()` aleatorio del proceso. El registro equivalente conserva ahora un ID estable basado en obra y contenido.
