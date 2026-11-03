"""Filesystem snapshot of the approved external PDF and the managed durable copy.

Usage: capture_fs.py <label> <output.json>
Read-only: opening the files for hashing may update atime on some filesystems;
content identity is size + sha256, never atime.
"""
from __future__ import annotations

import sys

import certlib as c


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: capture_fs.py <label> <output.json>")
    label, output = sys.argv[1], sys.argv[2]
    payload = {
        "label": label,
        "captured_at": c.now(),
        "external": c.file_stat(c.EXTERNAL_SOURCE),
        "durable": c.file_stat(c.MANAGED_SOURCE),
        "note": (
            "atime may move on read access; mtime/ctime/inode/size/sha256 are the "
            "content-identity fields"
        ),
    }
    c.write_json(output, payload)
    print(
        f"{label}: external_sha={payload['external']['sha256']} "
        f"durable_sha={payload['durable']['sha256']} "
        f"durable_size={payload['durable']['size_bytes']}"
    )


if __name__ == "__main__":
    main()
