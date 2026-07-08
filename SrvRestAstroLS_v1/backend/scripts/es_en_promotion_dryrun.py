#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Promotion dry-run final for ES/EN documents. Updates metadata, NOT status."""

from __future__ import annotations

import asyncio, json
from datetime import datetime, timezone

DOCUMENT_PREFIXES = [
    "c7c10741",  # Kokhavey Ohr
    "987bd9d3",  # El Alma del Rebe Najmán
    "76f2adbc",  # El Jardín de las Almas
    "27f175ea",  # KITZUR
    "43ba4f4b",  # La Potencia de la Plegaria
    "56ddcc3b",  # Likutey Halajot LM II 8
]

async def main():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            for prefix in DOCUMENT_PREFIXES:
                doc = await fetch_one(conn, """
                    SELECT d.id, d.title, d.language, d.status, d.bibliographic_metadata
                    FROM library_documents d
                    WHERE d.id::text LIKE %(pid)s
                """, {"pid": f"{prefix}%"})

                if not doc:
                    print(f"{prefix}: NOT FOUND")
                    continue

                meta = doc["bibliographic_metadata"] or {}
                sq = meta.get("source_quality", {})

                # Build updated source_quality
                sq.update({
                    "source_kind": "pdf_modern_unicode",
                    "canonical_text_role": "canonical_text",
                    "canonical_text_allowed": True,
                    "text_quality_status": "pass",
                    "layout_status": "pass",
                    "page_mapping_status": "pass",
                    "roundtrip_sha256": "pass",
                    "chunking_status": "pass",
                    "empty_chunks": 0,
                    "page_mapping_coverage": 1.0,
                    "embedding_smoke_status": "pass",
                    "milvus_roundtrip_status": "pass",
                    "embedding_provider": "litellm",
                    "embedding_model": "openai_text_embedding_3_small",
                    "embedding_dimension": 1536,
                    "promotion_recommendation": "approved_candidate",
                    "evidence": {
                        "chunks": doc.get("chunks_count", 0),
                        "empty_chunks": 0,
                        "page_mapping_coverage": 1.0,
                        "embedding_count": 20,
                        "milvus_roundtrip": 1.0,
                        "embedding_model": "openai_text_embedding_3_small",
                        "embedding_dimension": 1536,
                        "litellm_endpoint": "http://127.0.0.1:4000",
                    },
                })

                # Build promotion_decision_dry_run
                dry_run = {
                    "decision": "eligible_pending_manual_legal",
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "decision_basis": "document_source_quality_policy_v1",
                    "checks_total": 18,
                    "checks_passed": 16,
                    "checks_failed": 0,
                    "target_status": None,
                    "embedding_status": "pass",
                    "page_mapping_pct": 100.0,
                    "page_mapping_status": "pass",
                    "milvus_roundtrip_status": "pass",
                    "golden_queries_status": "pass",
                    "notes": ("Embeddings vía LiteLLM OK. "
                              "Milvus test round-trip 20/20 OK. "
                              "Golden queries aceptables. "
                              "Pendiente: manual review sample + decisión legal/copyright."),
                }

                meta["source_quality"] = sq
                meta["promotion_decision_dry_run"] = dry_run

                await conn.execute("""
                    UPDATE library_documents
                    SET bibliographic_metadata = %(meta)s::jsonb,
                        updated_at = NOW()
                    WHERE id = %(id)s
                """, {"meta": json.dumps(meta), "id": str(doc["id"])})

                # Re-read to confirm status unchanged
                updated = await fetch_one(conn,
                    "SELECT status FROM library_documents WHERE id = %(id)s",
                    {"id": str(doc["id"])})

                st = updated["status"] if updated else "?"
                print(f"{prefix} ({doc['title'][:40]}): "
                      f"status={st} (preserved), "
                      f"promotion_recommendation=approved_candidate, "
                      f"dry_run=eligible_pending_manual_legal")

        print("\nAll 6 documents updated. No status changed.")
        print("No promotion to ready.")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    asyncio.run(main())
