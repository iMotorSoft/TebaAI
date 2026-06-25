# ADR-002 - Fachada de configuracion global

Estado: Accepted.

Fecha: 2026-06-25.

## Contexto

TebaAI necesita una politica estable para configuracion global compartida entre
modulos backend y frontend. El proyecto conserva convenciones iMotorSoft, pero
debe evitar lectura dispersa de variables de entorno, secretos visibles,
conexiones durante import y mezcla entre configuracion global y configuracion
de dominio.

Documento canonico:

[`../../lat.md/global-configuration-facade-policy.md`](../../lat.md/global-configuration-facade-policy.md)

## Decision

Mantener `globalVar.py` como fachada de configuracion comun, respaldada por
configuracion tipada en `core/config.py`.

La arquitectura aprobada es:

```text
.env / variables de entorno
        |
        v
core/config.py
        |
        v
configuracion tipada y validada
        |
        v
globalVar.py
        |
        v
fachada comun y estable para el programador
```

Solo `core/config.py` debe leer variables de entorno directamente.
`globalVar.py` puede exponer valores comunes ya validados, pero no debe crear
conexiones, pools, clientes, llamadas de red ni side effects de infraestructura.

En frontend, `SrvRestAstroLS_v1/astro/src/components/global.js` se reserva
para configuracion publica, siguiendo la ubicacion usada en Team360. No debe
contener secretos; solo valores publicos, por ejemplo variables `PUBLIC_*`,
pueden llegar al navegador.

## Consecuencias

- Los modulos pueden importar valores comunes desde `globalVar.py` sin conocer
  la implementacion interna de settings.
- La compatibilidad futura mejora si cambia `core/config.py`.
- Los recursos vivos quedan fuera de imports globales y deben vivir en el
  lifecycle de Litestar, conceptualmente bajo `app.state`.
- PostgreSQL, Milvus y LiteLLM siguen siendo servicios externos permanentes y
  no se gestionan automaticamente por esta decision.
- Las excepciones o cambios estructurales deben actualizar la politica LAT o
  crear un ADR nuevo.
