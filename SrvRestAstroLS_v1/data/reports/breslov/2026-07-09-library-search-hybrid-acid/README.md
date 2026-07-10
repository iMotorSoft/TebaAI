# Library Search Hybrid Acid Batch

- endpoint: `http://127.0.0.1:7008/library/search`
- base commit: `b2b0355c471cd9590b2f29cd3acb88b11349ab9e`
- logical scope: `breslov_primary`
- Milvus collection_code alias: `breslov`
- global score: `189/200` (94.5%)
- status: `PASS fuerte`

| ID | Query | Mode | HTTP | Results | FTS | Vector direct | Hybrid vector | Score | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `hybrid_q01` | alegría | hybrid | 200 | 10 | 10 | 10 | 2 | 20 | PASS fuerte |
| `hybrid_q02` | plegaria | hybrid | 200 | 10 | 10 | 10 | 0 | 17 | PASS usable |
| `hybrid_q03` | hitbodedut | hybrid | 200 | 10 | 10 | 10 | 6 | 19 | PASS fuerte |
| `hybrid_q04` | sangre habla | hybrid | 200 | 10 | 10 | 10 | 10 | 20 | PASS fuerte |
| `hybrid_q05` | miedo y fe | hybrid | 200 | 10 | 2 | 10 | 10 | 20 | PASS fuerte |
| `hybrid_q06` | tristeza y alegría | hybrid | 200 | 10 | 10 | 10 | 10 | 20 | PASS fuerte |
| `hybrid_q07` | Tierra de Israel fe plegaria milagros | hybrid | 200 | 10 | 10 | 10 | 10 | 20 | PASS fuerte |
| `hybrid_q08` | suspiro de santidad | hybrid | 200 | 10 | 8 | 10 | 10 | 20 | PASS fuerte |
| `fts_q09` | "La plegaria es el arma principal del judío" | phrase | 200 | 0 | 0 | 0 | 0 | 13 | WARN |
| `fts_q10` | El mes de Elul es el momento más propicio para el arrepentimiento | fts | 200 | 2 | 2 | 0 | 0 | 20 | PASS fuerte |

## Vector Branch Summary
- hybrid queries: 8
- hybrid queries with direct vector hits: 8
- hybrid queries with response-visible vector hits: 7

## Gaps
- hybrid_q02: missing_expected_terms:oración,rezar
- hybrid_q03: missing_expected_terms:aislamiento
- fts_q09: empty_results, missing_expected_terms:plegaria,arma principal,judío

## Operational Note
- First run against the already-running backend process scored `145/200` with `0` response-visible vector hits. That process was stale and had not loaded commit `b2b0355`.
- The stale run is preserved as `stale_backend_before_restart_summary.json` and `stale_backend_before_restart_results.json`.
- Final run after loading commit `b2b0355` scored `189/200` with direct vector hits in `8/8` hybrid queries and response-visible vector hits in `7/8`.

## Recommendations
- Documentar el contrato alias en LAT si queda estable.
- Auditar otras rutas vectoriales que filtren Milvus por scope lógico.
- Ejecutar una validación visual de UI/library search.
