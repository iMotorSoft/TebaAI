# CONTENT MANAGER PREMIUM UX V1 — E2E GATE

## REAL PDF E2E TEST DOCUMENT

Usar como PDF real de prueba:

```text
/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf
```

## OBJETIVO

Validar el flujo real del Content Manager:

```text
seleccionar PDF
→ metadata / confirmación
→ upload
→ procesamiento
→ progreso
→ publicación/resultado
→ biblioteca
→ detalle
→ fuente visual
```

Este documento es exclusivamente el fixture real del E2E.

No reutilizar CURRENT C para esta prueba.

---

## 1. PRECHECK DEL PDF

Antes del upload, registrar read-only:

```text
path
exists
size
SHA-256
page count
```

No modificar ni copiar sobre el original.

Guardar estos datos en la evidencia E2E.

**Valores registrados:**

| Campo | Valor |
|-------|-------|
| path | /media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf |
| exists | YES |
| size | 1886278 bytes |
| SHA-256 | ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61 |
| page count | 412 |

---

## 2. BACKEND / FRONTEND

Levantar sólo DEV:

```text
backend:
127.0.0.1:7008

frontend:
puerto configurado para el Content Manager DEV
```

Usar las credenciales E2E existentes:

```text
TEBAAI_E2E_ADMIN_EMAIL
TEBAAI_E2E_ADMIN_PASSWORD
```

No imprimir valores.

No guardar secretos en screenshots, traces o reports.

---

## 3. FLUJO REAL DE UPLOAD

Usar exactamente:

```text
/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf
```

en el selector/file input del Content Manager.

No reemplazarlo por fixture sintético salvo para controles auxiliares.

Validar:

```text
archivo aceptado
nombre mostrado correctamente
metadata visible
confirmación funciona
upload real funciona
backend recibe el PDF
worker/orchestration inicia
estado de procesamiento visible
resultado final aparece en UI
```

---

## 4. CAPTURAS OBLIGATORIAS

Generar evidencia real al menos de:

```text
01 biblioteca inicial

02 selección de:
LIKUTEY MOHARAN II Interior.pdf

03 confirmación previa al upload

04 procesamiento en curso

05 éxito final sin advertencias
   o resultado real equivalente si existen advertencias legítimas

06 documento en biblioteca

07 detalle del documento

08 diagnóstico colapsable

09 fuente/PDF visual accesible
```

Además debe existir evidencia del estado:

```text
duplicate
```

Puede usarse el mismo PDF nuevamente después de la primera ingestión si ese es el flujo soportado para detectar duplicados.

No alterar datos sólo para fabricar la pantalla.

---

## 5. DESKTOP

Viewport:

```text
1440 × 900
```

Validar las 5 etapas completas del wizard.

Required:

```text
no clipped controls
no hidden primary CTA
no horizontal overflow
progress readable
status readable
document title readable
```

---

## 6. MOBILE

Viewport obligatorio:

```text
390 × 844
```

Como mínimo capturar:

```text
selección/confirmación
procesamiento
resultado
biblioteca
detalle
```

Required:

```text
no horizontal overflow
wizard usable
buttons tappable
document title wraps correctly
diagnostic collapses correctly
Hebrew/RTL does not break surrounding layout
```

---

## 7. HEBREW / RTL SMOKE

Este gate NO certifica todavía la calidad textual completa de Likutey Moharan II.

Sí debe verificar visualmente que contenido hebreo mostrado por la UI:

```text
does not invert surrounding numbers
does not break page layout
does not create bidi spill
```

El gate Hebrew RTL V2 ya está certificado; esto es sólo regresión visual del Content Manager.

---

## 8. REAL INGESTION

Como el objetivo es probar el flujo real:

```text
UPLOAD = YES
INGESTION = YES
```

pero exclusivamente en DEV.

Antes de iniciar, registrar el estado de la biblioteca.

Después registrar:

```text
new document id
run/job id
status
page count
chunk count
embedding/vector status
```

No asumir valores esperados previamente.

Usar los valores reales producidos por este PDF.

---

## 9. NO TOCAR CURRENT C

Prohibido durante esta prueba:

```text
reingest CURRENT C
switch CURRENT C generation
change CURRENT C pointer
delete CURRENT C
replace CURRENT C source
```

CURRENT C:

```text
ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa
```

debe permanecer intacto.

---

## 10. DUPLICATE FLOW

Después de una ingestión satisfactoria de:

```text
LIKUTEY MOHARAN II Interior.pdf
```

intentar seleccionar/subir nuevamente el mismo archivo según el flujo soportado.

Validar:

```text
duplicate detection = visible
message understandable
no accidental duplicate publication
no destructive overwrite
```

Capturar screenshot del estado duplicate.

---

## 11. BROWSER OBSERVABILITY

Durante todas las pantallas registrar:

```text
console errors
page errors
failed requests
HTTP 5xx
uncaught exceptions
```

Required:

```text
CONSOLE_ERRORS = 0
HTTP_5XX = 0
UNCAUGHT_EXCEPTIONS = 0
```

Errores esperados del control de duplicate deben distinguirse de 5xx reales.

---

## 12. E2E SPECS

Ejecutar:

```text
content-manager-captures.spec.ts
content-manager-premium.spec.ts
```

Adaptar únicamente los datos/fixture necesarios para usar:

```text
/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf
```

No cambiar assertions para hacer pasar un defecto visual.

---

## 13. REGRESIONES

También ejecutar nuevamente:

```text
pnpm check
pnpm test
```

y los tests backend focalizados relacionados con:

```text
upload
content manager publication
page-first ingestion
Hebrew fidelity
region worker enforcement
```

No hace falta ejecutar toda la suite backend si no es requisito del gate.

---

## 14. RESULTADO ESPERADO

PASS sólo si el flujo real del PDF llega desde selección hasta resultado visible:

```text
TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS
```

Con resumen:

```text
REAL_TEST_PDF =
/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf

PDF_SHA256 =
ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61

PDF_PAGES =
412

UPLOAD =
PASS

INGESTION =
PASS

CONFIRMATION_SCREEN =
PASS

PROCESSING_SCREEN =
PASS

SUCCESS_SCREEN =
PASS

DUPLICATE_SCREEN =
PASS

LIBRARY =
PASS

DOCUMENT_DETAIL =
PASS

DIAGNOSTIC_COLLAPSIBLE =
PASS

DESKTOP_1440x900 =
PASS

MOBILE_390x844 =
PASS

CONSOLE_ERRORS =
0

HTTP_5XX =
0

CURRENT_C_PRESERVED =
YES
```

---

## REGLA FINAL

Usar **Likutey Moharan II Interior.pdf como la prueba real completa del Content Manager**.

No usar CURRENT C.

No tocar `extractors.py`.

No hacer commit/push hasta que el E2E visual haya terminado y podamos revisar juntos el resultado exacto.

Esto además es mejor prueba que un fixture pequeño: valida el Content Manager con **un libro Breslov real**, sin poner en riesgo el C actual.
