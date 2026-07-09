# Collection health

## Current verdict

Milvus is not reachable, so the product collection could not be verified live.

## Probe output

- Host: `127.0.0.1`
- Port: `19530`
- Collection: `tebaai_breslov_chunks_v1`
- Connected: `false`
- Collection exists: `false`
- Num entities: unavailable
- Schema ok: `false`
- Loaded: `false`

## Operational interpretation

The collection health check is blocked by the container state, not by the application code.
No safe read-only verification of schema, load state, or entity count was possible while Milvus was exited.
