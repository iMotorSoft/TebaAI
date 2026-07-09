# Service status

## Preflight

- Branch: `feature/console-backend-core`
- Initial HEAD: `fd78fd42f6b38636eb905d35a708dcab33c39262`
- Backend dev server: PID file empty, port `7008` free
- Astro dev server: PID file empty, port `3008` free

## Runtime verdict

- Milvus container `milvus26-standalone`: `Exited (1)`, `unhealthy`
- PostgreSQL probe: connected
- Ready chunks in PG for `breslov_primary`: `5102`

## Note

- Backend HTTP Relation QA CLI was not exercised against the live server because the backend dev server was not running.
