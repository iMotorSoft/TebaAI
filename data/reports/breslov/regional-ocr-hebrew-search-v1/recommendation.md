# Recomendación — offline, sin integración

## Veredictos

- OCR: **MORE_EVIDENCE_REQUIRED**.
- `TEBAAI_BRESLOV_REGIONAL_OCR_FALLBACK_EVALUATION_V1`: **BLOCKED** (sin motor OCR hebreo ejecutable/verificado).
- `TEBAAI_BRESLOV_PAGE167_HYBRID_EXTRACTION_BENCHMARK_V1`: **BLOCKED**; comparación native/historical/reconstruction completada, OCR no medido.
- SEARCH: **HEBREW_UNPOINTED_SEARCH_BLOCKED** como gate completo. Equivalencia por niqqud con **las mismas letras base** PASS offline; no se emite `TEBAAI_BRESLOV_HEBREW_UNPOINTED_SEARCH_V1_PASS` global ni runtime.
- `READY_FOR_C_REINGEST = NO`.

No confundir BLOCKED con DO_NOT_USE_OCR: falta medir su valor. Tampoco recomendarlo por ver U+FFFD sin una salida OCR comparada con el render.

## Contrato de búsqueda propuesto

**La búsqueda no exige niqqud.** Mantener `canonical_text/display_text/citation_text/source_text` intactos, con niqqud cuando fiable. De ellos derivar una representación de búsqueda; no almacenarla sobre el original. No hace falta reinventar una capa: ya existen `normalize_hebrew_lexical`, `normalize_hebrew_search`, `HebrewSearchNormalization.original/without_niqqud` y `search_text_normalized`.

La ingesta actual `analyze_page` llama `normalize_pdf_search_text`, no prueba automáticamente un índice Hebrew unpointed completo. La equivalencia en helpers/tests no equivale a retrieval vivo PG/Milvus. No se accedió a esos servicios.

Para una futura `search_text_he` estricta, adaptar lo existente: descomposición Unicode, quitar **solo combining marks hebreos** (niqqud/taamim/meteg y marcas hebreas de categoría M), preservar letras base/finales, límites, dígitos y orden lógico. Mantener puntuación de referencias en la representación estricta; variantes de puntuación solo en carril explícito secundario. No reverse, inverse-bidi global, autocorrect, consonant substitution, traducción ni guessed spelling. Display siempre vuelve a la evidencia canónica original. La función existente broad `normalize_hebrew_search` elimina P/S/C, usa NFKC y casefold: sirve para matching tolerante, **no como certificado de identidad de referencias**. `(LM I, 22:1)` y `(LM I, 22-1)` colisionan; deben tener guard estructural/números antes de aceptar un exact match. Los tests lo documentan sin modificar runtime.

### El golden solicitado no tiene las mismas consonantes

```text
וְזֶה פֵּרוּשׁ הַפָּסוּק → וזה פרוש הפסוק
query solicitada:            וזה פירוש הפסוק
                                 ↑ י adicional
```

No puede exigirse igualdad por *solo quitar niqqud* y a la vez prohibir cambios consonánticos. El caso estricto con `וזה פרוש הפסוק` encuentra el mismo ID offline y muestra exactamente el original. El source separado `וְזֶה פֵּירוּשׁ הַפָּסוּק` sí comparte letras base con `וזה פירוש הפסוק`; también pasa. No se cambió el golden solicitado: se conserva como prueba negativa de no inventar י. Encontrar variantes ortográficas מלא/חסר necesita contrato separado de expansión aproximada, no una normalización silenciosa ni spell-correction. Ese contrato y validación de retrieval vivo quedan pendientes.

«Sin false positives» se limita a las negativas verificadas de letras/números/orden/límites; no es demostrable universalmente. La insensibilidad intencional al niqqud puede unir lecturas distintas: devolver evidencia, no afirmar identidad semántica.

## Arquitectura candidata, NO implementada

Native → confidence check **por región** → render solo región problemática → OCR → validación de letras base/orden/límites/números → decisión separada search/display.

Triggers propuestos: U+FFFD/densidad, CID/font map conocido roto, mojibake conocido, distribución Unicode implausible y confianza decoder baja. Todos requieren calibración contra controles nativos buenos; no se implementó detector ni umbral. **Hebreo presente no es un error.** Fuentes visualmente defectuosas → SOURCE_PDF_ERROR, registrar page/bbox/description/render y continuar. Native bueno → PASS_NATIVE. Regresión estructural conocida → corregir estructura, no OCR. Divergencia material sin golden → UNRESOLVED_SOURCE_OR_PIPELINE.

La geometría nativa de página167 permite clips y metadatos PDF points/page/block_id/region; los archivos `page167-*.png` demuestran la parte render/provenance. Mapear palabras OCR de pixels a puntos requiere conservar crop origin + DPI/scale/rotation y validar boxes; aún **no demostrado**, porque no hay OCR. No afirmar word-level provenance probado por generar clips.

Notas: conservar bloques29/30 separados, izquierda antes de derecha; nota65 continúa en derecha. El candidato de reconstrucción combina ambas columnas por seqno/baseline y falla; no utilizar su output completo como canonical ni como search. El decoder histórico además convierte notas españolas en pseudohebreo. Preferir native PDF geometry + texto validado, no OCR que reemplace todo.

## Qué falta para decidir OCR

Autorizar explícitamente un motor/modelo hebreo ya existente o una instalación/API con revisión de coste/privacy. Sin añadirlo automáticamente. Ejecutar primero A/B de167 y el fragmento roto55;41/143 y solo regiones realmente corruptas de56. Native español correcto se mantiene como control negativo. Separar notas L/R como control geométrico; no usar OCR para tapar el contrato Markdown35/36.

Métricas contra fragmentos visibles revisados, no contra reconstrucción ni texto corrupto:

| Métrica | Definición prevista |
|---|---|
| HEBREW_BASE_LETTER_ACCURACY | 1−distancia editada / letras base golden, reportar inserciones/borrados/sustituciones y longitud; no inferir desde niqqud |
| WORD_ORDER_ACCURACY | pares/posiciones de tokens golden alineados en orden lógico; no ordenar OCR para ganar |
| WORD_BOUNDARY_ACCURACY | precision/recall de límites sobre alineación de letras base |
| NUMBER_ACCURACY | strings numéricos exactos por referencia/folio, incluidos separadores significativos |
| PUNCTUATION_ACCURACY | alineación de signos, paréntesis y atribución regional |
| NIQQUD_FIDELITY | marcas y ownership por grapheme; NFC/NFD equivalente, no desplazar marcas |
| UNEXPECTED_CHARACTER_RATE | caracteres fuera del inventario esperado del golden/region ÷ longitud OCR, con lista |
| U+FFFD_COUNT | conteo absoluto sin declararlo suficiencia de fidelidad |

Reportar n/denominadores por fragmento, no precisión libro entero. No hay porcentajes OCR en esta fase; valores null significan **no medido**, no cero ni FAIL. Calibrar umbrales sobre más goldens antes de un gate de integración. OCR_SEARCH_PASS exige letras/orden/límites fiables, sin invenciones ni alteraciones materiales; OCR_DISPLAY_PASS además números/puntuación/niqqud aceptables. Puede resultar OCR_SEARCH_PASS + OCR_DISPLAY_FAIL; jamás OCR canonical por ese único PASS search.

Full-page solo control posterior opcional; no hay ventaja demostrada ni recomendación como fuente principal. Esta fase termina antes del worker, aunque un benchmark posterior recomiende integrar. No reingesta sin siguiente gate autorizado.
