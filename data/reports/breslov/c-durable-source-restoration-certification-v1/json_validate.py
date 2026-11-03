"""Strict JSON validation of every evidence file."""
from __future__ import annotations

import certlib as c


def main() -> None:
    audit = c.strict_json_audit()
    c.write_json("json-validation.json", audit)
    print(
        f"valid={audit['valid_count']} invalid={audit['invalid_count']} -> "
        f"{'PASS' if audit['ALL_JSON_VALID'] else 'FAIL'}"
    )
    if not audit["ALL_JSON_VALID"]:
        for item in audit["invalid_files"]:
            print(f"INVALID {item}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
