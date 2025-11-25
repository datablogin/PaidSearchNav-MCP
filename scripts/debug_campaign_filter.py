#!/usr/bin/env python3
"""Debug script to test campaign_id filter in get_keywords."""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from paidsearchnav_mcp.clients.google.client import GoogleAdsAPIClient
from paidsearchnav_mcp.clients.google.auth import GoogleAdsAuth


async def test_campaign_filter():
    """Test get_keywords with campaign_id filter."""

    # Initialize client using same approach as server.py
    developer_token = os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN") or os.getenv(
        "GOOGLE_ADS_DEVELOPER_TOKEN"
    )
    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID") or os.getenv(
        "GOOGLE_ADS_CLIENT_ID"
    )
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET") or os.getenv(
        "GOOGLE_ADS_CLIENT_SECRET"
    )
    refresh_token = os.getenv("PSN_GOOGLE_ADS_REFRESH_TOKEN") or os.getenv(
        "GOOGLE_ADS_REFRESH_TOKEN"
    )
    login_customer_id = os.getenv("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID") or os.getenv(
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID"
    )

    if not all([developer_token, client_id, client_secret, refresh_token]):
        print("❌ Missing required environment variables!")
        print("   Required: GOOGLE_ADS_DEVELOPER_TOKEN, CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN")
        sys.exit(1)

    # Create auth and client
    auth = GoogleAdsAuth(
        client_id=client_id,
        client_secret=client_secret,
        developer_token=developer_token,
        refresh_token=refresh_token,
        login_customer_id=login_customer_id,
    )

    client = GoogleAdsAPIClient(
        credentials=auth,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
    )

    # Test parameters
    customer_id = "9097587272"
    campaign_id = "22171301645"
    end_date = datetime(2025, 10, 31)
    start_date = datetime(2025, 10, 30)

    print(f"Testing get_keywords with:")
    print(f"  customer_id: {customer_id}")
    print(f"  campaign_id: {campaign_id}")
    print(f"  date range: {start_date.date()} to {end_date.date()}")
    print()

    try:
        # Test with campaign_id parameter
        print("=" * 60)
        print("Test 1: Using campaign_id parameter")
        print("=" * 60)
        keywords = await client.get_keywords(
            customer_id=customer_id,
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date,
            max_results=10,  # Limit for testing
        )
        print(f"✅ Success! Retrieved {len(keywords)} keywords")
        if keywords:
            print(f"\nFirst keyword:")
            kw = keywords[0]
            print(f"  Text: {kw.text}")
            print(f"  Campaign: {kw.campaign_name} ({kw.campaign_id})")
            print(f"  Match Type: {kw.match_type}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print()

    try:
        # Test with campaigns list parameter
        print("\n" + "=" * 60)
        print("Test 2: Using campaigns=[campaign_id] parameter")
        print("=" * 60)
        keywords = await client.get_keywords(
            customer_id=customer_id,
            campaigns=[campaign_id],
            start_date=start_date,
            end_date=end_date,
            max_results=10,  # Limit for testing
        )
        print(f"✅ Success! Retrieved {len(keywords)} keywords")
        if keywords:
            print(f"\nFirst keyword:")
            kw = keywords[0]
            print(f"  Text: {kw.text}")
            print(f"  Campaign: {kw.campaign_name} ({kw.campaign_id})")
            print(f"  Match Type: {kw.match_type}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_campaign_filter())
