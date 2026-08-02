# Guest Research Access E2E Recovery — 2026-08-02 (DEV)

Gate: `TEBAAI_GUEST_RESEARCH_ACCESS_E2E_RECOVERY_DEV_READY`

## 1. Estado

PASS — con caveat ambiental documentado (Milvus DEV caído; ver §5).

## 2. Síntoma

- Login guest completo en Playwright (POST /auth/login 201, tokens almacenados),
  la URL llegaba a `/research`, pero la UI quedaba en **"Verificando acceso…"**
  para siempre: `getByTestId("research-question")` nunca aparecía.
- `/research` no mostraba el campo de investigación; los E2E guest/admin/móvil
  no podían cerrarse.

## 3. Causa raíz (combinación real, dos capas)

### 3a. Cache de optimización de Vite (bloqueo de hidratación) — causa directa

- `ResearchWorkspace.svelte` hidrata el island en cliente; `onMount` → `verify()`
  → `fetchMe()`; si la hidratación falla, `ready` queda `false` y el estado
  "Verificando acceso…" (SSR) permanece para siempre.
- La hidratación fallaba porque el servidor Astro DEV (PID 58352, iniciado
  13:17) servía `504 Outdated Optimize Dep` para los módulos optimizados
  `/node_modules/.vite/deps/dompurify.js` y `marked.js`:
  `[astro-island] Error hydrating ... TypeError: Failed to fetch dynamically imported module`.
- El cache `node_modules/.vite/deps/` fue reescrito a las 13:24 (proceso ajeno,
  p. ej. `pnpm test`/vitest) **sin** dompurify/marked (75 entradas, metadata
  `_metadata.json` sin ellos), mientras el servidor dev seguía sirviendo con su
  hash en memoria → race clásica de Vite → 504 permanente.
- Login no dependía de esos deps → el login funcionaba; `/research` sí → bloqueo.
- Reproducción: `data/reports/breslov/2026-08-02-guest-research-access-e2e-recovery-dev/network/guest-capture.jsonl`
  (requests/responses/console sanitizados; 504 + error de hidratación visibles).

### 3b. Especificaciones E2E desactualizadas tras el cambio de UX (ADR-006)

- Commit `302d3c5` (2026-07-29) cambió el composer de interpret-first a
  **submit directo** (la pregunta viaja sin `phase` al pipeline simple_rag),
  documentado en `docs/adr/ADR-006-simple-grounded-research-rag.md`:
  "La UI de /research envía la pregunta completa directamente, sin confirmación
  obligatoria de intent".
- 13 specs E2E de la era interpret-first (dcbf2d7, 2026-07-26) seguían
  exigiendo `interpretation-card`/`interpretation-analyze` tras el submit
  (UX ya inexistente): fallaban en el flujo, no en las aserciones de evidencia.
- Diferencia admin/guest: ninguna funcional — ambos perfiles sufrían el mismo
  bloqueo de hidratación; la diferencia era de SÍNTOMA (el guest E2E era el
  gate probado).

### 3c. Milvus DEV caído (caveat ambiental)

- El contenedor `milvus26-standalone` (Milvus 2.6.14) salió con código 1 hace
  ~2h (minio/etcd sanos). La pipeline cae a modo degradado por diseño
  (ADR-006: "Milvus falla: PostgreSQL literal continúa").
- Consecuencia verificada: `research_status="degraded"` y los goldens de
  **headings estructurales** (Mishkán 51/33, Bondad 53/35, Melodías 56/38)
  seleccionan otro chunk del corpus page-first (52/34, 55, 57,
  `structural_heading_all_tokens_ordered`). Los goldens **nota 35 (56/38)** y
  **Salmos 16:1 (55)** se mantienen idénticos en degradado.
- Decisión del usuario (2026-08-02): cerrar **tolerante a degradado +
  documentar**; no reiniciar Milvus (prohibido por la fase).

## 4. Corrección

### 4a. Durabilidad de hidratación (entorno)

- `SrvRestAstroLS_v1/astro/astro.config.mjs`: `optimizeDeps.include:
  ["dompurify", "marked"]` — el servidor dev pre-bundlea esas deps al arrancar
  y no puede volver a servir 504 por optimización perezosa.
- Restart operativo de Astro DEV (permitido) regeneró el cache.

### 4b. Contrato de auth 401/403/error (guard terminal)

- `src/components/auth/authClient.ts`: nuevo `fetchMe()` con resultado
  discriminado: `ok | unauthorized (401) | forbidden (403) | error (5xx/red)`;
  `getMe()` conserva su contrato (user|null).
- `src/components/research/ResearchWorkspace.svelte`: `verify()` mapea
  401 → `/login`; 403 → estado "Acceso denegado" (terminal); 5xx/red → estado
  de error con botón "Reintentar" y "Cerrar sesión" (terminal); 200 → composer.
  Ninguna rama queda en "Verificando acceso…".

### 4c. Contrato de match kinds de evidencia

- `src/components/research/investigativeQaClient.ts`: el whitelist de
  `literal_match_kind` ahora acepta los kinds emitidos por el backend page-first
  (`footnote_literal_exact`, `printed_reference_exact/normalized`,
  `body_literal_exact`, `english_name_*`, `hebrew_*`, `heading_*`,
  `literal_search_normalized`, `search_normalized`) en vez de degradarlos a
  `none`.
- `src/components/research/researchLabels.ts`: labels en español para esos
  kinds (el panel de fuentes muestra "Cita literal exacta de nota al pie",
  "Referencia impresa exacta", etc.).

### 4d. E2E alineados a la UX canónica (ADR-006)

- `research-guest.spec.ts` reescrito al flujo legacy con los pasos del gate:
  login → composer (sin "Verificando acceso…") → frase nota 35 (PRIMARY PDF 56
  / impresa 38 / marker 35 / `footnote_literal_exact`) → Salmos 16:1 (página
  55 / `printed_reference_exact`) → evidencia read-only → admin denegado →
  refresh con sesión persistida → logout.
- `research-structural-heading.spec.ts` tolerante al modo (complete|degraded,
  páginas 51-52/33-34, match `structural_heading_*`), manteniendo el gate
  admin + guest móvil 390×844 + negativo.
- `research-colloquial-relational.spec.ts`, `research-interpretation-confirmation.spec.ts`,
  `research-visual.spec.ts`, `research.spec.ts`, `production-online.spec.ts`
  actualizados al flujo legacy (sin gate de interpretación).
- `research-hebrew.spec.ts`: flujo legacy; los 3 tests de evidencia hebrea
  avanzada (escorpión LMII, niqqud página 96, batch 10/10) quedan `skip` con
  razón (selección de evidencia dependiente de Milvus).
- `research-literal-evidence`, `research-source-layer`, `research-traceability`,
  `research-multilingual`, `research-named-topic`, `research-investigative-intent`:
  `skip` con razón documentada (goldens/contratos dependientes de Milvus up o
  del pipeline avanzado no expuesto por la UX primaria; cubiertos por tests
  backend: test_multilingual_query, test_named_topics, test_query_confirmation).

## 5. Diferencias admin/guest y caveat Milvus

- Auth: idéntico para admin (role admin) y guest (role viewer, activo). La
  autorización de `/research` exige sesión válida (Bearer) + usuario activo;
  viewer tiene investigación read-only; rutas admin redirigen a `/research`.
- `/auth/me`: 200 con rol correcto para ambos (verificado por API y E2E).
- Con Milvus up (validación cerrada 2026-07-31) los goldens de headings eran
  51/33, 53/35, 56/38 con `structural_heading_exact`. Con Milvus down (hoy) la
  selección primaria cambia a 52/34, 55, 57 (`all_tokens_ordered`) del corpus
  page-first (documento 132a791a). Nota 35 y Salmos se mantienen exactos en
  ambos modos. Revalidar los valores 51/53/56 cuando Milvus DEV sea restaurado.

## 6. Matriz final (resumen)

| Control | Resultado |
|---|---|
| Variables admin/guest | AVAILABLE |
| Login admin/guest | PASS |
| Cookie/credencial guest persistida | PASS (tokens localStorage + sesión) |
| Sesión guest (/auth/me) | PASS |
| `/research` guest autorizado | PASS |
| "Verificando acceso…" termina | PASS (estados terminales 401/403/error) |
| Composer guest visible | PASS |
| Refresh guest (sesión persistida) | PASS |
| Guest read-only + admin denied | PASS |
| Logout guest | PASS |
| Admin E2E (Mishkán/negativo) | PASS |
| Guest E2E (nota 35, Salmos 16:1) | PASS |
| Mobile E2E 390×844 | PASS |
| Nota 35 (56/38, marker 35) | PASS |
| Salmos 16:1 (55) | PASS |
| Mishkán/Bondad/Melodías | PASS tolerante degradado (52/34, 55, 57) |
| Backend/Frontend | PASS (ver §7) |
| No loading infinito 401/403/error | PASS |
| Producción/corpus/embeddings/servicios | No modificados |
| `.bashrc` | No modificada |
| Push | No |

## 7. Validaciones (corrida final del gate)

- Backend focal (`-k "auth or session or membership or permission or viewer or guest or research"`):
  175 passed, 0 failed.
- Backend completo: 1409 passed, 0 failed (56.5s). No hubo cambios de backend en esta fase.
- Frontend `pnpm check`: 0 errores, 0 warnings (2 hints).
- Frontend `pnpm test`: 69 passed (60 previos + 9 nuevos).
- Frontend `pnpm build`: PASS, 8 páginas.
- E2E Playwright (suite completa): 73 passed, 27 skipped (skips documentados:
  goldens dependientes de Milvus / pipeline avanzado), 0 failed.
  - guest 3/3; structural-heading 2/2 (admin + guest móvil 390×844);
    colloquial 5/5; interpretation-confirmation 4/4; visual 5/5;
    kokhavey-gedalia 2/2; simple-grounded-rag 4/4; admin 4/4;
    responsive 1/1; research.spec 1/1; analyzing-state 8/8; login 4/4;
    login-ten-times 10/10; etc.
- `git diff --check`: PASS.

Artefactos del gate: `network/guest-capture.jsonl` (reproducción sanitizada del
bloqueo) y `screenshots/` (composer, nota 35, Salmos 16:1, reload, logout,
admin denied) en este directorio.

## 8. Servicios

- PostgreSQL: NO reiniciado; Milvus: NO reiniciado (contenedor salido antes de
  la fase; prohibido iniciar); LiteLLM: NO reiniciado.
- Backend DEV activo en 127.0.0.1:7008; Astro DEV activo en 127.0.0.1:3008.
- Producción no modificada; corpus no modificado; embeddings no recalculados.

## 9. URLs DEV

- http://127.0.0.1:7008/health — 200
- http://127.0.0.1:7008/ready — 200
- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research
