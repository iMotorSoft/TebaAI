# ADR — Ingesta page-first LM II

El fallback `LMII 7:1` se elimina por contaminación estructural. La ingesta textual sucede antes de la clasificación: una página con texto recibe ancla, nodo, span y unidad semántica aunque no se conozca lección. La estructura posterior es enriquecimiento; no se crean relaciones fuertes por fallback. Rollback: eliminar sólo nodos y unidades con `source_run_id=lmii_full_page_first_v1`.
