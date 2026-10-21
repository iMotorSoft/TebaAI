# Future GO / NO-GO checklists

Every row must have fresh evidence + owner approval; missing/UNKNOWN/skipped = NO-GO. Planning PASS is NOT ingestion authorization. Current execution readiness = NO.

## Before ingestion (separate authorization)

- [ ] TEBAAI_BRESLOV_C_PARALLEL_GENERATION_SAFETY_V1 PASS: controlled duplicate admission, unified candidate/active visibility, atomic reversible switch, generation-safe retry/cleanup.
- [ ] Approved branch/version/code/config/certificate/publication hashes committed; dirty extraction dependencies independently resolved/revalidated; remote/worktree baseline approved.
- [ ] Source SHA exactly 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a, 284 physical pages; source size/hash checked immediately before job.
- [ ] OLD durable source/reference repaired under separate authority, readable through authorized viewer, retention/backup of actual configured storage root verified.
- [ ] Fresh coherent OLD logical snapshot captured/sealed, including actual vectors and complete source/page/chunk/citation mappings; no drift or unexplained generations/orphans.
- [ ] Fresh known-good/bad/partial-page retrieval baseline sealed, matching algorithm/lineage/geometry contract frozen, all page coverage established.
- [ ] PostgreSQL healthy (database/schema/read-only inspection), Milvus healthy (collection/schema/load/dimension/model/PK), unloaded collection attribution uncertainty closed; no fallback.
- [ ] Embedding service healthy, effective alias/provider/dimension verified under separately authorized health call, no fallback; no model change mid-run.
- [ ] Worker healthy/lease/queue bounded to approved candidate, unrelated jobs excluded; no worker startup implicit in preflight.
- [ ] Distinct computed NEW document ID/version, manifest/attempt/idempotency approval, namespace/doc-based vector isolation and exact tenant verified; normal user cannot retrieve NEW during draft/chunk/vector stages.
- [ ] OLD remains ready and sole authority through build/validation; no delete-first/overwrite-first.
- [ ] Rollback primitive verified on fixtures incl. lost response/concurrency/caches, retained OLD data/source/vector integrity checked, cleanup hold approved; capacity sufficient for both.
- [ ] Explicit future ingestion GO and user authorization, not best effort.

## Before cutover (separate decision)

- [ ] Candidate ingestion completed and run/job/manifest immutable seal PASS.
- [ ] Region/page/document reconciliation PASS; all 284 pages accounted for; ambiguity = 0.
- [ ] Unexpected accepted-content losses = 0, unexpected gains = 0, bad searchable leaks = 0, good-neighbor loss = 0.
- [ ] Known-good and partial-page retrieval PASS in isolated NEW; known-bad exclusion PASS across all supported paths.
- [ ] Citation/page/source identity and visual source availability PASS for accepted/quarantined regions.
- [ ] Exact chunk/embedding/vector mappings/content/model hashes PASS; duplicates = 0, cross-generation contamination = 0.
- [ ] Normal retrieval still only OLD; candidate not included by test_candidate flag or stale caches.
- [ ] All candidate vectors already exist; cutover requires no reembed/worker/index write.
- [ ] OLD fully retained, atomic switch and audited reverse available; expected active state/seals checked; no third generation.
- [ ] Explicit cutover approval, validation operator/window and rollback trigger response ready.

## Before eventual cleanup

- [ ] Post-cutover validation and stabilization PASS, explicit owner retention policy and rollback-window closure recorded.
- [ ] OLD dependency/reference/source retention audit and restorable backup verified; exact OLD-only manifest dry-run approved.
- [ ] Separate cleanup authorization; never scope/source-SHA-wide deletion; no deletion of NEW/shared source or unrelated corpus.
