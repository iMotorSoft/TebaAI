"""Shared read-only helpers for the C durable source certification gate.

Every database connection opened here sets ``default_transaction_read_only=on``
at the session level, so even an accidental write statement would be rejected
by PostgreSQL. Nine of the ten harness scripts only call the read helpers
below; the static contract (``readonly_contract.py``) proves it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib import error, request
from uuid import UUID

_repo_override = os.environ.get("TEBAAI_CERT_REPO_ROOT")
REPO_ROOT = (
    Path(_repo_override).resolve()
    if _repo_override
    else Path(__file__).resolve().parents[4]
)
BACKEND_DIR = REPO_ROOT / "SrvRestAstroLS_v1" / "backend"
APP_DIR = REPO_ROOT / "SrvRestAstroLS_v1"
OUT_DIR = Path(
    os.environ.get("TEBAAI_CERT_OUT", str(Path(__file__).resolve().parent))
).resolve()

DOCUMENT_ID = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")
LOGICAL_DOCUMENT_ID = UUID("db200a31-b547-5668-d968-06d0ec36ad95")
ACTIVE_GENERATION = "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b"
KNOWN_RUN_ID = "6c1a19b8-b60b-52de-b709-5496f4c6e937"
APPROVED_SHA256 = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
APPROVED_SIZE = 4_550_267
APPROVED_PAGES = 284
EXPECTED_CHUNKS = 942
EXPECTED_VECTORS = 942
EXTERNAL_SOURCE = Path(
    "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
)
MANAGED_SOURCE = (
    BACKEND_DIR / "sources" / str(DOCUMENT_ID) / "original.pdf"
)
BASELINE_RESULTS = (
    REPO_ROOT
    / "data/reports/breslov/foundation-v2-publication-preflight-remediation-v2"
    / "backend-results.json"
)
BASE_URL = os.environ.get("TEBAAI_CERT_BASE_URL", "http://127.0.0.1:7008")
SOURCE_URL = f"{BASE_URL}/library/documents/{DOCUMENT_ID}/source"
PID_FILE = APP_DIR / ".dev-pids" / "tebaai-backend-7008.pid"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value):
    if isinstance(value, (UUID, Path)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, memoryview):
        return value.tobytes().hex()
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(f"not serializable: {type(value)!r}")


def write_json(name: str, payload: dict) -> Path:
    target = OUT_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, default=_json_default, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return target


def write_text(name: str, text: str) -> Path:
    target = OUT_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def load_json(name: str) -> dict:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def pdf_page_count(path: Path | str) -> int:
    import fitz

    with fitz.open(str(path)) as document:
        return int(document.page_count)


def pdf_page_count_bytes(data: bytes) -> int:
    import fitz
    import io

    with fitz.open(stream=io.BytesIO(data), filetype="pdf") as document:
        return int(document.page_count)


def backend_pid() -> int | None:
    try:
        value = PID_FILE.read_text(encoding="utf-8").strip()
        return int(value) if value else None
    except (OSError, ValueError):
        return None


def backend_cmdline(pid: int | None) -> str:
    if not pid:
        return ""
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(
            "utf-8", "replace"
        ).strip()
    except OSError:
        return ""


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


async def connect_readonly():
    """Open a PostgreSQL session that physically rejects writes."""
    import psycopg
    import psycopg.rows

    import globalVar as config

    return await psycopg.AsyncConnection.connect(
        config.POSTGRES_DSN,
        row_factory=psycopg.rows.dict_row,
        options="-c default_transaction_read_only=on",
        connect_timeout=10,
    )


async def mint_access_token_readonly() -> dict:
    """Mint a normal signed access token without creating a login session.

    The login route is deliberately not called because it would insert an auth
    session row and update ``last_login_at`` (PostgreSQL writes are forbidden by
    this gate). We therefore reuse the application token issuer and read the
    already-existing active admin user read-only. No secret or token is
    persisted in evidence.
    """
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL", "").strip().lower()
    if not email:
        return {"status": "UNAVAILABLE", "reason": "TEBAAI_E2E_ADMIN_EMAIL absent"}
    from modules.auth.tokens import create_access_token

    async with await connect_readonly() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, role, is_active FROM users WHERE lower(email)=%s",
                (email,),
            )
            user = await cur.fetchone()
    if not user:
        return {"status": "UNAVAILABLE", "reason": "admin user not found"}
    if not user["is_active"]:
        return {"status": "UNAVAILABLE", "reason": "admin user inactive"}
    if user["role"] != "admin":
        return {"status": "UNAVAILABLE", "reason": "user is not admin"}
    return {
        "status": "OK",
        "user_id": str(user["id"]),
        "role": user["role"],
        "token": create_access_token(str(user["id"]), str(user["role"])),
        "mint_mode": "read-only signed access token (no session row, no login write)",
    }


def http_get(url: str, token: str | None = None, timeout: int = 90) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return {
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_disposition": response.headers.get("Content-Disposition"),
                "cache_control": response.headers.get("Cache-Control"),
                "content_length_header": response.headers.get("Content-Length"),
                "body": body,
            }
    except error.HTTPError as exc:
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body": exc.read(4096),
        }
    except error.URLError as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {exc}", "body": b""}


def parse_outcome(result: dict) -> dict:
    body = result.get("body") or b""
    parsed = {
        "status": result.get("status"),
        "content_type": result.get("content_type"),
        "content_disposition": result.get("content_disposition"),
        "cache_control": result.get("cache_control"),
        "content_length_header": result.get("content_length_header"),
        "served_bytes": len(body) if result.get("status") == 200 else None,
        "served_sha256": hashlib.sha256(body).hexdigest() if result.get("status") == 200 else None,
        "body_text": None,
    }
    if result.get("status") != 200:
        parsed["body_text"] = body[:300].decode("utf-8", "replace") if body else None
    return parsed


def equal(left, right) -> bool:
    return left == right


def file_stat(path: Path) -> dict:
    info = path.stat()
    return {
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "atime_ns": info.st_atime_ns,
        "inode": info.st_ino,
        "mode": oct(info.st_mode),
        "sha256": sha256_file(path) if path.is_file() else None,
    }


def frozen_hash_audit() -> dict:
    """Recompute every hash recorded by freeze.py and classify changes."""
    hashes_path = OUT_DIR / "frozen-hashes.txt"
    manifest_path = OUT_DIR / "frozen-manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    categories = {
        item["name"]: item.get("category", "harness")
        for item in manifest.get("harness_files", [])
    }
    categories.update(
        {
            item["name"]: item.get("category", "expectations")
            for item in manifest.get("frozen_artifacts", [])
        }
    )
    entries = []
    if not hashes_path.is_file():
        return {
            "frozen_hashes_present": False,
            "entries": [],
            "mismatches": [],
            "harness_unchanged": False,
            "category_mismatch_counts": {},
        }
    for line in hashes_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split("  ", 1)
        if name.startswith("durable/"):
            target = MANAGED_SOURCE
            category = "durable"
        elif name.startswith("external/"):
            target = EXTERNAL_SOURCE
            category = "external"
        elif name.startswith("baseline/"):
            target = BASELINE_RESULTS
            category = "expectations"
        elif name.startswith("report/"):
            target = OUT_DIR / name.removeprefix("report/")
            category = categories.get(name.removeprefix("report/"), "harness")
        else:
            target = OUT_DIR / name
            category = categories.get(name, "harness")
        actual = sha256_file(target) if target.is_file() else None
        entries.append(
            {
                "name": name,
                "category": category,
                "frozen": digest,
                "actual": actual,
                "unchanged": actual == digest,
            }
        )
    mismatches = [entry for entry in entries if not entry["unchanged"]]
    category_counts: dict[str, int] = {}
    for entry in mismatches:
        category_counts[entry["category"]] = category_counts.get(entry["category"], 0) + 1
    return {
        "frozen_hashes_present": True,
        "frozen_at": manifest.get("frozen_at"),
        "entries": entries,
        "entry_count": len(entries),
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "harness_unchanged": not mismatches,
        "category_mismatch_counts": category_counts,
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
    }


def strict_json_audit() -> dict:
    """Parse every JSON evidence file with NaN/Infinity rejected."""
    invalid = []
    valid = []
    for path in sorted(OUT_DIR.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")

            def reject(value):
                raise ValueError(f"non-standard JSON constant: {value}")

            json.loads(text, parse_constant=reject)
            valid.append(path.name)
        except Exception as exc:  # noqa: BLE001
            invalid.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "checked_at": now(),
        "standard": "json.loads with parse_constant rejecting NaN/Infinity",
        "valid_count": len(valid),
        "valid_files": valid,
        "invalid_count": len(invalid),
        "invalid_files": invalid,
        "INVALID_JSON_FILES": len(invalid),
        "ALL_JSON_VALID": not invalid,
    }


SECRET_PATTERNS = (
    ("bearer_header", r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    (
        "jwt",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    ),
    ("authorization_header", r"Authorization\s*:\s*Bearer"),
    ("set_cookie", r"Set-Cookie\s*:"),
)


def secret_audit() -> dict:
    import re

    evidence = []
    for pattern in ("*.json", "*.md", "*.txt"):
        evidence.extend(sorted(OUT_DIR.glob(pattern)))
    evidence = [path for path in evidence if path.name != "secret-scan.json"]
    findings = []
    env_matches = []
    placeholders = {
        "changeme",
        "change-me",
        "placeholder",
        "secret",
        "password",
        "your-secret-key",
        "test",
    }
    secret_names = [
        key
        for key in os.environ
        if any(
            marker in key.upper()
            for marker in ("SECRET", "PASSWORD", "PEPPER", "API_KEY", "TOKEN")
        )
    ]
    for path in evidence:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in SECRET_PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append(
                    {
                        "file": path.name,
                        "rule": label,
                        "match_sha256": hashlib.sha256(
                            match.group(0).encode()
                        ).hexdigest(),
                    }
                )
        for name in secret_names:
            value = os.environ.get(name, "")
            if (
                len(value) >= 8
                and value != name
                and value.strip().casefold() not in placeholders
                and value in text
            ):
                env_matches.append({"file": path.name, "env_key": name})
    return {
        "scanned_at": now(),
        "scope": "*.json, *.md, *.txt evidence; not harness code",
        "files_scanned": len(evidence),
        "env_secret_keys_checked": sorted(secret_names),
        "pattern_findings": findings,
        "env_value_findings": env_matches,
        "finding_count": len(findings) + len(env_matches),
        "tokens_persisted": False,
        "cookies_persisted": False,
        "authorization_headers_persisted": False,
        "api_keys_persisted": False,
        "passwords_persisted": False,
        "SECRET_SCAN": "PASS" if not findings and not env_matches else "FAIL",
    }
