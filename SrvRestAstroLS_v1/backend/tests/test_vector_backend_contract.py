import pytest

from modules.library.vector_backends import DisabledVectorBackend, VectorHit, VectorSearchBackend


@pytest.mark.asyncio
async def test_disabled_backend_implements_contract():
    backend = DisabledVectorBackend()
    assert isinstance(backend, VectorSearchBackend)
    health = await backend.health()
    assert health["status"] == "disabled"
    hits = await backend.search("consulta", "breslov_test")
    assert isinstance(hits, list)
    assert all(isinstance(hit, VectorHit) for hit in hits)
