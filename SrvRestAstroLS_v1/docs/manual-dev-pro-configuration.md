# Configuración HTTP DEV/PRO

El navegador usa siempre el prefijo relativo `/api`. No existe un selector manual
DEV/PRO en el frontend.

## Activar DEV

DEV conecta Astro con Litestar mediante el proxy del servidor de desarrollo.

1. Iniciar el backend con `./backend-dev.sh start` si no está activo.
2. Iniciar o reiniciar Astro con `./astro-dev.sh restart`.
3. Verificar `http://127.0.0.1:7008/health` y `http://127.0.0.1:3008/login`.

El navegador solicita `/api/...`; `astro.config.mjs` reenvía ese prefijo a
`http://127.0.0.1:7008` únicamente dentro del proceso DEV.

## Activar PRO

PRO genera un frontend que consume la API por el mismo prefijo relativo `/api`
del origen público.

1. Ejecutar `pnpm check`, `pnpm test` y `pnpm build` desde `astro/`.
2. Inspeccionar `dist/` y confirmar que no contiene `127.0.0.1:7008` ni
   `localhost:7008`.

No se modifica `globalVar.py` ni se reinicia el backend para seleccionar PRO. Las rutas de login, logout e investigación quedan bajo `/api` en el mismo origen.

## Invariante

`global.js` publica `/api` tanto en DEV como en PRO. `globalVar.py`,
`PUBLIC_TEBAAI_API_BASE_URL` y `TEBAAI_ENV` no cambian esa URL del navegador.
