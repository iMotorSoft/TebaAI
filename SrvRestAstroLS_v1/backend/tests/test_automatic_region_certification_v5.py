"""V5 positive identity is fail-closed, deterministic and permutation invariant."""
from copy import deepcopy
import random

from modules.library.automatic_region_certification_v5 import (
    CANDIDATE_CONTINUATION,
    IDENTITY_PROVEN,
    certify_document,
)
from test_automatic_region_certification_v4 import document
from test_region_markdown_provenance import SHA


def signature(pages):
    return [
        (
            page.provenance.pdf_page,
            tuple(sorted(
                (cert.region_id, cert.zone_type, cert.note_number,
                 cert.provenance_status, cert.quality_status,
                 cert.continuation_state, cert.identity_state,
                 tuple(cert.linked_region_ids), cert.editorial_unit_id,
                 tuple((proof.name, proof.passed) for proof in cert.identity_proof))
                for cert in page.certificates
            )),
        )
        for page in sorted(pages, key=lambda item: item.provenance.pdf_page)
    ]


def test_synthetic_weak_continuation_is_not_proven():
    parsed, natives = document()
    result = certify_document(parsed, SHA, native_pages=natives)
    assert not any(cert.identity_state == IDENTITY_PROVEN
                   for page in result for cert in page.certificates)
    assert not any(cert.linked_region_ids
                   for page in result for cert in page.certificates)
    assert any(cert.identity_state == CANDIDATE_CONTINUATION
               for page in result for cert in page.certificates)


def test_missing_native_evidence_fails_closed():
    parsed, _ = document()
    result = certify_document(parsed, SHA, native_pages={})
    assert not any(cert.identity_state == IDENTITY_PROVEN
                   for page in result for cert in page.certificates)
    assert not any(cert.linked_region_ids
                   for page in result for cert in page.certificates)


def test_page_box_and_line_permutation_is_invariant():
    parsed, natives = document()
    baseline = certify_document(parsed, SHA, native_pages=natives)
    shuffled = deepcopy(parsed)
    rng = random.Random(2718)
    rng.shuffle(shuffled.pages)
    for page in shuffled.pages:
        rng.shuffle(page.boxes)
        for box in page.boxes:
            if box.textlines:
                rng.shuffle(box.textlines)
    assert signature(certify_document(shuffled, SHA, native_pages=natives)) == signature(baseline)


def test_repeated_run_is_identical():
    parsed, natives = document()
    assert signature(certify_document(parsed, SHA, native_pages=natives)) == signature(
        certify_document(parsed, SHA, native_pages=natives)
    )


def test_non_note_certificates_are_never_cross_page():
    parsed, natives = document()
    result = certify_document(parsed, SHA, native_pages=natives)
    assert all(cert.identity_state == "NOT_CROSS_PAGE"
               for page in result for cert in page.certificates
               if cert.zone_type != "note")
