# Full backend failures — demonstrated preexisting

| Run | Passed | Failed | Warnings |
|---|---:|---:|---:|
|Initial worktree BEFORE new implementation/tests/API|1747|18|94|
|Final worktree|1775|18|94|

**PREEXISTING_BASELINE_FAILURE = 18; ENVIRONMENT_FAILURE = 0 established;
CURRENT_REGRESSION = 0.** Do not relabel these as environment failures without
cause evidence. 'Preexisting' refers to the preserved initial worktree, not a
new clean checkout of HEAD. No reset/stash/worktree replacement was used.

Proof exceeds HEAD equality: the full suite was executed before new files/API
existed, then after implementation. All18 failed node IDs match; the ENTIRE
failure-detail section is byte-identical, SHA256:

`565c26a094f1260ceebdcf5c322d1da70bc12c6f535251eb13ed81276c0219a1`

Raw evidence: `tests-baseline-full.txt` and `tests-backend-full.txt`;
individual exact node IDs, classification and line references:
`backend-failure-classification.json`. Both logs enumerate failures on445–462.

| Failure(s), same baseline/final log lines | Count | Classification |
|---|---:|---|
|psalm19 requested book/chapter,445|1|PREEXISTING_BASELINE_FAILURE|
|blood/speech mediated chain,446|1|PREEXISTING_BASELINE_FAILURE|
|scorpion grounded neighbors,447|1|PREEXISTING_BASELINE_FAILURE|
|Azamra named teaching,448|1|PREEXISTING_BASELINE_FAILURE|
|single-concept PostgreSQL retrieval,449|1|PREEXISTING_BASELINE_FAILURE|
|blood/speech traceability/per-work limit,450|1|PREEXISTING_BASELINE_FAILURE|
|Hebrew literal variants same physical page,451|1|PREEXISTING_BASELINE_FAILURE|
|Hebrew canonical niqqud/logical order,452|1|PREEXISTING_BASELINE_FAILURE|
|source-layer follow-up current question,453|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization1,454|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization2,455|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization3,456|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization4,457|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization5,458|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste parametrization6,459|1|PREEXISTING_BASELINE_FAILURE|
|copy/paste audit Spanish instruction exclusion,460|1|PREEXISTING_BASELINE_FAILURE|
|Tishá variant tisha beav,461|1|PREEXISTING_BASELINE_FAILURE|
|Tishá variant Tisha B'Av,462|1|PREEXISTING_BASELINE_FAILURE|

Observed symptom: real-corpus read-only QA calls return empty evidence,
primaries/claims/relations, producing assertions and empty-list IndexError.
`test_investigative_qa_v1.run_real` opens a psycopg connection and invokes the
existing QA retrieval; requested AI is disabled. There is no service timeout
in these failure details. Missing/mismatched corpus or scope is a possible
external cause, NOT established here. No real corpus mutation was made to
repair these unrelated expectations.

The final full suite remains FAIL. Passing focal91/related613 and zero new
suite regressions DO NOT override the certification gate's independent FAIL
(goldens/holdout), nor imply a globally passing backend.
