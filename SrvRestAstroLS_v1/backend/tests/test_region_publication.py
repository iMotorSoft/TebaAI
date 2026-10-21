"""Deterministic publication-consumer tests, not extraction-quality proofs."""
from dataclasses import replace
import json

import pytest

from modules.library.automatic_region_certification import CertifiedPage, RegionCertificate
from modules.library.chunking import paragraph_chunks
from modules.library.region_markdown_provenance import Ownership, ProvenancePage
from modules.library.region_publication import publish_certified_page

SOURCE = "a" * 64
GOOD_A = "GOOD_A vecino aceptado alfa"
GOOD_B = "GOOD_B nota aceptada omega"
BAD = "BAD_HEBREW אב\ufffdגד quarantineunique"


def certified_fixture(texts, statuses):
    """Declared internal verdicts test the consumer, never claim live quality."""
    units, certificates = [], []
    markdown = ""
    for index, (text, quality) in enumerate(zip(texts, statuses, strict=True)):
        start = len(markdown)
        markdown += text + "\n\n"
        end = len(markdown)
        bbox = (20, 20 + index * 40, 300, 40 + index * 40)
        rid = f"region-{index}"
        units.append(Ownership(rid, 1, bbox, (), "text", None, "BOX_BOUNDARY",
                               start, end, start, end))
        certificates.append(RegionCertificate(
            SOURCE, 1, rid, bbox, "text", "LTR", (), (), ((start, end),),
            "FORWARD_IR_SERIALIZATION", "CERTIFIED", quality,
            () if quality == "ACCEPTED" else ("QUALITY_EVIDENCE_INSUFFICIENT",),
        ))
    return CertifiedPage(ProvenancePage(SOURCE, 1, markdown, markdown, tuple(units)),
                         tuple(certificates))


@pytest.mark.parametrize("texts,statuses,status,expected", [
    ((GOOD_A,), ("ACCEPTED",), "FULL", (GOOD_A,)),
    ((BAD,), ("UNRESOLVED",), "UNUSABLE", ()),
    ((GOOD_A, BAD, GOOD_B), ("ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED"),
     "PARTIAL", (GOOD_A, GOOD_B)),
    ((BAD, BAD, GOOD_A), ("SOURCE_PDF_ERROR", "UNRESOLVED", "ACCEPTED"), "PARTIAL", (GOOD_A,)),
    ((BAD, BAD), ("UNRESOLVED", "PLATFORM_EXTRACTION_ERROR"), "UNUSABLE", ()),
])
def test_controlled_cases_filter_before_canonical_and_chunking(texts, statuses, status, expected):
    page = publish_certified_page(certified_fixture(texts, statuses), source_reference="fixture.pdf")
    assert page.status.value == status
    assert tuple(text.strip() for _, text in page.evidence_units) == expected
    assert BAD not in page.canonical_markdown
    chunks = [(rid, chunk["content"]) for rid, text in page.evidence_units
              for chunk in paragraph_chunks(text, 1400, 150, 1)]
    assert len(chunks) == len(expected)
    assert all("quarantineunique" not in text for _, text in chunks)
    # This is the set of inputs a consumer MAY embed/cite, not an embedding call.
    assert all(not (GOOD_A in text and GOOD_B in text) for _, text in chunks)
    metadata = page.metadata()
    assert BAD not in json.dumps(metadata, ensure_ascii=False)
    assert metadata["contains_quarantined_regions"] == (status != "FULL")
    for original, region in zip(statuses, metadata["regions"], strict=True):
        assert region["quality_status"] == original
        assert region["textually_citable"] == (original == "ACCEPTED")
        assert region["visual_reference"]["source_reference"] == "fixture.pdf"
        assert region["visual_reference"]["pdf_page"] == 1
        assert region["visual_reference"]["bbox"]
        if original != "ACCEPTED":
            assert region["reason_codes"]
            assert region["publication_status"] == "QUARANTINED"


@pytest.mark.parametrize("status", ["QUARANTINED", "UNRESOLVED", "SOURCE_PDF_ERROR",
                                     "PLATFORM_EXTRACTION_ERROR", "UNKNOWN", "accepted"])
def test_every_nonaccepted_status_is_excluded(status):
    page = publish_certified_page(certified_fixture((BAD,), (status,)), source_reference="source.pdf")
    assert not page.evidence_units
    assert not page.canonical_markdown
    assert page.regions[0].quality_status == status


@pytest.mark.parametrize("changes", [
    {"quality_status": "UNRESOLVED"},
    {"provenance_status": "UNRESOLVED"},
    {"document_sha": "b" * 64},
    {"pdf_page": 2},
    {"markdown_ranges": ((0, 10000),)},
    {"bbox": (1, 2, 3, 4)},
])
def test_bad_certificate_never_suppresses_independent_accepted_neighbors(changes):
    fixture = certified_fixture((GOOD_A, BAD, GOOD_B), ("ACCEPTED",) * 3)
    certs = list(fixture.certificates)
    certs[1] = replace(certs[1], **changes)
    page = publish_certified_page(replace(fixture, certificates=tuple(certs)), source_reference="source.pdf")
    assert tuple(t.strip() for _, t in page.evidence_units) == (GOOD_A, GOOD_B)
    assert page.status.value == "PARTIAL"


def test_missing_certificate_quarantines_only_its_region():
    fixture = certified_fixture((GOOD_A, BAD, GOOD_B), ("ACCEPTED",) * 3)
    fixture = replace(fixture, certificates=(fixture.certificates[0], fixture.certificates[2]))
    page = publish_certified_page(fixture, source_reference="source.pdf")
    assert tuple(t.strip() for _, t in page.evidence_units) == (GOOD_A, GOOD_B)
    assert "MISSING_OR_DUPLICATE_CERTIFICATE" in page.regions[1].reason_codes


def test_publication_is_deterministic_and_keeps_source_inventory_immutable():
    fixture = certified_fixture((GOOD_A, BAD, GOOD_B), ("ACCEPTED", "UNRESOLVED", "ACCEPTED"))
    before = fixture.to_dict()
    first = publish_certified_page(fixture, source_reference="source.pdf")
    second = publish_certified_page(fixture, source_reference="source.pdf")
    assert first == second
    assert before == fixture.to_dict()
    assert "quarantineunique" in fixture.provenance.markdown
    assert not any("quarantineunique" in text for _, text in first.evidence_units)


def test_source_reference_is_required():
    with pytest.raises(ValueError, match="source reference"):
        publish_certified_page(certified_fixture((BAD,), ("UNRESOLVED",)), source_reference=" ")


def test_overlapping_markdown_cannot_become_textual_evidence():
    fixture = certified_fixture((GOOD_A, BAD), ("ACCEPTED", "UNRESOLVED"))
    units = list(fixture.provenance.units)
    units[1] = replace(units[1], markdown_start=0)
    page = publish_certified_page(replace(fixture, provenance=replace(fixture.provenance, units=tuple(units))),
                                  source_reference="source.pdf")
    assert not page.evidence_units
    assert "OVERLAPPING_MARKDOWN_OWNERSHIP" in page.regions[0].reason_codes
