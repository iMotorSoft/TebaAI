# Rollback plan

## Runtime and UI

Revert the functional commit. The additive request/response fields disappear;
legacy fields and existing retrieval remain. No chunk or vector rollback is
needed.

## DEV metadata

`metadata-apply.json` captures the complete before/after values. For the three
guarded source hashes, remove only the versioned object:

```sql
UPDATE library_documents
SET bibliographic_metadata = bibliographic_metadata - 'canonical_identity_v1'
WHERE source_sha256 = ANY(:three_audited_hashes)
  AND status = :captured_status;
```

Before commit, verify exactly three rows and status values
`ready,test_candidate,test_candidate`. After rollback, verify the key is absent
and every other JSON key matches the captured `before` value.

Never rollback by replacing the complete JSON object unless matching the
captured hash/status guard, because unrelated metadata may be added later.
Milvus, embeddings, pages and chunks are not involved.
