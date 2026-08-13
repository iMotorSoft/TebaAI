# Validación visual

Superficies comparadas (identidad `רבי נחמן · REBE NAJMÁN · BRESLOV RESEARCH`):

- Navbar cerrado: «Ingresar →» sigue limpio como CTA principal.
- Navbar + modal: «¿Dónde querés ingresar?» con dos cards Investigación/Edición.
- Sección módulos inferior: permanece como presentación de producto.

Reutilización:

- Tokens `app.css` (navy/ivory/gold, serif/sans); sin DaisyUI genérico.
- `::backdrop` discreto (navy translúcido, blur 2px).
- Cards con borde superior gold; foco visible (borde + shadow).
- Móvil: cards apiladas, botón Cerrar accesible, sin overflow horizontal.

Evidencia: specs Playwright (`public-navbar-module-modal`,
`public-home-module-entry`, `home`, `breslov-home-visual`).
