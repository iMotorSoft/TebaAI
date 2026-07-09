#!/usr/bin/env python3
"""Read-only Milvus inventory probe. Lists collections, entities, schema."""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path

from pymilvus import Collection, connections, utility


def main() -> int:
    parser = argparse.ArgumentParser(description="Milvus Inventory Probe")
    parser.add_argument("--report-dir", required=True, type=Path)
    args = parser.parse_args()

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    connections.connect(alias="default", host="127.0.0.1", port=19530, timeout=30)
    all_collections = utility.list_collections()
    inventory: dict[str, dict] = {"all_collections": all_collections, "details": {}}

    for name in sorted(all_collections):
        info: dict = {"name": name, "exists": True}
        try:
            col = Collection(name)
            col.load()
            info["num_entities"] = col.num_entities
            info["schema_fields"] = [f.name for f in col.schema.fields]
            col.release()
        except Exception as exc:
            info["error"] = str(exc)[:150]
        inventory["details"][name] = info
        print(f"  {name}: {info.get('num_entities', 'error')} entities")

    connections.disconnect("default")

    # Check key collections
    prod = inventory["details"].get("tebaai_breslov_chunks_v1", {})
    if prod.get("num_entities"):
        c = prod["num_entities"]
        print(f"\n  Productive: {c} entities (expected 5102)")
        if c == 5102:
            print("  ✅ Count matches expected")
        else:
            print(f"  ⚠️ Mismatch: {c} vs 5102")

    hybrid = inventory["details"].get("tebaai_breslov_bookqa_v2_kitzur_test_pages_v1", {})
    if hybrid.get("num_entities"):
        print(f"  Hybrid test: {hybrid['num_entities']} entities")

    (report_dir / "milvus_collections_inventory.json").write_text(json.dumps(inventory, indent=2, default=str))
    print(f"\n  Report saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
