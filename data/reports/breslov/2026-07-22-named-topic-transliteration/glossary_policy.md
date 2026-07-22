# Política del glosario

- JSON versionado y validado al cargar.
- canonical IDs únicos y allowlisted por el archivo.
- aliases con idioma, script y bandera de búsqueda.
- la IA detecta spans; nunca crea equivalencias ni IDs.
- coincidencia exacta/normalizada primero; typo de distancia uno sólo para consulta completa, longitud mínima 8 y canonical único.
- aliases embebidos se aceptan sólo con wrappers de consulta controlados o en una relación explícita.
