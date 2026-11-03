"""Run the independent source+annotation validator before sealing."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))

from modules.library.annotation_preseal_validation import validate  # noqa: E402

OUT = Path(__file__).resolve().parent


def main():
    inventory = json.loads((OUT / "holdout-source-inventory.json").read_text())
    definition = json.loads((OUT / "holdout-definition.json").read_text())
    result = validate(inventory, definition)
    (OUT / "holdout-annotation-validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(result["status"], "errors=", len(result["errors"]),
          "warnings=", len(result["warnings"]))
    if result["status"] != "PASS":
        for error in result["errors"][:40]:
            print(error)


if __name__ == "__main__":
    main()
