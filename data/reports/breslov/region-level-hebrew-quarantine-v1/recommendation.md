# Recomendación

No activar ni anunciar region-level quarantine en runtime todavía.

El consumidor offline pasa sus pruebas, pero el worker sigue publicando páginas completas y no conserva durablemente el PDF upload. Completar el handoff de regiones y el storage de fuente antes de ejecutar un worker E2E aislado. Ver `architecture-decision.md`.

No resolver esta integración aceptando regiones por apariencia limpia, degradando certificación, usando OCR, reconstruyendo hebreo o modificando el evaluador. No requiere nuevo holdout independiente ni perfección global de extracción.

REGION_LEVEL_QUARANTINE_READY=NO
FULL_C_REINGEST_READY=NO
COMMIT=NO
PUSH=NO
