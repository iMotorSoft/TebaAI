# Security results

- Strict Pydantic schema remains `extra=forbid`.
- AI subjects must occur in the original query or validated conversation context.
- Open relational AI output must contain exactly one grounded subject.
- Binary relations still require a grounded pair.
- Complete relational queries cannot be accepted as their own subject.
- Markup, control characters, and bidi override controls are rejected from relational subject extraction.
- The client sends only `interpretation_id`; server-side stored structure remains authoritative for analysis.
- SQL, evidence IDs, and structured intent modifications from the client are not accepted.
- Svelte renders interpretation as text; HTML and Markdown do not execute.
- Schema failures use the bounded reason code `ai_schema_rejected`; raw model output and validation internals are not surfaced.
- Reports contain no credentials, tokens, cookies, storage state, prompts, or chain of thought.

Result: PASS.
