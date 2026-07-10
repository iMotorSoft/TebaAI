# Hybrid Search Milvus Alias Probe

- logical scope: `breslov_primary`
- Milvus collection: `tebaai_breslov_chunks_v1`
- Milvus metadata collection_code: `breslov`
- alias used: `True`

| Query | FTS hits | Direct vector hits | Hybrid hits | Hybrid vector hits |
| --- | ---: | ---: | ---: | ---: |
| `alegría` | 20 | 20 | 20 | 6 |
| `plegaria` | 20 | 20 | 20 | 0 |
| `hitbodedut` | 20 | 20 | 20 | 12 |
| `sangre habla` | 12 | 20 | 20 | 20 |
