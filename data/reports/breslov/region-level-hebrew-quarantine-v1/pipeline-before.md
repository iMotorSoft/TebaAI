# Pipeline antes de cambios

Base: `704ae24597e916b56ddec8a71fd0a30d34793aab`, rama `feature/console-backend-core`.

1. `content_manager_worker.py` ejecuta `ConcretePageFirstPipeline`.
2. `page_first_pipeline.extract_pdf_page_first` llama `pdf_hebrew_fidelity.page_markdown` por página física. `analyze_page` sólo deriva normalización y señales editoriales, no calidad.
3. `ExtractedPage` transporta una cadena por página, sin regiones/certificados.
4. `ExtractedDocument.content_markdown` concatena páginas completas.
5. `PostgresMilvusPageFirstGateway.persist_document_and_pages` persiste esas cadenas en `library_document_texts` y `library_pages_v2`.
6. `persist_chunks` ejecuta `paragraph_chunks(page.original_markdown, 1400, 150, 1)`. No consulta calidad ni procedencia regional. Puede cruzar un hueco que debería estar quarantined.
7. El pipeline embebe todos los chunks, persiste embeddings y llama `index_vectors` (Milvus), después reconcilia por manifest.
8. Retrieval literal lee chunks PG; retrieval vectorial obtiene IDs Milvus y rehidrata PG. Las citas usan evidencia textual derivada de esos chunks. No existe en este camino una exclusión regional previa.
9. `finalize` elimina el PDF temporal y pone `temp_path=NULL`; el INSERT documental no persiste `source_path`. Un hash/bbox por sí solo no garantiza acceso visual posterior.

## Dónde se pierde granularidad

La extracción del worker ya entrega una página concatenada. La frontera alternativa `extract_pdf_with_region_certificates` sí entrega V5 y procedencia forward, pero es opt-in/offline; el worker no la consume. Las representaciones no se deben vincular por búsqueda inversa de texto.

`region_quality.QualityPage` ya expresa FULL/PARTIAL/UNUSABLE y unidades separadas, pero sus positivos requieren evidencia. V5 entrega `CertifiedPage` con unidades/rangos/certificados, por lo que se puede probar un consumidor sin cambiar el evaluador ni aceptar texto por apariencia.

## Límite observado (no nuevo requisito de holdout)

Probe actual de C, páginas 55/167/168: existen ACCEPTED y UNRESOLVED en la misma página. V5 no es certificación universal de todo contenido bueno. Activarlo indiscriminadamente no demuestra GOOD_NEIGHBOR_LOSS=0 respecto al contenido válido del worker actual. No se exige holdout independiente ni recall cross-page para este gate.
