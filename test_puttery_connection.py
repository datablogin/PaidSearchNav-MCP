#!/usr/bin/env python3
"""Test script to verify Google Ads API connection with Puttery credentials."""

import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from paidsearchnav_mcp.clients.google.client import GoogleAdsAPIClient
from paidsearchnav_mcp.core.config import Settings


async def test_puttery_connection():
    """Test connection to Puttery Google Ads account."""
    print("=" * 80)
    print("Testing Puttery Google Ads API Connection")
    print("=" * 80)

    # Check environment variables
    dev_token = os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("PSN_GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if not all([dev_token, client_id, client_secret, refresh_token]):
        print("❌ Missing required Google Ads credentials in .env file")
        print(f"  Developer Token: {'✅' if dev_token else '❌'}")
        print(f"  Client ID: {'✅' if client_id else '❌'}")
        print(f"  Client Secret: {'✅' if client_secret else '❌'}")
        print(f"  Refresh Token: {'✅' if refresh_token else '❌'}")
        return

    print("\n📋 Configuration:")
    print(f"  Developer Token: {dev_token[:8] if dev_token else 'N/A'}...")
    print(f"  Client ID: {client_id[:20] if client_id else 'N/A'}...")
    print(f"  Has Refresh Token: {'✅' if refresh_token else '❌'}")
    print(f"  Login Customer ID: {login_customer_id or 'Not set (will use accessible accounts)'}")

    # Initialize client
    print("\n🔌 Initializing Google Ads API client...")
    try:
        client = GoogleAdsAPIClient(
            developer_token=dev_token,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            login_customer_id=login_customer_id,
        )
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        import traceback
        traceback.print_exc()
        return

    # Try to get accessible customers
    print("\n👥 Fetching accessible customer accounts...")
    try:
        # Use the internal _get_client() method to get the Google Ads client
        google_ads_client = client._get_client()
        service = google_ads_client.get_service("CustomerService")
        accessible_customers = service.list_accessible_customers()

        print(f"✅ Found {len(accessible_customers.resource_names)} accessible customer(s):")
        for resource_name in accessible_customers.resource_names:
            customer_id = resource_name.split('/')[-1]
            print(f"   - Customer ID: {customer_id}")

        if not accessible_customers.resource_names:
            print("❌ No accessible customers found. Check your credentials.")
            return

        # Use the first accessible customer for testing
        first_customer_id = accessible_customers.resource_names[0].split('/')[-1]
        print(f"\n📊 Using customer ID {first_customer_id} for testing...")

    except Exception as e:
        print(f"❌ Failed to fetch accessible customers: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Try to fetch campaigns
    print(f"\n🎯 Fetching campaigns for customer {first_customer_id}...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        campaigns = await client.get_campaigns(
            customer_id=first_customer_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )

        print(f"✅ Successfully fetched {len(campaigns)} campaign(s):")
        for i, campaign in enumerate(campaigns[:5], 1):  # Show first 5
            print(f"   {i}. {campaign.name} "
                  f"(ID: {campaign.campaign_id}, "
                  f"Status: {campaign.status}, "
                  f"Type: {campaign.type})")

        if len(campaigns) > 5:
            print(f"   ... and {len(campaigns) - 5} more")

    except Exception as e:
        print(f"❌ Failed to fetch campaigns: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Try to fetch search terms for a campaign (if we have campaigns)
    # Find an enabled search campaign for better test results
    if campaigns and len(campaigns) > 0:
        # Try to find an ENABLED SEARCH campaign first
        test_campaign = None
        for campaign in campaigns:
            if campaign.status == "ENABLED" and campaign.type == "SEARCH":
                test_campaign = campaign
                break

        # Fall back to any SEARCH campaign if no enabled ones
        if not test_campaign:
            for campaign in campaigns:
                if campaign.type == "SEARCH":
                    test_campaign = campaign
                    break

        # Fall back to first campaign if no search campaigns
        if not test_campaign:
            test_campaign = campaigns[0]

        campaign_id = test_campaign.campaign_id
        if campaign_id:
            print(f"\n🔍 Fetching search terms for campaign {campaign_id}...")
            try:
                search_terms = await client.get_search_terms(
                    customer_id=first_customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    campaigns=[campaign_id]
                )

                print(f"✅ Successfully fetched {len(search_terms)} search term(s):")
                for i, term in enumerate(search_terms[:5], 1):  # Show first 5
                    query = term.search_term
                    impressions = term.impressions
                    clicks = term.clicks
                    cost = term.cost_micros if hasattr(term, 'cost_micros') else 0
                    print(f"   {i}. '{query}' - {impressions} impr, {clicks} clicks, ${cost/1000000:.2f}")

                if len(search_terms) > 5:
                    print(f"   ... and {len(search_terms) - 5} more")

            except Exception as e:
                print(f"❌ Failed to fetch search terms: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_puttery_connection())
