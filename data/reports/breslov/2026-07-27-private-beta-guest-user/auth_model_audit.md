# Auditoría del modelo de autorización

El contrato canónico es RBAC con roles globales `admin`, `editor` y `viewer`,
complementados por membresías `organization_members`, `workspace_members` y
`project_members`.

- Los access tokens son JWT firmados con issuer, audience, subject, role, type,
  jti y expiración.
- Los refresh tokens son opacos; sólo se persiste SHA-256, se rotan y se revocan.
- Las contraseñas usan el hasher Argon2id canónico y pepper opcional tipado.
- `viewer` es el rol de lectura equivalente solicitado; no se creó un rol nuevo.
- Las rutas `/users*` requieren `admin` en backend.
- Las rutas de búsqueda e investigación requieren autenticación y membresía
  activa en el scope.
- Cada request investigativo vuelve a comprobar usuario activo y concordancia
  entre el rol del JWT y PostgreSQL. Los endpoints admin repiten esa comprobación
  contra el rol canónico.
- Cambiar rol o desactivar sincroniza membresías y revoca refresh sessions.

La aplicación activa no registra endpoints HTTP de ingesta, promoción,
edición/borrado documental, reindexación, Milvus, configuración o reportes
privados. Los scripts locales no son accesibles al usuario web.
