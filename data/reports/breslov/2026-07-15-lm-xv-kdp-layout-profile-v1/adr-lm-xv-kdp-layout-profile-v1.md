# ADR — LM XV KDP layout profile V1

La fuente validada contiene texto embebido en 509/514 páginas y no coincide con Likutey Halajot. Se usaron bloques y coordenadas PyMuPDF, no OCR ni IA. El layout requiere preservar bloques/bbox y un orden column-aware futuro; por eso la estrategia es `PAGE_FIRST_COLUMN_AWARE_REQUIRED`. No hubo escrituras de DB, embeddings, Milvus ni relaciones.
