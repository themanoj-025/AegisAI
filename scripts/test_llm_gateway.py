#!/usr/bin/env python3
"""Sanity test for the LLM gateway.

Run this to confirm your LLM provider and API key are configured correctly:

    python scripts/test_llm_gateway.py

Set LLM_PROVIDER=anthropic or LLM_PROVIDER=openai in .env and the
corresponding API key.
"""

import json
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm_gateway import call_llm


def main():
    """Run a trivial test prompt to verify the LLM gateway works."""
    print("=== AegisAI LLM Gateway Test ===\n")

    # Print provider info
    from app.config import settings

    provider = settings.llm_provider
    print(f"Configured provider: {provider}")
    print(f"Anthropic API key set: {bool(settings.anthropic_api_key)}")
    print(f"OpenAI API key set: {bool(settings.openai_api_key)}")
    print()

    try:
        system_prompt = "You are a helpful assistant. Always respond with valid JSON."
        user_prompt = 'Reply with the exact JSON: {"status": "ok"}'

        print("Sending test prompt...")
        response = call_llm(system_prompt, user_prompt, response_format="json")
        print(f"Response received: {response[:200]}")

        # Try to parse as JSON
        parsed = json.loads(response)
        if parsed.get("status") == "ok":
            print("\n✓ LLM gateway test PASSED — API keys and provider are working correctly.")
        else:
            print(f"\n⚠ Response parsed but unexpected content: {parsed}")

    except Exception as e:
        print(f"\n✗ LLM gateway test FAILED: {e}")
        print("\nTroubleshooting tips:")
        print(f"  1. Check that {provider} API key is correct in .env")
        print(f"  2. Check that the API key has available credits/quota")
        print("  3. For Anthropic: verify the API key starts with 'sk-ant-'")
        print("  4. For OpenAI: verify the API key starts with 'sk-'")
        sys.exit(1)


if __name__ == "__main__":
    main()
