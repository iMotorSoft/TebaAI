#!/usr/bin/env python3
"""Ingestion V2 probe — El Jardín de las Almas. Read-only. No modifica datos."""

from __future__ import annotations

import asyncio, json, os, re, sys
from pathlib import Path

import httpx

HOST = os.environ.get("TEBAAI_BACKEND_HOST", "127.0.0.1")
PORT = os.environ.get("TEBAAI_BACKEND_PORT", "7008")
BASE = f"http://{HOST}:{PORT}"
REPORT = Path(__file__).resolve().parent.parent.parent.parent / "data/reports/breslov/2026-07-09-ingestion-v2-jardin-pilot"

async def main():
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: TEBAAI_E2E_ADMIN_EMAIL/PASSWORD required"); return 1

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code != 201: print(f"Auth failed: {r.status_code}"); return 1
        token = r.json()["access_token"]
        print("Auth OK")

        # Search for El Jardín de las Almas
        print("\n=== 1. Finding document ===")
        r = await c.post(f"{BASE}/library/relation-qa", headers={"Authorization": f"Bearer {token}"}, json={
            "question": "El Jardín de las Almas page 1 introduction",
            "concept_a": "Jardín", "concept_b": "Almas",
            "top_k": 50, "use_ai": False, "knowledge_scope_code": "breslov_primary", "evidence_depth": "full",
        }, timeout=60)
        if r.status_code != 200: print(f"Search failed: {r.status_code}"); return 1

        data = r.json()
        sources = data.get("sources", []) or data.get("source_map", [])
        jardin = [s for s in sources if "jardín" in (s.get("document_title") or "").lower()]
        print(f"Total sources: {len(sources)}, From Jardín: {len(jardin)}")
        if not jardin: print("ERROR: No sources from El Jardín de las Almas"); return 1

        doc_title = jardin[0]["document_title"]
        doc_id = jardin[0]["document_id"]
        doc_status = jardin[0]["document_status"]
        print(f"Title: {doc_title}\nID: {doc_id}\nStatus: {doc_status}")

        # Pages
        pages = sorted(set(s.get("page_number") for s in jardin if s.get("page_number")))
        print(f"\nPages in top-50: {len(pages)}, range: {min(pages) if pages else '?'}-{max(pages) if pages else '?'}")

        # Evidence types
        ev_types = {}
        for s in jardin:
            et = s.get("evidence_type", "?")
            ev_types[et] = ev_types.get(et, 0) + 1
        print(f"\nEvidence types: {json.dumps(ev_types, indent=2)}")

        # Block types
        block_types = {}
        for s in jardin:
            bt = s.get("block_type", "?") or "none"
            block_types[bt] = block_types.get(bt, 0) + 1
        print(f"\nBlock types: {json.dumps(block_types, indent=2)}")

        # Sections
        sections = sorted(set(s.get("section", "") or "" for s in jardin if s.get("section")))
        print(f"\nSections: {len(sections)}")
        for sec in sections[:15]: print(f"  - {sec}")

        # Section candidates from markdown headers
        section_candidates = set()
        for s in jardin:
            for h in re.findall(r"\*\*([^*]{3,60})\*\*", s.get("snippet") or ""):
                if not h.startswith("Page") and len(h) > 3: section_candidates.add(h)
        print(f"\nSection candidates: {len(section_candidates)}")
        for c2 in sorted(section_candidates)[:20]: print(f"  - {c2}")

        # Concepts
        concepts = [
            "alma", "tzadik", "Daat", "plegaria", "tefilá", "emuná",
            "simjá", "alegría", "tristeza", "atzvut", "hitbodedut", "tikún",
            "bitul", "Shevirat HaKeilim", "Tajlit", "Canción del Futuro",
            "Hebra de Bondad", "Jut shel Jesed", "Señor del Campo",
            "Otro Lado", "ekev", "voz", "Jardín del Edén",
        ]
        found = {}
        for concept in concepts:
            n = sum(1 for s in jardin if concept.lower() in (s.get("snippet") or "").lower())
            if n: found[concept] = n
        print(f"\nConcepts found: {len(found)}/{len(concepts)}")
        for c2, n in sorted(found.items(), key=lambda x: -x[1]): print(f"  {c2}: {n}")

        # Source references
        patterns = [
            (r"Salmos?\s+\d+", "Salmos"), (r"Zohar", "Zohar"),
            (r"Talmud", "Talmud"), (r"Midrash", "Midrash"),
            (r"Bereshit|Génesis|Genesis", "Torá"),
            (r"Proverbios|Mishlé|Proverbs", "Ketuvim"),
            (r"Likutey Moharán|Likutey Moharan", "Breslov"),
            (r"Avot|Pirkei", "Mishná"),
        ]
        src_counts = {}
        for s in jardin:
            snip = s.get("snippet") or ""
            for pat, name in patterns:
                if re.search(pat, snip, re.IGNORECASE): src_counts[name] = src_counts.get(name, 0) + 1
        print(f"\nSource references: {json.dumps(src_counts, indent=2)}")

        # Save report
        REPORT.mkdir(parents=True, exist_ok=True)
        report = {
            "document_title": doc_title, "document_id": doc_id, "document_status": doc_status,
            "sources_in_top50": len(jardin), "page_count": len(pages),
            "page_range": {"min": min(pages) if pages else None, "max": max(pages) if pages else None},
            "evidence_types": ev_types, "block_types": block_types,
            "sections": list(sections), "section_candidates": list(section_candidates)[:30],
            "concepts": found, "source_references": src_counts,
        }
        (REPORT / "document_inventory.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport saved to {REPORT / 'document_inventory.json'}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
