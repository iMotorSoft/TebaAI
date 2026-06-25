# Global Configuration Facade Policy

Estado: accepted.

Fecha: 2026-06-25.

## 1. Contexto

TebaAI esta en fase post-bootstrap como plataforma generica de contenidos para
iMotorSoft. Breslov sera la primera vertical, pero esta politica no introduce
logica Breslov, ingestion, migraciones ni integracion runtime con PostgreSQL,
Milvus o LiteLLM.

El proyecto conserva la convencion conceptual habitual de iMotorSoft:

```text
Backend Python -> globalVar.py
Frontend Astro/Svelte -> global.js
```

La convencion existe para dar a programadores y agentes un punto de acceso
comodo, estable y reconocible a valores comunes del proyecto.

## 2. Problema Que Resuelve

Sin una politica explicita, la configuracion global puede degradarse hacia:

- lectura dispersa de variables de entorno;
- secretos representados como strings ordinarios;
- conexiones creadas durante import;
- mezcla de valores experimentales con configuracion activa;
- duplicacion entre settings, repositories y clientes de infraestructura;
- configuracion de dominio mezclada con invariantes transversales;
- cambios masivos si se reemplaza el mecanismo interno de settings.

Esta politica define donde se leen, validan y exponen valores compartidos, y
donde deben vivir los recursos activos.

## 3. Decision Adoptada

TebaAI mantiene `globalVar.py` como fachada estable de configuracion comun,
respaldada por configuracion tipada y validada en `core/config.py`.

El flujo canonico es:

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

`core/config.py` es la unica fuente que lee directamente variables de entorno.
`globalVar.py` expone valores comunes ya validados, sin crear recursos vivos ni
ejecutar operaciones de infraestructura.

## 4. Motivo Para Conservar `globalVar.py`

`globalVar.py` se conserva por compatibilidad conceptual con iMotorSoft y por
ergonomia de desarrollo. Debe permitir imports simples y legibles:

```python
import globalVar

host = globalVar.POSTGRES_HOST
port = globalVar.MILVUS_PORT
```

Tambien debe permitir imports explicitos:

```python
from globalVar import (
    SERVICE_NAME,
    POSTGRES_DSN,
    MILVUS_HOST,
    LITELLM_BASE_URL,
)
```

La fachada evita que cada modulo conozca detalles internos de `core/config.py`.
Si en el futuro cambia la implementacion de settings, los consumidores de
valores comunes mediante `globalVar.py` no deberian requerir modificaciones
masivas.

## 5. Relacion Entre `.env`, `core/config.py` Y `globalVar.py`

- `.env` y las variables de entorno son entradas externas.
- `core/config.py` lee entradas externas, valida tipos, aplica defaults seguros,
  verifica campos obligatorios, construye valores derivados y representa
  secretos con tipos seguros.
- `globalVar.py` importa la configuracion tipada desde `core/config.py` y la
  expone como fachada publica interna del backend.

Ningun modulo de dominio, repository, service o cliente de infraestructura debe
llamar directamente a `os.getenv()` ni leer `.env` por su cuenta.

## 6. Responsabilidades Permitidas

`core/config.py` debe agrupar configuraciones por dominio tecnico:

- runtime general;
- PostgreSQL;
- Milvus;
- LiteLLM;
- autenticacion;
- otros bloques transversales aprobados.

`globalVar.py` puede exponer:

- constantes publicas internas del backend;
- settings tipados;
- valores derivados;
- secretos encapsulados;
- defaults comunes;
- referencias de configuracion compartida;
- aliases de compatibilidad deprecados cuando sean necesarios.

`globalVar.py` debe organizarse por secciones, no como una lista desordenada:

```python
# Runtime general
# PostgreSQL
# Milvus
# LiteLLM
# Auth
# Idiomas
# Feature flags
# Identificadores globales del proyecto
# Compatibilidad o aliases deprecados
```

## 7. Responsabilidades Prohibidas

`globalVar.py` no debe:

- abrir conexiones PostgreSQL;
- crear pools;
- crear clientes Milvus;
- conectarse a LiteLLM;
- ejecutar queries;
- crear tablas;
- crear colecciones;
- hacer llamadas de red;
- tener side effects de infraestructura;
- iniciar, detener o reiniciar servicios;
- leer nuevamente variables de entorno por su cuenta.

Regla central:

```text
globalVar.py contiene configuracion y valores,
no recursos vivos ni operaciones.
```

## 8. Manejo De Secretos

Los secretos deben leerse y validarse exclusivamente desde `core/config.py` y
deben representarse mediante tipos seguros o wrappers que eviten exposicion
accidental en logs, repr, errores o respuestas HTTP.

No deben exponerse como strings visibles:

- passwords PostgreSQL;
- tokens Milvus;
- API keys LiteLLM u OpenAI;
- secretos JWT;
- credenciales internas.

Los documentos, ejemplos y validaciones deben mencionar nombres de variables o
conceptos, nunca valores reales.

## 9. Lifecycle De Recursos

Los recursos activos viven en el lifecycle de Litestar, no en `globalVar.py`.

Objetivo conceptual:

```text
app.state.pg_pool
app.state.milvus_client
app.state.litellm_client
```

La creacion y cierre de esos recursos corresponde a `core/lifespan.py`.
Cada proceso worker debe tener su propia instancia de pool o cliente.

Esta politica no implementa el lifecycle; solo fija el limite arquitectonico.

## 10. PostgreSQL

`globalVar.py` puede exponer conceptualmente:

```text
POSTGRES_ENABLED
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_DSN
POSTGRES_MIN_POOL_SIZE
POSTGRES_MAX_POOL_SIZE
POSTGRES_CONNECT_TIMEOUT_SECONDS
POSTGRES_APPLICATION_NAME
```

El DSN expuesto para uso comun debe evitar imprimir passwords. Si existe una
forma sanitizada para logs o diagnostico, debe distinguirse claramente del DSN
operativo.

El pool PostgreSQL no debe existir dentro de `globalVar.py`. Cuando se
implemente PostgreSQL runtime, debe seguir la politica de
[`postgres-driver-policy.md`](postgres-driver-policy.md): `psycopg 3 async`,
SQL en repositories y sin SQLAlchemy, SQLModel o asyncpg salvo ADR dedicado.

## 11. Milvus

`globalVar.py` puede exponer conceptualmente:

```text
MILVUS_ENABLED
MILVUS_HOST
MILVUS_PORT
MILVUS_URI
MILVUS_TOKEN_SECRET
MILVUS_CONNECT_TIMEOUT_SECONDS
```

Los datos puramente de infraestructura son globales. Los valores especificos de
un dominio pueden vivir en la configuracion del modulo que los utiliza, salvo
que se determine explicitamente que son transversales a todo TebaAI.

Ejemplos de configuracion de dominio:

- nombre de coleccion;
- vector field;
- embedding version;
- knowledge scope;
- schema de una coleccion.

El cliente Milvus no debe crearse en `globalVar.py`.

## 12. LiteLLM

`globalVar.py` puede exponer conceptualmente:

```text
LITELLM_ENABLED
LITELLM_BASE_URL
LITELLM_API_KEY_SECRET
LITELLM_DEFAULT_MODEL_ALIAS
```

Las llamadas HTTP y el cliente LiteLLM deben vivir en infraestructura o
providers. `globalVar.py` no debe ejecutar llamadas a modelos ni instanciar
clientes activos.

## 13. Auth

La configuracion de autenticacion transversal puede vivir en `core/config.py` y
exponerse mediante `globalVar.py` cuando sea comun a todo el backend.

Ejemplos conceptuales:

- issuer;
- audience;
- algoritmo;
- expiraciones;
- flags de autenticacion;
- referencias a secretos encapsulados.

Los secretos JWT, signing keys y credenciales internas no deben exponerse como
strings visibles ni llegar al frontend.

## 14. Convencion De `global.js`

En Astro/Svelte se mantiene la convencion usada en Team360:

```text
SrvRestAstroLS_v1/astro/src/components/global.js
```

`global.js` sirve como punto de acceso a valores publicos compartidos por el
frontend:

- nombre de la aplicacion;
- URL publica del backend;
- idiomas;
- feature flags publicas;
- rutas;
- textos o identificadores comunes.

Regla critica:

```text
global.js nunca debe contener secretos.
```

No deben exponerse en frontend:

- claves PostgreSQL;
- passwords;
- tokens Milvus;
- API keys LiteLLM;
- claves OpenAI;
- secretos JWT;
- credenciales internas.

Solo variables con prefijo publico, por ejemplo `PUBLIC_*`, pueden llegar al
navegador.

## 15. Configuracion Global Vs Configuracion De Dominio

La configuracion global representa valores transversales de plataforma:

- nombre del servicio;
- version;
- environment;
- debug;
- URLs;
- hosts;
- puertos;
- datos de PostgreSQL 18;
- datos de Milvus 2.6;
- datos de LiteLLM;
- alias de modelos;
- idiomas soportados;
- flags comunes;
- identificadores globales del proyecto.

La configuracion de dominio pertenece al modulo que la usa cuando describe
comportamiento o datos especificos de ese modulo. No debe subir a
`globalVar.py` solo por comodidad.

## 16. Ejemplos Conceptuales De Import

Imports aceptados para valores comunes:

```python
import globalVar

dsn = globalVar.POSTGRES_DSN
model_alias = globalVar.LITELLM_DEFAULT_MODEL_ALIAS
```

```python
from globalVar import SERVICE_NAME, MILVUS_URI
```

Patron no aceptado fuera de `core/config.py`:

```python
import os

postgres_host = os.getenv("TEBAAI_POSTGRES_HOST")
```

## 17. Riesgos Y Guardrails

Riesgos principales:

- `globalVar.py` puede crecer sin clasificacion;
- imports globales pueden ocultar dependencias reales;
- secretos pueden filtrarse si se exponen como strings;
- clientes creados durante import pueden romper tests, workers y reloads;
- configuracion de dominio puede confundirse con configuracion transversal.

Guardrails:

- antes de modificar configuracion global, variables de entorno, PostgreSQL,
  Milvus, LiteLLM, auth, `globalVar.py` o `global.js`, leer este documento;
- solo `core/config.py` lee variables de entorno;
- `globalVar.py` no crea recursos vivos;
- recursos vivos se crean y cierran desde `core/lifespan.py`;
- `global.js` solo contiene configuracion publica;
- cambios de excepcion requieren ADR o actualizacion LAT explicita.

## 18. Relacion Con Team360

Esta decision conserva de Team360:

- acceso comun mediante `globalVar.py`;
- centralizacion de URLs, keys, puertos y settings comunes;
- DSN sanitizado;
- configuracion comun reutilizable;
- imports simples para el programador;
- lifecycle PostgreSQL probado;
- separacion entre settings y repositories.

Esta decision mejora respecto de Team360:

- evita que `globalVar.py` crezca sin clasificacion;
- evita valores experimentales mezclados con configuracion activa;
- evita lectura dispersa de variables de entorno;
- evita conexiones durante import;
- evita late imports fragiles;
- evita secretos como strings ordinarios;
- evita dos implementaciones diferentes de Milvus;
- evita logica especifica de un modulo dentro de la configuracion global.

## 19. Estructura De Archivos Objetivo

Estructura conceptual aprobada:

```text
SrvRestAstroLS_v1/
|-- backend/
|   |-- globalVar.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- config.py
|   |   |-- constants.py
|   |   `-- lifespan.py
|   |-- infrastructure/
|   |   |-- postgres/
|   |   |-- milvus/
|   |   `-- litellm/
|   `-- modules/
|
`-- astro/
    `-- src/
        `-- components/
            `-- global.js
```

Esta estructura es objetivo conceptual. No obliga a crear archivos o carpetas
antes de la fase de implementacion correspondiente.

## 20. Criterios De Aceptacion

Una implementacion futura de esta politica debe cumplir:

- existe `core/config.py` como unica lectura directa de entorno;
- existe `globalVar.py` como fachada backend sin side effects de
  infraestructura;
- existe `SrvRestAstroLS_v1/astro/src/components/global.js` solo con
  configuracion publica frontend;
- ningun modulo de dominio, repository, service o cliente de infraestructura
  llama directamente a `os.getenv()`;
- PostgreSQL, Milvus y LiteLLM se instancian desde lifecycle o infraestructura,
  nunca desde `globalVar.py`;
- secretos no se imprimen ni se exponen como strings visibles;
- imports comunes mediante `globalVar.py` siguen funcionando si cambia la
  implementacion interna de settings;
- la documentacion y los tests relevantes se actualizan sin tocar servicios
  externos automaticamente.

## 21. Decisiones Diferidas

Quedan fuera de esta decision:

- libreria concreta para settings tipados si se requiere algo mas que
  Pydantic o standard library;
- nombres definitivos de todas las variables `TEBAAI_*`;
- formato final de DSN operativo y DSN sanitizado;
- esquema exacto de `core/lifespan.py`;
- factories concretas de PostgreSQL, Milvus y LiteLLM;
- politicas de rotacion de secretos;
- colecciones Milvus y schemas de dominio;
- aliases finales de modelos LiteLLM;
- implementacion de auth.

## 22. Proximos Pasos

Siguiente fase recomendada:

1. Disenar `core/config.py` con settings tipados y variables `TEBAAI_*`.
2. Implementar `globalVar.py` como fachada sin side effects.
3. Crear `SrvRestAstroLS_v1/astro/src/components/global.js` solo con valores
   publicos.
4. Agregar tests de configuracion que validen defaults, obligatorios y
   sanitizacion de secretos sin usar servicios externos.
5. Implementar `core/lifespan.py` solo cuando corresponda crear recursos vivos.
