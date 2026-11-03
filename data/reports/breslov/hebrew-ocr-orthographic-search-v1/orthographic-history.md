# Historia dirigida de búsqueda hebrea

Consultas ejecutadas (no auditoría masiva):

```bash
rg -n 'orthograph|plene|defective|כתיב|פירוש|פרוש|query.expansion' \
 SrvRestAstroLS_v1/backend/modules/library SrvRestAstroLS_v1/backend/tests \
 data/reports/breslov/regional-ocr-hebrew-search-v1 --glob '*.py' --glob '*.json' --glob '*.md'
git log -8 --oneline --all --grep='hebrew\|Hebrew\|orthograph\|niqqud'
git log -6 --all --oneline --grep='orthograph\|spelling\|Hebrew literal\|multilingual'
git log -5 --oneline -- SrvRestAstroLS_v1/backend/modules/library/hebrew_lexical_normalizer.py
git show 126b678 --stat
```

Reutilizable:

- `hebrew_lexical_normalizer.py`: marks, presentation forms, controles bidi, maqaf y separación de glyphs PDF. `normalize_hebrew_search` preserva consonantes/finales; usa además tolerancia de puntuación, por tanto no es identidad editorial.
- `126b678`: normalización literal y prioridad Hebrew; aproximaciones de segmentación PDF no son plene/defective spelling.
- `f4fefa7` y `35e266f`: retrieval cross-language/multilingüe; no prueba de relación ortográfica absoluta.
- `simple_research_rag.py`: `_english_name_orthographic_variants`, específica English; no trasladar automáticamente a Hebrew.
- `lat.md/breslov-lemma-shoresh-layer-design.md`: expansión conceptual curada, preservación de query y advertencia de colisiones Hebrew; no spelling corrector ni benchmark de מלא/חסר.
- `2026-07-16-research-workspace-v1/hebrew_literal_batch.json`: goldens reales LM I / 96 con `תְּפִלָּה`, `חִדּוּשִׁין`, `עִבּוּר`; evidencia histórica de mismo fragmento con/sin marks, no medición semántica actual.
- Reporte regional anterior: caso `פירוש / פרוש` correctamente NO equivalente por sólo niqqud.

No se encontró una regla hebrea general מלא/חסר certificada en esta búsqueda limitada. No implica ausencia universal en todas las ramas/reportes. Se conservó el helper existente, no se añadió tolerancia al corpus. Las 8 entradas dirigidas nuevas viven exclusivamente en el experimento offline, con contextos/guardas anotados: NO son un diccionario lingüístico validado.
