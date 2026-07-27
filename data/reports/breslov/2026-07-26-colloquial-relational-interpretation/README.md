# Colloquial relational interpretation

Date: 2026-07-26

This gate fixes the pre-retrieval understanding of open relational queries without changing the existing `interpret` / `analyze` / `legacy` phase architecture.

The focal query `azamra la relaciones que tiene` is now validated as `concept_cooccurrence`, operation `find_related_concepts`, instruction span `la relaciones que tiene`, and subject `Azamra`. Its controlled display is:

> Interpreté que desea investigar con qué conceptos se relaciona Azamra.

Interpretation returns only `Analizar` and `Modificar`, contains no retrieval artifacts, and defers evidence until analysis. The pending source panel now says: `La evidencia verificable aparecerá después del análisis.`

The implementation uses ordered ES/EN/HE operation markers, separates instruction and subject spans, records prudent grammatical normalization, validates AI grounding, and retains a deterministic fallback. It does not hardcode Azamra in the parser; Azamra is registered as a case-equivalent conceptual term in the auditable concept catalog.

See `manual_review_checklist.md` for immediate review at:

- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research
