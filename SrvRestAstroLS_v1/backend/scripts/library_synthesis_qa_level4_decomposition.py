#!/usr/bin/env python3
"""Level 4 question decomposition — claims + relations for deep interconnection QA.

This module defines the canonical decomposition of the Level 4 test question
into atomic claims (A-H) and relations (R1-R15).  It is data-only: no retrieval,
no synthesis, no I/O.  Consumers import DECOMPOSITION and RELATIONS.
"""
from __future__ import annotations

from typing import Any

# ── Level 4 test question ────────────────────────────────────────────────────
LEVEL4_QUESTION_ID = "kitzur_level4_interconnection_01"
LEVEL4_QUESTION = (
    "Explica la interconexión entre la humildad, el conocimiento (daat), "
    "la verdad, la alegría, la pureza sexual y la unión con los Tzadikim "
    "como vía principal para alcanzar el propósito final de la vida "
    "según el Kitzur Likutey Moharán."
)

# ── Claim groups (A–H) ──────────────────────────────────────────────────────
# Each claim has: id, text, expected_pages, search_terms, category
DECOMPOSITION: list[dict[str, Any]] = [
    # A — Propósito final
    {
        "claim_id": "A1",
        "claim": "El propósito final de la vida es servir a Dios.",
        "expected_pages": [471],
        "search_terms": ["propósito final", "servir a Dios", "propósito de la vida", "para esto"],
        "category": "proposito_final",
    },
    {
        "claim_id": "A2",
        "claim": "El servicio a Dios conduce a merecer conocerlo.",
        "expected_pages": [471],
        "search_terms": ["conocerlo", "servicio a Dios", "merecer conocer"],
        "category": "proposito_final",
    },
    {
        "claim_id": "A3",
        "claim": "El conocimiento de Dios es el deleite eterno / Mundo que Viene.",
        "expected_pages": [103],
        "search_terms": ["Mundo que Viene", "deleite eterno", "conocimiento de Dios", "mundo venidero"],
        "category": "proposito_final",
    },

    # B — Humildad
    {
        "claim_id": "B1",
        "claim": "La humildad anula orgullo y materialidad.",
        "expected_pages": [22, 33],
        "search_terms": ["humildad", "orgullo", "anula", "quebrantando el orgullo"],
        "category": "humildad",
    },
    {
        "claim_id": "B2",
        "claim": "Aceptar insultos en silencio forma parte del camino espiritual.",
        "expected_pages": [22],
        "search_terms": ["insultos", "silencio", "humillación", "dejarse pisotear"],
        "category": "humildad",
    },
    {
        "claim_id": "B3",
        "claim": "Volverse 'nada' permite recibir la luz de Dios.",
        "expected_pages": [363],
        "search_terms": ["nada", "anulación", "luz de Dios", "nulidad", "volverse nada"],
        "category": "humildad",
    },

    # C — Verdad
    {
        "claim_id": "C1",
        "claim": "La verdad es luz de Dios o está ligada a la luz divina.",
        "expected_pages": [236, 237],
        "search_terms": ["verdad", "luz de Dios", "luz divina", "verdad es luz"],
        "category": "verdad",
    },
    {
        "claim_id": "C2",
        "claim": "La verdad es fundamento de la fe.",
        "expected_pages": [236, 237],
        "search_terms": ["verdad", "fundamento de la fe", "emuná", "fe"],
        "category": "verdad",
    },
    {
        "claim_id": "C3",
        "claim": "La verdad en la plegaria y acciones permite elevación o apertura espiritual.",
        "expected_pages": [41],
        "search_terms": ["verdad", "plegaria", "honestidad", "elevación", "apertura espiritual"],
        "category": "verdad",
    },

    # D — Alegría
    {
        "claim_id": "D1",
        "claim": "La alegría sostiene o recibe verdad y conocimiento.",
        "expected_pages": [462],
        "search_terms": ["alegría", "verdad", "conocimiento", "recipiente"],
        "category": "alegria",
    },
    {
        "claim_id": "D2",
        "claim": "La alegría es esencia o dimensión central de Shabat.",
        "expected_pages": [462],
        "search_terms": ["alegría", "Shabat", "esencia del Shabat", "dimensión del Shabat"],
        "category": "alegria",
    },
    {
        "claim_id": "D3",
        "claim": "La alegría permite bailar.",
        "expected_pages": [209],
        "search_terms": ["alegría", "baile", "bailar", "alegría permite bailar"],
        "category": "alegria",
    },
    {
        "claim_id": "D4",
        "claim": "La alegría mitiga juicios severos.",
        "expected_pages": [209],
        "search_terms": ["alegría", "juicios severos", "mitiga", "anula juicios", "fuerzas externas"],
        "category": "alegria",
    },

    # E — Daat / conocimiento
    {
        "claim_id": "E1",
        "claim": "Daat es percepción de la Divinidad.",
        "expected_pages": [148, 149],
        "search_terms": ["Daat", "daat", "conocimiento", "percepción", "Divinidad"],
        "category": "daat",
    },
    {
        "claim_id": "E2",
        "claim": "Daat es meta espiritual.",
        "expected_pages": [148, 149, 471],
        "search_terms": ["Daat", "daat", "conocimiento", "meta", "propósito"],
        "category": "daat",
    },
    {
        "claim_id": "E3",
        "claim": "Daat se vincula con rectificación de la mente.",
        "expected_pages": [148, 149],
        "search_terms": ["Daat", "daat", "conocimiento", "rectificación", "mente"],
        "category": "daat",
    },

    # F — Pureza sexual
    {
        "claim_id": "F1",
        "claim": "La pureza sexual rectifica la mente.",
        "expected_pages": [145],
        "search_terms": ["pureza sexual", "pureza", "rectifica", "mente", "pacto", "brit"],
        "category": "pureza_sexual",
    },
    {
        "claim_id": "F2",
        "claim": "La pureza sexual permite Lenguaje Sagrado.",
        "expected_pages": [82],
        "search_terms": ["pureza sexual", "Lenguaje Sagrado", "habla sagrada"],
        "category": "pureza_sexual",
    },
    {
        "claim_id": "F3",
        "claim": "La pureza sexual se relaciona con conocimiento / daat.",
        "expected_pages": [145],
        "search_terms": ["pureza", "conocimiento", "Daat", "daat"],
        "category": "pureza_sexual",
    },
    {
        "claim_id": "F4",
        "claim": "La pureza sexual facilita sustento o influjo espiritual.",
        "expected_pages": [82, 145],
        "search_terms": ["pureza", "sustento", "influjo espiritual", "profecía"],
        "category": "pureza_sexual",
    },

    # G — Tzadikim
    {
        "claim_id": "G1",
        "claim": "El Tzadik ilumina.",
        "expected_pages": [53, 54],
        "search_terms": ["Tzadik", "ilumina", "luz", "Tzadik ilumina"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G2",
        "claim": "El Tzadik despierta el corazón.",
        "expected_pages": [53, 54],
        "search_terms": ["Tzadik", "despierta", "corazón", "despertar"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G3",
        "claim": "El Tzadik enseña la verdad.",
        "expected_pages": [53, 54, 177, 178],
        "search_terms": ["Tzadik", "verdad", "enseña", "revela la verdad"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G4",
        "claim": "El Tzadik guía en el arrepentimiento.",
        "expected_pages": [177, 178],
        "search_terms": ["Tzadik", "arrepentimiento", "teshuvá", "guía"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G5",
        "claim": "El Tzadik revela la Torá.",
        "expected_pages": [53, 54, 177, 178],
        "search_terms": ["Tzadik", "Torá", "revela", "enseña Torá"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G6",
        "claim": "El Tzadik acerca a los lejanos.",
        "expected_pages": [70, 71],
        "search_terms": ["Tzadik", "lejanos", "acerca", "alejados"],
        "category": "tzadikim",
    },
    {
        "claim_id": "G7",
        "claim": "El Tzadik revela la voluntad de Dios.",
        "expected_pages": [70, 71],
        "search_terms": ["Tzadik", "voluntad de Dios", "revela", "voluntad divina"],
        "category": "tzadikim",
    },

    # H — Reconocer al verdadero Tzadik
    {
        "claim_id": "H1",
        "claim": "La humildad ayuda a reconocer y unirse al verdadero Tzadik.",
        "expected_pages": [312],
        "search_terms": ["humildad", "reconocer", "verdadero Tzadik", "unirse", "Tzadik"],
        "category": "reconocer_tzadik",
    },
    {
        "claim_id": "H2",
        "claim": "La verdad ayuda a reconocer y unirse al verdadero Tzadik.",
        "expected_pages": [312],
        "search_terms": ["verdad", "reconocer", "verdadero Tzadik", "unirse", "Tzadik"],
        "category": "reconocer_tzadik",
    },
]

# ── Relations (R1–R15) ──────────────────────────────────────────────────────
RELATIONS: list[dict[str, Any]] = [
    {
        "relation_id": "R1",
        "from_claim_id": "B1",
        "to_claim_id": "C1",
        "from_label": "humildad",
        "to_label": "verdad",
        "description": "humildad → verdad",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R2",
        "from_claim_id": "B3",
        "to_claim_id": "C1",
        "from_label": "humildad (nada)",
        "to_label": "recibir luz divina",
        "description": "humildad → recibir luz divina",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R3",
        "from_claim_id": "C2",
        "to_claim_id": "C2",
        "from_label": "verdad",
        "to_label": "fe",
        "description": "verdad → fe",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R4",
        "from_claim_id": "C3",
        "to_claim_id": "C3",
        "from_label": "verdad",
        "to_label": "plegaria elevada",
        "description": "verdad → plegaria elevada",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R5",
        "from_claim_id": "D1",
        "to_claim_id": "E1",
        "from_label": "alegría",
        "to_label": "verdad / conocimiento",
        "description": "alegría → verdad/conocimiento",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R6",
        "from_claim_id": "D4",
        "to_claim_id": "D4",
        "from_label": "alegría",
        "to_label": "mitigación de juicios",
        "description": "alegría → mitigación de juicios",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R7",
        "from_claim_id": "F1",
        "to_claim_id": "E3",
        "from_label": "pureza sexual",
        "to_label": "rectificación de mente",
        "description": "pureza sexual → rectificación de mente",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R8",
        "from_claim_id": "F3",
        "to_claim_id": "E1",
        "from_label": "pureza sexual",
        "to_label": "daat / conocimiento",
        "description": "pureza sexual → daat",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R9",
        "from_claim_id": "G3",
        "to_claim_id": "C1",
        "from_label": "Tzadik",
        "to_label": "verdad",
        "description": "Tzadik → verdad",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R10",
        "from_claim_id": "G4",
        "to_claim_id": "G4",
        "from_label": "Tzadik",
        "to_label": "arrepentimiento",
        "description": "Tzadik → arrepentimiento",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R11",
        "from_claim_id": "G5",
        "to_claim_id": "G5",
        "from_label": "Tzadik",
        "to_label": "Torá",
        "description": "Tzadik → Torá",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R12",
        "from_claim_id": "G6",
        "to_claim_id": "G6",
        "from_label": "Tzadik",
        "to_label": "acercar lejanos",
        "description": "Tzadik → acercar lejanos",
        "expected_relation_type": "literal",
    },
    {
        "relation_id": "R13",
        "from_claim_id": "H1",
        "to_claim_id": "H2",
        "from_label": "humildad + verdad",
        "to_label": "reconocer verdadero Tzadik",
        "description": "humildad + verdad → reconocer verdadero Tzadik",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R14",
        "from_claim_id": "E2",
        "to_claim_id": "A2",
        "from_label": "daat",
        "to_label": "propósito final de la vida",
        "description": "daat → propósito final de la vida",
        "expected_relation_type": "thematic",
    },
    {
        "relation_id": "R15",
        "from_claim_id": "A3",
        "to_claim_id": "A3",
        "from_label": "red completa",
        "to_label": "conocimiento de Dios / Mundo que Viene",
        "description": "red completa → conocimiento de Dios / Mundo que Viene",
        "expected_relation_type": "literal",
    },
]

# ── Evidence type classification ─────────────────────────────────────────────
EVIDENCE_TYPES = [
    "literal",         # exact quote match
    "paraphrase",      # close paraphrase
    "thematic",        # thematic/contextual relevance
    "cooccurrence",    # both terms appear on same page
    "same_page",       # claims on same page
    "same_section",    # claims in same section
    "ai_inferred",     # AI inference from validated evidence matrix
    "remesh_derash",   # interpretive connection, not literal
]

# ── Helper ───────────────────────────────────────────────────────────────────


def get_claim_by_id(claim_id: str) -> dict[str, Any] | None:
    for c in DECOMPOSITION:
        if c["claim_id"] == claim_id:
            return c
    return None


def get_claims_by_category(category: str) -> list[dict[str, Any]]:
    return [c for c in DECOMPOSITION if c["category"] == category]


def get_relations_for_claim(claim_id: str) -> list[dict[str, Any]]:
    return [r for r in RELATIONS if r["from_claim_id"] == claim_id or r["to_claim_id"] == claim_id]


def all_expected_pages() -> set[int]:
    pages: set[int] = set()
    for c in DECOMPOSITION:
        pages.update(c["expected_pages"])
    return pages
