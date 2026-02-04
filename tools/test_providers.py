"""Test script to verify LLM provider configurations.

Tests connectivity and basic functionality for OpenAI, Grok, Gemini, and local providers
without requiring a running game or OpenEnv proxy.

Usage:
    # Test all providers
    python tools/test_providers.py

    # Test specific provider
    python tools/test_providers.py --provider openai
    python tools/test_providers.py --provider grok
    python tools/test_providers.py --provider gemini
    python tools/test_providers.py --provider local --base-url http://localhost:1234/v1

Environment variables:
    OPENAI_API_KEY  - Required for OpenAI tests
    XAI_API_KEY     - Required for Grok tests
    GEMINI_API_KEY  - Required for Gemini tests
"""

import argparse
import json
import os
import urllib.request
from typing import Dict, Any, Optional


def test_provider(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Test a single provider's chat completion endpoint.

    Args:
        provider: "openai", "grok", or "local"
        model: Model name to test
        base_url: API base URL (optional, provider-specific defaults used)
        api_key: API key (optional, read from env if not provided)

    Returns:
        True if test passed, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing {provider.upper()} Provider")
    print(f"{'='*70}")

    # Get provider-specific defaults
    if provider == "openai":
        if base_url is None:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        if model == "auto":
            model = "gpt-3.5-turbo"  # Cheap model for testing

    elif provider == "grok":
        if base_url is None:
            base_url = "https://api.x.ai/v1"
        if api_key is None:
            api_key = os.environ.get("XAI_API_KEY")
        if model == "auto":
            model = "grok-beta"

    elif provider == "gemini":
        if base_url is None:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
        if model == "auto":
            model = "gemini-3-flash-preview"

    elif provider == "local":
        if base_url is None:
            base_url = "http://localhost:1234/v1"
        if api_key is None:
            api_key = "not-needed"  # Local servers often don't validate
        if model == "auto":
            print("ERROR: Must specify model name for local provider")
            print("Use: --model your-model-name")
            return False

    else:
        print(f"ERROR: Unknown provider: {provider}")
        return False

    print(f"Model:     {model}")
    print(f"Base URL:  {base_url}")
    print(f"API Key:   {'✓ Set' if api_key else '✗ Not set'}")

    if not api_key and provider in ("openai", "grok", "gemini"):
        print(f"\nERROR: API key required for {provider}")
        if provider == "gemini":
            print(f"Set environment variable: GEMINI_API_KEY")
            print(f"Get API key from: https://aistudio.google.com/app/apikey")
        else:
            print(f"Set environment variable: {provider.upper()}_API_KEY")
        return False

    print("\nSending test request...")

    # Prepare test request
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello' if you can hear me."},
        ],
        "temperature": 0.0,
        "max_tokens": 50,
    }

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }

    try:
        # Make request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")

        response = json.loads(raw)

        # Extract response
        content = response["choices"][0]["message"]["content"]
        print(f"\n✓ Success! Response:")
        print(f"  {content}")

        # Check for usage info (token counts)
        if "usage" in response:
            usage = response["usage"]
            print(f"\nToken usage:")
            print(f"  Prompt:     {usage.get('prompt_tokens', 'N/A')}")
            print(f"  Completion: {usage.get('completion_tokens', 'N/A')}")
            print(f"  Total:      {usage.get('total_tokens', 'N/A')}")

        return True

    except urllib.error.HTTPError as e:
        print(f"\n✗ HTTP Error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode("utf-8")
            error_data = json.loads(error_body)
            print(f"  Error details: {error_data}")
        except Exception:
            pass
        return False

    except urllib.error.URLError as e:
        print(f"\n✗ URL Error: {e.reason}")
        print(f"  Could not connect to {url}")
        if provider == "local":
            print(f"\n  Is your local server running?")
            print(f"  Try: curl {base_url}/models")
        return False

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        return False


def test_openenv_proxy(base_url: str = "http://127.0.0.1:8001") -> bool:
    """Test OpenEnv proxy connectivity.

    Args:
        base_url: OpenEnv proxy URL

    Returns:
        True if healthy, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing OpenEnv Proxy")
    print(f"{'='*70}")
    print(f"URL: {base_url}")

    # Test health endpoint
    print("\nTesting /health endpoint...")
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") in ("ok", "healthy"):
            print("✓ Proxy is healthy")
            return True
        else:
            print(f"✗ Unexpected response: {data}")
            return False

    except urllib.error.URLError:
        print(f"✗ Could not connect to {base_url}")
        print("\nIs the OpenEnv proxy running?")
        print("Start it with:")
        print("  export ZEROAD_RL_URL=http://127.0.0.1:6000")
        print("  python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8001")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test LLM provider configurations")
    parser.add_argument(
        "--provider",
        choices=["openai", "grok", "gemini", "local", "all"],
        default="all",
        help="Provider to test (default: all)",
    )
    parser.add_argument(
        "--model",
        default="auto",
        help="Model name (default: provider-specific default)",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for API (provider-specific default used if not set)",
    )
    parser.add_argument(
        "--api-key",
        help="API key (read from environment if not provided)",
    )
    parser.add_argument(
        "--skip-openenv",
        action="store_true",
        help="Skip OpenEnv proxy test",
    )
    parser.add_argument(
        "--openenv-url",
        default="http://127.0.0.1:8001",
        help="OpenEnv proxy URL (default: http://127.0.0.1:8001)",
    )

    args = parser.parse_args()

    results = {}

    # Test providers
    if args.provider == "all":
        providers_to_test = ["openai", "grok", "gemini", "local"]
    else:
        providers_to_test = [args.provider]

    for provider in providers_to_test:
        # Skip local if no base_url specified in "all" mode
        if provider == "local" and args.provider == "all" and not args.base_url:
            print(f"\n{'='*70}")
            print(f"Skipping LOCAL Provider (no --base-url specified)")
            print(f"{'='*70}")
            continue

        result = test_provider(
            provider=provider,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
        )
        results[provider] = result

    # Test OpenEnv proxy
    if not args.skip_openenv:
        results["openenv"] = test_openenv_proxy(args.openenv_url)

    # Summary
    print(f"\n{'='*70}")
    print("Test Summary")
    print(f"{'='*70}")

    all_passed = all(results.values())

    for component, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{component.ljust(20)} {status}")

    print(f"{'='*70}")

    if all_passed:
        print("\n✓ All tests passed! You're ready to run matches.")
        return 0
    else:
        print("\n✗ Some tests failed. Check configuration and try again.")
        return 1


if __name__ == "__main__":
    exit(main())
