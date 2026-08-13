# Validación visual

Superficies comparadas (misma identidad: `רבי נחמן · REBE NAJMÁN · BRESLOV RESEARCH`):

- `/research` admin con enlace «Gestor de Contenidos» (header desktop).
- Gestor — biblioteca documental (indicadores + tabla «Biblioteca»).
- Gestor — filtro «Mostrar datos de prueba» OFF/ON (badge `E2E`).
- Móvil 390×844: cards + panel móvil con «Gestor de Contenidos».

Reutilización:

- Tokens `app.css` (`navy`/`ivory`/`gold`, serif/sans).
- Patrones de `/research` (header sticky, kicker gold, focus visible).
- Sin sidebar SaaS, topbar Bootstrap ni admin theme independiente.

Capturas automáticas: `content-manager-captures.spec.ts` regenera los
estados (library/empty/upload/result/diagnostic) en 1440/1024/768/390.
