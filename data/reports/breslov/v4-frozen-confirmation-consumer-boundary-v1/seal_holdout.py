"""Seal the new holdout, annotation, evaluator and frozen V4 inputs."""
import hashlib
import json
from pathlib import Path
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PATHS = [
    OUT / "collect_previous_pages.py",
    OUT / "previous-holdout-page-inventory.json",
    OUT / "inspect_source.py",
    OUT / "holdout-source-inventory.json",
    OUT / "annotate_holdout.py",
    OUT / "holdout-annotation-sanity.json",
    OUT / "holdout-definition.json",
    OUT / "evaluate_holdout.py",
    ROOT / "SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v4.py",
    ROOT / "SrvRestAstroLS_v1/backend/modules/library/region_markdown_provenance.py",
    ROOT / "SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v4.py",
]


def main():
    seal = OUT / "holdout-sealed-hash.txt"
    sealed_at = OUT / "holdout-sealed-at.json"
    assert not seal.exists() and not sealed_at.exists(), "Holdout already sealed"
    assert not (OUT / "holdout-first-open.json").exists(), "Holdout already opened"
    lines = []
    digests = {}
    for path in sorted(PATHS):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests[str(path.relative_to(ROOT))] = digest
        lines.append(f"{digest}  {path.relative_to(ROOT)}")
    seal.write_text("\n".join(lines) + "\n")
    sealed_at.write_text(json.dumps({
        "sealed_unix": time.time(),
        "seal_sha256": hashlib.sha256(seal.read_bytes()).hexdigest(),
        "digests": digests,
        "v4_frozen": True,
        "holdout_definition_frozen": True,
        "evaluator_frozen": True,
        "single_open_required": True,
    }, indent=2) + "\n")
    print(hashlib.sha256(seal.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
