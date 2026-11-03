"""Scoped, heuristic secret scan; findings never print matched secret values."""
import json
from pathlib import Path
import re

OUT = Path(__file__).parent
ROOT = OUT.resolve().parents[3]
SCOPED = [
    "SrvRestAstroLS_v1/backend/modules/library/content_manager_cleanup.py",
    "SrvRestAstroLS_v1/backend/modules/library/hybrid_search.py",
    "SrvRestAstroLS_v1/backend/modules/library/page_first_gateway.py",
    "SrvRestAstroLS_v1/backend/tests/test_content_manager_cleanup.py",
    "SrvRestAstroLS_v1/backend/tests/test_parallel_generation_safety_prerequisites.py",
]
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider_key": re.compile(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,})\b"),
    "credential_uri": re.compile(r"(?:postgres(?:ql)?|https?|redis)://[^\s/:]+:[^\s/@]+@"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    "literal_secret_assignment": re.compile(r'''(?i)["'](?:password|api_key|secret|access_token|refresh_token)["']\s*[:=]\s*["'][^"'\n]{8,}["']'''),
}


def main():
    files = [ROOT / name for name in SCOPED]
    files.extend(p for p in OUT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p.name not in {"secret-scan.json"})
    findings = []
    for path in sorted(set(files)):
        text = path.read_text()
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({"file": str(path.relative_to(ROOT)), "line": text.count("\n", 0, match.start()) + 1, "kind": kind})
    result = {"status": "PASS" if not findings else "FAIL", "files_scanned": len(set(files)),
              "scope": "five backend files plus this report directory; preexisting user files not scanned/modified",
              "method": "local heuristic regex scan; gitleaks/detect-secrets not installed; not a guarantee of absence",
              "findings": findings}
    (OUT / "secret-scan.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"], result["files_scanned"], "files;", len(findings), "findings")
    assert not findings


if __name__ == "__main__":
    main()
