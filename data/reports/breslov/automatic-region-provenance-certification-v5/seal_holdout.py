"""Seal the source-only safety holdout before the first certifier run."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    validation = json.loads(
        (OUT / "holdout-annotation-validation.json").read_text()
    )
    if validation["status"] != "PASS":
        raise SystemExit("annotation validation is not PASS")
    selection = json.loads((OUT / "holdout-selection.json").read_text())
    seal = {
        "status": "SEALED",
        "version": "automatic-region-provenance-certification-v5-holdout-v1",
        "scope": selection["scope"],
        "physical_pages": selection["physical_pages"],
        "page_count": selection["page_count"],
        "cross_page_positives": selection["cross_page_positives"],
        "cross_page_negatives": selection["cross_page_negatives"],
        "cross_page_negative_count": selection["cross_page_negative_count"],
        "annotation_validation": validation["status"],
        "definition_sha256": digest(OUT / "holdout-definition.json"),
        "inventory_sha256": digest(OUT / "holdout-source-inventory.json"),
        "selection_sha256": digest(OUT / "holdout-selection.json"),
        "validation_sha256": digest(OUT / "holdout-annotation-validation.json"),
    }
    (OUT / "holdout-seal.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2) + "\n"
    )
    print("SEALED", seal["page_count"], "pages")


if __name__ == "__main__":
    main()
