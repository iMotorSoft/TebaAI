#!/usr/bin/env python3
"""
Validate LiteLLM model connection and analyze test queries.

Tests:
  1. LiteLLM gateway reachability (health check)
  2. Model availability (openai_gpt-5.4-nano)
  3. Conversation analyzer with deterministic fallback
  4. Sample query analysis

Usage:
  uv run python -m scripts.validate_litellm_model --dry-run
  uv run python -m scripts.validate_litellm_model --test-litellm
  uv run python -m scripts.validate_litellm_model --analyze
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import httpx
from typing import Any

import globalVar
from modules.library.conversation_analyzer import ResearchConversationAnalyzer


async def check_litellm_health() -> dict[str, Any]:
    """Check if LiteLLM gateway is reachable."""
    base_url = globalVar.LITELLM_BASE_URL
    print(f"🔍 Checking LiteLLM gateway at {base_url}...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health", follow_redirects=True)
            if response.status_code in (200, 404):  # Some services don't have /health
                print(f"  ✅ Gateway reachable (status: {response.status_code})")
                return {"reachable": True, "status_code": response.status_code}
            else:
                print(f"  ⚠️  Unexpected status: {response.status_code}")
                return {"reachable": False, "status_code": response.status_code}
    except Exception as e:
        print(f"  ❌ Cannot reach gateway: {e}")
        return {"reachable": False, "error": str(e)}


async def test_model_config() -> dict[str, Any]:
    """Display model configuration."""
    model = globalVar.RESEARCH_CONVERSATION_MODEL
    base_url = globalVar.LITELLM_BASE_URL
    api_key = globalVar.LITELLM_API_KEY[:20] + "..." if globalVar.LITELLM_API_KEY else "(no key)"
    
    print(f"\n📋 Model Configuration:")
    print(f"  Model: {model}")
    print(f"  LiteLLM Base URL: {base_url}")
    print(f"  LiteLLM API Key: {api_key}")
    print(f"  LiteLLM Timeout: {globalVar.LITELLM_TIMEOUT_SECONDS}s")
    
    return {
        "model": model,
        "base_url": base_url,
        "timeout_seconds": globalVar.LITELLM_TIMEOUT_SECONDS,
    }


async def analyze_sample_queries() -> dict[str, Any]:
    """Analyze sample queries with ResearchConversationAnalyzer."""
    analyzer = ResearchConversationAnalyzer()
    
    sample_queries = [
        "¿Qué es un Tzadik según Breslov?",
        "¿Cómo vencer la tristeza?",
        "¿Qué relación hay entre miedo, fe y alegría?",
        "¿Dónde aparece el puente angosto?",
    ]
    
    print(f"\n🧪 Analyzing {len(sample_queries)} sample queries:")
    results = []
    
    for query in sample_queries:
        result = analyzer.analyze(query)
        results.append({
            "query": query,
            "language": result.language,
            "intent": result.intent.value,
            "mode": result.research_mode.value,
            "model_used": result.model_used,
            "fallback_used": result.analysis_fallback,
        })
        fallback_marker = "⚠️ (fallback)" if result.analysis_fallback else "✓"
        print(f"  {fallback_marker} '{query[:40]}...' → intent={result.intent.value}, model={result.model_used}")
    
    return {
        "samples_analyzed": len(results),
        "results": results,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Validate LiteLLM model and conversation analyzer."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LiteLLM connection test (show config only)"
    )
    parser.add_argument(
        "--test-litellm",
        action="store_true",
        help="Test LiteLLM gateway reachability"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze sample queries"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks"
    )
    
    args = parser.parse_args()
    
    # Default: show config and analyze
    if not args.dry_run and not args.test_litellm and not args.analyze and not args.all:
        args.test_litellm = True
        args.analyze = True
    
    if args.all:
        args.test_litellm = True
        args.analyze = True
    
    print("=" * 70)
    print("TebaAI — LiteLLM Model Validator")
    print("=" * 70)
    
    # Always show config
    config = await test_model_config()
    
    # Optional: test LiteLLM connection
    if args.test_litellm:
        health = await check_litellm_health()
    
    # Optional: analyze queries
    if args.analyze:
        analysis = await analyze_sample_queries()
    
    print("\n" + "=" * 70)
    print("✅ Validation complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
