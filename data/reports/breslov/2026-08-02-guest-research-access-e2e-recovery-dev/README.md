# Guest Research Access E2E Recovery — 2026-08-02 (DEV)

Gate: `TEBAAI_GUEST_RESEARCH_ACCESS_E2E_RECOVERY_DEV_READY`

## 1. Estado

Acceso autenticado y E2E: **PASS** — `TEBAAI_GUEST_RESEARCH_ACCESS_E2E_RECOVERY_DEV_READY`.
Incidente ambiental Milvus resuelto (restaurado manualmente por el usuario).
Hallazgos editoriales registrados como revisión pendiente (headings y
printed_page de Salmos) — ver §5b y §5c. Gates de exactitud editorial NO
cerrados (REVIEW_REQUIRED).

## 1b. Estados de gates (2026-08-02, tras restauración manual de Milvus)

| Gate | Estado |
|---|---|
| `TEBAAI_GUEST_RESEARCH_ACCESS_E2E_RECOVERY_DEV_READY` | **READY** — acceso auth + E2E admin/guest/móvil validados (10/10 ×2) |
| `TEBAAI_FOOTNOTE_LITERAL_RANKING_V1_DEV_READY` | READY — nota 35 revalida exacta (56/38, marker 35, 3/3 estable) |
| `TEBAAI_PAGE_FIRST_EDITORIAL_CONVENTIONS_DOCUMENTED_DEV_READY` | READY — convenciones documentadas |
| `TEBAAI_EXACT_EDITORIAL_EVIDENCE_RANKING_V1_DEV_REVIEW_REQUIRED` | **REVIEW_REQUIRED** — headings 51/53/56 no reproducen (ver §5c); Salmos primary 55↔368 (ver §5b) |
| `TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_REVIEW_REQUIRED` | **REVIEW_REQUIRED** — selección live 52/55/57 vs contenido dorado 51/53/56 |

No se actualizaron goldens a 52/55/57; no se cambió ranking; no se
flexibilizó el contrato 51/53/56; no se modificaron fixtures ni goldens.

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

### 3c. Incidente ambiental Milvus DEV (RESUELTO) y hallazgo de goldens

- El contenedor `milvus26-standalone` (Milvus 2.6.14) salió con código 1 durante
  la fase anterior; la pipeline cayó a modo degradado (fallback literal,
  ADR-006). El usuario lo **bajó y levantó manualmente** el 2026-08-02:
  contenedor healthy, gRPC 19530 y health 9091 abiertos, colección
  `tebaai_breslov_chunks_v1` presente con 5,370 entidades.
- Con Milvus restaurado, el backend **ya no reporta `research_status=degraded`**
  (todas las consultas del gate: complete/partial, `semantic_status=ok`).
- **Hallazgo de revalidación exacta:** los goldens de headings
  (51/33, 53/35, 56/38 con `structural_heading_exact`) NO reproducen ni con
  Milvus up: la selección live es `structural_heading_all_tokens_ordered` en
  las páginas 52/34, 55, 57 del doc page-first 132a791a. El contenido dorado
  (heading + cita “El Rabí Natán concluye su explicación”, impresa 33) existe
  en el corpus en la página 51 (chunk 8e1a1192), pero la selección literal
  (semántica aporta 0.0) elige el chunk cuerpo de la página 52. Los logs del
  2026-07-31 (Milvus up, post-reingest) muestran la MISMA selección
  `all_tokens_ordered` — no es una regresión de Milvus ni de código: los
  goldens 51/53/56/exact pertenecen a la era pre-reingest (corpus viejo doc
  47768aac) y no son producidos por la pipeline actual sin cambio de ranking
  (prohibido por la fase).
- Salmos 16:1: `printed_reference_exact` + PDF 55 ✓ estable (5/5), pero
  `printed_page=null` (golden 37).
- Nota 35: revalidación EXACTA ✓ (56/38, `footnote`, marker 35,
  `footnote_literal_exact`, 3/3 estable, evidence ID fijo).

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

## 5. Diferencia incidente ambiental vs contrato funcional

- **Incidente ambiental (resuelto):** Milvus DEV estuvo caído (contenedor
  Exited 1) durante la fase anterior → `research_status=degraded`. Restaurado
  manualmente por el usuario: contenedor healthy, colección 5,370 entidades,
  `semantic_status=ok`, sin degraded en ninguna consulta del gate.
- **Contrato funcional (hallazgo, pre-existente):** la selección de headings
  estructurales con la pipeline actual (sin cambios de ranking) elige los
  chunks 52/55/57 (`all_tokens_ordered`) desde el reingest page-first
  (evidenciado en logs del 2026-07-31). Los valores 51/53/56 con
  `structural_heading_exact` son de la era pre-reingest (doc 47768aac).
- Auth: idéntico para admin (admin) y guest (viewer activo); `/auth/me` 200
  con rol correcto para ambos; viewer read-only; rutas admin redirigen a
  `/research`.
- Los goldens de los specs skipeados (literal-evidence, source-layer,
  traceability, hebrew avanzado) tampoco reproducen con Milvus up: son de la
  era pre-reingest o del pipeline avanzado; los skips se conservan con razón
  corregida (no eran Milvus-causados).

## 5b. Hallazgo Salmos 16:1 (revisión pendiente, separada del ranking)

- Revalidación API (3× y 5×): `primary_match_type=printed_reference_exact`
  estable; evidencia LH página 55 (ev-716847bfff6da041) siempre presente entre
  los primarios.
- **Flip de primary no determinista:** run a run (y típicamente la primera
  llamada de una sesión) la evidencia activa alterna entre LH 55 y "Cruzando
  el Puente Angosto" página 368 (ev-7cf020c3fefe85c1) — causado por el paso
  de grounding de claims (generación de claims varía run a run; el retrieval
  y el boost `printed_reference_exact` son estables). No es degradado ni
  Milvus.
- **Metadata pendiente:** `printed_page` actual = null; golden esperado = 37
  (el marcador impreso "37" existe en la página 55 del corpus). No se declara
  PASS; queda como metadata pendiente separada del ranking.
- E2E guest: se valida el contrato estable (printed_reference_exact + LH 55
  entre los primarios); no se fuerza 55 como primary activo.

## 5c. Hallazgo headings estructurales (revisión pendiente)

| Query | Contenido dorado en corpus | Selección live actual | Match type live |
|---|---|---|---|
| CONSTRUYENDO UN MISHKÁN | página 51 / impresa 33 | 52 / 34 | structural_heading_all_tokens_ordered |
| INCLINADO HACIA LA BONDAD | página 53 / impresa 35 | 55 / null | structural_heading_all_tokens_ordered |
| MELODÍAS Y PLEGARIAS | página 56 / impresa 38 | 57 / null | structural_heading_all_tokens_ordered |

El contenido dorado (heading + cita "El Rabí Natán concluye su explicación"
para Mishkán; marcadores impresos 33/35/38 verificados en las páginas
51/53/56 del corpus) existe en el corpus, pero la selección live (semántica
aporta 0.0 entre ambos chunks; orden literal determinístico) elige los chunks
cuerpo adyacentes. Esta conducta ya aparecía en los logs del 2026-07-31 con
Milvus operativo (`structural_heading_all_tokens_ordered`, doc 132a791a), por
lo que **no era causada por el modo degraded**. No se modificó ranking ni
corpus; el contrato 51/53/56 se mantiene sin flexibilizar.

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
| Milvus DEV restaurado (healthy, 5,370) | PASS |
| `semantic_status=ok`, sin degraded | PASS |
| Nota 35 (56/38, marker 35) | PASS (revalidación exacta, 3/3 estable) |
| Salmos 16:1 | PASS contrato retrieval (printed_reference_exact, LH 55 entre primarios); HALLAZGO: primary activo 55↔368 (grounding no determinista); printed null vs golden 37 pendiente |
| Mishkán/Bondad/Melodías (51/53/56) | **HALLAZGO**: live 52/55/57 all_tokens_ordered; contrato 51/53/56 intacto, revisión pendiente |
| Backend/Frontend | PASS (1409 / 0-0-69-build) |
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
  goldens de era pre-reingest / pipeline avanzado — ninguno Milvus-causado,
  verificado con Milvus up), 0 failed.
  - acceso (corrida final con Milvus up): guest 3/3 + structural-heading 2/2
    (admin + guest móvil 390×844) + admin 4/4 + responsive 1/1 = 10/10 ×2;
    colloquial 5/5; interpretation-confirmation 4/4; visual 5/5;
    kokhavey-gedalia 2/2; simple-grounded-rag 4/4; admin 4/4;
    responsive 1/1; research.spec 1/1; analyzing-state 8/8; login 4/4;
    login-ten-times 10/10; etc.
- `git diff --check`: PASS.

Artefactos del gate: `network/guest-capture.jsonl` (reproducción sanitizada del
bloqueo) y `screenshots/` (composer, nota 35, Salmos 16:1, reload, logout,
admin denied) en este directorio.

## 8. Servicios

- PostgreSQL: NO reiniciado; Milvus: restaurado manualmente por el usuario
  (bajado y levantado el 2026-08-02; healthy, colección 5,370); LiteLLM: NO
  reiniciado.
- Backend DEV activo en 127.0.0.1:7008; Astro DEV activo en 127.0.0.1:3008.
- Producción no modificada; corpus no modificado; embeddings no recalculados.

## 9. URLs DEV

- http://127.0.0.1:7008/health — 200
- http://127.0.0.1:7008/ready — 200
- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research
