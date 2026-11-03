# Auditoría OCR histórica acotada

`HISTORICAL_OCR_STATUS = FOUND_EXPERIMENTAL` **adyacente**, no un motor OCR probado.
OCR visual/raster hebreo ejecutado y validado: **NOT_FOUND** en el alcance revisado.
La auditoría histórica de 11 áreas sigue PASS; no se reabrió.

## Evidencia / alcance

- Búsqueda dirigida `ocr`, `tesseract`, `vision`, `raster`, `scanned`, `image extraction`, `visual fallback`, `hebrew ocr`: backend scripts/tests, ADR y reportes Breslov. Resultados conservados en `historical-ocr-search.txt` (52 coincidencias iniciales).
- `git log --all -G 'tesseract|hebrew.ocr|visual.fallback|scanned|raster|\bocr\b' -- SrvRestAstroLS_v1/backend docs/adr`: cuatro commits, conservados en `historical-ocr-git.txt`. Son probes/preflights/layout/ingesta nativa, no benchmark OCR regional. El alcance son refs disponibles y paths dirigidos, no todo Git ni archivos externos.
- `backend/scripts/lmii_ai_zone_classifier_spike.py`: tarea llamada `ocr_layout_zone_detection`, pero manda **page_text** extraído con `get_text('text')` a chat, NO una imagen. Clasifica zonas candidatas; no transcribe glifos del render. Inspeccionado, no ejecutado.
- `backend/scripts/library_ai_zone_candidate_store_import.py` y `data/reports/breslov/2026-07-14-lmii-ai-zone-candidate-store/README.md`: cuatro candidatos importados manualmente, `can_write_authoritative=false`. El nombre de modelo/origen almacenado no demuestra OCR real ni disponibilidad API actual. Importador SQL no ejecutado.
- Preflights de LH 2026-07-05 y LM XV 2026-07-15 dicen «OCR no requerido» por existencia de texto embebido. Esa señal NO certifica Unicode confiable; página167 lo refuta como criterio suficiente.
- ADR-022 excluye OCR de su alcance; ADR-020 no usa OCR/IA correctora.

## Reutilización

PARCIAL: separación candidato/autoridad, provenance, geometría y normalización lexical existente. NO un OCR engine, golden de precisión OCR, modelo hebreo disponible ni benchmark raster reutilizable. No reactivar SI-960 global: se conserva solo su output como comparador offline; vuelve a corromper notas españolas en página167. Ningún orquestador histórico SQL se importó/ejecutó.

## Inventario DEV

`engine-inventory.json`: PATH y backend venv reales, búsquedas dirigidas en `/usr/bin`, `/usr/local/bin`, `/opt` y cache local. Tesseract y paquetes pytesseract/easyocr/paddleocr/rapidocr/surya/docling/transformers/torch no disponibles en el entorno revisado; tampoco se localizó heb.traineddata en la búsqueda acotada. PyMuPDF y pdftoppm renderizan, no reconocen texto.

API OCR: no endpoint/modelo con entrada imagen y soporte hebreo **verificado**. Existe antecedente LiteLLM de clasificación textual, no disponibilidad demostrada de OCR. No se consultaron credenciales, no se hizo probe HTTP ni se enviaron regiones a proveedores. `NOT_AVAILABLE` significa no ejecutable/verificado para este benchmark, no prueba de inexistencia universal en el host o en proveedores. Coste/latencia OCR desconocidos; no inventar mediciones. No instalaciones, descargas ni servicios nuevos.
