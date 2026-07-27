# Instruction and subject contract

For the focal query:

```json
{
  "instruction_span": "la relaciones que tiene",
  "subject_span": "azamra",
  "subject": {
    "raw": "azamra",
    "normalized": "azamra",
    "canonical": "Azamra",
    "subject_type": "conceptual_term"
  }
}
```

The original query remains unchanged. Pattern matching removes only the validated instruction capture. The remainder must contain a safe non-stop subject. AI subjects must be grounded in the query and may not equal the complete relational query.
