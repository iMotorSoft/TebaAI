#!/usr/bin/env python3
"""
Repair Milvus Productive Embeddings — restore 1828 missing vectors for
3 documents whose Milvus entities were deleted by cleanup FASE D (2026-07-05).

Documents:
  - Likutey Halajot LM II 8  (56ddcc3b) — 1039 missing
  - La Potencia de la Plegaria  (43ba4f4b) — 643 missing
  - El Jardín de las Almas  (76f2adbc) — 146 missing

Usage:
  # Dry-run (default): lists chunk_ids, validates sha256, estimates cost
  uv run python -m scripts.repair_milvus_productive_embeddings --dry-run

  # Generate backups before anything
  uv run python -m scripts.repair_milvus_productive_embeddings --backup

  # Full repair (requires explicit --apply)
  uv run python -m scripts.repair_milvus_productive_embeddings --apply

  # Repair single document
  uv run python -m scripts.repair_milvus_productive_embeddings --document-id 56ddcc3b

Environment:
  LITELLM_MASTER_KEY required for embeddings.
  No OpenAI key directa.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

SCOPE_CODE = "breslov_primary"
MILVUS_PROD_COLL = "tebaai_breslov_chunks_v1"

AFFECTED_DOCS: dict[str, str] = {
    "56ddcc3b-8296-4832-ac95-2bfe032cd4c6": "Likutey Halajot LM II 8",
    "43ba4f4b-d3ee-49b6-8d09-dfa152379893": "La Potencia de la Plegaria",
    "76f2adbc-b79a-4432-9ea5-521a337a5502": "El Jardín de las Almas",
}

BATCH_SIZE = 16
EMBEDDING_MODEL = "openai_text_embedding_3_small"
EMBEDDING_DIM = 1536


@dataclass
class MissingChunk:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    page_start: int | None
    page_end: int | None
    language: str | None
    content: str
    content_sha256: str
    old_milvus_pk: str | None
    content_length: int
    citable: bool = True


# ── PG helpers ─────────────────────────────────────────────────────────────

async def _get_pool():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool
    pool = create_pool_from_settings()
    await open_pool(pool)
    return pool


async def _close_pool(pool):
    from infrastructure.postgres.pool import close_pool
    await close_pool(pool)


async def fetch_missing_chunks(pool, doc_ids: list[str] | None = None) -> list[MissingChunk]:
    """Fetch the 1828 chunks that exist in PG but not in Milvus prod."""
    from pymilvus import Collection, connections

    # Get Milvus PKs currently in prod for affected docs
    connections.connect(host="127.0.0.1", port=19530)
    c = Collection(MILVUS_PROD_COLL)
    c.load()

    # Query by chunk_id to detect existing entities (more reliable than PK)
    prod_chunk_ids: set[str] = set()
    for did in AFFECTED_DOCS:
        if doc_ids and did not in doc_ids:
            continue
        results = c.query(
            expr=f'document_id like "{did[:12]}%"',
            output_fields=["chunk_id"],
            limit=10000,
        )
        for r in results:
            cid = r.get("chunk_id", "")
            if cid:
                prod_chunk_ids.add(cid)

    c.release()
    connections.disconnect("default")

    missing: list[MissingChunk] = []
    targets = list(AFFECTED_DOCS.keys())
    if doc_ids:
        targets = [d for d in targets if d in doc_ids]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for did in targets:
                await cur.execute(
                    """
                    SELECT c.id::text, c.chunk_index, c.page_start, c.page_end,
                           c.language, c.content, c.content_sha256, c.content_length,
                           c.citable,
                           e.milvus_primary_key,
                           d.title AS document_title
                    FROM library_chunk_embeddings e
                    JOIN library_document_chunks c ON c.id = e.chunk_id
                    JOIN library_documents d ON d.id = c.document_id
                    WHERE c.document_id = %s
                      AND e.status IS DISTINCT FROM 'stale'
                      AND e.milvus_primary_key IS NOT NULL
                    ORDER BY c.chunk_index
                    """,
                    (did,),
                )
                rows = await cur.fetchall()
                for row in rows:
                    cid = row["id"]
                    if cid in prod_chunk_ids:
                        continue
                    missing.append(MissingChunk(
                        chunk_id=row["id"],
                        document_id=did,
                        document_title=row["document_title"],
                        chunk_index=row["chunk_index"],
                        page_start=row["page_start"],
                        page_end=row["page_end"],
                        language=row["language"],
                        content=row["content"],
                        content_sha256=row["content_sha256"],
                        old_milvus_pk=mpk,
                        content_length=row["content_length"],
                        citable=row.get("citable", True),
                    ))
    return missing


async def update_milvus_pk(pool, chunk_id: str, new_pk: str) -> bool:
    """Update milvus_primary_key in PG after successful Milvus upsert."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE library_chunk_embeddings SET milvus_primary_key = %s "
                "WHERE chunk_id = %s",
                (new_pk, chunk_id),
            )
            return cur.rowcount > 0


# ── Backup ─────────────────────────────────────────────────────────────────

async def backup_pg_chunks(pool, missing: list[MissingChunk], path: str) -> None:
    """Backup the 1828 PG chunk records to JSON."""
    records = []
    for m in missing:
        records.append({
            "document_id": m.document_id,
            "chunk_id": m.chunk_id,
            "chunk_index": m.chunk_index,
            "old_milvus_primary_key": m.old_milvus_pk,
            "content_sha256": m.content_sha256,
            "content_length": m.content_length,
            "citable": m.citable,
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"  ✅ PG backup: {len(records)} chunks → {path}")


async def backup_milvus_snapshot(path: str) -> dict[str, Any]:
    """Snapshot current Milvus prod entity counts."""
    from pymilvus import Collection, connections, utility

    connections.connect(host="127.0.0.1", port=19530)
    result: dict[str, Any] = {
        "collection": MILVUS_PROD_COLL,
        "num_entities": 0,
        "by_document": {},
        "timestamp": time.time(),
    }

    c = Collection(MILVUS_PROD_COLL)
    c.load()
    result["num_entities"] = c.num_entities

    all_doc_ids = list(AFFECTED_DOCS.keys())
    all_doc_ids.extend([
        "0bad063c-f7a8-429c-a0ac-c01af224d5cb",
        "987bd9d3-bee7-46af-b03e-1ad5f5a97895",
        "27f175ea-bc8b-40d1-9fb7-7531949831eb",
        "c7c10741-c324-4068-8b2a-201c67ae0b33",
        "a852721d-ae41-42a7-a227-8141e5da36f5",
    ])

    for did in all_doc_ids:
        results = c.query(
            expr=f'document_id like "{did[:12]}%"',
            output_fields=["pk"],
            limit=10000,
        )
        result["by_document"][did[:12]] = len(results)

    # Also check stale entities (empty source_type)
    stale = c.query(expr='source_type == ""', output_fields=["pk"], limit=10000)
    result["stale_entities_empty_source_type"] = len(stale)

    c.release()
    connections.disconnect("default")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"  ✅ Milvus snapshot: {result['num_entities']} entities → {path}")

    return result


# ── Embed + Upsert ─────────────────────────────────────────────────────────

def embed_and_upsert(
    missing: list[MissingChunk],
    dry_run: bool = False,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """Generate embeddings via LiteLLM and upsert to Milvus prod."""
    from modules.embeddings.client import embed_batch
    from pymilvus import Collection, connections

    total = len(missing)
    batches = (total + batch_size - 1) // batch_size
    result: dict[str, Any] = {
        "total_chunks": total,
        "total_batches": batches,
        "batch_size": batch_size,
        "successful": 0,
        "failed": 0,
        "chunks_upserted": [],      # list of chunk_ids
        "pk_map": {},               # chunk_id → new pk
        "errors": [],
    }

    if dry_run:
        print(f"  🏃 Dry-run mode: {total} chunks, {batches} batches of {batch_size}")
        if total > 0:
            sample = missing[0]
            result["sample_payload"] = _build_milvus_entity(sample, [0.0] * EMBEDDING_DIM)
            result["sample_payload"]["embedding"] = f"<{EMBEDDING_DIM} floats>"  # placeholder
            result["chunks_upserted"] = [m.chunk_id for m in missing]
        return result

    connections.connect(host="127.0.0.1", port=19530)
    col = Collection(MILVUS_PROD_COLL)
    col.load()

    for i in range(0, total, batch_size):
        batch = missing[i : i + batch_size]
        texts = [m.content for m in batch]
        batch_label = f"batch {i//batch_size + 1}/{batches} (chunks {i+1}-{i+len(batch)})"

        print(f"  [{batch_label}] Embedding {len(batch)} chunks...")
        try:
            vectors = embed_batch(texts, model=EMBEDDING_MODEL)
        except Exception as exc:
            err = f"Embedding failed for {batch_label}: {exc}"
            print(f"    ❌ {err}")
            result["errors"].append(err)
            result["failed"] += len(batch)
            continue

        if not vectors or len(vectors) != len(batch):
            err = f"Vector mismatch for {batch_label}: got {len(vectors)} vectors for {len(batch)} texts"
            print(f"    ❌ {err}")
            result["errors"].append(err)
            result["failed"] += len(batch)
            continue

        entities = []
        for j, m in enumerate(batch):
            entity = _build_milvus_entity(m, vectors[j])
            result["pk_map"][m.chunk_id] = entity["pk"]
            entities.append(entity)

        print(f"    Upserting {len(entities)} entities to Milvus...")
        try:
            col.upsert(entities)
            for m in batch:
                result["successful"] += 1
                result["chunks_upserted"].append(m.chunk_id)
            print(f"    ✅ Done")
        except Exception as exc:
            err = f"Upsert failed for {batch_label}: {exc}"
            print(f"    ❌ {err}")
            result["errors"].append(err)
            result["failed"] += len(batch)

    col.flush()
    connections.disconnect("default")
    return result


def _truncate_utf8(text: str | None, max_bytes: int = 1024) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[: max_bytes - 3]
    # Decode safely, dropping any partial multi-byte character at the boundary
    result = truncated.decode("utf-8", errors="ignore")
    return result + "..."


def _build_milvus_entity(m: MissingChunk, vector: list[float]) -> dict[str, Any]:
    new_pk = str(uuid.uuid4())
    return {
        "pk": new_pk,
        "chunk_id": m.chunk_id,
        "document_id": m.document_id,
        "collection_code": "breslov",
        "language": m.language or "es",
        "title": m.document_title[:512] if m.document_title else "",
        "source_type": "book",
        "source_sha256": "",
        "content_sha256": m.content_sha256 or "",
        "chunk_index": m.chunk_index,
        "page_start": m.page_start or 0,
        "page_end": m.page_end or 0,
        "content_preview": _truncate_utf8(m.content),
        "embedding": vector,
    }


# ── Validation ─────────────────────────────────────────────────────────────

def validate_sha256(missing: list[MissingChunk]) -> dict[str, Any]:
    """Validate content_sha256 for all chunks."""
    import hashlib

    result = {"total": len(missing), "valid": 0, "invalid": 0, "errors": []}
    for m in missing:
        if m.content_sha256:
            computed = hashlib.sha256(m.content.encode("utf-8")).hexdigest()
            if computed == m.content_sha256:
                result["valid"] += 1
            else:
                result["invalid"] += 1
                result["errors"].append(f"sha256 mismatch: {m.chunk_id[:12]}")
        else:
            result["invalid"] += 1
            result["errors"].append(f"missing sha256: {m.chunk_id[:12]}")
    return result


# ── Post-repair validation ─────────────────────────────────────────────────

async def validate_post_repair(pool) -> dict[str, Any]:
    """Validate PG↔Milvus match after repair."""
    from pymilvus import Collection, connections

    result: dict[str, Any] = {}

    # PG counts
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            total_pg = 0
            pg_by_doc = {}
            for did, dtitle in AFFECTED_DOCS.items():
                await cur.execute(
                    "SELECT count(*) FROM library_chunk_embeddings e "
                    "JOIN library_document_chunks c ON c.id = e.chunk_id "
                    "WHERE c.document_id = %s AND e.status IS DISTINCT FROM 'stale'",
                    (did,),
                )
                cnt = (await cur.fetchone())["count"]
                pg_by_doc[did[:12]] = {"title": dtitle, "embeddings": cnt}
                total_pg += cnt
            result["pg_total_active"] = total_pg
            result["pg_by_document"] = pg_by_doc

            # Pending check
            await cur.execute("SELECT count(*) FROM library_chunk_embeddings WHERE status='pending'")
            result["pg_pending"] = (await cur.fetchone())["count"]

    # Milvus counts
    connections.connect(host="127.0.0.1", port=19530)
    c = Collection(MILVUS_PROD_COLL)
    c.load()
    result["milvus_num_entities"] = c.num_entities

    mv_by_doc = {}
    for did in AFFECTED_DOCS:
        results = c.query(
            expr=f'document_id like "{did[:12]}%"',
            output_fields=["pk", "source_type"],
            limit=10000,
        )
        mv_by_doc[did[:12]] = {
            "entities": len(results),
            "source_types": list(set(r.get("source_type", "") for r in results)),
        }
    result["milvus_by_document"] = mv_by_doc

    # Stale check
    stale = c.query(expr='source_type == ""', output_fields=["pk"], limit=10000)
    result["milvus_stale_empty_source_type"] = len(stale)

    c.release()
    connections.disconnect("default")

    # Match check
    result["match"] = True
    for did in AFFECTED_DOCS:
        pg_cnt = result["pg_by_document"].get(did[:12], {}).get("embeddings", 0)
        mv_cnt = result["milvus_by_document"].get(did[:12], {}).get("entities", 0)
        if pg_cnt != mv_cnt:
            result["match"] = False
            result["_mismatch_detail"] = result.get("_mismatch_detail", {})
            result["_mismatch_detail"][did[:12]] = {"pg": pg_cnt, "milvus": mv_cnt}

    return result


# ── Print helpers ──────────────────────────────────────────────────────────

def print_dry_run_report(
    missing: list[MissingChunk],
    sha_result: dict[str, Any],
    backup_info: dict[str, Any] | None = None,
) -> None:
    from collections import Counter

    print(f"\n{'='*70}")
    print("  DRY-RUN REPORT — Milvus Productive Embedding Repair")
    print(f"{'='*70}")

    doc_counts = Counter(m.document_id for m in missing)
    total_chars = sum(m.content_length for m in missing)
    batches = (len(missing) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n📊 Resumen:")
    print(f"  Total chunks faltantes: {len(missing)}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Batches estimados (size={BATCH_SIZE}): {batches}")
    print(f"  Documentos afectados: {len(doc_counts)}")

    for did, dtitle in AFFECTED_DOCS.items():
        cnt = doc_counts.get(did, 0)
        expected = {
            "56ddcc3b-8296-4832-ac95-2bfe032cd4c6": 1039,
            "43ba4f4b-d3ee-49b6-8d09-dfa152379893": 643,
            "76f2adbc-b79a-4432-9ea5-521a337a5502": 146,
        }
        expected_cnt = expected.get(did, 0)
        status = "✅" if cnt == expected_cnt else "⚠️"
        print(f"  {status} {dtitle[:50]:50s} {cnt:5d} chunks (esperado: {expected_cnt})")

    print(f"\n🔐 SHA-256 Validation:")
    print(f"  Válidos: {sha_result['valid']}")
    print(f"  Inválidos: {sha_result['invalid']}")
    if sha_result["errors"]:
        print(f"  Errores (primeros 5):")
        for e in sha_result["errors"][:5]:
            print(f"    • {e}")

    if missing:
        sample = missing[0]
        print(f"\n📋 Payload sample (sin vector):")
        payload = _build_milvus_entity(sample, [0.0] * EMBEDDING_DIM)
        payload["embedding"] = f"<{EMBEDDING_DIM} floats>"
        print(f"  {json.dumps(payload, indent=2, ensure_ascii=False)[:600]}...")

        total_chars_sample = sum(m.content_length for m in missing)
        print(f"\n💰 Costo estimado:")
        print(f"  Chars totales: {total_chars_sample:,}")
        print(f"  Embeddings: {len(missing)}")
        print(f"  Costo aprox (OpenAI text-embedding-3-small): < $1.00 USD")

    print(f"\n🛡️ Rollback plan:")
    print(f"  1. PG milvus_primary_key solo se actualiza tras upsert exitoso")
    print(f"  2. Backup pre-repair disponible en data/reports/breslov/2026-07-08-milvus-relation-qa/backups/*.json")
    print(f"  3. Si upsert falla parcial: re-ejecutar con --apply (idempotente)")
    print(f"  4. Si hay corrupción: restaurar desde backup + re-ejecutar")

    print(f"\n{'='*70}")
    print("  END DRY-RUN — 0 writes ejecutados")
    print(f"{'='*70}\n")


def print_repair_summary(embed_result: dict[str, Any]) -> None:
    print(f"\n{'='*70}")
    print("  REPAIR SUMMARY")
    print(f"{'='*70}")
    print(f"  Total chunks: {embed_result['total_chunks']}")
    print(f"  Successful: {embed_result['successful']}")
    print(f"  Failed: {embed_result['failed']}")
    if embed_result["errors"]:
        print(f"  Errors:")
        for e in embed_result["errors"][:5]:
            print(f"    ❌ {e}")
    print(f"{'='*70}\n")


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Repair Milvus Productive Embeddings — restore 1828 missing vectors"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Dry-run: list chunks, validate, no writes (default)")
    mode.add_argument("--apply", action="store_true",
                      help="Apply: embed + upsert to Milvus prod")
    mode.add_argument("--backup", action="store_true",
                      help="Backup: generate PG backup + Milvus snapshot, no repair")
    parser.add_argument("--document-id", type=str, default=None,
                        help="Restore single document (prefix)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"Embedding batch size (default: {BATCH_SIZE})")
    parser.add_argument("--skip-sha-validation", action="store_true",
                        help="Skip SHA-256 validation (not recommended)")
    args = parser.parse_args()

    # ── Resolve mode ──────────────────────────────────────────────────
    is_dry_run = args.dry_run and not args.apply and not args.backup
    is_apply = args.apply
    is_backup = args.backup

    doc_ids = None
    if args.document_id:
        matched = [d for d in AFFECTED_DOCS if d.startswith(args.document_id)]
        if not matched:
            print(f"ERROR: document_id '{args.document_id}' no coincide con ningún documento afectado.")
            print(f"  Afectados: {list(AFFECTED_DOCS.keys())}")
            return 1
        doc_ids = matched

    # ── Banner ────────────────────────────────────────────────────────
    mode_label = "DRY-RUN" if is_dry_run else "BACKUP" if is_backup else "APPLY"
    print(f"\n{'='*70}")
    print(f"  BRESLOV MILVUS PRODUCTIVE EMBEDDING REPAIR — {mode_label}")
    print(f"{'='*70}")
    if doc_ids:
        print(f"  Documentos: {[AFFECTED_DOCS[d] for d in doc_ids]}")
    else:
        print(f"  Documentos: {list(AFFECTED_DOCS.values())}")
    print(f"  Modo: {'read-only' if not is_apply else 'ESCRITURA Milvus'}")
    print()

    # ── Connect PG ────────────────────────────────────────────────────
    pool = await _get_pool()

    try:
        # ── Fetch missing chunks ──────────────────────────────────────
        print("[1/4] Detectando chunks faltantes (PG vs Milvus)...")
        missing = await fetch_missing_chunks(pool, doc_ids=doc_ids)
        print(f"  → {len(missing)} chunks faltantes encontrados")

        if not missing:
            print("  ✅ No hay chunks faltantes. Milvus productivo está al día.")
            return 0

        # ── SHA-256 validation ────────────────────────────────────────
        print("[2/4] Validando SHA-256...")
        sha_result = validate_sha256(missing)
        print(f"  → {sha_result['valid']} válidos, {sha_result['invalid']} inválidos")

        if sha_result["invalid"] > 0 and not args.skip_sha_validation:
            print("  ❌ SHA-256 validation failed. Use --skip-sha-validation to override.")
            return 1

        # ── Backup mode ───────────────────────────────────────────────
        if is_backup:
            print("[3/4] Generando backups...")
            await backup_pg_chunks(pool, missing, "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_pg_chunks.json")
            await backup_milvus_snapshot("data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_milvus_snapshot_before_repair.json")

            print(f"\n  ✅ Backups generados. No se ejecutaron writes.")
            return 0

        # ── Dry-run mode ──────────────────────────────────────────────
        if is_dry_run:
            print("[3/4] Generando backup pre-dry-run...")
            await backup_pg_chunks(pool, missing, "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_pg_chunks.json")
            await backup_milvus_snapshot("data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_milvus_snapshot_before_repair.json")

            print("[4/4] Construyendo reporte dry-run...")
            backup_info = {"pg_backup": "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_pg_chunks.json",
                           "milvus_snapshot": "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_milvus_snapshot_before_repair.json"}
            print_dry_run_report(missing, sha_result, backup_info)
            return 0

        # ── Apply mode ────────────────────────────────────────────────
        if is_apply:
            print("  ⚠️  MODO APPLY — se escribirán datos en Milvus productivo.")
            print(f"  Documentos: {list(AFFECTED_DOCS.values())}")
            print(f"  Total chunks: {len(missing)}")

            # Confirm
            confirm = input("\n  ¿Confirmar upsert a Milvus productivo? (yes/N): ").strip().lower()
            if confirm != "yes":
                print("  ❌ Cancelado por el usuario.")
                return 1

            print("[3/4] Generando backups pre-repair...")
            await backup_pg_chunks(pool, missing, "data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_pg_chunks.json")
            await backup_milvus_snapshot("data/reports/breslov/2026-07-08-milvus-relation-qa/backups/repair_milvus_snapshot_before_repair.json")

            print("[4/4] Embed + Upsert...")
            embed_result = embed_and_upsert(missing, dry_run=False, batch_size=args.batch_size)
            print_repair_summary(embed_result)

            # Backfill PG milvus_primary_key
            if embed_result["successful"] > 0:
                print(f"  Actualizando PG milvus_primary_key...")
                updated = 0
                for chunk_id in embed_result["chunks_upserted"]:
                    new_pk = embed_result.get("pk_map", {}).get(chunk_id)
                    if new_pk:
                        ok = await update_milvus_pk(pool, chunk_id, new_pk)
                        if ok:
                            updated += 1
                print(f"  ✅ {updated} registros actualizados en PG")

            # Validate
            print(f"\n  Validando post-repair...")
            validation = await validate_post_repair(pool)
            print(f"  PG total activo: {validation.get('pg_total_active', '?')}")
            print(f"  Milvus num_entities: {validation.get('milvus_num_entities', '?')}")
            print(f"  Match PG↔Milvus: {'✅' if validation.get('match') else '❌'}")
            if not validation.get("match"):
                for did, detail in validation.get("_mismatch_detail", {}).items():
                    print(f"    {did}: PG={detail['pg']}, Milvus={detail['milvus']}")

            if embed_result["failed"] > 0 or not validation.get("match"):
                print(f"\n  ⚠️  Repair completado con errores. Revisar el reporte.")
                return 1
            else:
                print(f"\n  ✅ Repair completado exitosamente.")
                return 0

    finally:
        await _close_pool(pool)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
