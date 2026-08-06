# Premium UX — Inventario visual (2026-08-05)

Inventario obligatorio del sistema visual de Breslov Research antes de la
implementación del Gestor de Contenidos premium. Verificado contra
`astro/src/assets/app.css`, `research.css`, layouts y componentes.

## Layout principal

| Elemento | Componente existente reutilizado | Token existente | Componente nuevo | Razón del nuevo |
|---|---|---|---|---|
| Shell de página | `Layout.astro` (importa app.css + research.css) | — | — | Reutilizado tal cual |
| Cabecera | Patrón `.research-header` de `ResearchWorkspace` | `--ivory-50`, `--line`, `--navy-950` | `.cm-header` en `content-manager.css` | Continuidad visual con `/research` sin arrastrar el grid de 3 columnas |
| Identidad de producto | `RebbeNajmanIdentity` / `.research-brand` | `--serif`, `--navy-950` | `.cm-brand` | Marca `רבי נחמן` + REBE NAJMÁN · BRESLOV RESEARCH |
| Navegación | Patrón `/research` (Volver al inicio, Cerrar sesión) | — | `.cm-header-context` | Sin shell administrativo paralelo; enlace a Investigación + logout |
| Columna de lectura | `.research-main` (clamp padding) | — | `.cm-main` width min(1060px, 100% - 56px) | Ancho de lectura controlado, no tabla full-width |

## Tokens visuales (reutilizados de `app.css:4`)

| Token | Valor | Uso en el gestor |
|---|---|---|
| `--navy-950` | `#061f3b` | Títulos, botón primario, fondo del stepper activo |
| `--navy-900` | `#09294b` | Labels, headings de tarjetas |
| `--navy-800` | `#123a60` | Links, bordes de foco |
| `--ivory-50` | `#fdfaf4` | Fondo del shell |
| `--ivory-100` | `#f8f1e7` | Fondo alterno |
| `--paper-200` | `#eee2d0` | Badges neutros |
| `--gold-500` | `#c89432` | Kickers, acentos, marcas de éxito |
| `--ink-900` | `#142235` | Texto base |
| `--ink-700` | `#3e4854` | Texto secundario |
| `--line` | `rgba(23,43,66,.14)` | Bordes |
| `--serif` | Georgia + Noto Serif Hebrew | Títulos editoriales |
| `--sans` | Inter + system | UI |

Radios: 6-10px (botones research 6px, cards 10px, pills 20px). Sombras: solo
`0 10px 28px rgba(6,31,59,.06)` suave en cards; sin sombras pesadas.

## Componentes

| Superficie | Reutilizado | Nuevo | Razón |
|---|---|---|---|
| Botón primario | `.login-button` / `.header-login` (navy, hover navy-800) | `.cm-action` | Mismo carácter; área táctil ≥ 44px |
| Botón secundario | `.secondary-action` / botones `.research` | `.cm-action--ghost` | Outline sutil, sin relleno |
| Cards | `.bri-card` / `#fffdf9` border line | `.cm-card` | Superficie editorial con borde y sombra suave |
| Badges de estado | `.source-stats` pills (r20, paper-200) | `.cm-status` con `data-tone` | Estados por texto+icono+color (no solo color) |
| Dropzone | — | `.cm-dropzone` | No existía; accesible (Enter/Space), drag + click |
| Stepper 5 etapas | — | `.cm-stepper` | No existía; requerido por la política |
| Tabla editorial | `table-zebra` DaisyUI (descartado) | `.cm-table` | La tabla DaisyUI era el patrón de dashboard genérico; se reemplazó por tabla ligera con hover ivory |
| Cards móviles | Patrón `md:hidden` cards existente | `.cm-mobile-cards` | Misma estrategia responsive del producto |
| Acordeón técnico | `details/summary` de `works-results` | `.cm-details` | Mismo patrón, subordinación de lo técnico |
| Mensajes | `.error`/`.warning` de research.css | `.cm-message--*` | Borde izquierdo de 3px + fondo tintado |
| Loader | — | `.cm-loading` | Spinner discreto sin animación permanente |
| RTL hebreo | `.research-hebrew-text` (research.css) | `.cm-hebrew` | Misma fuente Noto Serif Hebrew, direction/plaintext |

## Estados vacíos, focus, motion

- Estado vacío: patrón `.research-empty` (título serif + p + acción) → `.cm-empty`.
- Focus: `a:focus-visible, button:focus-visible { outline 3px gold-500 }` global — reutilizado; extendido a filas de tabla y dropzone.
- Motion: `prefers-reduced-motion` global en app.css:42; el gestor añade el mismo respeto a su barra de progreso y hover.

## Nada nuevo del sistema visual

No se agregaron colores, tipografías ni radios fuera de los tokens existentes.
No se creó un segundo design system: el CSS nuevo es una capa delgada sobre
los tokens de Breslov Research.
