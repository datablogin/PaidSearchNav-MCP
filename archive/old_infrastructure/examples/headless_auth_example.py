#!/usr/bin/env python3
"""Example demonstrating OAuth2 authentication in headless environments.

This script shows how the OAuth2TokenManager automatically detects
the environment and chooses the appropriate authentication method.
"""

import os

from paidsearchnav.core.config import GoogleAdsConfig, Settings
from paidsearchnav.platforms.google.auth import OAuth2TokenManager


def main():
    """Demonstrate headless authentication.

    SECURITY NOTE: This example does not display actual tokens to prevent
    accidental exposure in logs or console output. In production, handle
    tokens securely and never log or print them.
    """
    # Set up configuration
    settings = Settings(
        google_ads=GoogleAdsConfig(
            client_id="your-client-id",
            client_secret="your-client-secret",
            developer_token="your-developer-token",
        )
    )

    # Create token manager
    token_manager = OAuth2TokenManager(settings)

    customer_id = "1234567890"

    print("=== PaidSearchNav OAuth2 Authentication Example ===\n")

    # Example 1: Automatic environment detection
    print("1. Automatic Environment Detection")
    print("-" * 40)
    try:
        creds = token_manager.get_credentials(customer_id)
        print("✅ Authentication successful!")
        print(f"   Token available: {'Yes' if creds.token else 'No'}")
        print(f"   Expires: {creds.expiry}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")

    print("\n")

    # Example 2: Force device flow (useful for testing)
    print("2. Force Device Flow")
    print("-" * 40)
    try:
        creds = token_manager.get_credentials(customer_id, force_auth_method="device")
        print("✅ Device flow authentication successful!")
        print(f"   Token available: {'Yes' if creds.token else 'No'}")
    except Exception as e:
        print(f"❌ Device flow failed: {e}")

    print("\n")

    # Example 3: Force browser flow (if in interactive environment)
    print("3. Force Browser Flow")
    print("-" * 40)
    try:
        creds = token_manager.get_credentials(customer_id, force_auth_method="browser")
        print("✅ Browser flow authentication successful!")
        print(f"   Token available: {'Yes' if creds.token else 'No'}")
    except Exception as e:
        print(f"❌ Browser flow failed: {e}")

    print("\n")

    # Example 4: Show environment detection details
    print("4. Environment Detection Details")
    print("-" * 40)
    from paidsearchnav.platforms.google.auth import _is_headless_environment

    is_headless = _is_headless_environment()
    print(f"Headless environment detected: {is_headless}")

    env_indicators = []
    if os.getenv("CI"):
        env_indicators.append("CI environment variable")
    if os.getenv("GITHUB_ACTIONS"):
        env_indicators.append("GitHub Actions")
    if os.getenv("DOCKER_CONTAINER"):
        env_indicators.append("Docker container")
    if os.path.exists("/.dockerenv"):
        env_indicators.append("Docker environment file")
    if os.getenv("PSN_HEADLESS"):
        env_indicators.append("Explicit PSN_HEADLESS flag")

    if env_indicators:
        print(f"Environment indicators: {', '.join(env_indicators)}")
    else:
        print("No special environment indicators detected")

    print(
        f"Authentication method would be: {'Device Flow' if is_headless else 'Browser Flow'}"
    )


if __name__ == "__main__":
    main()
