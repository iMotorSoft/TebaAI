# Milvus 2.6 acid validation

- Milvus collection: `tebaai_breslov_chunks_v1`
- Scope code: `breslov_primary`
- Milvus connected: `True`
- PG connected: `True`

## Milvus
- collections: 14
- collection_exists: True
- num_entities: 5102
- loaded: True

## PG
- ready_chunks: 5102
- sample_size: 50

## Round-trip
- status: warn
- sample_found: 50
- sample_missing: 0
- duplicates: 0

## Search latency
- status: warn
- runs: 28

## Relation QA fallback
- status: warn
- runs: 2
