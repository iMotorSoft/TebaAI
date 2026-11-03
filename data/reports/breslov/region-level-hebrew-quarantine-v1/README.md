# Region-level Hebrew Quarantine V1

**BLOCKED — implementación parcial offline, no enforcement del worker.**

- [Reporte](REPORT.md): alcance exacto, tests y riesgos pendientes.
- [Pipeline anterior](pipeline-before.md).
- [Contrato y tareas restantes](architecture-decision.md).
- `gate.json`: métricas live null, no ceros inventados.
- `region-publication-results.json`: resultados sólo del consumidor offline.
- `tests-backend-full.txt` / `tests-backend-baseline.txt`: 20 fallos idénticos, 0 nuevos.

Reproducir desde `SrvRestAstroLS_v1/backend`:

```bash
uv run pytest tests/test_region_publication.py
uv run python ../../data/reports/breslov/region-level-hebrew-quarantine-v1/probe_publication.py
```

El probe requiere el PDF original local y el V5 local preexistente; no escribe stores. Los snapshots se obtienen con `snapshot_dev.py before|after|after-cleanup`, sin reset/apply.

Sin commit/push; reingesta completa C NO autorizada por este resultado.
