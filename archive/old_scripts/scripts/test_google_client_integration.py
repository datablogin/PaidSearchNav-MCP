#!/usr/bin/env python3
"""
Test the PaidSearchNav Google Ads client implementation.
"""

import os

from dotenv import load_dotenv

from paidsearchnav.platforms.google import GoogleAdsAPIClient, GoogleAdsConfig

# Load environment variables
load_dotenv()


def validate_environment():
    """Validate all required environment variables are present."""
    required_vars = [
        "PSN_GOOGLE_ADS_DEVELOPER_TOKEN",
        "PSN_GOOGLE_ADS_CLIENT_ID",
        "PSN_GOOGLE_ADS_CLIENT_SECRET",
        "PSN_GOOGLE_ADS_REFRESH_TOKEN",
        "PSN_GOOGLE_ADS_CLIENT_CUSTOMER_ID",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file.")
        return False

    return True


def test_google_client():
    """Test the GoogleAdsAPIClient with our credentials."""

    # Validate environment variables
    if not validate_environment():
        return False

    # Create configuration from environment
    config = GoogleAdsConfig(
        developer_token=os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN"),
        client_id=os.getenv("PSN_GOOGLE_ADS_CLIENT_ID"),
        client_secret=os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET"),
        refresh_token=os.getenv("PSN_GOOGLE_ADS_REFRESH_TOKEN"),
        login_customer_id=os.getenv("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace(
            "-", ""
        ),
        use_proto_plus=True,
    )

    # Test client customer ID
    client_customer_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_CUSTOMER_ID", "").replace(
        "-", ""
    )

    try:
        # Initialize client
        client = GoogleAdsAPIClient(
            developer_token=config.developer_token,
            client_id=config.client_id,
            client_secret=config.client_secret,
            refresh_token=config.refresh_token,
            login_customer_id=config.login_customer_id,
            use_proto_plus=config.use_proto_plus,
        )

        print("✅ GoogleAdsAPIClient initialized successfully")
        print(f"🔍 Testing with client customer: {client_customer_id}")

        # Test basic functionality if implemented
        print("\n📊 Available client methods:")
        methods = [method for method in dir(client) if not method.startswith("_")]
        for method in methods[:10]:  # Show first 10 methods
            print(f"   - {method}")

        if len(methods) > 10:
            print(f"   ... and {len(methods) - 10} more")

        return True

    except Exception as e:
        print(f"❌ Error testing GoogleAdsAPIClient: {e}")
        return False


if __name__ == "__main__":
    test_google_client()
