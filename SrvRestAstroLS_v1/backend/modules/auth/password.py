from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from core.config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    pepper = get_settings().auth_password_pepper.get_secret_value()
    secret = password + pepper if pepper else password
    return _hasher.hash(secret)


def verify_password(password: str, password_hash: str) -> bool:
    pepper = get_settings().auth_password_pepper.get_secret_value()
    secret = password + pepper if pepper else password
    try:
        return _hasher.verify(password_hash, secret)
    except VerifyMismatchError:
        return False
