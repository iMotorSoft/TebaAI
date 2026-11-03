"""Focused reproduction of the fixture IndeterminateDatatype defect.

Runs the exact jsonb_build_object fragment from
tests/test_generation_foundation.py::_create_synthetic inside a transaction
that is always rolled back. No persistent write.
"""

from __future__ import annotations

import asyncio
import json

import psycopg

import globalVar as g


async def probe(conn, label: str, sql: str, params: tuple):
    row = {"label": label, "sql": sql.strip(), "params": [repr(p) for p in params]}
    try:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row["result"] = await cur.fetchone()
            raise RuntimeError("rollback-probe")
    except RuntimeError:
        row["outcome"] = "OK"
    except psycopg.errors.IndeterminateDatatype as exc:
        row["outcome"] = "IndeterminateDatatype"
        row["exception_class"] = type(exc).__name__
        row["exception_message"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        row["outcome"] = "OTHER_ERROR"
        row["exception_class"] = type(exc).__name__
        row["exception_message"] = str(exc)
    return row


async def main() -> None:
    results = []
    async with await psycopg.AsyncConnection.connect(g.POSTGRES_DSN) as conn:
        results.append(
            await probe(
                conn,
                "buggy_untyped_marker",
                "SELECT jsonb_build_object('region_publication',"
                " jsonb_build_object('page_status', 'FULL', 'marker', %s))",
                ("OLDGENERATIONEVIDENCE",),
            )
        )
        results.append(
            await probe(
                conn,
                "typed_marker_text",
                "SELECT jsonb_build_object('region_publication',"
                " jsonb_build_object('page_status', 'FULL', 'marker', %s::text))",
                ("OLDGENERATIONEVIDENCE",),
            )
        )
        results.append(
            await probe(
                conn,
                "typed_marker_int",
                "SELECT jsonb_build_object('region_publication',"
                " jsonb_build_object('page_status', 'FULL', 'marker', %s::int))",
                ("12",),
            )
        )
        results.append(
            await probe(
                conn,
                "control_plain_select",
                "SELECT %s",
                ("OLDGENERATIONEVIDENCE",),
            )
        )
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
