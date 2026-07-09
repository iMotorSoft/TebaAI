# Error catalog

## Confirmed errors

### Milvus connection failure

- `MilvusConnectionError`
- Message: `Failed to connect to Milvus at 127.0.0.1:19530: <MilvusException: (code=2, message=Fail connecting to server on 127.0.0.1:19530, illegal connection params or server unavailable)>`

### Round-trip blocked

- `MilvusUnavailable`
- Message: `Milvus is not connected or the collection does not exist`

### Relation QA fallback warning

- `milvus_unavailable: MilvusConnectionError — lexical retrieval used`
- Observed in both local Relation QA runs

### etcd timeout

- Repeated message: `rpc error: code = Unavailable desc = etcdserver: request timed out, waiting for the applied index took too long`
- First visible occurrences in the tail:
  - `2026-07-09T15:32:12.438706Z`
  - `2026-07-09T15:32:12.442756Z`
  - `2026-07-09T15:32:13.387651Z`
  - `2026-07-09T15:32:13.465457Z`
  - `2026-07-09T15:32:14.414690Z`
  - `2026-07-09T15:32:14.494311Z`

### Streaming and balancer symptoms

- `streaming node is not alive`
- `fail to apply balance, start a backoff...`
- `no available streaming node`

## Exact phrase search

- Exact `apply request took too long` was **not** found in the captured tail or in the repo search.
- The operationally relevant and repeated adjacent failure is the etcd applied-index timeout above.
