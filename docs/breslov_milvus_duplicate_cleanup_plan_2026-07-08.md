# Breslov Milvus Duplicate Cleanup Plan

**Date:** 2026-07-08
**Status:** EJECUTADO Y CERRADO

> Este documento conserva el plan de cleanup. La operación eliminó las 1828 PK redundantes y cerró con 5102 chunks únicos, 0 duplicados y match PG↔Milvus 100%. El resultado canónico está en `docs/breslov_milvus_productive_baseline_restoration_2026-07-08.md`.

## 1. Problem

Repair re-run created 1828 duplicate entities in `tebaai_breslov_chunks_v1`.

| Document | Unique chunks | Entities | Duplicates |
|---|---|---|---|
| Likutey Halajot LM II 8 | 1205 | 2244 | 1039 |
| La Potencia de la Plegaria | 646 | 1289 | 643 |
| El Jardín de las Almas | 147 | 293 | 146 |
| **Total** | **1998** | **3826** | **1828** |

Non-affected docs (5 docs): 3104 entities, 0 duplicates.

## 2. Strategy

For each of the 1828 duplicated chunk_ids:
- Milvus has 2 PKs (A and B)
- PG `milvus_primary_key` matches exactly one of them (B from run 2 backfill)
- **Keep** the PK matching PG (B)
- **Delete** the PK not matching PG (A — from run 1 without backfill)

## 3. Dry-run

Script: `scripts/cleanup_milvus_duplicates.py` with `--dry-run` (default).

Dry-run delivers:
- List of 1828 PKs to delete
- List of 1828 PKs to keep
- Per-document breakdown
- Backup JSON of PKs to delete
- Validation that PG references are correct

## 4. Delete operation

`--apply` mode:
- `collection.delete(expr=f'pk in [{pks}])'` in batches of 100
- Only for the 3 affected documents
- Verification: num_entities drops from 6930 → 5102
- Verification: duplicates = 0, unique chunks = 5102

## 5. Rollback

Backup of deleted PKs available. Re-insert via:
```python
col.insert(backup_entities)
```

## 6. Validation post-cleanup

| Check | Expected | Command |
|---|---|---|
| Milvus num_entities | 5102 | `c.num_entities` |
| Unique chunks | 5102 | query + dedup |
| Duplicates | 0 | query + group |
| PG↔Milvus match | 100% | compare per doc |
| source_type='' | 0 | query expr |
| Golden queries | 15/15 PASS | script |

## 7. Script

`scripts/cleanup_milvus_duplicates.py`:
- `--dry-run` (default): identify + backup, no delete
- `--apply`: execute delete PK by PK
- Requires interactive confirmation
