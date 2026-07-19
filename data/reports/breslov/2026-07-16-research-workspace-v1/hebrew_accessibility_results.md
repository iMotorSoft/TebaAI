# Accesibilidad hebrea

Resultado: PASS automatizado, pendiente confirmación lingüística humana.

- Axe sobre respuesta mixta: 0 violaciones críticas.
- Orden DOM lógico; no hay strings invertidos ni orden visual por CSS.
- `lang=he`, `dir=rtl`, `unicode-bidi:plaintext` en bloques hebreos.
- Metadata LTR separada; runs inline aislados con `bdi`.
- Escape cierra drawer/bottom sheet y devuelve foco al disparador.
- Focus trap existente revalidado en suite responsive.
- Composer conserva cursor/Enter y restaura LTR al vaciarse.
- 320 px, 390 px, 820 px y desktop sin overflow horizontal.
- Cuerpo hebreo de 17–18 px; zoom 200% conserva el bloque visible.
- `prefers-reduced-motion: reduce` fue emulado sin errores críticos.
- Fuente efectiva verificada por CDP: Noto Serif Hebrew (781 glifos); Liberation Serif sólo para 33 glifos auxiliares.

Limitación: la automatización no evalúa naturalidad lingüística ni pronunciación de lector de pantalla. El checklist humano es el gate final.
