# Checklist manual de hebreo

Usar las credenciales administrativas configuradas en el entorno. No registrar credenciales, cookies ni storage state.

- Login: http://127.0.0.1:3008/login
- Workspace: http://127.0.0.1:3008/research

## Caso 1 — Escorpión

Consultar `donde aparece el termino escorpion`. Abrir la evidencia hebrea de Likutey Moharán II, PDF p. 28 / página impresa 18, y revisar:

- lectura natural de derecha a izquierda;
- palabras completas y niqqud unido a su letra;
- ausencia de espacios artificiales;
- puntuación, números y páginas;
- tamaño, interlineado y ancho;
- panel desktop, drawer tablet y bottom sheet móvil;
- `Ver fuente` abre la evidencia vinculada correcta.

## Caso 2 — Pregunta hebrea

Escribir una pregunta breve en hebreo y comprobar cursor, selección, copiar/pegar, números, puntuación, Enter, Shift+Enter, auto-resize, envío, turno y fuentes. Al vaciar el composer debe volver a LTR.

## Caso 3 — Texto mixto

Abrir una respuesta española con cita hebrea. Confirmar español LTR, hebreo RTL, interfaz general sin invertir, metadata y referencias legibles.

## Caso 4 — Móvil

Probar 390×844 y 320×568. Confirmar texto a ancho completo, bottom sheet, scroll vertical, ausencia de overflow horizontal, composer, teclado y safe area.

## Caso 5 — Fuente vinculada

Usar `Ver fuente` en un claim con evidencia hebrea y confirmar identidad, página, foco, Escape y devolución de foco.

## Aceptación humana

- [ ] el orden de palabras es lingüísticamente natural;
- [ ] niqqud y signos se asocian a las letras correctas;
- [ ] números, citas y referencias se leen en posición natural;
- [ ] desktop, tablet y móvil son cómodos de leer;
- [ ] lector de pantalla pronuncia el bloque como hebreo;
- [ ] no se detectan fragmentos que requieran corrección editorial del corpus.
