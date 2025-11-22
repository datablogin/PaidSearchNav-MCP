#!/usr/bin/env python3
"""Find client accounts under MCC."""

import os

from google.ads.googleads.client import GoogleAdsClient

from paidsearchnav.core.config import Settings


def find_mcc_clients(mcc_customer_id=None, mcc_name=None):
    """Find all client accounts under an MCC."""
    settings = Settings.from_env()

    # Use provided MCC customer_id, environment variable, or default from settings
    if not mcc_customer_id:
        mcc_customer_id = (
            os.getenv("PSN_MCC_CUSTOMER_ID") or settings.google_ads.login_customer_id
        )

    if not mcc_customer_id:
        print("❌ Error: No MCC customer ID provided. Use:")
        print("   1. Set PSN_MCC_CUSTOMER_ID environment variable")
        print("   2. Pass mcc_customer_id parameter")
        print("   3. Configure login_customer_id in settings")
        return None

    mcc_name = mcc_name or os.getenv("PSN_MCC_NAME", "MCC Account")

    print(f"🔍 Searching for client accounts under {mcc_name}...")

    credentials_dict = {
        "developer_token": settings.google_ads.developer_token.get_secret_value(),
        "client_id": settings.google_ads.client_id,
        "client_secret": settings.google_ads.client_secret.get_secret_value(),
        "refresh_token": settings.google_ads.refresh_token.get_secret_value(),
        "login_customer_id": mcc_customer_id,  # Set MCC as login customer
        "use_proto_plus": True,
    }

    client = GoogleAdsClient.load_from_dict(
        credentials_dict, version=settings.google_ads.api_version
    )
    ga_service = client.get_service("GoogleAdsService")

    print(f"📋 Using MCC Customer ID: {mcc_customer_id} ({mcc_name})")

    try:
        # Query to get all client accounts under the MCC
        query = """
            SELECT
                customer_client.client_customer,
                customer_client.descriptive_name,
                customer_client.currency_code,
                customer_client.time_zone,
                customer_client.status
            FROM customer_client
            WHERE customer_client.status = 'ENABLED'
        """

        response = ga_service.search(customer_id=mcc_customer_id, query=query)

        clients = []
        legent_spine_clients = []

        for row in response:
            client_info = row.customer_client
            client_id = client_info.client_customer.split("/")[-1]
            client_name = client_info.descriptive_name

            client_data = {
                "id": client_id,
                "name": client_name,
                "currency": client_info.currency_code,
                "timezone": client_info.time_zone,
                "status": client_info.status.name,
            }
            clients.append(client_data)

            print(f"   📁 {client_id}: {client_name}")

            # Check for Legent Spine
            name_lower = client_name.lower()
            if "legent" in name_lower or "spine" in name_lower:
                legent_spine_clients.append(client_data)
                print("      🎯 FOUND LEGENT SPINE MATCH!")

        print(f"\n✅ Found {len(clients)} total client accounts under MCC")

        if legent_spine_clients:
            print(f"\n🎯 Found {len(legent_spine_clients)} Legent Spine account(s):")
            for client in legent_spine_clients:
                print(f"   Customer ID: {client['id']}")
                print(f"   Name: {client['name']}")
                print(f"   Currency: {client['currency']}")
                print(f"   Timezone: {client['timezone']}")
                print(f"   Status: {client['status']}")
            return legent_spine_clients[0]["id"]
        else:
            print("\n❓ No 'Legent Spine' found. All client accounts:")
            for client in clients:
                print(f"   {client['id']}: {client['name']}")
            return None

    except Exception as e:
        print(f"❌ Error accessing MCC client accounts: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    import sys

    # Allow MCC customer ID to be passed as command line argument
    mcc_customer_id = None
    mcc_name = None

    if len(sys.argv) > 1:
        mcc_customer_id = sys.argv[1]
    if len(sys.argv) > 2:
        mcc_name = sys.argv[2]

    result = find_mcc_clients(mcc_customer_id, mcc_name)
    if result:
        print(f"\n🎯 Found target account with Customer ID: {result}")
    else:
        print(
            "\n💡 Please check the client account names or provide the correct Customer ID"
        )
