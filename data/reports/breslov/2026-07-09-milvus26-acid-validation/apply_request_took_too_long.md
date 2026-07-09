# apply request took too long

## Evidencia exacta

The exact string `apply request took too long` was not reproduced in the captured Milvus tail.
What is confirmed instead is the adjacent etcd failure:

`rpc error: code = Unavailable desc = etcdserver: request timed out, waiting for the applied index took too long`

## Contexto operativo

- Timestamp window: `2026-07-09T15:32:12.438706Z` to `2026-07-09T15:32:14.500703Z`
- Component: `etcd-client`
- Surrounding symptoms:
  - `streaming node is not alive`
  - `fail to apply balance, start a backoff...`
  - `no available streaming node`
- Container end state:
  - `Exited (1)`
  - `unhealthy`

## Hipotesis

The failure is consistent with an etcd apply backlog or cluster coordination stall, not with an application-level request timeout in TebaAI.
The logs point to Milvus internals losing healthy streaming capacity while etcd retries were timing out.

## Impact on TebaAI

- Milvus became unavailable for read-only retrieval.
- Relation QA fell back to lexical retrieval.
- Hybrid/vector search could not be exercised live.
- Search latency could not be measured beyond the embedding step.

## Action recommended

- Inspect Milvus and etcd logs together for coordination stalls.
- Check host pressure and container restart history before any manual recovery.
- Do not auto-restart from the application.
- Re-run this probe only after a manual operator action confirms Milvus is healthy.

## Estado

`historical` with a related timeout confirmed; exact literal phrase not reproduced.
