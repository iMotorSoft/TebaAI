# ADR-012: Bibliographic Query Planner V1

**Status:** Accepted (DEV)

**Date:** 2026-07-30

## Context

Research queries like "Azamra, ¿en qué tomo de Likutey Halajot está?" require 
bibliographic localization — not conceptual explanation. The system needs to:
1. Detect the bibliographic locator intent
2. Resolve the subject concept (Azamra)
3. Scope retrieval to a specific work (Likutey Halajot)
4. Identify the volume/tome from document metadata
5. Return grouped, evidence-grounded bibliographic results

## Decision

Implement a **BibliographicQueryPlanV1** module that sits alongside the 
page-first evidence contract and intercepts bibliographic queries before 
they enter the standard AI rendering pipeline.

## Architecture

```
User query
→ Intent classifier (deterministic patterns)
→ Subject resolver (canonical concept + variants)
→ Work resolver (document family matching)
→ Bibliographic planner (builds query plan)
→ Scoped retrieval (literal + structural)
→ Volume resolver (metadata precedence chain)
→ Occurrence classifier (presence type detection)
→ Answer formatter (markdown with evidence links)
```

### Models

- `QueryPlan` — structured intents, subject, scope, dimensions
- `BibliographicSubject` — canonical concept with variants and aliases
- `BibliographicScope` — resolved work with document IDs
- `ResolvedVolume` — volume with source and confidence
- `BibliographicOccurrence` — single concept occurrence
- `BibliographicResult` — grouped results per volume
- `BibliographicAnswer` — full answer with plan + results + evidence

### Volume resolution priority

1. Explicit `metadata.volume` or `metadata.volume_number`
2. Document code parsing
3. Document title parsing
4. Filename parsing
5. Edition label
6. Unresolved (single-volume fallback with warning)

### Presence types (from most to least reliable)

1. `literal_exact` — term appears literally
2. `hebrew_exact` — Hebrew variant appears
3. `bibliographic_reference` — alias/reference (e.g., "LM 282")
4. `thematic_development` — topic without literal term

## Files

- `backend/modules/library/bibliographic_planner.py` — planner + resolvers
- `backend/tests/test_bibliographic_planner.py` — 35 unit tests
- `backend/modules/library/simple_research_rag.py` — integration hook

## Limits

- Only `intent=bibliographic_locator` and `return_dimension=volume` implemented
- Likutey Halajot has no explicit volume metadata — returns single-volume default
- Subject registry is minimal (only Azamra + aliases)
- Future planners needed: structural aggregation, exclusion, relations

## Next phase

**Structural Aggregation Planner V1** — counting sections in a work.
