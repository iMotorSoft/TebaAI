# Service start results

The official launchers were executed from `SrvRestAstroLS_v1/` after securely loading the local shell environment.

| Service | Launcher | URL | Result |
| --- | --- | --- | --- |
| Backend Litestar | `./backend-dev.sh start` | `http://127.0.0.1:7008` | PASS |
| Astro | `./astro-dev.sh start` | `http://127.0.0.1:3008` | PASS |

The backend listens on the expected Uvicorn command and `/health` returned HTTP 200. Astro returned HTTP 200 for `/`, `/login`, and `/request-access`. Logs and PID files remained under `.dev-logs/` and `.dev-pids/` as defined by the launchers.
