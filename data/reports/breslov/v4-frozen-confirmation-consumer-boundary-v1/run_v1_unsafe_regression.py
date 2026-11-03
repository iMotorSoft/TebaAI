"""Re-run the five V1 unsafe certifications through frozen V4."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))

from modules.library.automatic_region_certification_v4 import (
    extract_pdf_region_certificates,
)

PDF = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
OUT = Path(__file__).resolve().parent / "v1-unsafe-regression-results.json"

CASES = [
    {"page": 80, "region_id": "region-cbabcc634980c627e2d2280b"},
    {"page": 80, "region_id": "region-5c800da9132cbc4511454e79"},
    {"page": 140, "region_id": "region-4208ec6381b2a5e29276d00e"},
    {"page": 200, "region_id": "region-9a246f83b66e789817d4e727"},
    {"page": 200, "region_id": "region-6bcfd2e337fb9ad3f7934fe4"},
]

pages = sorted({case["page"] for case in CASES})
extracted = {
    page.provenance.pdf_page: page.to_dict()
    for page in extract_pdf_region_certificates(PDF, pages=pages)
}

results = []
for case in CASES:
    tokens = {
        region["region_id"]: region
        for region in extracted[case["page"]]["certificates"]
    }
    actual = tokens.get(case["region_id"])
    results.append(
        {
            **case,
            "v1_decision": "CERTIFIED",
            "v4_decision": actual["provenance_status"] if actual else "REGION_MISSING",
            "v4_quality": actual["quality_status"] if actual else "REGION_MISSING",
            "v4_note_number": actual.get("note_number") if actual else None,
            "v4_certificate_version": actual.get("certificate_version") if actual else None,
            "passed": bool(
                actual
                and actual["provenance_status"] == "UNRESOLVED"
                and actual.get("note_number") is None
                and actual.get("certificate_version")
                == "automatic-region-certification-v4"
            ),
        }
    )

payload = {
    "gate": "PASS" if all(item["passed"] for item in results) else "FAIL",
    "cases": results,
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(0 if payload["gate"] == "PASS" else 1)
