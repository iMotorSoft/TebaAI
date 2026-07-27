# Colloquial normalization policy

Normalization assists intent detection and never rewrites `original_query`.

The focal agreement mismatch records:

```json
{
  "original_fragment": "la relaciones",
  "interpreted_as": "las relaciones",
  "reason": "article_number_agreement",
  "confidence": "high"
}
```

The matcher also tolerates missing accents, punctuation, capitalization, spacing, and colloquial word order. Religious terms and names are not semantically corrected without controlled catalog identity.
