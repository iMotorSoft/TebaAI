# Continuación tras reset de conversación — 2026-10-11

Rama: `feature/console-backend-core`. Gate integral **BLOCKED**. Sin commit/push ni acceso/mutación a producción. Esta continuación no ejecutó otro reset, ingesta ni publicación.

## Estado medido

`user-reset-observation.json`: los tres documentos nuevos siguen ready en DEV: A 196/296, B 416/908, C 284/942 (páginas/chunks); total 896 páginas, 2146 chunks, 2146 entidades vivas en Milvus primary. Las otras seis colecciones TebaAI revisadas están vacías. Esto NO es corpus cero y NO prueba por sí solo fidelidad editorial. Las validaciones A/B previas permanecen acotadas a sus muestras críticas; C sigue bloqueado.

La cuenta de archivos observada por ese proceso corresponde a su propia configuración de storage y no certifica que el storage del worker activo esté vacío. No se borraron archivos ni PDFs.

## C: diagnóstico a primera capa

1. Cuatro fuentes CID/Identity-H carecen de ToUnicode. Se renderizaron sus glifos directamente desde los programas embebidos; atlas de glifos y atlas ampliados de marcas conservados. Mapas exactos seleccionados por SHA-256, no por familia, título, filename o vocabulario. Se revisaron diferencias entre shin/sin, dagesh, holam y compuestos kaf/lamed.
2. Nuevo prototipo reusable `backend/modules/library/pdf_font_unicode.py` y banco de datos `modules/library/data/pdf_font_unicode_profiles.json`: añade ToUnicode únicamente a una instancia en memoria y únicamente a cuatro programas de font conocidos sin mapa existente. **No está conectado al flujo de ingesta**. El original C conserva su hash.
3. El prototipo recupera Unicode, pero los resultados Markdown siguen incorrectos: el converter divide/reordena palabras y emite marcas delante de sus bases. No se adoptó un mapeo semánticamente falso para compensar el comportamiento del converter.
4. Diagnóstico aislado con inhibición de espacios sintéticos mejora la secuencia de palabras, pero no resuelve la asociación de marcas ni el orden de todos los segmentos. Ese cambio afectó solo el proceso de prueba; no se modificó el paquete, configuración, servidor ni pipeline activo.
5. Hallazgo adicional, reproducible: el PDF conserva texto antiguo debajo de rectángulos blancos opacos y dibuja luego traducciones. La extracción incluye contenido no visible. `probe-c-fonts.py` identifica **671 runs enteramente cubiertos** en el documento (no son 671 errores independientes). `c-font-visibility-probe.json` conserva bbox, fuente, glyph IDs y secuencias de texto/cobertura; detecta todavía cuatro runs con reemplazos no enteramente cubiertos en las páginas revisadas (1/55/56/143).

Ejemplo página física 55:
- texto secuencia 16, bbox `[209.875,178.159,289.023,184.809]`, debajo del rectángulo blanco opaco secuencia 17, bbox `[208.988,176.340,291.232,187.529]`;
- texto secuencia 21, bbox `[226.478,555.301,272.841,561.951]`, debajo del rectángulo blanco opaco secuencia 22, bbox `[222.554,552.217,278.246,563.500]`.

Esto no autoriza borrar todos los U+FFFD o transcribir headers según vocabulario. Debe demostrarse visibilidad por geometría/orden de pintura y preservar el texto sobrepuesto que sí se ve. La cobertura parcial requiere diagnóstico adicional; no se considera invisible un run solo por intersectar un rectángulo.

## Validaciones de esta continuación

- Backend: `test_pdf_font_unicode.py`, `test_pdf_hebrew_fidelity.py`, `test_dev_content_reset.py`: **47 PASS**.
- Frontend: `markdownRenderer.test.ts`, `sourceTextRuns.test.ts`: **35 PASS**.
- `pnpm check`: 0 errores, 9 hints preexistentes; `pnpm build`: PASS, 9 páginas.
- Probe completo de fuente C: PASS como diagnóstico; PDF SHA antes/después idéntico.
- `git diff --check`: PASS.
- Estos tests no equivalen a cerrar C, a QA Chromium nuevo ni al gate integral.

## Próximo paso

Resolver extracción de texto visible y orden/asociación niqqud con evidencia de glifos y tests de regresión. Después integrar el fix mínimo, reingestar por UI (sin cambios manuales PG/Milvus/status), reconciliar y ejecutar QA de C desktop/móvil, negativa y cross-document. No emitir `TEBAAI_BRESLOV_CLEAN_CORPUS_HEBREW_INGESTION_V1_PASS` mientras falten esos pasos.
