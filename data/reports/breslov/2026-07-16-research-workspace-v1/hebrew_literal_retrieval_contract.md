# Hebrew Literal Retrieval Contract

> Updated 2026-07-18: the production literal path now includes `lmi`,
> `intent=literal_lookup`, the shared `normalize_hebrew_search` representation,
> stable content-node evidence IDs, and physical page-anchor metadata. See
> `hebrew_normalization_contract.md` and `hebrew_literal_layer_comparison.json`.

## Query language resolution

```
Input: "donde aparece כי יש עון שמעכב תשובה"
→ interface_language: es
→ primary_retrieval_language: he
→ query_language: he
→ literal_phrases: [{text: "עון שמעכב תשובה", language: he}]
→ concepts: ["עון שמעכב תשובה", "עון"]

Input: "כי יש עון שמעכב תשובה"
→ interface_language: he
→ primary_retrieval_language: he
→ literal_phrases: [{text: "עון שמעכב תשובה", language: he}]
→ concepts: ["עון שמעכב תשובה", "עון"]

Input: "donde aparece el termino escorpion"
→ interface_language: es
→ primary_retrieval_language: es
→ literal_phrases: []
→ concepts: ["escorpion"]
```

## Retrieval ordering

### Hebrew primary: Tier 0 → 1 → 2 → 3 → 4
- Tier 0: Exact Hebrew literal phrase (language_match=exact, literal_match_kind=exact_phrase)
- Tier 1: Hebrew single term (language_match=exact, literal_match_kind=single_term)
- Tier 2: Hebrew semantic (language_match=exact, literal_match_kind=semantic)
- Tier 3: Secondary language match (es/en)
- Tier 4: Fallback

### Spanish primary: Same structure with es as primary

### English primary: Same structure with en as primary

## Hit model fields

- `language_match`: "exact" (primary language) | "primary" | "secondary" | "fallback"
- `literal_match_kind`: "exact_phrase" | "normalized" | "no_niqqud" | "single_term" | "semantic" | "none"
- `retrieval_tier`: 0-4 integer for sorting

## Primary evidence selection

- Backend selects primary_evidence_ids from claims
- AI rendering respects language priority
- Deterministic fallback uses best-ranked hits
- No Spanish substitute for missing Hebrew content
