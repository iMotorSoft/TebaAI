# Generic bounded main-body proof

Runtime input: live canonical layout IR plus native PDF drawings/text trace. No positive caller flags, golden roles, page selectors, filenames or note identities enter the proof.

Supported family: two broad horizontal opaque native stroked rules of matching width. The lower rule intersects the unique historical notes separator and precedes explicitly numbered note anchors. The upper rule intersects a unique centered small caption. This yields a bounded editorial panel, not an arbitrary central rectangle. Unsupported single-rule/unruled/multi-column families stay unresolved. Fixed one-point alignment and four-point source-bbox tolerance are geometric tolerances, not confidence scores; half-frame width excludes narrow side material, not a body score.

All must hold:

- `BODY_ZONE_PROOF`: inside the main panel, above the note separator, broad inset/full-panel box; paragraph sizes exceed note size and are homogeneous except explicit superscripts; no leading note marker.
- `OWNERSHIP_PROOF`: every part has exactly one source line identity; no line overlap or borrowed source owner.
- `ORDER_PROOF`: unique source IDs agree with geometric line order; native visible opaque horizontal LTR trace and strong LTR script. No mixed direction is certified. Geometry is authoritative for input-container permutation; within-line spans remain source-authoritative.
- `BOUNDARY_PROOF`: mapped forward serialization, no conflicting non-text box or overlapping owner.

Only this conjunction yields `MAIN_BODY / CERTIFIED`. Labels `text`, language, centrality, area and line count never suffice independently. Headers, footers, captions and headings outside the panel are not promoted by this proof. Mixed font-size interleaving/sidebars fail closed.

`ACCEPTED` additionally requires exact unchanged native/source token order, allowlisted serializer transformation and decoration-only Markdown equivalence, no replacement/control text. Provenance alone cannot grant quality. No normalization or repair was added. A body can have CERTIFIED provenance and UNRESOLVED quality.

This is a limited supported family, not a universal body detector or a guarantee for arbitrary unlabelled captions inside an otherwise supported panel. Holdout safety is empirical and source-annotation-scoped.
