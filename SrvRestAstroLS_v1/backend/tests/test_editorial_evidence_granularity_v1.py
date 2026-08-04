"""Unit tests for editorial evidence identity functions (v2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.library.simple_research_rag import (
    _entity_key,
    _evidence_id,
    _legacy_chunk_evidence_id,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "editorial_evidence_granularity_stable_ids_v1.json").read_text(encoding="utf-8")
)


def test_note_35_and_36_different_ids() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    n35 = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35})
    n36 = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36})
    assert n35 != n36
    assert n35 == _evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35})


def test_same_entity_different_query_variants() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    base = {"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36}
    assert _evidence_id(base) == _evidence_id(base)


def test_heading_vs_footnote_different_ids() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    h = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "structural_heading_exact", "heading_original": "6 ■ MELODÍAS Y PLEGARIAS"})
    f = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35})
    assert h != f


def test_reference_variants_same_id() -> None:
    chunk_id = "4ab8b2bd-e9a3-4818-9c99-5f757816c8ae"
    r1 = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "Salmos 16:1"})
    r2 = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "(Salmos 16:1)"})
    r3 = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "salmos 16:1"})
    assert r1 == r2 == r3


def test_body_and_footnote_different() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    body = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "body_literal_exact"})
    fn = _evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35})
    assert body != fn


def test_deterministic() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    c = {"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36}
    assert _evidence_id(c) == _evidence_id(c)


def test_rank_does_not_affect_id() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    c1 = {"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36, "literal_score": 100.0}
    c2 = {"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36, "literal_score": 0.5}
    assert _evidence_id(c1) == _evidence_id(c2)


def test_legacy_id_preserved() -> None:
    chunk_id = "036be7c5-2dde-4b0a-9dde-010e9d24e53e"
    assert _legacy_chunk_evidence_id(chunk_id) == "ev-e419ec6448d2d992"


def test_different_pages_different_ids() -> None:
    n36_p56 = _evidence_id({"chunk_id": "036be7c5-2dde-4b0a-9dde-010e9d24e53e", "literal_match_type": "footnote_literal_exact", "footnote_number": 36})
    head_p51 = _evidence_id({"chunk_id": "8e1a1192-02f2-4903-97f8-ce85f29bdf2a", "literal_match_type": "structural_heading_exact", "heading_original": "4 ■ CONSTRUYENDO UN MISHKÁN"})
    assert n36_p56 != head_p51


def test_id_does_not_include_status() -> None:
    c = {"chunk_id": "x", "literal_match_type": "footnote_literal_exact", "footnote_number": 36}
    ids = []
    for status in ["ready", "test_candidate", "archived"]:
        c2 = {**c, "document_status": status}
        ids.append(_evidence_id(c2))
    assert len(set(ids)) == 1


def test_entity_key_for_footnote_without_number() -> None:
    # If literal_match_type is footnote but no number, fall back to chunk
    assert _entity_key({"literal_match_type": "footnote_literal_exact", "footnote_number": None}) == "chunk"
    # With evidence_role=footnote_body, it resolves to footnote:unknown
    assert _entity_key({"evidence_role": "footnote_body", "literal_match_type": "", "block_type": ""}) == "footnote:unknown"


def test_entity_key_for_role_only() -> None:
    assert _entity_key({"evidence_role": "commentary", "literal_match_type": "", "block_type": ""}) == "role:commentary"
    assert _entity_key({"evidence_role": "", "literal_match_type": "", "block_type": ""}) == "chunk"
