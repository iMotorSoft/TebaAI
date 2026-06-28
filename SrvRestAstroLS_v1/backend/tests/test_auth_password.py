from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.auth.password import hash_password, verify_password


class TestArgon2id:
    def test_hash_and_verify(self) -> None:
        pw = "my-secure-password-123"
        h = hash_password(pw)
        assert h != pw
        assert verify_password(pw, h) is True

    def test_wrong_password(self) -> None:
        h = hash_password("correct-password")
        assert verify_password("wrong-password", h) is False

    def test_empty_password(self) -> None:
        h = hash_password("")
        assert verify_password("", h) is True

    def test_hash_changes_each_time(self) -> None:
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_verify_fails_on_different_hash(self) -> None:
        h = hash_password("password-a")
        assert verify_password("password-b", h) is False


class TestPepper:
    def test_pepper_changes_hash(self) -> None:
        with patch("modules.auth.password.get_settings") as mock_settings:
            s1 = mock_settings.return_value
            s1.auth_password_pepper.get_secret_value.return_value = "pepper1"
            h1 = hash_password("password")

        with patch("modules.auth.password.get_settings") as mock_settings:
            s2 = mock_settings.return_value
            s2.auth_password_pepper.get_secret_value.return_value = "pepper2"
            h2 = hash_password("password")

        assert h1 != h2

    def test_pepper_verify_works(self) -> None:
        with patch("modules.auth.password.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_password_pepper.get_secret_value.return_value = "my-pepper"
            h = hash_password("password")

        with patch("modules.auth.password.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_password_pepper.get_secret_value.return_value = "my-pepper"
            assert verify_password("password", h) is True

    def test_wrong_pepper_fails_verify(self) -> None:
        with patch("modules.auth.password.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_password_pepper.get_secret_value.return_value = "correct-pepper"
            h = hash_password("password")

        with patch("modules.auth.password.get_settings") as mock_settings:
            s = mock_settings.return_value
            s.auth_password_pepper.get_secret_value.return_value = "wrong-pepper"
            assert verify_password("password", h) is False
