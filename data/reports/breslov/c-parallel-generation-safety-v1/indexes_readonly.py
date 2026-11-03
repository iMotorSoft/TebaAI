"""Supplemental local DEV schema-only probe. No migrations or lifecycle."""
import asyncio
import json
from pathlib import Path

import globalVar as g
from psycopg import AsyncConnection
from psycopg.rows import dict_row

OUT = Path(__file__).with_name("schema-index-inventory.json")
SQL = "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='library_documents' ORDER BY indexname"


async def main():
    assert not OUT.exists(), "Do not replace sealed evidence"
    assert g.TEBAAI_ENV == "development" and not g.is_tebaai_production()
    assert g.POSTGRES_HOST in {"127.0.0.1", "localhost"} and g.POSTGRES_DB == "tebaai"
    async with await AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row, connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=20000") as conn:
        rows = await (await conn.execute(SQL)).fetchall()
        await conn.rollback()
    OUT.write_text(json.dumps({"query": SQL, "read_only": True, "indexes": rows}, indent=2) + "\n")
    matches = [r for r in rows if r["indexname"] == "uq_library_documents_scope_collection_sha256"]
    assert len(matches) == 1
    assert "UNIQUE INDEX" in matches[0]["indexdef"]
    print(matches[0]["indexdef"])


if __name__ == "__main__":
    asyncio.run(main())
