import pytest

from modules.library.vector_backends.backends import MilvusVectorBackend


@pytest.mark.asyncio
async def test_milvus_ensure_loaded_timeout_is_explicit(monkeypatch):
    backend = MilvusVectorBackend("test_collection")
    monkeypatch.setattr(backend, "_connect", lambda: None)
    monkeypatch.setattr("modules.library.vector_backends.backends.utility.load_state", lambda _: "NotLoad")

    class FakeCollection:
        def __init__(self, *_): pass
        def load(self): pass

    monkeypatch.setattr("modules.library.vector_backends.backends.Collection", FakeCollection)
    health = await backend.ensure_loaded(timeout_seconds=0.01, poll_interval_seconds=0.001)
    assert health["status"] == "not_ready"
    assert health["details"]["load_requested"] is True
    assert health["details"]["timeout"] is True
