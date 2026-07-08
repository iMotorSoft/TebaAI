"""Portable PASETO v4.public issue/verify primitives.

This module deliberately has no environment, HTTP, database, Console, or
TebaAI product dependencies. Applications inject keys and expected claims.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import time
from types import MappingProxyType
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pyseto import Key as PasetoKey
from pyseto import decode as paseto_decode
from pyseto import encode as paseto_encode


_KID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_RESERVED_CLAIMS = frozenset({"iss", "aud", "sub", "typ", "iat", "exp", "jti"})
_MAX_TOKEN_LENGTH = 32_768
_MAX_FOOTER_LENGTH = 512


class PasetoConfigurationError(ValueError):
    """Signer or verifier configuration is invalid."""


class PasetoTokenError(ValueError):
    """Token validation failed without exposing cryptographic details."""

    def __init__(self, code: str = "invalid_token") -> None:
        self.code = code
        super().__init__("PASETO token is invalid")


@dataclass(frozen=True)
class PasetoKeyPair:
    """Ed25519 PEM key pair for provisioning and tests."""

    key_id: str
    private_pem: str = field(repr=False)
    public_pem: str

    @classmethod
    def generate(cls, key_id: str) -> PasetoKeyPair:
        _validate_key_id(key_id)
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return cls(
            key_id=key_id,
            private_pem=private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8"),
            public_pem=public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8"),
        )


@dataclass(frozen=True)
class PasetoV4PublicSigner:
    """Fail-closed signer for one active Ed25519 key."""

    issuer: str
    audience: str
    key_id: str
    private_key_pem: str = field(repr=False)
    ttl_seconds: int = 900
    clock: Callable[[], float] = field(default=time, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validate_expected_text("issuer", self.issuer)
        _validate_expected_text("audience", self.audience)
        _validate_key_id(self.key_id)
        if type(self.ttl_seconds) is not int or self.ttl_seconds <= 0:
            raise PasetoConfigurationError("ttl_seconds must be a positive integer")
        _private_paseto_key(self.private_key_pem)

    def issue(
        self,
        *,
        subject: str,
        token_type: str,
        claims: Mapping[str, Any] | None = None,
    ) -> str:
        _validate_expected_text("subject", subject)
        _validate_expected_text("token_type", token_type)
        custom_claims = dict(claims or {})
        conflicts = _RESERVED_CLAIMS.intersection(custom_claims)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise PasetoConfigurationError(f"reserved claims cannot be overridden: {names}")

        now = int(self.clock())
        payload = {
            **custom_claims,
            "iss": self.issuer,
            "aud": self.audience,
            "sub": subject,
            "typ": token_type,
            "iat": now,
            "exp": now + self.ttl_seconds,
            "jti": str(uuid.uuid4()),
        }
        footer = json.dumps({"kid": self.key_id}, separators=(",", ":"))
        token = paseto_encode(
            _private_paseto_key(self.private_key_pem),
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            footer=footer.encode("utf-8"),
        )
        return token.decode("utf-8")


@dataclass(frozen=True)
class PasetoV4PublicVerifier:
    """Verifier with an injected multi-kid public keyring."""

    issuer: str
    audience: str
    token_type: str
    public_keys_by_id: Mapping[str, str] = field(repr=False)
    leeway_seconds: int = 30
    clock: Callable[[], float] = field(default=time, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validate_expected_text("issuer", self.issuer)
        _validate_expected_text("audience", self.audience)
        _validate_expected_text("token_type", self.token_type)
        if type(self.leeway_seconds) is not int or self.leeway_seconds < 0:
            raise PasetoConfigurationError("leeway_seconds must be a non-negative integer")
        if not self.public_keys_by_id:
            raise PasetoConfigurationError("public keyring cannot be empty")
        for key_id, public_pem in self.public_keys_by_id.items():
            _validate_key_id(key_id)
            _public_paseto_key(public_pem)
        object.__setattr__(
            self,
            "public_keys_by_id",
            MappingProxyType(dict(self.public_keys_by_id)),
        )

    def verify(self, token: str) -> dict[str, Any]:
        try:
            key_id = _extract_key_id(token)
            public_pem = self.public_keys_by_id.get(key_id)
            if public_pem is None:
                raise PasetoTokenError("unknown_key")
            decoded = paseto_decode(
                _public_paseto_key(public_pem),
                token.encode("utf-8"),
            )
            payload = json.loads(decoded.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                raise PasetoTokenError()
            self._validate_claims(payload)
            return {**payload, "_key_id": key_id}
        except PasetoTokenError:
            raise
        except Exception as exc:
            raise PasetoTokenError() from exc

    def _validate_claims(self, payload: Mapping[str, Any]) -> None:
        if payload.get("iss") != self.issuer:
            raise PasetoTokenError("invalid_issuer")
        if payload.get("aud") != self.audience:
            raise PasetoTokenError("invalid_audience")
        if payload.get("typ") != self.token_type:
            raise PasetoTokenError("invalid_type")
        if not isinstance(payload.get("sub"), str) or not payload["sub"].strip():
            raise PasetoTokenError("invalid_subject")

        iat = payload.get("iat")
        exp = payload.get("exp")
        jti = payload.get("jti")
        if type(iat) is not int or type(exp) is not int:
            raise PasetoTokenError("invalid_time")
        if not isinstance(jti, str):
            raise PasetoTokenError("invalid_jti")
        try:
            uuid.UUID(jti)
        except (ValueError, AttributeError) as exc:
            raise PasetoTokenError("invalid_jti") from exc

        now = int(self.clock())
        if iat > now + self.leeway_seconds:
            raise PasetoTokenError("issued_in_future")
        if exp <= iat:
            raise PasetoTokenError("invalid_time")
        if now > exp + self.leeway_seconds:
            raise PasetoTokenError("expired")


def validate_key_pair(private_key_pem: str, public_key_pem: str) -> None:
    """Fail when an Ed25519 private/public key pair is inconsistent."""
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as exc:
        raise PasetoConfigurationError("invalid Ed25519 key material") from exc
    if not isinstance(private_key, ed25519.Ed25519PrivateKey) or not isinstance(
        public_key,
        ed25519.Ed25519PublicKey,
    ):
        raise PasetoConfigurationError("PASETO v4.public requires Ed25519 keys")
    derived = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    configured = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived != configured:
        raise PasetoConfigurationError("private and public keys do not match")


def _extract_key_id(token: str) -> str:
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        raise PasetoTokenError()
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v4" or parts[1] != "public":
        raise PasetoTokenError()
    footer_encoded = parts[3]
    if not footer_encoded or len(footer_encoded) > _MAX_FOOTER_LENGTH:
        raise PasetoTokenError()
    try:
        padded = footer_encoded + "=" * (-len(footer_encoded) % 4)
        footer_raw = base64.b64decode(
            padded,
            altchars=b"-_",
            validate=True,
        )
        footer = json.loads(footer_raw.decode("utf-8"))
    except Exception as exc:
        raise PasetoTokenError() from exc
    if not isinstance(footer, dict) or set(footer) != {"kid"}:
        raise PasetoTokenError()
    key_id = footer.get("kid")
    if not isinstance(key_id, str):
        raise PasetoTokenError()
    try:
        _validate_key_id(key_id)
    except PasetoConfigurationError as exc:
        raise PasetoTokenError() from exc
    return key_id


def _private_paseto_key(private_pem: str) -> PasetoKey:
    try:
        return PasetoKey.new(
            version=4,
            purpose="public",
            key=private_pem.encode("utf-8"),
        )
    except Exception as exc:
        raise PasetoConfigurationError("invalid Ed25519 private key") from exc


def _public_paseto_key(public_pem: str) -> PasetoKey:
    try:
        return PasetoKey.new(
            version=4,
            purpose="public",
            key=public_pem.encode("utf-8"),
        )
    except Exception as exc:
        raise PasetoConfigurationError("invalid Ed25519 public key") from exc


def _validate_key_id(key_id: str) -> None:
    if not isinstance(key_id, str) or _KID_PATTERN.fullmatch(key_id) is None:
        raise PasetoConfigurationError("key_id must be a safe 1-128 character identifier")


def _validate_expected_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PasetoConfigurationError(f"{name} cannot be empty")
