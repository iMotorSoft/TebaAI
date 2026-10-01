"""Exercise migration SQL on connection-local temporary rows only."""
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

import globalVar


@pytest.mark.asyncio
async def test_migration_preserves_duplicate_guards_without_cross_scope_collision():
    if globalVar.TEBAAI_ENV != "development" or not globalVar.POSTGRES_ENABLED:
        pytest.skip("DEV PostgreSQL required for isolated temporary-table migration test")
    migration = Path(__file__).parents[1] / "db/migrations/042_scope_legacy_source_uniqueness.sql"
    async with await psycopg.AsyncConnection.connect(globalVar.POSTGRES_DSN, connect_timeout=5) as conn:
        await conn.execute("CREATE TEMP TABLE hebrew_fidelity_documents(collection_id uuid,knowledge_scope_id uuid,source_sha256 text) ON COMMIT DROP")
        await conn.execute("CREATE UNIQUE INDEX uq_hebrew_fidelity_documents_collection_sha256 ON hebrew_fidelity_documents(collection_id,source_sha256)")
        collection, other_collection, primary, isolated = uuid4(), uuid4(), uuid4(), uuid4()

        async def insert(coll, scope, sha):
            await conn.execute("INSERT INTO hebrew_fidelity_documents VALUES(%s,%s,%s)", (coll, scope, sha))

        await insert(collection, primary, "same-pdf")
        with pytest.raises(psycopg.errors.UniqueViolation):
            async with conn.transaction():
                await insert(collection, isolated, "same-pdf")

        await conn.execute(migration.read_text().replace("library_documents", "hebrew_fidelity_documents"))
        await insert(collection, isolated, "same-pdf")
        with pytest.raises(psycopg.errors.UniqueViolation):
            async with conn.transaction():
                await insert(collection, isolated, "same-pdf")
        await insert(other_collection, isolated, "same-pdf")
        await insert(collection, isolated, "different-pdf")
        await insert(collection, None, "same-pdf")
        with pytest.raises(psycopg.errors.UniqueViolation):
            async with conn.transaction():
                await insert(collection, None, "same-pdf")
        await insert(collection, None, None)
        await insert(collection, None, None)
        await conn.rollback()
