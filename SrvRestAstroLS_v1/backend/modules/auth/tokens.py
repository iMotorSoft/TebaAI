from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from core.config import get_settings


# ── Access token (JWT) ────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.auth_access_token_ttl_minutes)
    payload = {
        "sub": user_id,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "role": role,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
    }
    return jwt.encode(
        payload,
        settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=[settings.auth_jwt_algorithm],
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            options={
                "require": ["sub", "type", "exp", "iss", "aud"],
                "verify_exp": True,
            },
        )
    except jwt.InvalidTokenError:
        raise ValueError("Invalid or expired token")

    if payload.get("type") != "access":
        raise ValueError("Token is not an access token")

    return payload


# ── Refresh token (opaque) ────────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, h
