# Cierre de legibilidad hebrea en `/research`

Fecha de validación final: 2026-07-18. Caso principal: `donde aparece el termino escorpion`.

## Causa raíz

El defecto apareció en dos capas. PostgreSQL conservaba correctamente el literal extraído, pero el PDF BRI de LM II codifica líneas hebreas como glifos posicionados de izquierda a derecha. PyMuPDF insertaba espacios dentro de palabras y entre letras y niqqud. El JSON y el DOM preservaban ese literal sin inversión, por lo que la fragmentación ya existía antes de CSS. La presentación la agravaba con 273 px de ancho, 14.4 px, cursiva, ausencia de `lang=he`, `unicode-bidi:isolate` y fallback latino.

El batch real expuso además dos defectos de selección: el límite final por obra eliminaba toda evidencia hebrea secundaria aunque `he` estuviera solicitado, y una reformulación IA podía reemplazar los conceptos literales de una pregunta standalone. La selección final ahora reserva, sin superar el límite, una evidencia cuya proyección visible sea hebreo dominante; los conceptos del usuario siguen siendo la autoridad de retrieval salvo resolución explícita de follow-up.

## Corrección

- `quote`, hashes e IDs canónicos permanecen intactos.
- El backend deriva `display_quote` y `display_snippet` desde la geometría de glifos del PDF, normaliza el derivado a NFC y declara `display_normalization=pdf_glyph_geometry_nfc_v1`.
- No se invierte ningún string y no se modifica PostgreSQL.
- El frontend asigna idioma y dirección por bloque, aísla runs inline con `bdi`, y agrega semántica segura después de DOMPurify.
- El panel separa metadata LTR del cuerpo RTL.
- La tipografía efectiva verificada por CDP es Noto Serif Hebrew (781 glifos del bloque inspeccionado; Liberation Serif sólo cubre 33 glifos auxiliares); el cuerpo usa 18 px/1.82 en desktop y 17 px/1.8 en móvil.
- El panel desktop creció; tablet usa drawer y móvil bottom sheet.

## Resultado

El literal canónico sigue disponible para auditoría y el texto visible coincide exactamente con el derivado de presentación recibido. El E2E real, el batch 10/10 repetido dos veces, casos mixtos, Axe, hidratación, trazabilidad y Playwright completo 35/35 pasan.

Estado técnico: `HEBREW_READABILITY_FULL_PASS`.

La naturalidad lingüística final requiere revisión humana: `READY_FOR_MANUAL_HEBREW_REVIEW`.
