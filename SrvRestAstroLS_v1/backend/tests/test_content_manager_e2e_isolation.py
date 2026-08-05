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
