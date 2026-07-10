# Alias Contract

```text
Logical scope: breslov_primary
Milvus metadata collection_code: breslov
```

Reason: historical productive vectors were inserted with `collection_code=breslov`; Relation QA already uses this metadata; hybrid search must resolve logical scope to physical metadata code.

Current explicit alias map:

```python
MILVUS_COLLECTION_CODE_ALIASES = {
    "breslov_primary": "breslov",
}
```

Passthrough behavior:

- `breslov` resolves to `breslov`.
- unknown scopes resolve to themselves.
- `None` resolves to `None`.

Scope boundary:

- PostgreSQL filters continue to use logical `knowledge_scope_code`.
- Milvus vector filters use the resolved metadata code.
- No PostgreSQL rows, Milvus entities, embeddings, or corpus records are modified by this contract.
