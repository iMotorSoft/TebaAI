# Response contract

El normalizador acepta `ok`, `partial` y `no_evidence`; rechaza estados desconocidos, respuestas no renderizables, hits sin identidad o cita, páginas con tipos inválidos y matrices incompatibles. Arrays opcionales se normalizan a `[]`; `null` se preserva. `answer_text` es fallback narrativo de `answer_markdown`.
