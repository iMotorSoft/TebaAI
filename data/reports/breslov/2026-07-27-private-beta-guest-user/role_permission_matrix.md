# Matriz rol-permiso

| Capacidad | viewer | admin |
| --- | --- | --- |
| Login, refresh, logout, perfil propio | Permitido | Permitido |
| `/research` | Permitido | Permitido |
| Interpretar, Analizar, Modificar | Permitido | Permitido |
| Leer síntesis, fuentes y evidencia | Permitido | Permitido |
| Búsqueda y filtros de lectura | Permitido | Permitido |
| Listar/crear/modificar usuarios | Denegado | Permitido |
| Cambiar roles o activación | Denegado | Permitido |
| Ingesta, promoción, edición, borrado | No expuesto y sin permiso | No expuesto |
| Reindexación, Milvus, configuración | No expuesto y sin permiso | No expuesto |
| Reportes privados o secretos | No expuesto y sin permiso | No expuesto |

`viewer` se asigna también como rol de membresía en organización, workspace y
proyecto. No se utilizan wildcards de permisos.
