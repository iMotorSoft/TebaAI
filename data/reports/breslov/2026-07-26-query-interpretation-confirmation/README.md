# Confirmación previa de interpretación — 2026-07-26

Implementación y evidencia de la separación real entre interpretación y retrieval en `/research`.

## Resultado

- La consulta inicial ejecuta únicamente `phase=interpret`.
- La UI muestra una interpretación controlada y exactamente `Analizar` y `Modificar`.
- `Analizar` ejecuta una vez `phase=analyze`.
- `Modificar` reinterpreta, supersede la versión previa y no ejecuta retrieval.
- El backend conserva autoridad sobre consulta, intent, subject y plan mediante `interpretation_id`.
- Reload, filtros existentes, fallback, ES/EN/HE, RTL, móvil e idempotencia están cubiertos.

## Gates

- backend: 1122 passed;
- frontend Vitest: 55 passed;
- `pnpm check`: cero diagnósticos;
- build: 7 páginas;
- Playwright focal de confirmación: 6 passed;
- Playwright Chromium completo: 71 passed;
- batch determinístico: 30/30;
- flujo A UI/HTTP real: 20/20;
- flujo B UI/HTTP real: 20/20;
- capturas: 10 archivos en `screenshots/`.

Los checks finales se registran en `regression_results.json` y `frontend_results.json`.
