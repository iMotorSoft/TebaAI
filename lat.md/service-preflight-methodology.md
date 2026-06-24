# Service Preflight Methodology

Before any test, smoke or benchmark that depends on real external services,
verify the service state explicitly.

## Services

- PostgreSQL
- Milvus
- LiteLLM

These services are permanent external services. Agents must not start, stop or
restart them automatically.

## Required Checks

When a future phase uses these services, document:

- service endpoint;
- health check command;
- expected database or collection;
- environment variables present without printing secrets;
- model alias registered when LiteLLM is used;
- minimal real call when model quality is being evaluated;
- fallback status.

If preflight fails, do not interpret the test as product quality evidence.
