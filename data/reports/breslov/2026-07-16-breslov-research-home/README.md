# Breslov Research home — validation report

Final validation report for the public Breslov Research home.

- Design baseline: `7f830475aa6ad9e69fcd12cfbe88453e587ef7b4`
- Authenticated-validation baseline: `b4ae60b22476aa86dfc63cf7864c16b1d3528590`
- Branch: `feature/console-backend-core`
- Public routes: `/`, `/login`, `/request-access`
- Browser evidence: `screenshots/`

The home is static Astro markup. `MobileMenu.svelte` and `LanguageSelector.svelte` are the only interactive Svelte 5 islands. The landscape was generated as a project-local asset, then converted to responsive WebP variants; no external runtime image is used.

The official backend and Astro launchers were used for the closing validation. Login, an authenticated session, administration, protected search, public home behavior, and the full Playwright suite are now verified against the real local services. See the companion evidence for service, authentication, full regression, accessibility, and secret-safety results.
