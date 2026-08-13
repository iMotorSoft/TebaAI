# Validación visual

Superficies comparadas (identidad `רבי נחמן · REBE NAJMÁN · BRESLOV RESEARCH`):

- Home anónima desktop: hero + selector de módulos (Investigación / Edición).
- Home anónima móvil (390×844): cards apiladas, sin overflow.
- Login desde Investigación (next=/research) y desde Edición (next=/admin/content).
- Acceso denegado Edición (viewer): mensaje legible + alternativas.
- Home autenticada: CTA directo a destino según sesión.

Reutilización:

- Tokens `app.css` (navy/ivory/gold, serif/sans).
- Patrones del hero y de las secciones existentes (section-kicker, heading).
- Sin launcher SaaS, sin grid de apps genérico, sin dashboard.

Corrección visual: contraste `.section-kicker` en fondos claros (`#76500b`) y
en navy (`gold-400`), cumpliendo WCAG AA (evidencia axe 0 violaciones críticas
o serias en `home.spec.ts`).

Capturas automáticas: specs Playwright (`public-home-module-entry`,
`auth-intended-destination`, `module-entry-permissions`).
