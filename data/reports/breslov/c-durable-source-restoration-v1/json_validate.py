"""Strict JSON validation for every JSON artifact in this report directory."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main() -> None:
    rows = []
    for path in sorted(OUT.glob("*.json")):
        entry = {"file": path.name, "valid": False, "error": None}
        try:
            json.loads(path.read_text())
            entry["valid"] = True
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(entry)
    result = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "files": rows,
        "invalid": [row["file"] for row in rows if not row["valid"]],
        "all_valid": all(row["valid"] for row in rows),
    }
    (OUT / "json-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"count": len(rows), "all_valid": result["all_valid"],
                      "invalid": result["invalid"]}))


if __name__ == "__main__":
    main()
