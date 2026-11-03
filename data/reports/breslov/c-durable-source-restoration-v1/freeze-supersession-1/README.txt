Freeze supersession record — 1
================================

First freeze:  2026-10-23T12:16:34.943332+00:00
Second freeze: 2026-10-23T12:18:25.882753+00:00

Reason
------
The first freeze included an aggregation-script defect (a key-name mismatch in
final_validation.py): it read
`preexisting_product_code_modified_before` while capture_git_state.py writes
`preexisting_product_code_modified_before_gate`. That mismatch falsely reported
the 20 pre-existing modified product files as gate-introduced changes.

What changed
------------
Only the aggregation/reporting key was corrected in final_validation.py, plus an
explicit `durable_pdf_gitignored` observation. No expected outcome, threshold,
verification procedure, durable byte, or database value changed.

What did NOT change
-------------------
* durable original.pdf sha256 = 440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a
* durable size = 4,550,267 bytes; pages = 284; inode and mtime unchanged
* library_documents source metadata unchanged after the single authorized UPDATE
* C content: 942 chunks, 942 vectors, one ACTIVE generation, same active pointer

The first freeze artifacts are preserved unmodified in this directory:
frozen-at.json, frozen-manifest.json, frozen-hashes.txt, final-validation.json,
gate.json (all captured before the correction).

After the second freeze, certify_frozen.py re-verified every frozen hash and the
live endpoint; frozen hashes stayed unchanged.
