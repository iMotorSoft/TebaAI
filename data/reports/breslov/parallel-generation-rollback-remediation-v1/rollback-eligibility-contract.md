# Rollback eligibility — immediate predecessor only

Required persisted evidence, all conjunctive:

1. Target belongs to the logical document and is currently INACTIVE.
2. Existing `retention_hold` is true. Target row lock serializes concurrent hold changes.
3. Active pointer `expected_generation_id` equals target: this is the immediate predecessor recorded by the last successful switch, not an arbitrary historical generation.
4. Audit contains APPLIED activation **to** target (including authoritative migration BACKFILL).
5. Audit contains APPLIED CUTOVER/ROLLBACK **from** target **to** current active.
6. Source identity matches and current active equals caller expectation; target differs from current for mutation.

No timestamp-only provenance. A retained never-active INACTIVE fails history. A retained historically ACTIVE G0 is not eligible when G1 is the pointer's immediate predecessor. Missing/inconsistent provenance fails closed, even if timestamps look plausible.

Every departing ACTIVE is retained with the existing hold. Cleanup's existing manifest admission rejects this hold before PG/vector deletion, including after rollback when NEW becomes the retained predecessor. Retention release stays an explicit existing administrative operation; no cleanup protection was weakened. Older retained generations may remain protected but are not thereby activatable. No automatic retention release or multi-hop target policy was added.

Production migration 043 already seeds APPLIED BACKFILL history. A manually created ACTIVE without audit is intentionally not rollback-eligible. No migration 044, reader modification, or operation on CURRENT C was performed.
