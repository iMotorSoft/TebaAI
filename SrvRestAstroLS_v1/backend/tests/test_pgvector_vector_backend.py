import pytest

from modules.library.vector_backends.backends import PgvectorVectorBackend


@pytest.mark.asyncio
async def test_pgvector_health_reports_unavailable_table(monkeypatch):
    backend = PgvectorVectorBackend(table="missing_vector_table")
    monkeypatch.setattr("modules.library.vector_backends.backends._pg_config", lambda: {"dbname": "missing"})
    health = await backend.health()
    assert health["backend"] == "pgvector"
    assert health["status"] == "error"
    assert health["error"]
