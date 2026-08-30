from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from core.config import AppSettings
from modules.library.content_manager_repository import ClaimedJob,ContentTenantContext
from modules.library.content_manager_schemas import IngestionStage
from modules.library.page_first_gateway import E2EIsolationError,PostgresMilvusPageFirstGateway


def job(collection='tebaai_content_manager_e2e_v1'):
    return ClaimedJob(uuid4(),uuid4(),1,'w',datetime.now(timezone.utc),IngestionStage.CLAIMED,
        'Fixture','es','auto','content_page_first_v1','openai_text_embedding_3_small',collection,
        ContentTenantContext(uuid4(),uuid4(),uuid4(),uuid4()))


def test_e2e_write_defaults_disabled(monkeypatch):
    monkeypatch.delenv('TEBAAI_CONTENT_MANAGER_E2E_ENABLED',raising=False)
    assert AppSettings().content_manager_e2e_enabled is False


def test_e2e_config_accepts_explicit_dev_guard(monkeypatch):
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_E2E_ENABLED','true')
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256','a'*64)
    settings=AppSettings()
    assert settings.is_development and settings.content_manager_e2e_enabled
    assert settings.content_manager_e2e_scope=='breslov_e2e'
    assert settings.content_manager_e2e_collection!='tebaai_breslov_chunks_v1'


def test_production_never_enables_test_candidate_research(monkeypatch):
    monkeypatch.setenv('TEBAAI_ENV','production')
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_E2E_ENABLED','true')
    monkeypatch.setenv('TEBAAI_POSTGRES_AUTO_MIGRATE','false')
    monkeypatch.setenv('TEBAAI_JWT_SECRET','x'*32)
    with pytest.raises(ValueError,match="allowed only in development"):
        AppSettings()


def test_gateway_guard_rejects_primary_and_fixture_mismatch(monkeypatch):
    import modules.library.page_first_gateway as module
    monkeypatch.setattr(module,'TEBAAI_ENV','development')
    monkeypatch.setattr(module,'CONTENT_MANAGER_E2E_ENABLED',True)
    monkeypatch.setattr(module,'CONTENT_MANAGER_E2E_SCOPE','breslov_e2e')
    monkeypatch.setattr(module,'CONTENT_MANAGER_E2E_COLLECTION','tebaai_content_manager_e2e_v1')
    monkeypatch.setattr(module,'CONTENT_MANAGER_E2E_FIXTURE_SHA256','a'*64)
    gateway=PostgresMilvusPageFirstGateway(None)
    with pytest.raises(E2EIsolationError): gateway._assert_e2e(job('tebaai_breslov_chunks_v1'),'breslov_primary','a'*64)
    with pytest.raises(E2EIsolationError): gateway._assert_e2e(job(),'breslov_e2e','b'*64)
    gateway._assert_e2e(job(),'breslov_e2e','a'*64)


def test_primary_worker_is_default_off_and_requires_explicit_enablement(monkeypatch):
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_WORKER_SCOPE','breslov_primary')
    monkeypatch.delenv('TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED',raising=False)
    with pytest.raises(ValueError,match='PRIMARY_INGESTION_ENABLED'):
        AppSettings()


def test_production_primary_worker_requires_absolute_storage(monkeypatch):
    monkeypatch.setenv('TEBAAI_ENV','production')
    monkeypatch.setenv('TEBAAI_POSTGRES_AUTO_MIGRATE','false')
    monkeypatch.setenv('TEBAAI_JWT_SECRET','x'*32)
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_WORKER_SCOPE','breslov_primary')
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED','true')
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_STORAGE_DIR','relative/uploads')
    with pytest.raises(ValueError,match='absolute'):
        AppSettings()
    monkeypatch.setenv('TEBAAI_CONTENT_MANAGER_STORAGE_DIR','/var/lib/tebaai/uploads')
    assert AppSettings().content_manager_worker_scope == 'breslov_primary'


def test_gateway_primary_guard_is_explicit_and_mapping_bounded(monkeypatch):
    import modules.library.page_first_gateway as module
    monkeypatch.setattr(module,'CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED',True)
    monkeypatch.setattr(module,'MILVUS_COLLECTION_BRESLOV','tebaai_breslov_chunks_v1')
    primary=job('tebaai_breslov_chunks_v1')
    gateway=PostgresMilvusPageFirstGateway(None)
    gateway._assert_write_allowed(primary,'breslov_primary','a'*64)
    with pytest.raises(E2EIsolationError):
        gateway._assert_write_allowed(primary,'another_scope','a'*64)
