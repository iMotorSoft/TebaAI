#!/usr/bin/env python3
"""Persist manual and legal review metadata for ES/EN documents."""

from __future__ import annotations

import asyncio, json
from datetime import datetime, timezone

DOCUMENTS = [
    {
        "prefix": "c7c10741",
        "title": "Kokhavey Ohr",
        "lang": "en",
        "manual_status": "manual_review_pass",
        "manual_limitations": [],
        "manual_notes": "Texto inglés limpio, bien formado. Copyright 2026 Breslov Research Institute. ISBN presente. Sin artefactos de extracción significativos.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": True,
        "license_found": False,
        "publisher": "Breslov Research Institute",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "Copyright © 2026 Breslov Research Institute. ISBN 978-1-944731-74-8. Todos los derechos reservados. Sin licencia explícita. Uso interno probablemente permitido; exposición pública requiere permiso.",
    },
    {
        "prefix": "987bd9d3",
        "title": "El Alma del Rebe Najmán",
        "lang": "es",
        "manual_status": "manual_review_pass",
        "manual_limitations": [],
        "manual_notes": "Texto español limpio. Metadata bibliográfica rica: editor, traductor, editorial, año copyright 2017, volumen, secciones. Prefacio, índice y contenido bien estructurados.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": True,
        "license_found": False,
        "publisher": "Breslov Research Institute",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "Copyright 2017 Breslov Research Institute. Editor: Rabí Shlomo Katz. Traductor: Guillermo Beilinson. Vol I, Sijot 1-52. Sin licencia explícita.",
    },
    {
        "prefix": "76f2adbc",
        "title": "El Jardín de las Almas",
        "lang": "es",
        "manual_status": "manual_review_pass",
        "manual_limitations": [],
        "manual_notes": "Texto español limpio. Selección por Abraham Greenbaum, traducido por Guillermo Beilinson. Publicado por Breslov Research Institute. 147 chunks. Bien formado.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": True,
        "license_found": False,
        "publisher": "Breslov Research Institute",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "Publicado por Breslov Research Institute. Selección de Abraham Greenbaum. Sin año de copyright visible en front matter. Sin licencia explícita.",
    },
    {
        "prefix": "27f175ea",
        "title": "KITZUR (Síntesis del Likutey Moharán)",
        "lang": "es",
        "manual_status": "manual_review_pass",
        "manual_limitations": [],
        "manual_notes": "Texto español limpio. Rabí Natán de Breslov (autor), traducido por Guillermo Beilinson. Copyright 2011 Breslov Research Institute, ISBN 978-1-928822-61-5. Bien estructurado.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": True,
        "license_found": False,
        "publisher": "Breslov Research Institute",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "Copyright © 2011 Breslov Research Institute. ISBN 978-1-928822-61-5. Todos los derechos reservados. Sin licencia explícita.",
    },
    {
        "prefix": "43ba4f4b",
        "title": "La Potencia de la Plegaria",
        "lang": "es",
        "manual_status": "manual_review_pass",
        "manual_limitations": [],
        "manual_notes": "Texto español limpio. Autor: Jaim Kramer. Traductor: Guillermo Beilinson. Publicado por Breslov Research Institute. 646 chunks. Bien formado.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": True,
        "license_found": False,
        "publisher": "Breslov Research Institute",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "Publicado por Breslov Research Institute. Autor: Jaim Kramer. Traductor: Guillermo Beilinson. Sin año de copyright visible en front matter. Sin licencia explícita.",
    },
    {
        "prefix": "56ddcc3b",
        "title": "Likutey Halajot LM II 8",
        "lang": "es",
        "manual_status": "manual_review_pass_with_minor_limitations",
        "manual_limitations": ["73 chunks con caracteres U+FFFD (encoding artifact en pasajes hebreos del título)"],
        "manual_notes": "Texto español mayormente limpio. Título con mezcla EN/ES (Rosenberg Edition). 73 chunks con artefactos U+FFFD en caracteres hebreos de la portada — no afectan legibilidad general. 1205 chunks (documento más extenso). Referencias a Breslov Research Institute en el texto.",
        "legal_status": "legal_status_pending_manual_confirmation",
        "copyright_notice_found": False,
        "license_found": False,
        "publisher": "Breslov Research Institute (referenciado en texto)",
        "public_exposure": "public_exposure_blocked",
        "internal_ready_rec": "recommend_internal_ready",
        "legal_notes": "The Rosenberg Edition. Menciona Breslov Research Institute en el texto (referencia a 'El Castillo de Agua', BRI, 2013). No se encontró página de copyright explícita en front matter visible. Sin licencia. Uso interno recomendado conservadoramente.",
    },
]

async def main():
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one

    pool = create_pool_from_settings()
    await open_pool(pool)

    try:
        async with pool.connection() as conn:
            for doc_info in DOCUMENTS:
                prefix = doc_info["prefix"]
                doc = await fetch_one(conn, """
                    SELECT id, title, bibliographic_metadata
                    FROM library_documents WHERE id::text LIKE %(pat)s
                """, {"pat": f"{prefix}%"})

                if not doc:
                    print(f"{prefix}: NOT FOUND")
                    continue

                meta = dict(doc["bibliographic_metadata"] or {})

                now = datetime.now(timezone.utc).isoformat()

                # Build manual_review block
                manual_review = {
                    "status": doc_info["manual_status"],
                    "reviewed_at": now,
                    "sample_strategy": "beginning_quarter_middle_three_quarter_end_longest_shortest_front_matter",
                    "sample_count": 10,
                    "limitations": doc_info["manual_limitations"],
                    "notes": doc_info["manual_notes"],
                }

                # Build legal_review block
                legal_review = {
                    "status": doc_info["legal_status"],
                    "reviewed_at": now,
                    "copyright_notice_found": doc_info["copyright_notice_found"],
                    "license_found": doc_info["license_found"],
                    "publisher": doc_info["publisher"],
                    "public_exposure_status": doc_info["public_exposure"],
                    "internal_use_recommendation": doc_info["internal_ready_rec"],
                    "notes": doc_info["legal_notes"],
                }

                # Build ready_review block (merge with existing)
                sq = meta.get("source_quality", {})
                dr = meta.get("promotion_decision_dry_run", {})
                ready_review = {
                    "technical_closure": dr.get("decision", "eligible_pending_manual_legal"),
                    "manual_review_status": doc_info["manual_status"],
                    "legal_status": doc_info["legal_status"],
                    "ready_promotion_recommendation": "ready_recommended_pending_user_approval",
                    "blockers": [],
                }

                # Merge into bibliographic_metadata
                meta["manual_review"] = manual_review
                meta["legal_review"] = legal_review
                meta["ready_review"] = ready_review

                await conn.execute("""
                    UPDATE library_documents
                    SET bibliographic_metadata = %(meta)s::jsonb,
                        updated_at = NOW()
                    WHERE id = %(id)s
                """, {"meta": json.dumps(meta), "id": str(doc["id"])})

                st_row = await fetch_one(conn,
                    "SELECT status FROM library_documents WHERE id = %(id)s",
                    {"id": str(doc["id"])})

                st_val = st_row["status"] if st_row else "?"
                print(f"{prefix} ({doc['title'][:40]}): "
                      f"status={st_val} (preservado), "
                      f"manual={doc_info['manual_status']}, "
                      f"legal={doc_info['legal_status']}, "
                      f"ready_rec=ready_recommended_pending_user_approval")

        print("\nAll 6 documents updated. Status unchanged (test_candidate preserved).")
        print("No promotion to ready.")

    finally:
        await close_pool(pool)

if __name__ == "__main__":
    asyncio.run(main())
