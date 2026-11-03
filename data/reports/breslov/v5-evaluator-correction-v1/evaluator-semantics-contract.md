# Evaluator semantics — correction v1

Written after pre-fix reproduction and before implementation. Synthetic ground truth only.

## Relations

The source of truth is canonical continuation_of_page plus the terminal/leading
note's source line IDs, not the candidate's editorial ID or note number alone.
Expected endpoints match canonical parts[].ids exactly (order independent).
A partial document with no receiving canonical page cannot establish a true relation.
A claim into absent/ambiguous context is unsafe, never silently accepted.

A. A valid forward claim joins the expected terminal and receiving source regions,
with equal nonempty editorial_unit_id, equal note number and proven sender identity.
A forward-only claim is valid evidence of the relation, but the reciprocal output
contract is incomplete: missing_reciprocal_links=1 (not a false positive).
B. A valid back-reference represents the SAME unordered endpoint pair as A.
Forward and reverse together count ONE valid_cross_page_relations, zero false links.
C. A dangling reference is a false claimed relation; deduplicate repeated claims.
D. A wrong existing target (even same note number) is false, by source ownership.
E. Different/empty editorial unit IDs contradict identity and make a claim false.
F. One missing reciprocal is a structural miss tracked separately. No expected
link at either endpoint is missed_true_links=1, not a false link.
G. Duplicate edges are representation only. Every distinct conflicting edge is
scored once; it must not hide behind a valid first link. Relations are keyed by
unordered (page, region_id) endpoints. Nonexistent target inferred direction uses
CONTINUED_FROM_PREVIOUS => -1, otherwise +1. Region IDs must be unique per page.

false_cross_page_links counts unique claimed relations contradicted by truth or
incompatible endpoint identity, never misses or duplicate representation.
unsafe_false_identity_proven counts proven endpoints of such invalid claims.
Existing false_identity_proven / inconsistent_identity_state remain intact.
Identity proof entries marked passed=False make an identity claim incompatible.
Empty legacy proof arrays are not newly rejected (existing evidence contract).

## Completion

COMPLETE_LOCAL claims completion on this page. CONTINUES_NEXT_PAGE is open locally;
CONTINUED_FROM_PREVIOUS receives a continuation. CROSS_PAGE_COMPLETE is a relation
status, NOT local completion. Only COMPLETE_LOCAL contradicting the *matching
canonical editorial unit's* outgoing continuation increments
false_editorial_completions. Other notes on the same page are not penalized.

## Frozen boundaries

No coverage/utility thresholds, certificate versions, certifier, consumer,
provenance, body quality or expected corpus labels change. Existing ownership,
body-certification and identity-without-link safety checks are retained.
Additional counters are diagnostics, not thresholds. No adjudication of V5.
The old run_gate execution remains forbidden in this task; its audit entrypoint
will delegate to the standalone corrected evaluator for the next review/gate.
