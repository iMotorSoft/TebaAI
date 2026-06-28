from __future__ import annotations

from unittest.mock import patch

import pytest
import jwt as pyjwt

from modules.auth.tokens import create_access_token, decode_access_token, generate_refresh_token


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch("modules.auth.tokens.get_settings") as mock:
        s = mock.return_value
        s.auth_jwt_secret.get_secret_value.return_value = "test-secret-key"
        s.auth_jwt_algorithm = "HS256"
        s.auth_access_token_ttl_minutes = 15
        s.auth_issuer = "tebaai-api"
        s.auth_audience = "tebaai-web"
        yield


class TestAccessToken:
    def test_create_and_decode(self) -> None:
        token = create_access_token(user_id="user-123", role="admin")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert payload["iss"] == "tebaai-api"
        assert payload["aud"] == "tebaai-web"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert "nbf" in payload

    def test_requires_access_type(self) -> None:
        s = _get_patched_settings()
        payload = {
            "sub": "user-1",
            "type": "refresh",
            "jti": "abc",
            "role": "admin",
            "iat": 1000000,
            "nbf": 1000000,
            "exp": 9999999999,
            "iss": "tebaai-api",
            "aud": "tebaai-web",
        }
        token = pyjwt.encode(payload, "test-secret-key", algorithm="HS256")
        with pytest.raises(ValueError, match="not an access token"):
            decode_access_token(token)

    def test_invalid_signature(self) -> None:
        with patch("modules.auth.tokens.get_settings") as mock:
            s = mock.return_value
            s.auth_jwt_secret.get_secret_value.return_value = "real-secret"
            s.auth_access_token_ttl_minutes = 15
            s.auth_jwt_algorithm = "HS256"
            s.auth_issuer = "tebaai-api"
            s.auth_audience = "tebaai-web"
            token = create_access_token("u1", "admin")

        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_access_token(token)

    def test_wrong_issuer(self) -> None:
        s = _get_patched_settings()
        payload = {
            "sub": "u1", "type": "access", "jti": "x",
            "role": "viewer", "iat": 1000000, "nbf": 1000000,
            "exp": 9999999999, "iss": "wrong-issuer", "aud": "tebaai-web",
        }
        token = pyjwt.encode(payload, "test-secret-key", algorithm="HS256")
        with pytest.raises(ValueError):
            decode_access_token(token)

    def test_wrong_audience(self) -> None:
        s = _get_patched_settings()
        payload = {
            "sub": "u1", "type": "access", "jti": "x",
            "role": "viewer", "iat": 1000000, "nbf": 1000000,
            "exp": 9999999999, "iss": "tebaai-api", "aud": "wrong-aud",
        }
        token = pyjwt.encode(payload, "test-secret-key", algorithm="HS256")
        with pytest.raises(ValueError):
            decode_access_token(token)


class TestRefreshToken:
    def test_generate_returns_two_parts(self) -> None:
        raw, hashed = generate_refresh_token()
        assert isinstance(raw, str)
        assert isinstance(hashed, str)
        assert len(raw) > 20
        assert len(hashed) == 64  # sha256 hexdigest

    def test_hash_is_deterministic(self) -> None:
        raw, hashed1 = generate_refresh_token()
        import hashlib
        hashed2 = hashlib.sha256(raw.encode()).hexdigest()
        assert hashed1 == hashed2

    def test_tokens_are_unique(self) -> None:
        raw1, h1 = generate_refresh_token()
        raw2, h2 = generate_refresh_token()
        assert raw1 != raw2
        assert h1 != h2

    def test_no_password_in_token(self) -> None:
        raw, _ = generate_refresh_token()
        assert "password" not in raw
        assert "secret" not in raw


def _get_patched_settings():
    s = type("Settings", (), {})()
    s.auth_jwt_secret = type("Secret", (), {"get_secret_value": lambda: "test-secret-key"})()
    s.auth_jwt_algorithm = "HS256"
    s.auth_issuer = "tebaai-api"
    s.auth_audience = "tebaai-web"
    return s
