# ADR — AI-assisted notes LM II

Geometría sola no enlaza continuadores con seguridad. Se intenta adjudicación IA vía LiteLLM con JSON auditado y umbral 0.85. Si falla o es baja, no se descarta texto: se crea satélite citable no enlazado con PageAnchor físico, span, semantic unit, `fallback_unlinked` y sin relación fuerte. Así se distinguen página física y target lógico opcional, se preserva autoridad y se expone al investigador la traza IA/fallback. Las lecciones estándar pueden masificarse; layouts especiales requieren perfiles propios.
