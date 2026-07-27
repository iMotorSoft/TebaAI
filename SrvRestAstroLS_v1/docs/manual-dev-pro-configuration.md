# Selección manual DEV/PRO

Este documento describe únicamente cómo alternar la configuración pública HTTP de TebaAI. El modo versionado normal es DEV.

## Activar DEV

DEV conecta Astro directamente con Litestar y habilita los orígenes locales del navegador.

1. En `astro/src/components/global.js`, establecer `IS_REST_PRO = false`.
2. En `backend/globalVar.py`, establecer `IS_CORS_PRO = False`.
3. Iniciar o reiniciar el backend con `./backend-dev.sh restart`.
4. Iniciar o reiniciar Astro con `./astro-dev.sh restart`.
5. Verificar `http://127.0.0.1:7008/health` y `http://127.0.0.1:3008/login`.

El frontend usa `http://127.0.0.1:7008`. CORS admite `http://127.0.0.1:3008` y el alias local `http://localhost:3008`.

## Activar PRO

PRO genera un frontend que consume la API por el prefijo relativo `/api` del mismo origen público.

1. En `astro/src/components/global.js`, establecer `IS_REST_PRO = true`.
2. En `backend/globalVar.py`, establecer `IS_CORS_PRO = True`.
3. Ejecutar `pnpm check` y `pnpm build` desde `astro/`.
4. Inspeccionar `dist/` y confirmar que no contiene `127.0.0.1:7008` ni `localhost:7008`.
5. Reiniciar el backend cuando esa configuración vaya a entrar en vigor.

El frontend público canónico es `https://breslov.tebaai.live`. Las rutas de login, logout e investigación siguen siendo relativas y no requieren URLs separadas.

## Volver a DEV

La vuelta a desarrollo restaura ambos selectores y requiere regenerar o reiniciar los procesos que ya cargaron la configuración anterior.

1. Restablecer `IS_REST_PRO = false`.
2. Restablecer `IS_CORS_PRO = False`.
3. Reiniciar backend y Astro locales.
4. Repetir los health checks locales.

## Precedencia efectiva

La selección manual es la única precedencia para las URLs HTTP públicas cubiertas aquí.

```text
global.js: IS_REST_PRO
  false -> http://127.0.0.1:7008
  true  -> /api

globalVar.py: IS_CORS_PRO
  False -> orígenes Astro locales
  True  -> https://breslov.tebaai.live
```

`PUBLIC_TEBAAI_API_BASE_URL` no participa en la selección. `TEBAAI_ENV` sigue describiendo el entorno general tipado del backend, pero no sustituye los selectores HTTP manuales.
