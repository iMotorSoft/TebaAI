# Defecto de prioridad del idioma

La recuperación LM XV comparaba la consulta con la extracción PDF cruda mediante `ILIKE`. La capa usa formas hebreas de presentación y espacios entre grafemas, por lo que una consulta Unicode estándar no recuperaba el original y podía promover una edición española.

La corrección mantiene PostgreSQL como autoridad, usa una proyección de lectura NFKC/NFC derivada del PDF sin reescribir el texto almacenado, identifica por separado idioma de instrucción e idioma del término, y ordena por literalidad, idioma y capa editorial.

Caso confirmado: la transcripción consultada con `וְהָיוּ` difiere del PDF, que imprime `וְהָיָה`. La diferencia se acepta únicamente como variante normalizada de distancia uno; la respuesta conserva la forma del PDF.
