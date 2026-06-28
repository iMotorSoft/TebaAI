from __future__ import annotations

import pytest

from core.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Clear the cached AppSettings before every test."""
    get_settings.cache_clear()
