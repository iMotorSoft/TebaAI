# Root cause

The deterministic cooccurrence detector recognized explicit forms such as “con qué conceptos”, but not open colloquial relationship markers such as “X la relaciones que tiene”. `_content_subjects()` then removed instruction words independently and found no safe single subject, so the result became `unknown`.

The live AI result failed strict validation and reused that weak fallback. The confirmation contract represented an unknown query by copying the complete input into `subject`, and the generic display template echoed it.

Separately, `SourcePanel` had only one null-response state. It could not distinguish a pending interpretation from an analyzed conversation with no selected turn, so it displayed an impossible instruction to select evidence.

The correction adds an operation-first relational matcher, explicit spans, prudent normalization, grounded AI validation, and a state-aware evidence placeholder. Retrieval phase separation was not changed.
