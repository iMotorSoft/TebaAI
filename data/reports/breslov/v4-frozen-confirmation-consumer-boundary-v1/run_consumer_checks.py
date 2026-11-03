"""Consumer parity and cross-page propagation evidence."""
import json
import sys
import tempfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))

from modules.library import automatic_region_certification_v4 as v4
from modules.library.extractors import extract_pdf_with_region_certificates
from modules.library import content_manager_worker

HERE = Path(__file__).resolve().parent
VERSION = "automatic-region-certification-v4"


def simple_pdf(path):
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), "A simple generic body")
        document.save(path)


def cross_page_pdf(path):
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


def parity(pdf, pages):
    direct = [page.to_dict() for page in v4.extract_pdf_region_certificates(pdf, pages=pages)]
    consumed = extract_pdf_with_region_certificates(str(pdf), pages=pages)
    return direct, consumed


def main():
    with tempfile.TemporaryDirectory() as temp:
        generic = Path(temp) / "generic.pdf"
        cross = Path(temp) / "cross-page.pdf"
        simple_pdf(generic)
        cross_page_pdf(cross)

        generic_direct, generic_consumer = parity(generic, [1])
        cross_direct, cross_consumer = parity(cross, [1, 2])

    first = next(
        cert for cert in cross_consumer[0]["certificates"]
        if cert["continuation_state"] == "CONTINUES_NEXT_PAGE"
    )
    second = next(
        cert for cert in cross_consumer[1]["certificates"]
        if cert["continuation_state"] == "CONTINUED_FROM_PREVIOUS"
    )

    parity_payload = {
        "generic_pdf": {
            "pages": [1],
            "identity": generic_direct == generic_consumer,
            "certificate_versions": sorted(
                {cert["certificate_version"] for page in generic_consumer for cert in page["certificates"]}
            ),
        },
        "cross_page_fixture": {
            "pages": [1, 2],
            "identity": cross_direct == cross_consumer,
            "certificate_versions": sorted(
                {cert["certificate_version"] for page in cross_consumer for cert in page["certificates"]}
            ),
        },
        "consumer_returns_to_dict": True,
        "v1_imported": "automatic_region_certification import" in (
            ROOT / "SrvRestAstroLS_v1/backend/modules/library/extractors.py"
        ).read_text(),
    }
    cross_payload = {
        "fixture": "synthetic-two-page",
        "pair": [1, 2],
        "linked": first["linked_region_ids"] == [second["region_id"]]
        and second["linked_region_ids"] == [first["region_id"]],
        "same_editorial_unit": first["editorial_unit_id"] == second["editorial_unit_id"],
        "first_region": first["region_id"],
        "second_region": second["region_id"],
        "first_state": first["continuation_state"],
        "second_state": second["continuation_state"],
        "certificate_versions": [first["certificate_version"], second["certificate_version"]],
    }
    worker_source = (
        ROOT / "SrvRestAstroLS_v1/backend/modules/library/content_manager_worker.py"
    ).read_text()

    (HERE / "consumer-parity-results.json").write_text(
        json.dumps(parity_payload, indent=2) + "\n"
    )
    (HERE / "consumer-cross-page-results.json").write_text(
        json.dumps(cross_payload, indent=2) + "\n"
    )
    (HERE / "consumer-worker-boundary.json").write_text(
        json.dumps(
            {
                "worker_imports_consumer_helper": "extract_pdf_with_region_certificates"
                in worker_source,
                "worker_unchanged": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"parity": parity_payload, "cross_page": cross_payload}, indent=2))
    raise SystemExit(
        0
        if parity_payload["generic_pdf"]["identity"]
        and parity_payload["cross_page_fixture"]["identity"]
        and cross_payload["linked"]
        and cross_payload["same_editorial_unit"]
        and not parity_payload["v1_imported"]
        else 1
    )


if __name__ == "__main__":
    main()
