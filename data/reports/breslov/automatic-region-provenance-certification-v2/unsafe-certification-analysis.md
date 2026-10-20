# Safety evaluation

Two counters are deliberately separate:

1. Requested unsafe false certification: provenance CERTIFIED + quality ACCEPTED when the annotated correct decision requires UNRESOLVED/error.
2. Stricter V1 regression counter: any incorrect provenance CERTIFIED, even when quality UNRESOLVED.

Both counters are **0 on the new sealed 18-page / 240-region holdout**. All five exact V1 false-zone regions emit UNRESOLVED in development. Known development goldens 167/56 retain exact local note source boundaries, column ownership and order; 55 next note 33 remains the previously source-reviewed accepted neighbor. 36/66 are not falsely complete. Development certification subset: 33, 35, 61–64. No bad heading or RTL candidate is accepted.

Evaluation demands an exact match of manually annotated ordered source identities/bboxes, zone, note number, columns and editorial completion for every certificate. An unmatched certification is unsafe, not silently ignored. Quality ACCEPTED additionally requires a positive quality annotation. Annotation is source/rendering review by the implementing agent, not independent human review or a statistical guarantee over the corpus.

The five V1 negatives were explicitly moved to development before V2 evaluation. None of the 12 V1 holdout pages, 55/56/167 or their supporting continuation pages occurs in the new holdout.

The new definition, source inventory, evaluator, tests and implementation dependencies were SHA-256 sealed before the one-shot evaluator executed. `holdout-evaluation-started.json` records opening. All hashes were verified after evaluation. No rules, thresholds or exceptions were changed after opening. Re-sealing or re-opening is refused by the scripts.

Safety has improved on this bounded reviewed scope. This does NOT establish universal safe automatic provenance. V2 still FAILS required-class utility and lacks automatic cross-page owner linking. Therefore worker integration is not authorized despite the observed zero counters.
