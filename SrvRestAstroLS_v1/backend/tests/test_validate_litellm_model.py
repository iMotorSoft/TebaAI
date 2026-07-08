from __future__ import annotations

import asyncio

from scripts import validate_litellm_model


def test_model_config_never_prints_api_key(monkeypatch, capsys) -> None:
    secret = "sk-test-secret-that-must-never-appear"
    monkeypatch.setattr(validate_litellm_model.globalVar, "LITELLM_API_KEY", secret)
    monkeypatch.setattr(
        validate_litellm_model.globalVar,
        "RESEARCH_CONVERSATION_MODEL",
        "test-model-alias",
    )

    result = asyncio.run(validate_litellm_model.test_model_config())
    output = capsys.readouterr().out

    assert secret not in output
    assert secret[:20] not in output
    assert "LiteLLM API Key configured: yes" in output
    assert result["api_key_configured"] is True
