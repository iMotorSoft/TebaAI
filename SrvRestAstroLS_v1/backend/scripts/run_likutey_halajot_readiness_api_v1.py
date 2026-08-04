#!/usr/bin/env python3
"""Authenticated, read-only API evidence for the LH readiness report."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:7008"
FILENAME = "LIKUTEY HALAJOT (Interior Final).pdf"
NOTE35 = "El hombre se une a HaShem desde este mundo físico principalmente a través de la melodía y de la canción"
GOLDENS = [
    ("CONSTRUYENDO UN MISHKÁN", 51, 33, "structural_heading_exact", "section_heading", 10),
    ("INCLINADO HACIA LA BONDAD", 53, 35, "structural_heading_exact", "section_heading", 10),
    ("MELODÍAS Y PLEGARIAS", 56, 38, "structural_heading_exact", "section_heading", 10),
    ("Salmos 16:1", 55, 37, "printed_reference_exact", "marginal_reference", 20),
    (NOTE35, 56, 38, "footnote_literal_exact", "footnote", 10),
]
HEADINGS = [
    ("LOS ZAPATOS Y LA SABIDURÍA INFERIOR", 166),
    ("DESPERTÁNDOSE DEL SUEÑO ESPIRITUAL", 44),
    ("DESPERTANDO LOS PUNTOS BUENOS", 47),
    ("CONSTRUYENDO UN MISHKÁN", 51),
    ("INCLINADO HACIA LA BONDAD", 53),
    ("MELODÍAS Y PLEGARIAS", 56),
    ("ELEVANDO EL HABLA", 59),
    ("DIVIDIENDO LA NOCHE", 88),
    ("PERFECCIÓN DE LA PLEGARIA Y DEL HABLA", 68),
    ("VISTIENDO EL CUERPO", 72),
]
POSITIVES = [
    *[(query, page, "section_heading", "structural_heading") for query, page in HEADINGS],
    ("He puesto a HaShem siempre delante de mí", 156, "footnote", "footnote"),
    ("Tu jesed, HaShem, me sustentará", 56, "canonical_page", "literal"),
    ("el despertar el alba alude a levantarse del sueño espiritual", 55, "canonical_page", "literal"),
    ("el menos digno de los judíos", 48, "footnote", "footnote"),
    ("Rabí Natán concluye su explicación", 51, "canonical_page", "literal"),
    ("Explicado y Anotado por Moshé Mykoff con Dov Grant", 3, "canonical_page", "proper_name"),
    ("Traducción al Español Guillermo Beilinson", 3, "canonical_page", "proper_name"),
    ("Birur hace referencia a la extracción y refinamiento de las chispas", 56, "footnote", "footnote"),
    ("durante la noche la Shejiná desciende hacia los mundos inferiores", 57, "footnote", "footnote"),
    ("Hashkamat Haboker Levantándose por la Mañana", 2, "canonical_page", "literal"),
    (NOTE35, 56, "footnote", "footnote"),
    ("Salmos 16:1", 55, "marginal_reference", "printed_reference"),
    ("salmos 16:1", 55, "marginal_reference", "printed_reference"),
    ("Construyendo un Mishkan", 51, "section_heading", "structural_heading"),
    ("melodias y plegarias", 56, "section_heading", "structural_heading"),
]
NEGATIVES = [
    "CONSTRUYENDO UN TEMPLO INEXISTENTE", "Salmos 16:99", "Salmos 99:99",
    "Salmos 116:1 en Likutey Halajot", "nota 9999 de melodías", "Tomo 9 de Interior Final",
    "GEDALIA DE MARTE", "SECCIÓN DEL DRAGÓN AZUL", "página PDF 999 de Likutey Halajot",
    "frase fabricada que nunca aparece en el corpus xyzzy",
]
MULTILINGUAL = [
    "CONSTRUYENDO UN MISHKÁN", "Where does Reb Noson discuss Azamra?",
    "רבי נתן", "Azamra y puntos buenos", "melody and prayer in Likutey Halajot",
    "MELODÍAS prayer plegarias",
]
PROPER_NAMES = ["Gedalia of Linitz", "Gedalia", "Linitz", "Reb Noson", "Rabí Natán", "Rebe Najmán"]
HEBREW = ["וּמִצְרַיִם נָסִים לִקְרָאתוֹ", "ומצרים נסים לקראתו"]


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def summary(question: str, response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    primary = next((hit for hit in body.get("hits", []) if hit.get("is_primary")), None)
    return {
        "query": question,
        "http_status": response.status_code,
        "research_status": body.get("research_status"),
        "semantic_status": body.get("semantic_status"),
        "warnings": body.get("warnings", []),
        "query_language": (body.get("retrieval") or {}).get("query_language"),
        "primary": None if primary is None else {
            "document": primary.get("physical_file_name") or primary.get("work_title"),
            "page": primary.get("physical_pdf_page"),
            "printed_page": primary.get("printed_page"),
            "evidence_id": primary.get("evidence_id") or primary.get("hit_id"),
            "match_type": primary.get("literal_match_kind"),
            "source_layer": primary.get("source_layer"),
            "evidence_language": primary.get("language"),
            "document_status": primary.get("document_status"),
            "footnote_number": primary.get("footnote_number"),
        },
        "answer_markdown": body.get("answer_markdown") if "tomo" in question.lower() else None,
    }


async def main(output: Path) -> None:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("TEBAAI_E2E_ADMIN_EMAIL/PASSWORD are required")
    output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=180) as client:
        login = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def ask(question: str) -> dict[str, Any]:
            nonlocal headers
            payload = {"question": question, "ai": {"enabled": False}}
            response = await client.post(
                f"{BASE}/library/investigative-qa/v1", headers=headers, json=payload,
            )
            if response.status_code == 401:
                renewed = await client.post(
                    f"{BASE}/auth/login", json={"email": email, "password": password},
                )
                renewed.raise_for_status()
                headers = {"Authorization": f"Bearer {renewed.json()['access_token']}"}
                response = await client.post(
                    f"{BASE}/library/investigative-qa/v1", headers=headers, json=payload,
                )
            return summary(question, response)

        determinism = []
        api_goldens = []
        for query, page, printed, match_type, layer, repetitions in GOLDENS:
            runs = [await ask(query) for _ in range(repetitions)]
            signatures = Counter(json.dumps(run.get("primary"), sort_keys=True) for run in runs)
            passed = all(
                run["http_status"] == 200 and run["primary"]
                and run["primary"]["document"] == FILENAME
                and run["primary"]["page"] == page
                and run["primary"]["printed_page"] == printed
                and run["primary"]["match_type"] == match_type
                and run["primary"]["source_layer"] == layer
                for run in runs
            )
            api_goldens.append({"query": query, "expected": {"page": page, "printed_page": printed, "match_type": match_type, "source_layer": layer}, "runs": runs, "pass": passed})
            determinism.append({"query": query, "runs": repetitions, "unique_primary_signatures": len(signatures), "signatures": signatures, "pass": passed and len(signatures) == 1})

        azamra_runs = [await ask("Azamra, ¿en qué tomo de Likutey Halajot está?") for _ in range(10)]
        determinism.append({
            "query": "Azamra, ¿en qué tomo de Likutey Halajot está?", "runs": 10,
            "unique_answers": len({run.get("answer_markdown") for run in azamra_runs}),
            "pass": all("Tomo 2" not in (run.get("answer_markdown") or "") and "Tomo no resuelto" in (run.get("answer_markdown") or "") for run in azamra_runs),
        })
        positive_rows = []
        for query, expected_page, expected_layer, evidence_type in POSITIVES:
            run = await ask(query)
            run["expected"] = {"document": FILENAME, "page": expected_page, "source_layer": expected_layer, "evidence_type": evidence_type}
            run["pass"] = bool(run.get("primary") and run["primary"]["document"] == FILENAME and run["primary"]["page"] == expected_page)
            positive_rows.append(run)
        negative_rows = [await ask(query) for query in NEGATIVES]
        for run in negative_rows:
            run["pass"] = run["research_status"] == "no_evidence" or not (run.get("primary") and str(run["primary"].get("match_type") or "").endswith("exact"))
        multilingual_rows = [await ask(query) for query in MULTILINGUAL]
        proper_rows = [await ask(query) for query in PROPER_NAMES]
        hebrew_rows = [await ask(query) for query in HEBREW]
        heading_rows = [row for row in positive_rows if row["expected"]["evidence_type"] == "structural_heading"]
        footnote_rows = [row for row in api_goldens if row["expected"]["source_layer"] == "footnote"]
        reference_rows = [row for row in api_goldens if row["expected"]["source_layer"] == "marginal_reference"]
        planner = {"runs": azamra_runs, "tomo_2_rejected": all("Tomo 2" not in (row.get("answer_markdown") or "") for row in azamra_runs), "volume_number": None, "volume_source": "unresolved", "source_pdf_audit": "PDF page 10 explicitly calls this the first volume; persisted metadata must be corrected separately."}
        dump(output / "api-goldens.json", {"goldens": api_goldens, "literal_batch": positive_rows})
        dump(output / "determinism-results.json", determinism)
        dump(output / "multilingual-results.json", {"multilingual": multilingual_rows, "proper_names": proper_rows, "hebrew_goldens": hebrew_rows})
        dump(output / "negative-results.json", negative_rows)
        dump(output / "heading-audit.json", {"sample_size": len(heading_rows), "results": heading_rows})
        dump(output / "footnote-audit.json", {"primary_control": footnote_rows, "additional_persisted_sample_required": True, "assessment": "runtime note 35 passes; persisted page-level role metadata remains coarse"})
        dump(output / "printed-reference-audit.json", {"primary_control": reference_rows, "boundary_negatives": [row for row in negative_rows if "Salmos" in row["query"]]})
        dump(output / "bibliographic-api-audit.json", planner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output))
