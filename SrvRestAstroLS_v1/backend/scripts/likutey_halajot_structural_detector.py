"""Evidence-gated structural detector for the Likutey Halajot page-first run."""
from __future__ import annotations

import argparse
import asyncio
import json
import re

import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN

RUN = "likutey_halajot_structural_detector_v1_20260714"
EDITION = "likutey_halajot_page_first_v1"

# Every promoted interval has explicit local title evidence at its boundaries.
RANGES = (
    (1, 5, "front_matter", "front_matter", "edition_front_matter", None, r"Likutey\s+Halakhot"),
    (7, 7, "index", "index_material", "Índice", None, r"ÍNDICE"),
    (9, 10, "front_matter", "classified", "Prefacio del Editor", None, r"PREFACIO DEL EDITOR"),
    (11, 12, "front_matter", "classified", "Sobre el Rabí Natán", None, r"SOBRE EL RAB[ÍI]\s+NAT[ÁA]N"),
    (13, 15, "front_matter", "classified", "Sobre el Likutey Halajot", None, r"SOBRE EL LIKUTEY HALAJOT"),
    (16, 18, "front_matter", "classified", "Convenciones usadas en esta traducción", None, r"CONVENCIONES\s+USADAS"),
    (19, 34, "introduction", "classified", "Introducción del Rabí Natán", None, r"Likutey\s+Halakhot"),
    (35, 239, "main_text", "classified", "Hashkamat HaBoker — Levantarse por la Mañana", 1, r"Discourses\s+on|Discursos\s+sobre"),
    (241, 254, "appendix", "appendix_material", "Apéndice A — Reseña kabalística de la creación", 1, r"Appendices|Apéndices"),
    (255, 265, "appendix", "appendix_material", "Apéndice B — Antecedentes históricos y conceptuales", 2, r"AP[ÉE]NDICE B"),
    (267, 273, "glossary", "appendix_material", "Glosario", None, r"GLOSARIO"),
    (275, 283, "diagram", "diagram_material", "Apéndices — Diagramas", None, r"Appendices\s+Diagramas"),
)


def printed_page(text: str) -> int | None:
    # A printed folio is accepted only when it is adjacent to the recurring book header.
    match = re.search(r"\b(\d{1,3})\s+LIKUTEY\s+HALAJOT\b", text, flags=re.I)
    return int(match.group(1)) if match else None


def hints(text: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    if re.search(r"HALAJ[ÁA]\s+\d+\s*:\s*\d+", text, re.I):
        values.append({"kind": "halakhah_header", "origin": "deterministic_regex"})
    if "Notas y Fuentes" in text:
        values.append({"kind": "notes_and_sources", "origin": "visible_label"})
    if re.search(r"\bINTRODUCCI[ÓO]N\b", text, re.I):
        values.append({"kind": "introduction_header", "origin": "visible_label"})
    if re.search(r"\bAP[ÉE]NDICE\b", text, re.I):
        values.append({"kind": "appendix_header", "origin": "visible_label"})
    if re.search(r"\bGLOSARIO\b", text, re.I):
        values.append({"kind": "glossary_header", "origin": "visible_label"})
    return values


def classify(page: int, text: str, verified: set[int]) -> dict[str, object]:
    if not text.strip():
        return {"document_part": "blank", "structural_status": "blank_page", "label": None, "number": None, "confidence": 1.0, "origin": ["blank_page_detection"], "evidence": ["no embedded text"], "action": "keep_unclassified", "review": "deterministic", "rationale": "No embedded text extracted; blank is inventory, not a structural promotion."}
    for start, end, part, status, label, number, _pattern in RANGES:
        if start <= page <= end and start in verified:
            return {"document_part": part, "structural_status": status, "label": label, "number": number, "confidence": 0.90, "origin": ["explicit_local_title", "continuity_from_verified_boundaries"], "evidence": [f"verified interval {start}-{end}", label], "action": "promote", "review": "deterministic", "rationale": "Promoted only within a locally titled interval closed by the next explicit boundary."}
    return {"document_part": "unknown", "structural_status": "unclassified", "label": None, "number": None, "confidence": 0.0, "origin": ["fallback_none"], "evidence": [], "action": "keep_unclassified", "review": "needs_structural_classification", "rationale": "No verified local structural boundary."}


async def run(write: bool) -> list[dict[str, object]]:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""SELECT a.page_anchor_id,a.pdf_page_number,a.printed_page_number,n.content_node_id,n.literal_text
              FROM library_page_anchors_v2 a JOIN library_documents d ON d.id=a.document_id
              LEFT JOIN library_content_nodes_v2 n ON n.page_anchor_id=a.page_anchor_id AND n.metadata_json->>'source_run_id'='likutey_halajot_page_first_v1'
              WHERE d.document_code='likutey_halajot_interior_final' AND a.edition_id=%s ORDER BY a.pdf_page_number""", (EDITION,))
            rows = await cur.fetchall()
            text_by_page = {row["pdf_page_number"]: row["literal_text"] or "" for row in rows}
            verified = {start for start, _end, _part, _status, _label, _number, pattern in RANGES if re.search(pattern, text_by_page.get(start, ""), re.I)}
            decisions: list[dict[str, object]] = []
            for row in rows:
                text = row["literal_text"] or ""
                result = classify(row["pdf_page_number"], text, verified)
                record = {"pdf_page": row["pdf_page_number"], "printed_page": printed_page(text), **result, "zone_hints": hints(text)}
                decisions.append(record)
                if write:
                    await cur.execute("""INSERT INTO library_page_structural_classifications_v2
                    (source_run_id,page_anchor_id,content_node_id,pdf_page,printed_page,document_part,structural_status,unit_type,unit_label,unit_number,confidence,evidence_origin,evidence_text,zone_hints,detector_version,classification_action,review_status,rationale)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,'v1',%s,%s,%s)
                    ON CONFLICT(source_run_id,page_anchor_id) DO UPDATE SET content_node_id=EXCLUDED.content_node_id,printed_page=EXCLUDED.printed_page,document_part=EXCLUDED.document_part,structural_status=EXCLUDED.structural_status,unit_type=EXCLUDED.unit_type,unit_label=EXCLUDED.unit_label,unit_number=EXCLUDED.unit_number,confidence=EXCLUDED.confidence,evidence_origin=EXCLUDED.evidence_origin,evidence_text=EXCLUDED.evidence_text,zone_hints=EXCLUDED.zone_hints,classification_action=EXCLUDED.classification_action,review_status=EXCLUDED.review_status,rationale=EXCLUDED.rationale""",
                    (RUN,row["page_anchor_id"],row["content_node_id"],row["pdf_page_number"],record["printed_page"],result["document_part"],result["structural_status"],"document_part",result["label"],result["number"],result["confidence"],json.dumps(result["origin"]),json.dumps(result["evidence"]),json.dumps(record["zone_hints"]),result["action"],result["review"],result["rationale"]))
            if write:
                await conn.commit()
            return decisions


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    decisions = asyncio.run(run(args.write))
    result = {"run": RUN, "write": args.write, "evaluated": len(decisions), "promoted": sum(x["action"] == "promote" for x in decisions), "unclassified": sum(x["action"] != "promote" for x in decisions), "decisions": decisions}
    if args.output:
        open(args.output, "w", encoding="utf-8").write(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "decisions"}, ensure_ascii=False))
