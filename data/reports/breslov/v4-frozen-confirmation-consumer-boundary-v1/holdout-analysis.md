# Sealed holdout analysis — V1 FAIL

## Outcome

The holdout was sealed before its first and only opening. Frozen V4 failed the
safety and utility requirements:

| Metric | Result |
|---|---:|
| Pages / regions | 35 / 447 |
| Unsafe false certifications | 6 |
| Unsafe false provenance certifications | 6 |
| False body certifications | 0 |
| Unsafe false continuations | 2 |
| False editorial completions | 6 |
| Body coverage | 99/119 |
| Notes coverage | 44/103 |
| Cross-page coverage | 0/3 |

No V4 rule, test or contract was changed after opening. No reseal or second
opening was performed.

## Two independent causes

### 1. Annotation mapping defect on pages 13 and 15

The source review grouped note lines using the centre of full-width note
lines. Continuation lines whose visual centre fell in a different column were
grouped separately from their marker line. In the sealed definition this left
expected note units that could not be matched one-to-one to the V4 regions.

V4 still emitted the expected note numbers and text for the note column
(1–4 on page 13; 7–9 on page 15). The evaluator counted five of those V4
regions as unsafe because their expected unit index was `null` or pointed at a
different unit. This is an annotation/holdout construction defect, not evidence
that V4 certified the wrong editorial text.

It still fails the gate: the sealed labels are the contract, and the labels
cannot be repaired without invalidating the single opening.

### 2. Genuine V4 false continuation on pages 206–207

This is a V4 defect independent of the annotation:

- `p206 note 5` (`region-5217650b8bbdf4a813b705d4`) was certified and linked
  across the page boundary to `p207 region-9454bd9ab68eb0ae5c16daca`.
- The p207 region is leading body text, not note 5 continuation. The actual
  p207 note 5 is a different unit at expected index 3, which is explicitly
  not certifiable.
- V4 certified and accepted the leading body region as `note 5`, producing
  one false certification, one false provenance/acceptance, and two false
  links/continuation states.

Root cause: the cross-page continuation proof checks marker continuity,
ownership and local flow, but does not independently exclude a leading body
region at the top of the next page from being treated as the terminal note
continuation.

## Cross-page result

None of the three annotated cross-page units linked:

- 108 → 109, note 31: terminal region unresolved.
- 164 → 165, note 57: terminal region unresolved.
- 226 → 227, note 77: terminal region unresolved.

The consumer-boundary synthetic cross-page test passes, but that only proves
the consumer preserves V4 output; it does not repair holdout utility.

## Determinism

- Repeated execution on all 35 pages: identical, 2 runs.
- Page-order permutation (sorted vs reversed): identical for every page.

Determinism does not offset the safety failure.

## Gate consequence

`TEBAAI_BRESLOV_V4_FROZEN_CONFIRMATION_AND_CONSUMER_BOUNDARY_V1` = **FAIL**.

- `CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO`
- `READY_FOR_C_REINGEST = NO`

The consumer boundary change is retained because it is independently correct
and tested, but it cannot make an unsafe V4 certifier ready for integration.
Do not reuse this holdout to tune V4.
