# Search latency

## Verdict

`WARN`

Milvus search was blocked. The probe still measured embedding latency through LiteLLM.

## Summary by top_k

| top_k | Runs | Embedding avg ms | Milvus search ms | Total ms | Error |
|---:|---:|---:|---:|---:|---|
| 5 | 7 | 933.4 | N/A | N/A | Milvus unavailable |
| 10 | 7 | 933.4 | N/A | N/A | Milvus unavailable |
| 20 | 7 | 933.4 | N/A | N/A | Milvus unavailable |
| 50 | 7 | 933.4 | N/A | N/A | Milvus unavailable |

## Per-query embedding latency

| Query | Embedding ms |
|---|---:|
| tristeza | 2577 |
| miedo | 586 |
| alegría plegaria | 642 |
| sangre habla | 493 |
| ruaj habla | 871 |
| hitbodedut | 779 |
| emuná | 586 |

## What this means

- Milvus search latency could not be measured because the container was not reachable.
- The embedding baseline is usable for later comparison once Milvus is restored.
- All 28 search attempts ended with `Milvus unavailable`.
