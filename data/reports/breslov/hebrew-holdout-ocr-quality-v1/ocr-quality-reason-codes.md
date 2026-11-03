# Reason codes

| Code | Significado / uso |
|---|---|
| OCR_DIGIT_LOSS | Secuencia numérica distinta de referencia estructural fiable; MATERIAL_OCR_ERROR; rechazo obligatorio, incluye sustitución/inserción |
| OCR_WORD_MERGE | Mismas letras, menos límites frente referencia confiable |
| OCR_WORD_SPLIT | Mismas letras, más límites frente referencia confiable |
| OCR_BASE_LETTER_ERROR | Diferencia material frente referencia confiable |
| OCR_LOW_HEBREW_RATIO | Reservado diagnóstico; sin umbral calibrado, no aplicado (LTR válido no es error) |
| OCR_UNICODE_INVALID | U+FFFD, surrogate o private-use inesperado |
| OCR_GEOMETRY_MISMATCH | Metadata de layout no certifica una región lógica; columna combinada conocida |
| OCR_CONFIG_DISAGREEMENT | 300/400 DPI difieren en letras/orden/límites/puntuación; no decide qué salida es correcta |
| OCR_UNCERTAIN | Sin referencia independiente confiable; fail closed |
| OCR_DISPLAY_UNCERTAIN | Search aceptable pero display sin transcript pointed completo |
| OCR_ACCEPT_SEARCH | Todas las condiciones operativas satisfechas; ninguno real en este replay |
| OCR_ACCEPT_DISPLAY | Además igualdad NFC de referencia display confiable; ninguno real |
| SOURCE_PDF_ERROR | Fuente visual defectuosa; no rescatar automáticamente (unit test sintético solamente) |

Los códigos merge/split/base-letter tienen cobertura unitaria sintética, no se
atribuyen al detector real cuando sólo el golden permite conocer el error.
El fallback es KEEP_NATIVE_RECONSTRUCTION_OR_UNRESOLVED; no SILENT_REPAIR.
