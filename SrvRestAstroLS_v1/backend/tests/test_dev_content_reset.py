from types import SimpleNamespace

import pytest

from infrastructure.postgres.dev_content_reset import (
    CONTENT_TABLES, PRESERVED_TABLES, assert_preserved, deletion_order, guard_config,
)


def config(**overrides):
    values = dict(ENV='development', is_tebaai_production=lambda: False,
                  POSTGRES_HOST='localhost', POSTGRES_DB='tebaai', POSTGRES_PORT=5432,
                  MILVUS_HOST='127.0.0.1', MILVUS_PORT=19530, MILVUS_URI='')
    values.update(overrides)
    return SimpleNamespace(**values)


def test_local_dev_only():
    guard_config(config())


@pytest.mark.parametrize('override', [
    {'ENV': 'production'}, {'ENV': 'staging'}, {'is_tebaai_production': lambda: True},
    {'POSTGRES_HOST': 'prod.example.com'}, {'POSTGRES_DB': 'team360'},
    {'POSTGRES_PORT': 5433}, {'MILVUS_HOST': 'prod.example.com'},
    {'MILVUS_PORT': 19531}, {'MILVUS_URI': 'http://127.0.0.1:19530'},
])
def test_remote_or_ambiguous_config_refused(override):
    with pytest.raises(ValueError):
        guard_config(config(**override))


def test_allowlists_disjoint_preserve_identity_and_configuration():
    assert not CONTENT_TABLES & PRESERVED_TABLES
    assert {'users', 'auth_identities', 'auth_sessions', 'schema_migrations',
            'organizations', 'workspaces', 'projects', 'knowledge_scopes',
            'library_collections_legacy'} <= PRESERVED_TABLES
    assert {'library_pages_v2', 'library_vector_embeddings_v2_dev',
            'content_manager_job_attempts', 'library_documents'} <= CONTENT_TABLES


def test_child_first_and_self_references():
    assert deletion_order({'documents', 'chunks', 'attempts'},
                          [('chunks', 'documents'), ('attempts', 'attempts')]) == ['attempts', 'chunks', 'documents']


def test_preserved_child_or_cycle_refused():
    with pytest.raises(ValueError):
        deletion_order({'content'}, [('users', 'content')])
    with pytest.raises(ValueError):
        deletion_order({'a', 'b'}, [('a', 'b'), ('b', 'a')])


def test_platform_digest_must_match():
    before = {'identity': 'local', 'schema_sha256': 'schema',
              'tables': {t: {'count': 1, 'sha256': 'same'} for t in PRESERVED_TABLES}}
    assert_preserved(before, before)
    after = {**before, 'tables': {**before['tables'], 'users': {'count': 1, 'sha256': 'changed'}}}
    with pytest.raises(ValueError):
        assert_preserved(before, after)
    with pytest.raises(ValueError):
        assert_preserved(before, {**before, 'schema_sha256': 'changed'})
