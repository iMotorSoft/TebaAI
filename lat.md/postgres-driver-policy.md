# PostgreSQL Driver Policy

TebaAI does not implement PostgreSQL runtime access in the bootstrap phase.

When PostgreSQL is introduced, the default iMotorSoft policy is:

- SQL migrations are the schema source of truth.
- Use `psycopg 3 async` directly for runtime DB access.
- Keep SQL in repositories, not in route handlers.
- Use Pydantic only at HTTP/API boundaries when validation or serialization is
  useful.
- Do not introduce SQLAlchemy, SQLModel or asyncpg without a dedicated ADR.

PostgreSQL is an external permanent service and must not be started, stopped or
restarted automatically by agents.
