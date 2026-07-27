# Resultados de seguridad

Completado:

- JWT: firma, issuer, audience, tipo y manipulación cubiertos por tests.
- Rol stale: el backend contrasta claim con PostgreSQL.
- Usuario inactivo: rechazado en cada request investigativo.
- Scope/tenant: acceso ligado a membresías activas.
- Interpretaciones: IDs ligados a usuario y conversación.
- Administración: guard `admin` más revalidación canónica.
- Desactivación/degradación: membresías sincronizadas y refresh sessions revocadas.
- No existen endpoints web activos de escritura de corpus o infraestructura.
- Login con patrón de SQL injection: 401.
- Query mayor al máximo: 400.
- Investigación sin autenticación: 401.
- Método alternativo no registrado: 405.
- Preflight CORS desde origen no confiable: 400.
- Token access manipulado: 401.
- Interpretation ID de otro usuario: 409.
- Denegaciones administrativas directas: 20/20 por endpoint.
- Snapshots PostgreSQL antes/después idénticos; vectores y corpus sin cambios.
- E2E guest 3/3 y Playwright no mutante 77/77.
- Escaneo de diff, reportes y logs: sin credenciales, JWT ni refresh tokens.

Riesgo conocido: no se observó rate limit dedicado de login o consultas. Es
aceptable sólo temporalmente para un grupo pequeño conocido, no para registro
público.
