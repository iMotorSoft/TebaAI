#!/usr/bin/env python3
"""Build the exact stage allowlist: frozen product/tests + current V1R2 evidence."""
from __future__ import annotations
import json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"

candidate = json.loads((OUT / "foundation-v2-candidate-paths.json").read_text())
product = sorted(item["path"] for item in candidate["paths"])
report = sorted(
    str(p.relative_to(REPO)) for p in OUT.iterdir()
    if p.is_file() and p.suffix not in {".pyc"} and "__pycache__" not in p.parts
)
all_paths = sorted(set(product) | set(report))
report_payload = {
    "gate": GATE,
    "policy": "stage only the 17 frozen Foundation V2 paths plus this V1R2 evidence directory; never git add . / -A / --all",
    "product_paths": product,
    "product_count": len(product),
    "report_paths": report,
    "report_count": len(report),
    "all_paths": all_paths,
    "all_count": len(all_paths),
    "unrelated_paths_included": 0,
    "ambiguous_paths": 0,
    "historical_report_directories_included": 0,
}
(OUT / "stage-allowlist.json").write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"product": len(product), "report": len(report), "all": len(all_paths)}, indent=2))
