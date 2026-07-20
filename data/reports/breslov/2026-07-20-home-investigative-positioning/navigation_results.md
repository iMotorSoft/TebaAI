# Resultados de navegación

- `/`: HTTP 200.
- `/login`: HTTP 200; formulario y sesión recuperada validados.
- `/request-access`: HTTP 200; CTA HTML real validado.
- `/research`: documento HTTP 200; la protección cliente redirige a `/login` sin sesión.
- Sesión válida: el CTA de hero cambia a “Abrir investigación” con `href="/research"` y navega sin nuevo login.
- Sesión inválida o ausente: el CTA conserva `href="/login"`.
- Menú móvil: rutas HTML reales, cierre con Escape y devolución de foco PASS.
- Logout y reingreso: PASS en Playwright completo, incluida regresión 10/10.
