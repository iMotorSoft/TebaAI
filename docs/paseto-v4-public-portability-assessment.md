# PASETO v4.public: evaluación de portabilidad desde Team360

Estado: núcleo reusable implementado en TebaAI, todavía inactivo en autenticación. Team360 conserva la implementación de origen y TebaAI mantiene JWT/refresh vigente.

## Valor Reutilizable

Team360 implementó una base portable para tokens propios firmados con PASETO v4.public y Ed25519.

El diseño reusable incluye emisión y verificación separadas, selección de clave mediante `kid`, claims tipados, TTL corto, errores sanitizados y pruebas de token válido, expirado, malformado, issuer/type incorrectos y clave desconocida.

## Contrato Portable

Una futura librería compartida debe ser neutral respecto del producto y no leer variables de entorno directamente.

```text
issue_v4_public(claims, private_key, kid) -> token
verify_v4_public(token, public_keys_by_kid, expected_issuer, expected_type, leeway) -> claims
```

Claims base recomendados:

```text
iss
sub
typ
iat
exp
jti
```

El footer contiene `kid`. Claims de tenant, usuario, audiencia o propósito se agregan en adapters específicos de cada proyecto.

## Guardrails

La portabilidad depende de separar criptografía, configuración y autorización de negocio.

- private keys nunca llegan al frontend ni al repositorio;
- producción no genera claves efímeras en cada arranque;
- la configuración se resuelve mediante la fachada canónica de cada proyecto;
- verificar firma y claims no reemplaza membership, permisos ni ownership;
- tokens completos y payloads sensibles no se registran;
- rotación soporta varias public keys por `kid`;
- revocación usa TTL corto y, cuando el riesgo lo requiera, estado persistente por `jti`;
- refresh tokens siguen siendo opacos y rotables salvo ADR explícito distinto.

## Hardening de la Referencia Team360

La implementación actual demuestra emisión y verificación, pero debe cerrar varios puntos antes de extraerse como componente compartido.

1. Fallar al iniciar cuando PASETO está habilitado sin claves persistentes; no caer silenciosamente a una clave efímera.
2. Mover toda lectura de `TEAM360_*` a la fachada de configuración del proyecto e inyectar settings tipados.
3. Validar tipos y rangos de `iat`, `exp`, `jti` y TTL; rechazar `iat` futuro fuera del leeway y expiraciones inválidas.
4. Incorporar `aud` cuando un token pueda cruzar servicios o consumidores.
5. Convertir excepciones criptográficas y de parsing en códigos públicos genéricos; conservar detalle solo en telemetría sanitizada.
6. Verificar al arranque que private/public key y `kid` configurados son coherentes.
7. Separar keyring de verificación, signer activo y política de rotación; no asumir una sola clave.
8. Añadir test vectors oficiales, tests de claims con tipos maliciosos, clock skew, claves inconsistentes y configuración incompleta.
9. Mantener el payload base reservado para que claims del caller no puedan sustituir `typ`, `iss`, `iat`, `exp` o `jti`.

## Situación de TebaAI

TebaAI ya tiene access JWT, refresh opaco, rotación y detección de reutilización; Team360 tomó PASETO porque no tenía ese legado.

Reemplazar JWT ahora no aporta por sí solo una mejora funcional suficiente para justificar dos formatos en producción. PASETO queda como candidato para una migración deliberada o para nuevos tokens portables con un propósito que JWT no cubra adecuadamente.

El primitive neutral vive en `SrvRestAstroLS_v1/backend/modules/security/paseto_v4_public.py`. No lee entorno, no conoce rutas y exige claves, issuer, audience, propósito y reloj por inyección.

## Condiciones de Adopción en TebaAI

Una adopción futura requiere un ADR de seguridad y una migración compatible.

1. Definir qué token migra y por qué: access, invitación, magic link o service-to-service.
2. Mantener refresh opaco y sesiones PostgreSQL salvo evidencia contraria.
3. Integrar configuración solo mediante `core/config.py` y `globalVar.py`.
4. Diseñar key storage, rotación multi-`kid`, revocación y clock skew.
5. Validar `pyseto` con vectores oficiales y fijar versión de dependencia.
6. Soportar una ventana de convivencia JWT/PASETO con `typ` e issuer estrictos si se migra access auth.
7. Ejecutar regresiones de login, refresh, logout, reutilización, roles y expiración.
8. Actualizar `lat.md/authentication-security-policy.md` únicamente después de aprobar el ADR.

## Extracción a Otros Proyectos

La implementación Team360 debería evolucionar hacia un módulo reusable sin identidad `team360`, rutas Console ni lectura directa de `TEAM360_*`.

El núcleo compartible contiene primitives criptográficas y validación temporal. Cada proyecto conserva settings, claims de dominio, principal autenticado, autorización, storage de sesiones y respuestas HTTP.

## Decisión Actual

PASETO se preserva como activo técnico de Team360 y candidato de plataforma; no se rechaza ni se copia ciegamente sobre JWT.

El hardening portable y sus tests ya fueron extraídos en TebaAI. El próximo paso seguro es definir un paquete compartido o backport controlado hacia Team360; la activación runtime sigue sujeta a ADR y plan de compatibilidad.
