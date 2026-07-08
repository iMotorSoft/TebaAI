# TebaAI AI Gateway and Model Routing Policy

This policy defines the implementation boundary for embeddings and generative model calls through LiteLLM.

## Gateway Rule

LiteLLM is the only model gateway for TebaAI runtime calls; domain logic does not call upstream providers directly.

```text
domain service -> typed AI port -> LiteLLM adapter -> configured alias -> upstream provider
```

Tests may use deterministic fake adapters. A deterministic production fallback is allowed only when the feature contract defines it and exposes that fallback in result metadata.

## Configuration Rule

Model configuration is resolved in `backend/core/config.py` and exposed through the existing backend facade where required.

- use TebaAI model aliases, not provider slugs, in application code;
- keep secrets outside code, frontend, tests and documentation;
- do not infer API protocol from an alias name;
- configure timeout and protocol explicitly;
- do not add a second environment reader in scripts or modules.

Embedding configuration continues to follow [[embeddings-configuration-policy]].

## Adapter Contract

Each AI capability exposes a narrow typed port aligned to its output rather than a generic unvalidated chat client.

Examples include an embedding port, conversation-analysis port, reranking port or answer-synthesis port. The adapter owns HTTP transport, authentication, timeout, retry policy and provider response normalization.

Domain services own prompts, business validation and the decision whether a normalized output is usable.

## Structured Output

Machine-consumed model output is untrusted input and must pass schema validation.

The implementation defines schema and version, required fields, enums, size limits, parse failure behavior and low-confidence behavior when applicable.

Invalid output cannot be repaired into a business fact by silently guessing required fields.

## Routing Rule

Routing selects the cheapest validated alias that satisfies the capability, context size, language, latency and quality gate.

Model prices and provider slugs are operational data and must not be frozen into this policy. Any routing change requires a focused evaluation over representative inputs and records the effective alias and model returned by LiteLLM.

Embedding aliases are not interchangeable: changing the embedding contract requires complete compatible reindexing and retrieval evaluation.

## Telemetry

Every generative call should emit sanitized operational metadata suitable for correlation and cost analysis.

```text
capability
configured alias
effective model when returned
protocol
latency
prompt, completion and total tokens when returned
cost when returned
correlation_id
knowledge_scope_id and session/run identifiers when applicable
fallback_used
error category
```

Prompts, retrieved passages and model responses may contain sensitive content and are not logged by default.

## Failure and Fallback

Fallback is explicit, bounded and observable; a successful HTTP response does not prove usable model output.

- transport, authentication, quota, timeout, parsing and empty-output errors remain distinct;
- retries are limited to transient failures and must not multiply non-idempotent effects;
- provider or alias fallback is disabled unless the capability documents and validates it;
- deterministic fallback reports `fallback_used=true` and its limitations;
- retrieval may degrade to PostgreSQL lexical search under [[knowledge-scope-contract]], never to a broader scope.

## Decision Boundary

Models may interpret, extract, classify provisionally, summarize or draft; TebaAI remains responsible for authority and evidence.

Models cannot grant access, select a tenant scope without authorization, promote documents, approve sensitive actions, invent references or turn inference into a literal citation.

For research answers, PostgreSQL evidence is retrieved first and returned with the generated result. Evidence level and limitations remain explicit.

## Validation

Real model claims require the service preflight and a representative evaluation, not only unit tests with fakes.

Validation records alias, effective provider/model when available, protocol, sample set, schema success, empty responses, latency, fallback behavior and known limitations according to [[service-preflight-methodology]].
