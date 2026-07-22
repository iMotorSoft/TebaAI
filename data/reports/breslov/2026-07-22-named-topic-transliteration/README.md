# Resolución multilingüe de temas nominales — 2026-07-22

Estado automatizado: implementación y gates focales completos. La revisión humana queda guiada por `manual_review_checklist.md`.

- canonical focal: `jewish_calendar.tisha_beav` / `Tishá BeAv`;
- resolver: glosario versionado, previo al tokenizer y sin aliases creados por IA;
- retrieval: variantes nominales SQL sobre PostgreSQL, sin Milvus para aliases exactos;
- primary: Likutey Moharán XV KDP, PDF 262, impresa 248, `LIKUTEY MOHARÁN II #85:2`;
- repetición: función 20/20 por forma, HTTP 40/40 y UI 40/40;
- capturas: `screenshots/`.

El `ValidationError` observado antes de esta fase no reapareció en el HEAD inicial con LiteLLM vivo. La causa verificable del failure mode es incompatibilidad entre JSON de modelo incompleto y el schema estricto de `QuerySubject`; el fallback ahora conserva el span nominal completo y resuelve por glosario.
