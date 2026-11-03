"""Consumer boundary parity: V5 direct output == opt-in consumer output."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v5 import (  # noqa: E402
    extract_pdf_region_certificates as v5_extract,
)
from modules.library.extractors import extract_pdf_with_region_certificates  # noqa: E402

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"


def main():
    pages = [108, 109, 206, 207]
    direct = [page.to_dict() for page in v5_extract(SOURCE, pages=pages)]
    consumed = extract_pdf_with_region_certificates(SOURCE, pages=pages)
    identical = consumed == direct
    versions = {
        cert["certificate_version"]
        for page in consumed for cert in page["certificates"]
    }
    by_page = {page["pdf_page"]: page for page in consumed}
    first = next(
        cert for cert in by_page[206]["certificates"]
        if cert["note_number"] == 5 and cert["linked_region_ids"]
    )
    second = next(
        cert for cert in by_page[207]["certificates"]
        if cert["note_number"] == 5 and cert["linked_region_ids"]
    )
    positive_ok = bool(
        first["identity_state"] == "IDENTITY_PROVEN"
        and second["identity_state"] == "IDENTITY_PROVEN"
        and first["editorial_unit_id"] == second["editorial_unit_id"]
        and tuple(first["linked_region_ids"]) == (second["region_id"],)
        and tuple(second["linked_region_ids"]) == (first["region_id"],)
    )
    negative_ok = not any(
        cert["linked_region_ids"]
        for cert in by_page[108]["certificates"]
        if cert["note_number"] == 8
    )
    output = {
        "status": "PASS" if identical and versions == {"automatic-region-certification-v5"}
        and positive_ok and negative_ok else "FAIL",
        "consumer_equals_direct_v5": identical,
        "versions": sorted(versions),
        "positive_206_207_preserved": positive_ok,
        "negative_108_109_not_linked": negative_ok,
        "pages": pages,
    }
    (OUT / "consumer-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
