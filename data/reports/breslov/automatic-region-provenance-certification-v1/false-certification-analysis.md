# Unsafe false certifications — 5 observed

Sealed12-page holdout:148 automatically discovered regions,44 provenance
certificates;39 correct structural certifications and5 wrong zones.104
unresolved:28 correctly unsupported,76 structurally good source regions left
unresolved. Quality:2 ACCEPTED,8 platform errors,0 source errors,138 unresolved.

| Page | Source annotation boxes | Expected | Actual CERTIFIED zone | Quality |
|---|---|---|---|---|
|80|9,10 (two independent regions)|note|footer|UNRESOLVED each|
|140|11|note continuation|editorial_heading|UNRESOLVED|
|200|9,10 (two independent regions)|note|footer|UNRESOLVED each|

False source ownership/zone assertions are unsafe EVEN when a downstream
quality decision withholds acceptance. Therefore gate FAIL is mandatory.
No unsafe ACCEPTED quality was observed on this structurally annotated sample;
that is NOT a general visible-text fidelity guarantee or an excuse for the five
false provenance certificates.

Annotations were source-IR structural review, not exhaustive rendered glyph
inspection. They cannot establish a zero visual-error rate. Empty100 is retained
in page counts with zero regions, not invented positive coverage. The sample
contains simple body190, notes, columns, damaged Hebrew, mixed script and
interleaved-layout defects; target categories were not inferred as successful
certifications. Raw visual Hebrew remains unresolved rather than manually
marked good.

No rules changed after evaluation. Sealed annotations and implementation hashes
are retained. Numeric >99/merged90 and mixed content remain recorded limitations,
not rule-tuning opportunities within V1. Future V2 must replace semantic trust
in extractor class labels and provide a new sealed holdout.

Known checked golden note ownership has no observed false certificate; however
167 body/RTL,55 previous good tail isolation and56 cross-page full end FAIL.
Hence zero-unsafe and good-coverage criteria are both unmet.
