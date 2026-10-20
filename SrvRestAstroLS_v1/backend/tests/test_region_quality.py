from dataclasses import replace
from pathlib import Path
import json

import pytest

from modules.library.chunking import paragraph_chunks
from modules.library.region_quality import (
    AggregateState, QUALITY_POLICY_VERSION, QualityPage, RegionCandidate,
    RegionState, Remediation, classify_region, document_quality, markdown_note_starts,
)


def good(**kwargs):
    return RegionCandidate(**({
        "source_sha256": "a" * 64, "pdf_page": 1, "region_id": "body",
        "markdown": "# Good region\n\nLiteral reliable text.",
        "source_method": "pymupdf4llm", "evidence_refs": ("fixture:synthetic-reviewed",),
        "visual_good": True, "text_verified": True, "order_verified": True,
        "structure_verified": True, "bbox": (0, 0, 100, 100),
    } | kwargs))


def test_full_good_page_normal_canonical_and_chunks():
    candidate = good()
    p = QualityPage((classify_region(candidate),))
    assert p.quality == document_quality((p,)) == AggregateState.FULL
    assert p.canonical_markdown == candidate.markdown
    assert paragraph_chunks(p.canonical_markdown, 1400, 150, 1)[0]["content"] == candidate.markdown


@pytest.mark.parametrize("bad,reason", [
    ("\ufffd damaged", "replacement_character"),
    ("broken\x03Latin font", "unexpected_control_character"),
])
def test_generic_encoding_errors_reject_even_with_claimed_certificate(bad, reason):
    r = classify_region(good(markdown=bad))
    assert r.state == RegionState.PLATFORM_EXTRACTION_ERROR
    assert reason in r.reasons
    assert r.accepted_markdown == ""


@pytest.mark.parametrize("diagnostic", [
    "mojibake", "pseudo_script", "unsafe_column_merge", "known_broken_order",
    "material_digit_corruption", "visual_uncertainty",
])
def test_declared_diagnostics_fail_closed(diagnostic):
    c = good(diagnostics=(diagnostic,), visual_good=None if diagnostic == "visual_uncertainty" else True)
    r = classify_region(c)
    assert r.state != RegionState.ACCEPTED
    assert r.accepted_markdown == ""


def test_partial_preserves_good_neighbors_without_evidence_crossing_gap():
    a = classify_region(good(region_id="before"))
    bad = classify_region(good(region_id="bad", markdown="\ufffd BROKEN_UNIQUE"))
    b = classify_region(good(region_id="after", markdown="Good later text."))
    page = QualityPage((a, bad, b))
    assert page.quality == document_quality((page,)) == AggregateState.PARTIAL
    assert page.evidence_units == (("before", a.accepted_markdown), ("after", b.accepted_markdown))
    chunks = [c["content"] for _, text in page.evidence_units for c in paragraph_chunks(text, 1400, 150, 1)]
    assert "BROKEN_UNIQUE" not in " ".join(chunks)
    assert a.accepted_markdown in chunks and b.accepted_markdown in chunks
    meta = page.metadata()
    assert len(meta["regions"]) == 3
    assert meta["regions"][1]["classification"] == "PLATFORM_EXTRACTION_ERROR"
    assert "BROKEN_UNIQUE" not in json.dumps(meta)
    assert meta["quality"] == "PARTIAL"


def test_source_error_recorded_no_autofix_document_continues():
    r = classify_region(good(region_id="source", visual_good=False, markdown="visibly broken"))
    assert r.state == RegionState.SOURCE_PDF_ERROR
    assert r.remediation == Remediation.SOURCE_ERROR
    assert r.candidate.markdown == "visibly broken"
    assert document_quality((QualityPage((classify_region(good()), r)),)) == AggregateState.PARTIAL


@pytest.mark.parametrize("changes", [
    {"visual_good": None}, {"text_verified": False}, {"order_verified": False},
    {"structure_verified": False}, {"evidence_refs": ()},
    {"visual_good": False, "evidence_refs": ()},
])
def test_insufficient_evidence_is_unresolved_not_platform_error(changes):
    r = classify_region(replace(good(), **changes))
    assert r.state == RegionState.UNRESOLVED
    assert r.accepted_markdown == ""


def test_unusable_and_empty_inventory_never_full():
    assert QualityPage(()).quality == AggregateState.UNUSABLE
    assert document_quality(()) == AggregateState.UNUSABLE
    assert QualityPage((classify_region(good(visual_good=None)),)).quality == AggregateState.UNUSABLE


def test_reconnect_is_action_not_quality_bypass():
    r = classify_region(good(diagnostics=("markdown_note_contract",), safe_reconnect_available=True))
    assert r.remediation == Remediation.SAFE_RECONNECT
    assert r.state != RegionState.ACCEPTED


def test_notes_35_36_recognized_without_mutating_original_or_offsets():
    original = '> 35 Ver §1. El hombre se une a HaShem.\n\n> 36 _Birur_ significa reﬁ namiento.\n'
    starts = markdown_note_starts(original)
    assert tuple(s.number for s in starts) == (35, 36)
    assert original[starts[0].body_start:starts[1].start].strip() == 'Ver §1. El hombre se une a HaShem.'
    assert original[starts[1].body_start:].strip() == '_Birur_ significa reﬁ namiento.'
    assert markdown_note_starts('body [35] text.\n## 6 TITLE\n35:5 reference') == ()


def test_idempotence_metadata_and_policy_version():
    c = good(markdown="\ufffd")
    assert classify_region(c) == classify_region(c)
    assert classify_region(c).metadata() == classify_region(c).metadata()
    assert classify_region(c).metadata()["quality_policy_version"] == QUALITY_POLICY_VERSION


@pytest.mark.parametrize("changes", [
    {"source_sha256": "bad"}, {"pdf_page": 0}, {"region_id": ""},
    {"source_method": ""}, {"bbox": (1, 0, 0, 1)}, {"bbox": (0, 0, float('nan'), 1)},
])
def test_invalid_provenance_rejected(changes):
    with pytest.raises(ValueError):
        good(**changes)


@pytest.mark.parametrize("method", ["visual_ocr_fallback", "native_raw_diagnostic", "unknown"])
def test_noncanonical_sources_never_accepted(method):
    assert classify_region(good(source_method=method)).state != RegionState.ACCEPTED


def test_real_page56_existing_audit_contract_recovers_both_starts():
    root = Path(__file__).resolve().parents[3]
    path = root / 'data/reports/breslov/historical-extraction-solution-audit-v1/closure/pdf-56-current_canonical.txt'
    text = path.read_text()
    starts = markdown_note_starts(text)
    assert {35, 36}.issubset({s.number for s in starts})
    s35 = next(s for s in starts if s.number == 35)
    s36 = next(s for s in starts if s.number == 36)
    assert s35.start < s36.start
    assert 'El hombre se une a HaShem' in text[s35.body_start:s36.start]
    assert '_Birur_' in text[s36.body_start:]


def test_real_page167_body_retained_rejected_notes_tracked_offline():
    root = Path(__file__).resolve().parents[3]
    text = json.loads((root / 'data/reports/breslov/quality-aware-partial-ingestion-v1/page167-candidate.json').read_text())['original_markdown']
    start = text.index('**protección extra')
    end = text.index('## ~~_Notas y Fuentes')
    body = classify_region(good(region_id='spanish_body', markdown=text[start:end].strip()))
    bad = classify_region(good(region_id='hebrew', markdown=text[:start]))
    notes = classify_region(good(region_id='notes', markdown=text[end:], diagnostics=('known_broken_column_order',)))
    p = QualityPage((bad, body, notes))
    assert p.quality == AggregateState.PARTIAL
    assert p.evidence_units == (('spanish_body', text[start:end].strip()),)
    assert 'zapato derecho primero' in p.canonical_markdown
    assert '\ufffd' not in p.canonical_markdown
    assert len(p.metadata()['regions']) == 3
    # Demonstrate the actual order defect, not an invented Hebrew heuristic.
    assert text.index('66 Comentando') < text.index('64 Ver') < text.index('65 Estudia')


def test_duplicate_and_cross_page_regions_rejected():
    r = classify_region(good())
    with pytest.raises(ValueError):
        QualityPage((r, r))
    with pytest.raises(ValueError):
        QualityPage((r, classify_region(good(pdf_page=2, region_id="other"))))
