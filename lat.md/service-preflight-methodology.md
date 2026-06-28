# Service Preflight Methodology

Any test, smoke, benchmark or quality claim that depends on external services begins by proving the effective runtime state.

## Services

The controlled services are PostgreSQL, Milvus, LiteLLM and any upstream model provider reached through LiteLLM.

They are permanent external services. Agents do not start, stop, restart, migrate or reconfigure them without explicit instruction.

## Required Checks

Preflight records enough sanitized evidence to distinguish product behavior from infrastructure failure.

1. Confirm endpoint and process reachability.
2. Confirm expected database, schema, collection or model alias.
3. Confirm required variables exist without printing secrets.
4. Confirm dimensions, metric and embedding model for vector work.
5. Execute a minimal real call before model-dependent evaluation.
6. Record effective provider, model and fallback status when available.
7. Stop the conclusion if preflight fails.

## Evidence Rule

A successful HTTP status alone does not prove retrieval quality, provider identity or absence of fallback.

Reports must separate service availability, functional correctness, quality metrics and known limitations.
