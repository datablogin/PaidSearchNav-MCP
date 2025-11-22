#!/usr/bin/env python3
"""Simple Google Ads API connectivity test."""

import asyncio

from dotenv import load_dotenv

from paidsearchnav.core.config import get_settings
from paidsearchnav.platforms.google.auth import OAuth2TokenManager
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


async def test_simple_connectivity():
    """Test basic Google Ads API connectivity."""
    print("🔍 Testing Google Ads API connectivity...")

    # Load environment variables
    load_dotenv()
    settings = get_settings()

    if not settings.google_ads:
        print("❌ Google Ads configuration not found!")
        return False

    print("✅ Configuration loaded successfully")

    try:
        # Test OAuth2 token manager
        print("🔐 Testing OAuth2 token manager...")
        oauth_manager = OAuth2TokenManager(settings)
        print("✅ OAuth2 token manager initialized")

        # Get credentials
        print("🎫 Getting credentials...")
        try:
            customer_id = settings.google_ads.login_customer_id or "1884837039"
            credentials = oauth_manager.get_credentials(customer_id)
            print(
                f"✅ Credentials obtained: {credentials.token[:20] if credentials.token else 'No token'}..."
            )
        except Exception as e:
            print(f"❌ Failed to get credentials: {e}")
            return False

        # Initialize Google Ads client
        print("🚀 Initializing Google Ads client...")
        client = GoogleAdsAPIClient(
            developer_token=str(settings.google_ads.developer_token),
            client_id=settings.google_ads.client_id,
            client_secret=str(settings.google_ads.client_secret),
            refresh_token=str(settings.google_ads.refresh_token),
            login_customer_id=settings.google_ads.login_customer_id,
        )
        print("✅ Google Ads client initialized")

        # Try a simple API call
        print("📊 Testing basic API call...")
        try:
            # Get campaigns
            customer_id = settings.google_ads.login_customer_id or "1884837039"
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            campaigns = await client.get_campaigns(
                customer_id=customer_id, start_date=start_date, end_date=end_date
            )
            print(f"✅ Successfully retrieved {len(campaigns)} campaigns")

            for i, campaign in enumerate(campaigns[:3]):  # Show first 3
                print(f"   - Campaign {i + 1}: {campaign.name} (ID: {campaign.id})")
                print(f"     Status: {campaign.status}, Type: {campaign.campaign_type}")

        except Exception as e:
            print(f"❌ API call failed: {e}")
            import traceback

            traceback.print_exc()
            return False

        print("\n🎉 All tests passed! Google Ads API connectivity is working.")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_simple_connectivity())
    exit(0 if success else 1)
