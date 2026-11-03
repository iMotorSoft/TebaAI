# Threshold analysis — no tuning

Política implementada en ocr_gate.py, hash previo al replay en ocr-gate-hash.txt.
No se ajustó después de observar resultados. No se buscó corte de confidence,
ratio hebreo, token counts ni agreement para hacer pasar las regiones buenas.

Tolerancia de discrepancia material = cero: trazabilidad exige números exactos;
referencia confiable debe preservar letras/orden/límites. Es un requisito de
integridad, no un porcentaje ajustado a muestra. DISPLAY exige además referencia
pointed/puntuada completa y exactitud NFC. Niqqud parcial puede ser search-only,
pero no basta sin corroboración independiente de letras.

Se midieron confidence TSV, disagreement nativo, número de palabras/tokens (mismo
split aquí), Unicode, ratio Hebrew, U+FFFD, geometría suministrada y líneas TSV.
No son un clasificador calibrado. Token divergence contra native corrupto y reducción
U+FFFD no validan OCR. Acuerdo entre dos DPI correlacionados no es prueba independiente.

Los dos headers muestran el problema: título 11/11 letras y secuencia estable,
pero 149→9 / 37→7. OCR_DIGIT_LOSS rechaza ambos por referencia ASCII nativa
corroborada visualmente. Crops sólo número también fallan. Son errores materiales,
no minor character errors. Fiabilidad de la referencia numérica está anotada,
no detectada automáticamente por el prototipo.

El fragmento pointed tiene 8/8 letras y 4/5 marks, pero no existe runtime trusted
base-reference para certificarlo sin usar golden. El gate lo rechaza; no se pasa
golden por otra clave ni se crea allowlist de regiones buenas. Línea143 y título
limpio también son false rejections. 3/3 buenos rechazados: BLOCKED, no PASS.

No hay sensibilidad/precisión operacional calibrada ni display positivos transcritos
exhaustivamente. No se exige alcanzar un recall arbitrario; la falta total de capacidad
de aceptación real basta para NO autorizar integración. El replay sólo prueba rechazo
condicionado a evidencia fiable. SOURCE ERROR != PLATFORM ERROR sigue intacto.
