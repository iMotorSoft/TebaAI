# Literal evidence final gates — 2026-07-21

Rama: `feature/console-backend-core`. Checkpoint inicial: `659f9d0752df7874ac281313c4d3e54188967389`.

El caso «servir a HaShem por la noche» conserva `literal_lookup`, Likutey Halajot, PDF 137, `exact_phrase`, evidencia `lh-37c67830012c`, snippet visible limpio y raw separado para auditoría. La auditoría estructural mantiene `source_layer=unknown`, confianza baja y `author_quote_status=not_confirmed` porque la página es `page_literal_only` y no posee zona, nota o marcador validado.

La UI presenta una sola síntesis y un solo fragmento completo. El follow-up «¿es texto de Rabí Natán o comentario editorial?» usa `intent=source_layer_question`, conserva evidencia/obra/página y responde prudentemente desde la misma capa.

Gates cerrados: backend focal 133/133; backend completo 1036/1036; frontend 51/51; check 0; build 7 páginas; E2E focal 2/2, incluido UI 20/20; HTTP 20/20; función directa 20/20; texto corrupto 20/20; source layer 20/20; LAT y diff-check PASS. Playwright Chromium final: 59/59, retries 0.

Estados:

- `LITERAL_EVIDENCE_PRESENTATION_FULL_PASS`
- `CORRUPTED_SNIPPET_SANITIZATION_FULL_PASS`
- `SOURCE_LAYER_CLASSIFICATION_FULL_PASS`
- `LITERAL_OCCURRENCE_ATTRIBUTION_FULL_PASS`
- `DUPLICATED_SUMMARY_RENDERING_FULL_PASS`
- `LITERAL_EVIDENCE_UI_E2E_FULL_PASS`
- `READY_FOR_MANUAL_LITERAL_EVIDENCE_REVIEW`
