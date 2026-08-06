# Clasificación de archivos tracked modificados — 2026-08-06

Categorías: A=legítimo de fase cerrada sin commitear, B=config DEV/PRO, C=branding/assets, D=test, E=documentación, F=reporte reproducible, G=herramienta/probe read-only, H=runtime/temporal, I=cambio preexistente ajeno, J=dudoso.

## Código y configuración

| ruta | estado | categoría | propósito | fase de origen | secretos | commitear |
|---|---|---|---|---|---|---|
| `SrvRestAstroLS_v1/astro/src/components/global.js` | M | A+B | Elimina el selector manual DEV/PRO; el navegador usa siempre `/api`. El proxy DEV ya está commiteado en `astro.config.mjs` (rewrite `/api` → `127.0.0.1:7008`). Contrato anterior `false→http://127.0.0.1:7008, true→/api` queda **superseded** por esta pieza ya validada. | cierre 2026-07-28 (producción assets) + pruebas 2026-08-05 | no | sí |
| `SrvRestAstroLS_v1/astro/src/components/global.test.ts` | M | B+D | Test alineado al nuevo contrato `/api`. | misma | no | sí |
| `SrvRestAstroLS_v1/astro/src/layouts/PublicLayout.astro` | M | C | Añade `<link rel="icon">` favicon.svg/16/32 + apple-touch-icon. | 2026-07-28 assets sociales | no | sí |
| `SrvRestAstroLS_v1/docs/manual-dev-pro-configuration.md` | M | B+E | Documenta la nueva configuración HTTP DEV/PRO (proxy único `/api`). | misma | no | sí |
| `lat.md/frontend-implementation-policy.md` | M | B+E | LAT actualizado al contrato `/api` same-origin. | misma | no | sí |
| `SrvRestAstroLS_v1/backend/tests/test_simple_research_rag.py` | M | D | Esperado de `primary_evidence_ids` alineado a evidence ID v2 (`ev-71b37371035d805f`). | ADR-021 2026-08-04 | no | sí |
| `docs/adr/ADR-013-page-first-editorial-evidence-v2.md` | M | E | Sección "Corpus reconciliation": casos B (Salmos 16:1 PASS) y C (nota 35 DATA GAP) + fixes aplicados. | 2026-08-03/04 | no | sí |

## Capturas de reportes (reproducibles)

| ruta | estado | categoría | propósito | fase de origen | secretos | commitear |
|---|---|---|---|---|---|---|
| `data/reports/breslov/2026-07-16-breslov-research-home/screenshots/auth/login-form.png` | M | F | Captura regenerada del home investigativa. | 2026-07-20 | no | sí |
| `data/reports/breslov/2026-07-26-colloquial-relational-interpretation/screenshots/{before-generic-echo,mobile,modified-interpretation,relational-result}.png` | M | F | Capturas regeneradas de interpretación coloquial/relacional. | 2026-07-26 | no | sí |
| `data/reports/breslov/2026-07-26-query-interpretation-confirmation/screenshots/{initial-composer,mobile,rtl}.png` | M | F | Capturas regeneradas de confirmación de interpretación. | 2026-07-26 | no | sí |
| `data/reports/breslov/2026-08-02-guest-research-access-e2e-recovery-dev/screenshots/{research-guest-footnote-35,research-guest-salmos-16-1}.png` | M | F | Capturas regeneradas del E2E guest. | 2026-08-02 | no | sí |

**Nota:** los 17 tracked modificados están clasificados. Ninguno contiene secretos (escaneo `api_key|secret|password|token|Bearer` sin coincidencias reales). Ninguno es runtime. `git diff --check` PASS.
