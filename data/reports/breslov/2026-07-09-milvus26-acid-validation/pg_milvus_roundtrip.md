# PG <-> Milvus round-trip

## Result

`BLOCKED`

## Evidence

- PostgreSQL ready chunk count for `breslov_primary`: `5102`
- Milvus collection count: unavailable
- Deterministic sample size: `20`
- Sample found in Milvus: `0`
- Sample missing: `0`
- Duplicates: `0`

## Why it is blocked

Milvus connection failed before the round-trip query could run.
The probe therefore could not validate `chunk_id` round-trips, `document_id`, or `content_sha256` parity.

## Intended read-only check

If Milvus is reachable, the probe queries a deterministic sample of 20 PG chunk ids and compares:

- `chunk_id`
- `document_id`
- `collection_code`
- `content_sha256`

No writes, no inserts, no deletes, no reindexing.
