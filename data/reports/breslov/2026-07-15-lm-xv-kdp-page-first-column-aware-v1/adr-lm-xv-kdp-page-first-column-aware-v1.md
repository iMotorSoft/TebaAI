# ADR — LM XV KDP page-first column-aware V1

## Contexto

Se ingiere el PDF validado `LIKUTEY MOHARÁN XV KDP.pdf` (SHA-256 `f4d7…1303`), no Likutey Halajot. El perfil previo confirmó texto embebido suficiente y 52 páginas con columnas estrictas.

## Decisión

PyMuPDF provee el texto autoritativo, bloques y coordenadas. Se guardan 514 filas de página y 3.208 bloques. El orden es `blank` (5), `raw_order` (2), `block_order` (455) o `column_aware_order` (52). La fase no invoca OCR/layout; queda permitido sólo como hint visual futuro, nunca como reemplazo textual.

## Consecuencias

La búsqueda inicial funciona por literal, página, hebreo, estado y metadatos de layout. No se escribieron embeddings, Milvus, relaciones, lecciones, notas ni referencias nominales. La siguiente fase puede detectar estructura usando evidencia local y bbox.
