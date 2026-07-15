# Modelo de evidencia cruzada

Fuerte: `literal_same_document_page`, `explicit_nominal_reference`, `resolved_reference`, `validated_numbered_note`, `validated_fine_zone`.

Media: `same_topic_same_work`, `same_halakhah_or_section_context`, `note_source_context`.

Débil: `thematic_parallel`, `remesh_or_derash_candidate`, `co_located_page_records`. No prueba relación doctrinal.

No evidencia: auditoría `rejected_false_positive`, nombres sin `surface_form`, IA sin quote o coincidencia semántica sin literal. Toda salida local conserva obra, quote y página cuando el origen la provee; si un chunk Kitzur carece de marcador se emite advertencia y no se inventa página.
