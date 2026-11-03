"""Path safety and permission verification for the durable source (read-only)."""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[4] / "SrvRestAstroLS_v1" / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from modules.library.durable_source import file_sha256, source_path

OUT = Path(__file__).resolve().parent
EXTERNAL = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
EXPECTED_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
C_DOCUMENT = UUID("ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa")


def describe(path: Path) -> dict:
    info = path.stat()
    return {
        "path": str(path),
        "owner": __import__("pwd").getpwuid(info.st_uid).pw_name,
        "group": __import__("grp").getgrgid(info.st_gid).gr_name,
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode_octal": oct(stat.S_IMODE(info.st_mode)),
        "is_symlink": path.is_symlink(),
        "read_by_service_user": os.access(path, os.R_OK),
    }


def main() -> None:
    target = source_path(C_DOCUMENT)
    root = target.parent.parent.parent
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    chain = []
    cursor = resolved_target
    while cursor != resolved_root and cursor.parent != cursor:
        chain.append({"component": str(cursor), "is_symlink": cursor.is_symlink()})
        cursor = cursor.parent

    body = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "canonical_durable_root": str(root),
        "resolved_durable_root": str(resolved_root),
        "canonical_target": str(target),
        "resolved_target": str(resolved_target),
        "inside_approved_durable_root": resolved_target.is_relative_to(resolved_root),
        "path_traversal": ".." in target.parts,
        "target_component_chain": chain,
        "symlink_escape": any(item["is_symlink"] for item in chain),
        "target_is_regular_file": target.is_file() and not target.is_symlink(),
        "external_source_path": str(EXTERNAL),
        "resolved_target_equals_external": resolved_target == EXTERNAL.resolve(),
        "durable_source_is_managed_copy": resolved_target != EXTERNAL.resolve(),
        "sha256": file_sha256(target) if target.is_file() else None,
        "sha_matches_approved": (file_sha256(target) == EXPECTED_SHA) if target.is_file() else False,
        "symlink_policy": "durable source must be a regular file with no symlinked components",
    }
    body["pass"] = (
        body["inside_approved_durable_root"]
        and not body["path_traversal"]
        and not body["symlink_escape"]
        and body["target_is_regular_file"]
        and body["durable_source_is_managed_copy"]
        and body["sha_matches_approved"]
    )
    (OUT / "path-safety.json").write_text(json.dumps(body, indent=2, allow_nan=False) + "\n")

    dir_mode = stat.S_IMODE(target.parent.stat().st_mode)
    file_mode = stat.S_IMODE(target.stat().st_mode)
    permissions = {
        "measured_at": body["measured_at"],
        "durable_root": describe(root),
        "sources_dir": describe(target.parent.parent),
        "document_dir": describe(target.parent),
        "durable_file": describe(target),
        "file_mode_octal": oct(file_mode),
        "file_group_or_other_writable": bool(file_mode & (stat.S_IWGRP | stat.S_IWOTH)),
        "directory_group_or_other_writable": bool(dir_mode & (stat.S_IWGRP | stat.S_IWOTH)),
        "service_user": os.environ.get("USER"),
        "service_can_read": os.access(target, os.R_OK),
        "global_permissions_loosened_for_gate": False,
        "acceptable": os.access(target, os.R_OK) and not (file_mode & (stat.S_IWGRP | stat.S_IWOTH)),
    }
    (OUT / "permissions.json").write_text(json.dumps(permissions, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"path_safety": body["pass"], "file_mode": oct(file_mode),
                      "service_can_read": permissions["service_can_read"]}))


if __name__ == "__main__":
    main()
