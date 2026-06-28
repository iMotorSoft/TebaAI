# PostgreSQL Driver Policy

TebaAI uses PostgreSQL 18 as persistent truth through explicit asynchronous repositories and SQL migrations.

## Driver

Runtime database access uses `psycopg 3 async` and `psycopg_pool.AsyncConnectionPool`.

- pools are created and closed by the Litestar lifecycle;
- handlers obtain the pool through dependency injection;
- transactions use explicit async context managers;
- connections and pools are never created at import time.

## Persistence Boundary

PostgreSQL stores authoritative users, sessions, documents, chunks, metadata, search vectors and embedding records.

Milvus contains a derived retrieval index and cannot become the authority for content, permissions or bibliographic metadata.

## Repository Rules

SQL belongs in repositories or infrastructure helpers, not route handlers or schemas.

- SQL migrations are the schema source of truth.
- Pydantic is used at HTTP boundaries when validation or serialization helps.
- Domain objects may use dataclasses and enums.
- SQLAlchemy, SQLModel, asyncpg and ORMs require a dedicated ADR.

## Operations

PostgreSQL is an external permanent service and follows [[service-preflight-methodology]].

Agents must not start, stop, restart, reconfigure or migrate the service without explicit user instruction.
