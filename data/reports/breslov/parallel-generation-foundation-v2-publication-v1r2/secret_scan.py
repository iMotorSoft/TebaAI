#!/usr/bin/env python3
"""Scan candidate and report text for credentials/secrets."""
from __future__ import annotations
import json, pathlib, re

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"
PATTERNS = {
    "database_password": re.compile(r"TodaRaba"),
    "db_pass_assignment": re.compile(r"DB_PG_PASS\s*=\s*\S+"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "api_key_literal": re.compile(r"api[_-]?key\s*[:=]\s*['\"][^'\"]{16,}['\"]", re.I),
    "password_literal": re.compile(r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I),
    "secret_literal": re.compile(r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I),
}
SKIP = {"secret-scan.json", "secret_scan.py"}

candidate = json.loads((OUT / "foundation-v2-candidate-paths.json").read_text())
targets = [(REPO / item["path"], item["path"]) for item in candidate["paths"]]
targets += [(p, str(p.relative_to(REPO))) for p in OUT.iterdir()
            if p.is_file() and p.suffix in {".py", ".json", ".txt", ".md", ".xml"}
            and p.name not in SKIP]

matches = []
scanned = 0
for path, rel in targets:
    if not path.is_file():
        continue
    scanned += 1
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                matches.append({"path": rel, "line": number, "pattern": name,
                                "snippet": line.strip()[:240]})
report = {
    "gate": GATE, "scanned_files": scanned, "patterns": sorted(PATTERNS),
    "matches": matches, "SECRETS_FOUND": len(matches),
    "PASS": len(matches) == 0,
}
(OUT / "secret-scan.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"scanned": scanned, "matches": len(matches), "PASS": report["PASS"]}, indent=2))
