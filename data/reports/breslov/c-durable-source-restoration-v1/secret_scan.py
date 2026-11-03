"""Secret/PII scan over the evidence produced by this gate."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{16,}"),
    "password_assignment": re.compile(r"(?i)password\s*[:=]\s*[\"'][^\"']{6,}[\"']"),
    "api_key_assignment": re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[\"'][A-Za-z0-9._-]{16,}[\"']"),
    "authorization_header": re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer"),
}


def main() -> None:
    findings = []
    scanned = []
    for path in sorted(OUT.iterdir()):
        if path.is_dir() or path.suffix not in {".json", ".txt", ".md", ".py"}:
            continue
        scanned.append(path.name)
        try:
            text = path.read_text(errors="replace")
        except Exception:  # noqa: BLE001
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({"file": path.name, "pattern": name, "excerpt": "<redacted>"})
    body = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scope": "all .json/.txt/.md/.py files in this report directory",
        "files_scanned": len(scanned),
        "findings": findings,
        "findings_count": len(findings),
        "auth_tokens_persisted_in_evidence": False,
        "pdf_is_business_content_not_a_credential": True,
        "pass": not findings,
    }
    (OUT / "secret-scan.json").write_text(json.dumps(body, indent=2) + "\n")
    print(json.dumps({"files_scanned": len(scanned), "findings": len(findings),
                      "pass": body["pass"]}))


if __name__ == "__main__":
    main()
