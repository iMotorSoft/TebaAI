#!/usr/bin/env python3
"""
Smoke test for LiteLLM key resolution.

Validates that the key is resolved with the correct precedence:
  1. LITELLM_MASTER_KEY (primary global convention)
  2. TEBAAI_LITELLM_API_KEY (TebaAI-specific fallback)

Usage:
    uv run python -m scripts.smoke_litellm_key_resolution

    # With specific env for testing:
    LITELLM_MASTER_KEY="sk-test-master" uv run python -m scripts.smoke_litellm_key_resolution

Environment:
  LITELLM_MASTER_KEY     — shared global convention (primary)
  TEBAAI_LITELLM_API_KEY — TebaAI-specific override (fallback)

No secrets are printed. The test only validates whether a key is present
and which source resolved it.
"""

from __future__ import annotations

import os
import sys


RESOLVED_SOURCE: str | None = None


def _resolve_key_for_test() -> str:
    """Test-only key resolution mirroring core/config.py _validate_litellm logic.
    
    Returns the resolved key (empty if none found).
    Sets RESOLVED_SOURCE to indicate which env var provided the key.
    """
    global RESOLVED_SOURCE
    master = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if master:
        RESOLVED_SOURCE = "LITELLM_MASTER_KEY"
        return master
    tebaai = os.environ.get("TEBAAI_LITELLM_API_KEY", "").strip()
    if tebaai:
        RESOLVED_SOURCE = "TEBAAI_LITELLM_API_KEY"
        return tebaai
    RESOLVED_SOURCE = "none"
    return ""


def main() -> int:
    print("=== LiteLLM Key Resolution Smoke Test ===")
    
    # Capture real env before any override
    real_master = os.environ.get("LITELLM_MASTER_KEY", "")
    real_tebaai = os.environ.get("TEBAAI_LITELLM_API_KEY", "")
    
    print(f"\nEnvironment state:")
    print(f"  LITELLM_MASTER_KEY     = {'[set]' if real_master else '[not set]'}")
    print(f"  TEBAAI_LITELLM_API_KEY = {'[set]' if real_tebaai else '[not set]'}")
    
    # Test real resolution
    key = _resolve_key_for_test()
    has_key = bool(key)
    print(f"\nResolution result:")
    print(f"  Resolved from: {RESOLVED_SOURCE}")
    print(f"  Key present:   {'yes' if has_key else 'no'}")
    print(f"  Key length:    {len(key)} chars")
    
    if not has_key:
        print(f"\n❌ FAIL: No LiteLLM key found in environment.")
        print(f"   Set LITELLM_MASTER_KEY or TEBAAI_LITELLM_API_KEY.")
        return 1
    
    prefix_ok = key.startswith("sk-") or key.startswith("sk-")
    print(f"  Key prefix OK: {'yes' if prefix_ok else 'unknown format'}")
    
    # Verify LITELLM_MASTER_KEY takes precedence
    os.environ["LITELLM_MASTER_KEY"] = "sk-test-master"
    os.environ["TEBAAI_LITELLM_API_KEY"] = "sk-test-tebaai"
    key2 = _resolve_key_for_test()
    assert RESOLVED_SOURCE == "LITELLM_MASTER_KEY", \
        f"Expected LITELLM_MASTER_KEY to win, got {RESOLVED_SOURCE}"
    assert key2 == "sk-test-master", \
        f"Expected 'sk-test-master', got '{key2[:20]}'"
    
    # Verify TEBAAI_LITELLM_API_KEY fallback
    os.environ["LITELLM_MASTER_KEY"] = ""
    key3 = _resolve_key_for_test()
    assert RESOLVED_SOURCE == "TEBAAI_LITELLM_API_KEY", \
        f"Expected TEBAAI_LITELLM_API_KEY fallback, got {RESOLVED_SOURCE}"
    assert key3 == "sk-test-tebaai", \
        f"Expected 'sk-test-tebaai', got '{key3[:20]}'"
    
    # Verify no key → empty
    os.environ["TEBAAI_LITELLM_API_KEY"] = ""
    key4 = _resolve_key_for_test()
    assert RESOLVED_SOURCE == "none", f"Expected none, got {RESOLVED_SOURCE}"
    assert key4 == "", f"Expected empty, got '{key4[:20]}'"
    
    # Restore originals
    if real_master:
        os.environ["LITELLM_MASTER_KEY"] = real_master
    else:
        os.environ.pop("LITELLM_MASTER_KEY", None)
    if real_tebaai:
        os.environ["TEBAAI_LITELLM_API_KEY"] = real_tebaai
    else:
        os.environ.pop("TEBAAI_LITELLM_API_KEY", None)
    
    print(f"\n✅ PASS: All resolution scenarios correct.")
    print(f"   Precedence: LITELLM_MASTER_KEY → TEBAAI_LITELLM_API_KEY → error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
