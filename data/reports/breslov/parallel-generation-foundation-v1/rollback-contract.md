# Rollback — proposed, NOT implemented or exercised

Rollback is the same CAS primitive with expected NEW, target retained OLD and current expected epoch. No extraction, model call, chunk creation, embedding, vector insert/delete, collection alias or run reconstruction is permitted.

Retention must preserve document/text/pages/chunks/embeddings/actual vectors/source/manifests and generation-bound citations for both generations. Pointer change alone makes OLD/NEW normal-visible/invisible. Retained formerly active generations cannot be deleted by candidate cleanup; explicit retention release is a future separate operation.

No cutover occurred, so OLD_RETAINED_AFTER_CUTOVER and NEW_RETAINED_AFTER_ROLLBACK are NOT TESTED. Current C remained physically unchanged, which is not a rollback test. Existing source repository excludes archived documents and chooses latest completed page run; historical viewer access must be adapted before this contract can pass.
