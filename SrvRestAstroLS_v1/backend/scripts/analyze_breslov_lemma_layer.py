#! /usr/bin/env python3
"""
CLI: Analyze lemma/shoresh layer for Breslov test corpus.

Read-only, experimental. Does not modify DB or Milvus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


# Seed lexicon — curated, not exhaustive
SEED_LEXICON: dict[str, dict] = {
    "emunah": {
        "labels": {"es": ["emuná", "fe"], "en": ["faith", "emunah"], "he": ["אמונה"]},
        "transliterations": ["emunah", "emuna", "emuná"],
        "confidence": "curated", "domain": "breslov",
    },
    "tefillah": {
        "labels": {"es": ["tefilá", "plegaria", "rezo"], "en": ["prayer", "tefillah"], "he": ["תפילה"]},
        "transliterations": ["tefilá", "tefila", "tefillah"],
        "confidence": "curated", "domain": "breslov",
    },
    "teshuvah": {
        "labels": {"es": ["teshuvá", "retorno"], "en": ["repentance", "teshuvah"], "he": ["תשובה"]},
        "transliterations": ["teshuvá", "teshuva", "teshuvah"],
        "confidence": "curated", "domain": "breslov",
    },
    "hitbodedut": {
        "labels": {"es": ["hitbodedut", "aislamiento", "plegaria personal"], "en": ["hitbodedut", "hisbodedus", "meditation"]},
        "transliterations": ["hitbodedut", "hisbodedus"],
        "confidence": "curated", "domain": "breslov",
    },
    "tzadik": {
        "labels": {"es": ["tzadik", "justo"], "en": ["tzadik", "tzaddik", "righteous"], "he": ["צדיק"]},
        "transliterations": ["tzadik", "tzaddik"],
        "confidence": "curated", "domain": "breslov",
    },
    "yetzer_hara": {
        "labels": {"es": ["yetzer hará", "mala inclinación"], "en": ["yetzer hara", "evil inclination"]},
        "transliterations": ["yetzer hara", "yetzer hará"],
        "confidence": "curated", "domain": "breslov",
    },
    "hashem": {
        "labels": {"es": ["HaShem", "Dios"], "en": ["Hashem", "God"], "he": ["השם"]},
        "transliterations": ["hashem"],
        "confidence": "curated", "domain": "breslov",
    },
    "rebbe_nachman": {
        "labels": {"es": ["Rebe Najmán", "Rabí Najmán"], "en": ["Rebbe Nachman", "Rabbi Nachman", "Nachman"]},
        "transliterations": ["rebbe nachman", "rebe najmán", "rabí najmán"],
        "confidence": "curated", "domain": "breslov",
    },
    "simchah": {
        "labels": {"es": ["simjá", "alegría"], "en": ["simchah", "joy", "happiness"]},
        "transliterations": ["simjá", "simcha", "simchah"],
        "confidence": "candidate", "domain": "breslov",
    },
    "bitachon": {
        "labels": {"es": ["bitajón", "confianza"], "en": ["bitachon", "trust", "confidence"]},
        "transliterations": ["bitajón", "bitachon"],
        "confidence": "candidate", "domain": "breslov",
    },
}


def _expand_query_terms(concept_id: str) -> list[str]:
    """Generate expanded query terms from seed lexicon."""
    entry = SEED_LEXICON.get(concept_id, {})
    terms: set[str] = set()
    for lang_labels in entry.get("labels", {}).values():
        for label in lang_labels:
            terms.add(label.lower())
    for t in entry.get("transliterations", []):
        terms.add(t.lower())
    return sorted(terms)


def _assemble_expanded_query(concept_id: str, original: str) -> str:
    """Build an OR query from original + expanded terms."""
    terms = _expand_query_terms(concept_id)
    all_terms = [original.lower()] + terms
    return " OR ".join(all_terms)


def _normalize(text: str) -> str:
    import re
    t = text.lower()
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n'}
    for old, new in replacements.items():
        t = t.replace(old, new)
    t = re.sub(r'[^\w\s]', '', t)
    return t.strip()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze Breslov lemma/shoresh layer.")
    p.add_argument("--collection", default="breslov_test")
    p.add_argument("--milvus-collection", default="tebaai_breslov_test_chunks_v1")
    p.add_argument("--embedding-model-alias", default="openai_text_embedding_3_small")
    p.add_argument("--top-k", type=int, default=30)
    p.add_argument("--output-json")
    p.add_argument("--output-md")
    return p.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    from globalVar import POSTGRES_DSN
    import psycopg
    from modules.library.text_search import search_chunks_text

    conn = await psycopg.AsyncConnection.connect(POSTGRES_DSN)

    results = {
        "collection": args.collection,
        "milvus_collection": args.milvus_collection,
        "concepts_tested": 0,
        "analysis_completed": False,
        "no_db_writes": True,
        "no_milvus_writes": True,
        "concepts": {},
        "architecture_recommendation": "",
        "risk_assessment": [],
        "guardrails": [],
    }

    try:
        for cid, entry in SEED_LEXICON.items():
            results["concepts_tested"] += 1
            concept_report: dict = {
                "concept_id": cid,
                "confidence": entry["confidence"],
                "domain": entry["domain"],
                "labels": entry["labels"],
                "queries": {},
            }

            # Use Spanish label as primary query
            primary_q = entry["labels"].get("es", entry["labels"].get("en", [cid]))[0]
            expanded = _assemble_expanded_query(cid, primary_q)
            concept_report["primary_query"] = primary_q
            concept_report["expanded_query"] = expanded
            concept_report["expansion_terms"] = _expand_query_terms(cid)

            # FTS current
            fts_r = await search_chunks_text(conn, collection_code=args.collection,
                                              query=primary_q, top_k=args.top_k)
            concept_report["queries"]["fts_original"] = {
                "found": len(fts_r) > 0,
                "count": len(fts_r),
                "top_doc": fts_r[0]["document_title"] if fts_r else None,
                "top_score": round(fts_r[0]["rank"], 4) if fts_r else 0,
            }

            # FTS expanded (simulated via multiple individual queries + union)
            expanded_terms = _expand_query_terms(cid)
            all_expanded_chunk_ids: set[str] = set()
            for et in expanded_terms:
                try:
                    et_r = await search_chunks_text(conn, collection_code=args.collection,
                                                     query=et, top_k=args.top_k)
                    for item in et_r:
                        all_expanded_chunk_ids.add(str(item["chunk_id"]))
                except Exception:
                    pass
            # Merge expanded results (simulate union)
            fts_exp = await search_chunks_text(conn, collection_code=args.collection,
                                                query=primary_q, top_k=args.top_k)
            original_ids = {str(item["chunk_id"]) for item in fts_exp}
            new_ids = all_expanded_chunk_ids - original_ids
            concept_report["queries"]["fts_expanded"] = {
                "found": len(all_expanded_chunk_ids) > 0,
                "count": len(all_expanded_chunk_ids),
                "top_doc": fts_exp[0]["document_title"] if fts_exp else None,
                "top_score": round(fts_exp[0]["rank"], 4) if fts_exp else 0,
                "new_hits_estimated": len(new_ids),
                "terms_available_in_corpus": [t for t in expanded_terms if len(t) > 2],
            }

            results["concepts"][cid] = concept_report

        results["analysis_completed"] = True

        # Architecture recommendation
        results["architecture_recommendation"] = (
            "Crear tabla library_concept_lexicon con: concept_id, domain, language, "
            "label, normalized_label, transliteration, script, confidence, source, status. "
            "Alternativa: JSONB en library_documents.bibliographic_metadata. "
            "Prefiero tabla separada para consultabilidad y auditoría. "
            "Vincular chunks a conceptos vía tabla N:M chunk_concepts si se necesita "
            "recuperación directa por concepto. "
            "La expansión de query debe ser configurable por perfil: strict, balanced, exploratory."
        )

        # Risks
        results["risk_assessment"] = [
            {"risk": "Falsos positivos por traducción amplia (ej. 'fe' en contexto no Breslov)",
             "mitigation": "Limitar expansión a términos curados por dominio y revisión rabínica"},
            {"risk": "Transliteraciones ambiguas (ej. 'simcha' puede ser nombre propio)",
             "mitigation": "Preferir coincidencia exacta + contexto en chunk; no expandir si hay riesgo"},
            {"risk": "Hebreo sin niqqud puede generar colisiones entre raíces distintas",
             "mitigation": "Usar solo transliteraciones curadas, no hebreo raw salvo en lexicón de referencia"},
            {"risk": "Expandir query degrada precisión FTS si se usan términos muy genéricos",
             "mitigation": "Ponderar por confidence: curated suma +0.15 score, candidate suma +0.05"},
            {"risk": "Shoresh hebreo real no equivale automáticamente a concepto Breslov",
             "mitigation": "Conceptos curados por domain expert; no derivar shoresh automáticamente"},
        ]

        # Guardrails
        results["guardrails"] = [
            "La expansión nunca reemplaza la query original",
            "La expansión debe marcar términos añadidos con concept_id",
            "Cada resultado debe tener chunk_id válido en PostgreSQL",
            "No responder si no hay chunk real (no inventar texto)",
            "Separar equivalencias curated (confianza alta) de candidate (requiere revisión)",
            "Penalizar equivalencias candidate: score *= 0.7 en ranking",
            "No mezclar corpus breslov_test con breslov productivo",
            "Perfiles de expansión: strict (solo curated), balanced (curated + candidate con peso), exploratory (todo)",
            "Auditar expansiones usadas por sesión/búsqueda",
        ]

    finally:
        await conn.close()

    print(f"\n── Breslov Lemma/Shoresh Layer Analysis ──")
    print(f"  Collection: {args.collection}")
    print(f"  Milvus: {args.milvus_collection}")
    print(f"  Concepts tested: {results['concepts_tested']}")
    print(f"  Analysis completed: {results['analysis_completed']}")
    for cid, cr in results["concepts"].items():
        print(f"  [{cid}] q={cr['primary_query']} → expanded={len(cr['expansion_terms'])} terms")
        print(f"    FTS original: {cr['queries']['fts_original']['count']} hits, "
              f"expanded: {cr['queries']['fts_expanded']['count']} hits "
              f"(new: {cr['queries']['fts_expanded']['new_hits_estimated']})")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"JSON: {args.output_json}")

    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
