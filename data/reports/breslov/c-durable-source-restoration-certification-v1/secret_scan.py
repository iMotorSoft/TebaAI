"""Scan certification evidence for persisted secrets and headers."""
from __future__ import annotations

import certlib as c


def main() -> None:
    audit = c.secret_audit()
    c.write_json("secret-scan.json", audit)
    print(
        f"files={audit['files_scanned']} findings={audit['finding_count']} -> "
        f"{audit['SECRET_SCAN']}"
    )
    if audit["SECRET_SCAN"] != "PASS":
        for item in audit["pattern_findings"] + audit["env_value_findings"]:
            print(f"FINDING {item}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
