#!/usr/bin/env python3
"""Final comprehensive Google Ads API test."""

from google.ads.googleads.client import GoogleAdsClient

from paidsearchnav.core.config import Settings


def test_final_api():
    """Final test using the official Google Ads client directly."""
    print("🎯 Final Google Ads API Connection Test")
    print("=" * 50)

    settings = Settings.from_env()
    if not settings.google_ads:
        print("❌ Google Ads configuration not found")
        return False

    try:
        # Create client using official Google Ads library
        credentials_dict = {
            "developer_token": settings.google_ads.developer_token.get_secret_value(),
            "client_id": settings.google_ads.client_id,
            "client_secret": settings.google_ads.client_secret.get_secret_value(),
            "refresh_token": settings.google_ads.refresh_token.get_secret_value()
            if settings.google_ads.refresh_token
            else None,
            "login_customer_id": settings.google_ads.login_customer_id,
            "use_proto_plus": True,
        }

        client = GoogleAdsClient.load_from_dict(
            credentials_dict, version=settings.google_ads.api_version
        )
        print("✅ Google Ads client initialized")

        # Test 1: List accessible customers
        print("\n📋 Test 1: List Accessible Customers")
        customer_service = client.get_service("CustomerService")
        customers = customer_service.list_accessible_customers()

        customer_ids = [c.split("/")[-1] for c in customers.resource_names]
        print(f"✅ Found {len(customer_ids)} accessible customers:")
        for i, customer_id in enumerate(customer_ids[:5]):
            print(f"   {i + 1}. Customer ID: {customer_id}")
        if len(customer_ids) > 5:
            print(f"   ... and {len(customer_ids) - 5} more")

        # Test 2: Get customer info
        print("\n📋 Test 2: Get Customer Information")
        customer_id = settings.google_ads.login_customer_id or customer_ids[0]
        print(f"Using customer ID: {customer_id}")

        ga_service = client.get_service("GoogleAdsService")
        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone
            FROM customer
            LIMIT 1
        """

        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            customer = row.customer
            print("✅ Customer Info:")
            print(f"   ID: {customer.id}")
            print(f"   Name: {customer.descriptive_name}")
            print(f"   Currency: {customer.currency_code}")
            print(f"   Timezone: {customer.time_zone}")

        # Test 3: Get campaigns (simple query without page size)
        print("\n📋 Test 3: Get Campaigns")
        campaign_query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.campaign_budget
            FROM campaign
            WHERE campaign.status != 'REMOVED'
            LIMIT 10
        """

        response = ga_service.search(customer_id=customer_id, query=campaign_query)
        campaigns = list(response)
        print(f"✅ Found {len(campaigns)} active campaigns:")

        for i, row in enumerate(campaigns[:5]):
            campaign = row.campaign
            print(f"   {i + 1}. {campaign.name}")
            print(f"      ID: {campaign.id}")
            print(f"      Status: {campaign.status.name}")
            print(f"      Budget: {campaign.campaign_budget}")

        if len(campaigns) > 5:
            print(f"   ... and {len(campaigns) - 5} more")

        print("\n🎉 All API tests passed successfully!")
        print("\n📊 Connection Summary:")
        print("   ✅ Authentication working")
        print("   ✅ Customer access verified")
        print("   ✅ Customer info retrieval working")
        print("   ✅ Campaign data retrieval working")
        print("   ✅ API permissions confirmed")

        return True

    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_final_api()
    if success:
        print("\n🚀 Your Google Ads API connection is fully functional!")
        print("You can now use the PaidSearchNav application.")
    else:
        print("\n❌ API connection test failed.")
    exit(0 if success else 1)
