# Checklist manual

URLs:

- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research

## Login

Ingresar `guest@tebaai.live` y la contraseña privada. Esperado: redirect a
`/research`, sin panel administrativo.

## Investigación

Consultar `tisha beav`. Esperado: interpretación, `Analizar`, `Modificar`,
síntesis y fuentes verificables.

## Modificar

Escribir una consulta imperfecta y pulsar `Modificar`. Esperado:
reinterpretación sin retrieval previo; análisis sólo al aprobar.

## Denegación

Abrir `/admin/users`. Esperado: redirect seguro a `/research`, sin datos ni
controles administrativos.

## Endpoint directo

Intentar `POST /users` con la sesión guest y un payload inocuo. Esperado: HTTP
403 antes de cualquier escritura.

## Logout

Cerrar sesión y volver a `/research`. Esperado: redirect a `/login`.
