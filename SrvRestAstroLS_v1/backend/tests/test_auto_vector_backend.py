import pytest

from modules.library.vector_backends.backends import AutoVectorBackend, VectorHit


class Failing:
    async def health(self): return {"status": "error", "details": {}, "error": "down"}
    async def search(self, *args, **kwargs): raise RuntimeError("down")


class Working:
    async def health(self): return {"status": "ready", "details": {}, "error": None}
    async def search(self, *args, **kwargs):
        return [VectorHit("pgvector", "c", "d", 1, "es", .9, .1, "texto", {})]


@pytest.mark.asyncio
async def test_auto_falls_back_and_records_backend():
    backend = AutoVectorBackend(milvus=Failing(), pgvector=Working())
    hits = await backend.search("consulta", "breslov_test")
    assert len(hits) == 1
    assert backend.backend_used == "pgvector"
    assert backend.last_error == "milvus:RuntimeError"
