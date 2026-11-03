"""Deterministic evidence validation for the preflight remediation gate.

* Strict JSON parsing of every .json in the report directory.
* Contradiction test across gate.json, final-validation.json,
  durable-source-verification.json and the machine-readable block of REPORT.md.
* Secret scan over the remediation sources and evidence.

Usage: python verify_evidence.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
REPORT = OUT / "REPORT.md"

SECRET_PATTERNS = [
    re.compile(r"postgres(?:ql)?://[^\s\"']+:[^\s\"']+@", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
]

CANONICAL_KEYS = [
    "GATE",
    "RESULT",
    "PUBLICATION_PREFLIGHT_READY",
    "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2",
    "FOUNDATION_V2_PUBLISHED",
    "INDETERMINATE_DATATYPE_REMEDIATED",
    "TARGETED_V1R1_ERROR_NODES_REMAINING",
    "PUBLICATION_FIXTURE_ERRORS",
    "PAGE_FIRST_GATEWAY_FIX_PRESERVED",
    "ROLLBACK_FIX_PRESERVED",
    "APPROVED_EXTERNAL_SHA_MATCH",
    "DURABLE_SOURCE_PRESENT",
    "DURABLE_SOURCE_RESOLVABLE",
    "DURABLE_BYTES_MATCH_APPROVED",
    "AUTHENTICATED_ACCESS",
    "UNAUTHENTICATED_BLOCKED",
    "CURRENT_C_PRESERVED",
    "REPORT_CONTRADICTIONS",
    "INVALID_JSON_FILES",
    "POST_FREEZE_MODIFICATIONS",
    "COMMIT",
    "PUSH",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def report_block() -> dict[str, str]:
    if not REPORT.is_file():
        return {}
    values: dict[str, str] = {}
    for line in REPORT.read_text().splitlines():
        match = re.match(r"^([A-Z0-9_]{3,}) = (.*)$", line.strip())
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def main() -> None:
    # 1. Strict JSON validation.
    invalid = []
    files = sorted(OUT.glob("*.json"))
    for path in files:
        try:
            json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            invalid.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
    (OUT / "json-validation.json").write_text(
        json.dumps(
            {"files": [p.name for p in files], "count": len(files),
             "invalid": invalid, "invalid_count": len(invalid)},
            indent=2,
        )
        + "\n"
    )

    # 2. Contradiction test.
    gate = load(OUT / "gate.json")
    final = load(OUT / "final-validation.json")
    durable = load(OUT / "durable-source-verification.json")
    report = report_block()

    canonical = {
        "GATE": gate.get("gate"),
        "RESULT": gate.get("result"),
        "PUBLICATION_PREFLIGHT_READY": gate.get("PUBLICATION_PREFLIGHT_READY"),
        "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2": gate.get(
            "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2"
        ),
        "FOUNDATION_V2_PUBLISHED": gate.get("FOUNDATION_V2_PUBLISHED"),
        "INDETERMINATE_DATATYPE_REMEDIATED": gate.get("checks", {}).get(
            "INDETERMINATE_DATATYPE_REMEDIATED"
        ),
        "TARGETED_V1R1_ERROR_NODES_REMAINING": gate.get("checks", {}).get(
            "TARGETED_V1R1_ERROR_NODES_REMAINING"
        ),
        "PUBLICATION_FIXTURE_ERRORS": gate.get("checks", {}).get("PUBLICATION_FIXTURE_ERRORS"),
        "PAGE_FIRST_GATEWAY_FIX_PRESERVED": gate.get("checks", {}).get(
            "PAGE_FIRST_GATEWAY_FIX_PRESERVED"
        ),
        "ROLLBACK_FIX_PRESERVED": gate.get("checks", {}).get("ROLLBACK_FIX_PRESERVED"),
        "APPROVED_EXTERNAL_SHA_MATCH": durable["decision"]["APPROVED_EXTERNAL_SHA_MATCH"],
        "DURABLE_SOURCE_PRESENT": durable["decision"]["DURABLE_SOURCE_PRESENT"],
        "DURABLE_SOURCE_RESOLVABLE": durable["decision"]["DURABLE_SOURCE_RESOLVABLE"],
        "DURABLE_BYTES_MATCH_APPROVED": durable["decision"]["DURABLE_BYTES_MATCH_APPROVED"],
        "AUTHENTICATED_ACCESS": durable["decision"]["AUTHENTICATED_ACCESS"],
        "UNAUTHENTICATED_BLOCKED": durable["decision"]["UNAUTHENTICATED_BLOCKED"],
        "CURRENT_C_PRESERVED": gate.get("checks", {}).get("CURRENT_C_PRESERVED"),
        "REPORT_CONTRADICTIONS": gate.get("checks", {}).get("REPORT_CONTRADICTIONS"),
        "INVALID_JSON_FILES": gate.get("checks", {}).get("INVALID_JSON_FILES"),
        "POST_FREEZE_MODIFICATIONS": gate.get("checks", {}).get("POST_FREEZE_MODIFICATIONS"),
        "COMMIT": gate.get("COMMIT"),
        "PUSH": gate.get("PUSH"),
    }

    def normalize(value):
        if isinstance(value, bool):
            return "YES" if value else "NO"
        return str(value)

    expected = {key: normalize(canonical[key]) for key in CANONICAL_KEYS}

    contradictions = []
    for key in CANONICAL_KEYS:
        final_value = final.get("semantics", {}).get(key)
        if final_value is not None and normalize(final_value) != expected[key]:
            contradictions.append(
                {"field": key, "source": "final-validation.json",
                 "expected": expected[key], "actual": normalize(final_value)}
            )
        durable_value = durable["decision"].get(key)
        if durable_value is not None and normalize(durable_value) != expected[key]:
            contradictions.append(
                {"field": key, "source": "durable-source-verification.json",
                 "expected": expected[key], "actual": normalize(durable_value)}
            )
        report_value = report.get(key)
        if report_value is not None and report_value != expected[key]:
            contradictions.append(
                {"field": key, "source": "REPORT.md",
                 "expected": expected[key], "actual": report_value}
            )

    result = {
        "canonical": expected,
        "sources": ["gate.json", "final-validation.json",
                    "durable-source-verification.json", "REPORT.md"],
        "contradictions": contradictions,
        "contradiction_count": len(contradictions),
        "REPORT_CONTRADICTIONS": len(contradictions),
        "INVALID_JSON_FILES": len(invalid),
    }
    (OUT / "evidence-consistency-results.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    # 3. Secret scan over the remediation sources and evidence.
    hits = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name in {"secret-scan.json"}:
            continue
        if path.suffix in {".png", ".pdf", ".xml", ".bin"}:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                hits.append({"file": str(path.relative_to(OUT)), "pattern": pattern.pattern,
                             "match": match.group(0)[:40]})
    (OUT / "secret-scan.json").write_text(
        json.dumps({"files_scanned": len([p for p in OUT.rglob('*') if p.is_file()]),
                    "hits": hits, "result": "PASS" if not hits else "FAIL"}, indent=2)
        + "\n"
    )

    print(
        json.dumps(
            {
                "invalid_json": len(invalid),
                "contradictions": len(contradictions),
                "secret_hits": len(hits),
            }
        )
    )
    assert not invalid, "invalid JSON evidence"
    assert not contradictions, "report contradictions"
    assert not hits, "secret scan failed"


if __name__ == "__main__":
    main()
