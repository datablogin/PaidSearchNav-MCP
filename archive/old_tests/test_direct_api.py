#!/usr/bin/env python3
"""Direct Google Ads API test bypassing the OAuth2TokenManager."""

import asyncio

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


async def test_direct_api():
    """Test Google Ads API directly with credentials."""
    print("🔍 Testing Google Ads API directly...")

    settings = Settings.from_env()
    if not settings.google_ads:
        print("❌ Google Ads configuration not found")
        return False

    try:
        # Create client directly with credentials (bypassing OAuth2TokenManager)
        client = GoogleAdsAPIClient(
            developer_token=settings.google_ads.developer_token.get_secret_value(),
            client_id=settings.google_ads.client_id,
            client_secret=settings.google_ads.client_secret.get_secret_value(),
            refresh_token=settings.google_ads.refresh_token.get_secret_value()
            if settings.google_ads.refresh_token
            else None,
            login_customer_id=settings.google_ads.login_customer_id,
        )
        print("✅ Google Ads client initialized")

        # Test basic operations
        customer_id = settings.google_ads.login_customer_id or "1884837039"
        print(f"🎯 Testing with customer ID: {customer_id}")

        # Get campaigns
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        campaigns = await client.get_campaigns(
            customer_id=customer_id, start_date=start_date, end_date=end_date
        )

        print(f"✅ Successfully retrieved {len(campaigns)} campaigns")

        if campaigns:
            print("\n📋 Sample campaigns:")
            for i, campaign in enumerate(campaigns[:3]):
                print(f"   {i + 1}. {campaign.name}")
                print(f"      ID: {campaign.id}")
                print(f"      Status: {campaign.status}")
                print(f"      Type: {campaign.campaign_type}")
                print()

        # Test ad groups
        print("🎯 Testing ad groups retrieval...")
        if campaigns:
            first_campaign_id = campaigns[0].id
            ad_groups = await client.get_ad_groups(
                customer_id=customer_id,
                campaign_id=first_campaign_id,
                start_date=start_date,
                end_date=end_date,
            )
            print(
                f"✅ Retrieved {len(ad_groups)} ad groups for campaign {campaigns[0].name}"
            )

        print("\n🎉 Direct API test successful! All connections working.")
        return True

    except Exception as e:
        print(f"❌ Direct API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_direct_api())
    exit(0 if success else 1)
