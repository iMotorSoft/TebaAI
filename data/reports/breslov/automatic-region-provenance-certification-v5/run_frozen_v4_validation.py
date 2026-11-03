"""Regression: the pre-seal validator must still reject the frozen V4 defects."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.annotation_preseal_validation import validate  # noqa: E402

OUT = Path(__file__).resolve().parent
FROZEN = ROOT / "data/reports/breslov/v4-frozen-confirmation-consumer-boundary-v1"


def main():
    inventory = json.loads((FROZEN / "holdout-source-inventory.json").read_text())
    definition = json.loads((FROZEN / "holdout-definition.json").read_text())
    result = validate(inventory, definition)
    result["error_codes"] = dict(Counter(error["code"] for error in result["errors"]))
    (OUT / "frozen-v4-validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(result["status"], len(result["errors"]), result["error_codes"])


if __name__ == "__main__":
    main()
