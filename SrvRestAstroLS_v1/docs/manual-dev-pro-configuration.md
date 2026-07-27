# Selección manual DEV/PRO

Este documento describe únicamente cómo alternar la configuración pública HTTP de TebaAI. El modo versionado normal es DEV.

## Activar DEV

DEV conecta Astro directamente con Litestar. El backend no tiene un selector DEV/PRO adicional.

1. En `astro/src/components/global.js`, establecer `IS_REST_PRO = false`.
2. Iniciar el backend con `./backend-dev.sh start` si no está activo.
3. Iniciar o reiniciar Astro con `./astro-dev.sh restart`.
4. Verificar `http://127.0.0.1:7008/health` y `http://127.0.0.1:3008/login`.

El frontend usa `http://127.0.0.1:7008`. CORS admite `http://127.0.0.1:3008` y el alias local `http://localhost:3008`.

## Activar PRO

PRO genera un frontend que consume la API por el prefijo relativo `/api` del mismo origen público.

1. En `astro/src/components/global.js`, establecer `IS_REST_PRO = true`.
2. Ejecutar `pnpm check` y `pnpm build` desde `astro/`.
3. Inspeccionar `dist/` y confirmar que no contiene `127.0.0.1:7008` ni `localhost:7008`.

No se modifica `globalVar.py` ni se reinicia el backend para seleccionar PRO. Las rutas de login, logout e investigación quedan bajo `/api` en el mismo origen.

## Volver a DEV

La vuelta a desarrollo restaura el único selector frontend y requiere regenerar o reiniciar Astro.

1. Restablecer `IS_REST_PRO = false`.
2. Reiniciar Astro local.
3. Repetir los health checks locales.

## Precedencia efectiva

La selección manual es la única precedencia para las URLs HTTP públicas cubiertas aquí.

```text
global.js: IS_REST_PRO
  false -> http://127.0.0.1:7008
  true  -> /api
```

`globalVar.py`, `PUBLIC_TEBAAI_API_BASE_URL` y `TEBAAI_ENV` no participan en esta selección manual.
