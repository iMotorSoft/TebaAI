# TEBAAI_BRESLOV_HEBREW_RTL_RENDERING_V1 — HEBREW_RTL_FAIL

Validación post-release realizada el 2026-10-01 sobre https://breslov.tebaai.live.
El gate TEBAAI_BRESLOV_EDITOR_UPLOAD_TO_USER_QUERY_PRODUCTION_V1_PASS permanece cerrado; no se reevalúa ni se altera.
Rama: `feature/console-backend-core`. Worktree inicialmente limpio.

## Resultado por evidencia

| Campo | Texto hebreo y español | Hebreo, números y puntuación |
| --- | --- | --- |
| Document | Un Día en la Vida de un Jasid de Breslov | La Potencia de la Plegaria |
| document_id | a852721d-ae41-4226-8cbb-b4419c0cabe9 | 43ba4f4b-d3ee-49b6-8d09-dfa152379893 |
| chunk_id | 045c39b8-4e46-400c-99f8-31f0fcff4c7f | b29a1432-2a34-422e-a748-d6174a94008f |
| page | PDF 187; chunk abarca 186–187 | PDF 416; el chunk registra 412 |
| Stored Hebrew | FAIL fidelidad de palabras; orden lógico del encabezado PASS | FAIL separación de pares número/letra |
| API Hebrew | PASS transporte exacto del canónico | PASS transporte exacto del canónico |
| Main answer rendering | PASS para la frase real del encabezado, dentro de español | PASS texto latino; la respuesta no contiene el listado hebreo |
| Citation rendering | FAIL legibilidad del párrafo vocalizado | FAIL pares numéricos ambiguos |
| Mixed RTL/LTR | FAIL en la cita completa; PASS en la respuesta breve | FAIL en la lista extraída |
| Characters reversed | NO en los dos fragmentos trazados | NO |
| Words internally reversed | NO; existen palabras fragmentadas por espacios | NO; existen entradas concatenadas |
| Fix required | YES, extracción/presentación de texto fuente | YES, extracción de tabla |

No se cierra `TEBAAI_BRESLOV_HEBREW_RTL_RENDERING_V1_PASS`.

## Evidencia exacta y causa

Frase correcta comprobada en PDF, PostgreSQL, API y respuesta productiva:

```text
תיקון הכללי 6
יהי רצון שאומרים קודם אמירת תהלים בימות החול:
```

El párrafo vocalizado de ese mismo chunk ya contiene espaciado interno de palabras, por ejemplo `יְהִ י רָ צוֹן מִלְּ פָ נֶיָך`. En el PDF las palabras están compuestas normalmente. La cita productiva conserva esas separaciones, aun con dirección visual RTL y sin inversión del string. Véanse `source-page-187.png`, `primary-storage.json`, `natural-desktop.png` y `natural-mobile.png`.

En el PDF 416, la guematría tiene columnas y pares separados. En PostgreSQL quedaron concatenados `6 = ו1 = א`, `400 = ת80 = פ,ף30 = ל7 = ז2 = ב` y `900 = ץ800 = ף700 = ן600 = ם500 = ך`. El navegador muestra los números junto a letras de entradas adyacentes. Véanse `source-page-416.png`, `storage.json` y `numbers-desktop.png`.

Root cause: defectos presentes en DATABASE, compatibles con pérdida de geometría/espaciado durante extracción PDF. La imagen fuente es legible. Esta auditoría localiza el defecto antes de API/DOM; no demuestra qué función histórica concreta lo introdujo. Corregir solo CSS no restaura los delimitadores ausentes ni determina espacios legítimos.

Hallazgo adicional, fuera de los dos casos trazados: el documento golden `ca7d6c5c-8023-5a52-96f8-761b214d7cb4`, chunk `efdc6315-ab18-5975-8354-f41d7fbe58f4`, página 2, almacena `הָקיִדְבִל יִרְבִע טְסְקֶטv4`. Parece una frase hebrea con palabras y letras invertidas. No se encontró su PDF fuente en esta auditoría ni se consiguió recuperar ese mismo chunk mediante la consulta por título: no se presenta como inversión confirmada extremo a extremo. `golden-api.json` y `golden-browser-api.json` recuperaron otros documentos; no sirven como prueba de ese chunk.

## Implementación RTL existente

- `astro/src/components/research/textDirection.ts`: detección he/ar/mixto, `rtl`/`auto`/`ltr`, normalización NFC y retiro de controles bidi; no invierte strings.
- `astro/src/components/research/markdownRenderer.ts`: atributos confiables tras sanitizar y aislamiento `bdi lang="he" dir="rtl"` de runs hebreos dentro del Markdown mixto.
- `astro/src/components/research/ResearchWorkspace.svelte`: dirección del composer, preguntas, síntesis, claims, tarjetas de evidencia y snippets por obra.
- `astro/src/components/research/SourcePanel.svelte`: snippet de fuente, idioma/dirección recibidos y clase hebrea; libro/página/evidence ID en superficies separadas.
- `astro/src/assets/research.css`: tipografía hebrea, `unicode-bidi: plaintext`, dirección RTL y estilos de citas; aislamiento de metadata.
- También hay soporte en `contentManagerLabels.ts` y `content-manager.css`; no se modificó ni se validó visualmente el Gestor en este gate.
- Contrato histórico: `data/reports/breslov/2026-07-16-research-workspace-v1/hebrew_render_contract.md`. Los tests históricos golden de `research-hebrew.spec.ts` tienen skips explícitos por cambios del corpus; no se contaron como PASS actual.

Observación DOM: la cita mayoritariamente hebrea recibe `lang="es" dir="ltr"` desde la API, pero su clase aplica CSS RTL; la cita numérica queda LTR/cursiva. El comportamiento existente no ofrece semántica consistente para todas las citas mixtas. No se infiere inversión de caracteres por esos atributos.

## Cadena y validaciones

- PostgreSQL 18.4, base `tebaai`; conexiones async psycopg, transacciones read-only. No escrituras al corpus.
- HTTPS productivo y login reales; API usada por la UI: `POST /api/library/investigative-qa/v1`.
- `layer-comparison.json`: `DB content == API quote == API paragraph_text` exacto en ambos chunks, con SHA-256. El DOM coincide con NFC de `display_snippet` en ambos casos. `display_snippet` es presentación abreviada y normalizada, no canónico completo; no se afirmó igualdad del snippet con todo el chunk.
- No fallback determinístico en las consultas trazadas: gateway `openai_gpt-5.4-nano`, embeddings `openai_text_embedding_3_small`, vector real. La consulta natural devuelve `partial`; eso no se confundió con un PASS de calidad investigativa.
- Playwright + Chromium, login y consultas sin interceptar respuestas: dos casos actuales, desktop 1600×1000 y captura móvil 390×844 para la cita hebrea. Cero errores console y cero HTTP 5xx registrados. Inspección visual de capturas y páginas PDF realizada.
- Frontend: `pnpm exec vitest run src/components/research/textDirection.test.ts src/components/research/markdownRenderer.test.ts` → 36/36 PASS.
- Backend: `uv run pytest tests/test_hebrew_pipeline_contract.py -q` → 12/12 PASS.
- `git diff --check` PASS; revisión final: solo artefactos de este reporte. No cambios frontend/backend ni LAT, por lo que build/check/lat check no corresponden a esta auditoría.

Repetición del navegador, desde la raíz, con credenciales E2E del entorno:

```sh
node data/reports/breslov/2026-10-01-hebrew-rtl-rendering-v1/browser-probe.mjs
```

`browser-probe.mjs` captura evidencia; no es un test que declare aprobado el gate por obtener HTTP 200. El veredicto incorpora comparación canónica e inspección del PDF y navegador.

## Cambios e impacto

Files modified: solo archivos nuevos dentro de este directorio de reporte.
Fix aplicado: NO. Corpus modificado: NO. Commit: NO. Push: NO. Deployed: NO.
No se inició, detuvo ni reconfiguró PostgreSQL, Milvus o LiteLLM.

Próximo paso: reproducir la extracción de estas páginas en DEV sin escribir el corpus, restaurar límites de palabras/celdas mediante geometría fuente y comprobar semántica de citas mixtas. La reparación de registros existentes exige una instrucción posterior que permita modificar el corpus; la petición actual lo prohíbe. Después corresponderán pruebas, build, deploy controlado si hay cambio y retest productivo de las mismas evidencias.
