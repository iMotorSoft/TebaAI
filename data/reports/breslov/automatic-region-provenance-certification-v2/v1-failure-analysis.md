# Root cause: V1 trusted converter classes as editorial zone proof

V1 FAIL is the demonstrated baseline, not reopened here. See [five exact regions](v1-unsafe-certifications.json).

## Reproduction and causal evidence

Four source note regions on pages 80/200 were labelled `page-footer`. One note continuation on 140 was labelled `section-header`. V1's `_ZONES` table converted these directly into trusted `footer`/`editorial_heading` certificates. Unique identities, non-overlap and LTR script did not prove those editorial zones. All five had quality UNRESOLVED; the provenance claims were nevertheless false.

One common root cause explains all five: **EXTRACTOR_CLASS_IS_NOT_EDITORIAL_ZONE_PROOF**. The secondary gap is lack of editorial boundary proof: a box or page ending is not note completion. No five per-region exceptions were added.

## Reuse versus withdrawal

Retained unchanged: V1 candidate discovery, source identities, forward canonical serializer, Markdown ranges, disjoint note-flow adapter, exact historical notes-heading vocabulary and independent native trace checks. No V1 evidence or source file was overwritten.

Withdrawn: automatic trust in header/footer/heading labels, script-only direction evidence, certification of an open terminal note. V2 requires a unique preceding editorial separator, explicit note anchors, mapped column flow, source identity/geometry non-overlap, native horizontal visible text order, and a subsequent explicit note marker. Predicates are conjunctive, not a score.

All five now emit UNRESOLVED + QUALITY_UNRESOLVED in live development evaluation and in portable source-IR regression tests. Exact region/source identities and missing proofs are preserved in the JSON.

## Other development gaps

- 167 body: five Spanish boxes remain unresolved. Generic `text` also labels unlabelled note continuations; no independent supported body-family certificate exists. Native equivalence alone does not establish editorial role.
- 167 notes: 61–64 certified/accepted; 60/65 lack native logical-order evidence; 66 lacks editorial closure. All seven have checked local source boundaries and column/order against existing editorial goldens.
- 167 RTL: extraction destroys much script evidence; neither zone nor direction/logical order is proven. No Hebrew-based rejection or repair.
- 55: same proof contract applies to both neighbors. The previous whole box has interleaving/ownership problems, unlike its historically selected good tail. Next note 33 has full proof and remains accepted. Bad heading now lacks zone proof, so even deterministic corruption cannot bypass provenance to assign quality.
- 56: note 35 provenance certified, quality unresolved. Note 36 has KNOWN local boundary but UNRESOLVED_CONTINUATION. Same for 66 on 167. The actual ends on 57/168 remain development goldens, NOT automatic links.

The implementation is deliberately incomplete rather than made to pass with weaker body/cross-page predicates. It is not authorized for worker integration.
