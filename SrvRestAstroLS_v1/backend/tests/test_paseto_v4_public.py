from __future__ import annotations

import json

import pytest
from pyseto import Key as PasetoKey
from pyseto import encode as paseto_encode

from modules.security.paseto_v4_public import (
    PasetoConfigurationError,
    PasetoKeyPair,
    PasetoTokenError,
    PasetoV4PublicSigner,
    PasetoV4PublicVerifier,
    validate_key_pair,
)


NOW = 1_800_000_000


@pytest.fixture
def key_pair() -> PasetoKeyPair:
    return PasetoKeyPair.generate("test-key-1")


@pytest.fixture
def signer(key_pair: PasetoKeyPair) -> PasetoV4PublicSigner:
    return PasetoV4PublicSigner(
        issuer="portable-test",
        audience="portable-api",
        key_id=key_pair.key_id,
        private_key_pem=key_pair.private_pem,
        ttl_seconds=300,
        clock=lambda: NOW,
    )


@pytest.fixture
def verifier(key_pair: PasetoKeyPair) -> PasetoV4PublicVerifier:
    return PasetoV4PublicVerifier(
        issuer="portable-test",
        audience="portable-api",
        token_type="access",
        public_keys_by_id={key_pair.key_id: key_pair.public_pem},
        clock=lambda: NOW,
    )


def test_issue_and_verify_round_trip(
    signer: PasetoV4PublicSigner,
    verifier: PasetoV4PublicVerifier,
) -> None:
    token = signer.issue(
        subject="user:123",
        token_type="access",
        claims={"role": "viewer"},
    )

    payload = verifier.verify(token)

    assert token.startswith("v4.public.")
    assert payload["sub"] == "user:123"
    assert payload["role"] == "viewer"
    assert payload["iat"] == NOW
    assert payload["exp"] == NOW + 300
    assert payload["_key_id"] == "test-key-1"


def test_reserved_claims_cannot_be_overridden(signer: PasetoV4PublicSigner) -> None:
    with pytest.raises(PasetoConfigurationError, match="reserved claims"):
        signer.issue(
            subject="user:123",
            token_type="access",
            claims={"iss": "attacker"},
        )


def test_unknown_kid_is_rejected_without_detail_leak(
    signer: PasetoV4PublicSigner,
    key_pair: PasetoKeyPair,
) -> None:
    token = signer.issue(subject="user:123", token_type="access")
    verifier = PasetoV4PublicVerifier(
        issuer="portable-test",
        audience="portable-api",
        token_type="access",
        public_keys_by_id={"other-key": key_pair.public_pem},
        clock=lambda: NOW,
    )

    with pytest.raises(PasetoTokenError) as error:
        verifier.verify(token)

    assert error.value.code == "unknown_key"
    assert str(error.value) == "PASETO token is invalid"
    assert "test-key-1" not in str(error.value)


@pytest.mark.parametrize(
    ("claim", "value", "error_code"),
    [
        ("iat", "not-an-int", "invalid_time"),
        ("exp", True, "invalid_time"),
        ("jti", "not-a-uuid", "invalid_jti"),
    ],
)
def test_invalid_claim_types_are_rejected(
    key_pair: PasetoKeyPair,
    verifier: PasetoV4PublicVerifier,
    claim: str,
    value: object,
    error_code: str,
) -> None:
    payload = {
        "iss": "portable-test",
        "aud": "portable-api",
        "sub": "user:123",
        "typ": "access",
        "iat": NOW,
        "exp": NOW + 300,
        "jti": "9a9480a0-bef6-4273-b99a-85523f55a334",
        claim: value,
    }
    token = _encode_raw(key_pair, payload)

    with pytest.raises(PasetoTokenError) as error:
        verifier.verify(token)

    assert error.value.code == error_code


def test_future_iat_is_rejected(
    key_pair: PasetoKeyPair,
    verifier: PasetoV4PublicVerifier,
) -> None:
    payload = {
        "iss": "portable-test",
        "aud": "portable-api",
        "sub": "user:123",
        "typ": "access",
        "iat": NOW + 31,
        "exp": NOW + 300,
        "jti": "9a9480a0-bef6-4273-b99a-85523f55a334",
    }

    with pytest.raises(PasetoTokenError) as error:
        verifier.verify(_encode_raw(key_pair, payload))

    assert error.value.code == "issued_in_future"


def test_expired_token_is_rejected(
    key_pair: PasetoKeyPair,
    verifier: PasetoV4PublicVerifier,
) -> None:
    payload = {
        "iss": "portable-test",
        "aud": "portable-api",
        "sub": "user:123",
        "typ": "access",
        "iat": NOW - 500,
        "exp": NOW - 31,
        "jti": "9a9480a0-bef6-4273-b99a-85523f55a334",
    }

    with pytest.raises(PasetoTokenError) as error:
        verifier.verify(_encode_raw(key_pair, payload))

    assert error.value.code == "expired"


def test_malformed_and_tampered_tokens_are_generic(
    signer: PasetoV4PublicSigner,
    verifier: PasetoV4PublicVerifier,
) -> None:
    token = signer.issue(subject="user:123", token_type="access")
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tampered.{parts[3]}"

    for invalid in ("not-a-token", tampered):
        with pytest.raises(PasetoTokenError, match="PASETO token is invalid"):
            verifier.verify(invalid)


def test_empty_keyring_and_nonpositive_ttl_fail_closed(
    key_pair: PasetoKeyPair,
) -> None:
    with pytest.raises(PasetoConfigurationError, match="positive integer"):
        PasetoV4PublicSigner(
            issuer="issuer",
            audience="audience",
            key_id=key_pair.key_id,
            private_key_pem=key_pair.private_pem,
            ttl_seconds=0,
        )
    with pytest.raises(PasetoConfigurationError, match="cannot be empty"):
        PasetoV4PublicVerifier(
            issuer="issuer",
            audience="audience",
            token_type="access",
            public_keys_by_id={},
        )


def test_key_pair_consistency_validation() -> None:
    first = PasetoKeyPair.generate("first")
    second = PasetoKeyPair.generate("second")

    validate_key_pair(first.private_pem, first.public_pem)
    with pytest.raises(PasetoConfigurationError, match="do not match"):
        validate_key_pair(first.private_pem, second.public_pem)


def _encode_raw(key_pair: PasetoKeyPair, payload: dict) -> str:
    key = PasetoKey.new(
        version=4,
        purpose="public",
        key=key_pair.private_pem.encode("utf-8"),
    )
    footer = json.dumps({"kid": key_pair.key_id}, separators=(",", ":"))
    return paseto_encode(
        key,
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        footer=footer.encode("utf-8"),
    ).decode("utf-8")
