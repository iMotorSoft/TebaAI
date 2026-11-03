"""Consumer boundary must expose V5 explicitly and never fall back to V1."""
from pathlib import Path

import pymupdf
import pytest

from modules.library import automatic_region_certification as v1
from modules.library import automatic_region_certification_v5 as v5
from modules.library.extractors import extract_pdf_with_region_certificates

V5_VERSION = "automatic-region-certification-v5"


def _simple_pdf(path):
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), "A simple generic body")
        document.save(path)
    return path


def _cross_page_pdf(path):
    with pymupdf.open() as document:
        first = document.new_page(width=496, height=694)
        first.insert_text((56, 100), "Main body text for the page.")
        first.insert_text((200, 500), "Notas y Fuentes")
        first.insert_text((56, 520), "8 First note")
        second = document.new_page(width=496, height=694)
        second.insert_text((56, 100), "Main body text on the next page.")
        second.insert_text((200, 500), "Notas y Fuentes")
        second.insert_text((56, 520), "continued text")
        second.insert_text((56, 540), "9 Next note")
        document.save(path)
    return path


def test_consumer_boundary_dispatches_to_v5_and_never_calls_v1(monkeypatch):
    sentinel = {"pdf_page": 1, "certificates": [{"certificate_version": V5_VERSION}]}

    class Page:
        def to_dict(self):
            return sentinel

    def forbidden(*args, **kwargs):
        raise AssertionError("V1 must not be called by the V5 consumer boundary")

    monkeypatch.setattr(v1, "extract_pdf_region_certificates", forbidden)
    monkeypatch.setattr(v5, "extract_pdf_region_certificates", lambda *a, **k: [Page()])

    assert extract_pdf_with_region_certificates("unused.pdf", pages=[1]) == [sentinel]


def test_consumer_boundary_fails_closed_without_v1_fallback(monkeypatch):
    def broken_v5(*args, **kwargs):
        raise RuntimeError("V5 unavailable")

    def forbidden(*args, **kwargs):
        raise AssertionError("V1 fallback is forbidden")

    monkeypatch.setattr(v5, "extract_pdf_region_certificates", broken_v5)
    monkeypatch.setattr(v1, "extract_pdf_region_certificates", forbidden)

    with pytest.raises(RuntimeError, match="V5 unavailable"):
        extract_pdf_with_region_certificates("unused.pdf", pages=[1])


def test_consumer_output_is_identical_to_direct_v5(tmp_path):
    pdf = _simple_pdf(tmp_path / "generic.pdf")
    direct = [page.to_dict() for page in v5.extract_pdf_region_certificates(pdf, pages=[1])]
    consumed = extract_pdf_with_region_certificates(str(pdf), pages=[1])
    assert consumed == direct


def test_consumer_certificates_are_explicitly_v5(tmp_path):
    pdf = _simple_pdf(tmp_path / "generic.pdf")
    consumed = extract_pdf_with_region_certificates(str(pdf), pages=[1])
    certificates = [cert for page in consumed for cert in page["certificates"]]
    assert certificates
    assert {cert["certificate_version"] for cert in certificates} == {V5_VERSION}


def test_consumer_preserves_cross_page_continuation(tmp_path):
    pdf = _cross_page_pdf(tmp_path / "cross-page.pdf")
    consumed = extract_pdf_with_region_certificates(str(pdf), pages=[1, 2])
    first = next(
        cert for cert in consumed[0]["certificates"]
        if cert["note_number"] == 8 and cert["linked_region_ids"]
    )
    second = next(
        cert for cert in consumed[1]["certificates"]
        if cert["continuation_state"] == "CONTINUED_FROM_PREVIOUS"
    )
    assert first["continuation_state"] == "CONTINUES_NEXT_PAGE"
    assert second["continuation_state"] == "CONTINUED_FROM_PREVIOUS"
    assert tuple(first["linked_region_ids"]) == (second["region_id"],)
    assert tuple(second["linked_region_ids"]) == (first["region_id"],)
    assert first["editorial_unit_id"] == second["editorial_unit_id"]
    assert first["certificate_version"] == second["certificate_version"] == V5_VERSION


def test_consumer_fail_closed_keeps_unresolved_output(tmp_path):
    pdf = _simple_pdf(tmp_path / "generic.pdf")
    consumed = extract_pdf_with_region_certificates(str(pdf), pages=[1])
    assert any(
        cert["provenance_status"] == "UNRESOLVED"
        for cert in consumed[0]["certificates"]
    )
    assert all(
        cert["certificate_version"] == V5_VERSION
        for cert in consumed[0]["certificates"]
    )


def test_consumer_preserves_one_based_unique_page_contract(tmp_path):
    pdf = _simple_pdf(tmp_path / "generic.pdf")
    with pytest.raises(ValueError):
        extract_pdf_with_region_certificates(str(pdf), pages=[0])
    with pytest.raises(ValueError):
        extract_pdf_with_region_certificates(str(pdf), pages=[1, 1])


def test_worker_does_not_use_the_opt_in_consumer_boundary():
    worker = (
        Path(__file__).resolve().parents[1]
        / "modules/library/content_manager_worker.py"
    ).read_text()
    assert "extract_pdf_with_region_certificates" not in worker
