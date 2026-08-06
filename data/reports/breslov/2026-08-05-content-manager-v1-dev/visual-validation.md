# Validación visual — PASS (2026-08-05)

## Continuidad con Breslov Research

El Gestor de Contenidos se comparó con las superficies existentes:

| Superficie | Continuidad |
|---|---|
| `/research` | Cabecera con identidad `רבי נחמן` + REBE NAJMÁN · BRESLOV RESEARCH, botones navy con hover, tarjetas `#fffdf9` con borde `--line`, acordeones details/summary, pills de estado, RTL local para hebreo |
| Home premium | Kickers gold uppercase con letter-spacing, títulos serif navy-950, botón primario navy con sombra suave, fondo ivory |
| `/login` | Mismo sistema DaisyUI base no expuesto aquí; el gestor usa la capa premium de tokens (igual que research) |
| `/request-access` | Kicker `.section-kicker`, títulos serif — replicados en el gestor |

Tipografía, espaciado, ancho de lectura (min(1060px)), colores, radios y
sombras coinciden con los tokens de `app.css`. Diferencias intencionales:
el gestor agrupa densidad administrativa (tabla de cargas) dentro del ancho
de lectura, sin ocupar todo el viewport.

## Estados validados (evidencia por captura)

- **Vacío** — `Todavía no hay documentos cargados` con acción `Cargar primer documento`; sin tabla vacía (4 viewports).
- **Historial** — tabla editorial desktop / cards móvil con título, idioma, fecha, estado, etapa, intento, Ver detalle (4 viewports).
- **Archivo seleccionado/válido** — ficha con nombre, tamaño, páginas, tipo, `Archivo válido`, detalles técnicos contraíbles.
- **Archivo inválido** — mensaje legible (`El archivo no es un PDF válido.`) con código técnico secundario.
- **Duplicado** — `Este mismo archivo ya fue cargado.` + documento existente; sin botón Continuar.
- **Metadata** — título, idioma, familia opcional, nota opcional; sin campos técnicos.
- **Confirmación** — ficha con archivo/título/idioma/páginas/tamaño/familia/duplicados/proceso/estado final + mensajes de candidato y no-publicación.
- **Procesamiento** — 7 etapas editoriales con estados reales (pendiente/en curso/completada/fallida), barra secundaria, nota de persistencia.
- **Resultado con observaciones** — `Documento procesado con observaciones`, candidato, advertencias editoriales, stats reales, acciones.
- **Fallido** — `No se pudo completar el procesamiento`, etapa/mensaje, código secundario, Reintentar.
- **Retry** — nuevo attempt, historial conservado, resultado final.
- **Diagnóstico** — contraído por defecto; expandido con PDF/canonical/textual/empty pages, headings, notas, referencias, chunks, embeddings, Milvus, PG↔Milvus, integridad, duración, IDs.
- **Teclado** — foco en dropzone visible (gold outline), Enter abre selector nativo.

## Criterios de rechazo

- No parece dashboard genérico: no hay stats DaisyUI, tabla-zebra, ni shell admin paralelo.
- No hay sistema de colores nuevo: solo tokens existentes.
- La tabla no domina: ancho de lectura controlado, resumen compacto arriba.
- Los IDs no son protagonistas: nivel técnico contraíble.
- El progreso no es solo spinner: etapas con estado + porcentaje real del backend.
- Estados reales: sin delays artificiales, sin éxito por HTTP 202.
- Móvil sin overflow (scrollWidth - clientWidth ≤ 1).
- RTL local sin romper layout.
- Errores con texto+icono+color, no solo color.
- Flujo completo operable por teclado.
- La estética premium se basa en tokens/tipografía/espaciado, no solo sombras.

## Conclusión

`TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS` — la UI del Gestor es una
extensión natural de Breslov Research y el flujo completo funciona con
backend real en el navegador.
