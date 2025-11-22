#!/usr/bin/env python3
"""Detailed authentication debugging for Google Ads API."""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from paidsearchnav.core.config import Settings


def test_oauth_token_refresh():
    """Test OAuth2 token refresh directly."""
    print("🔍 Testing OAuth2 token refresh...")

    settings = Settings.from_env()
    if not settings.google_ads:
        print("❌ No Google Ads configuration found")
        return False

    # Get the raw values
    client_id = settings.google_ads.client_id
    client_secret = settings.google_ads.client_secret.get_secret_value()
    refresh_token = (
        settings.google_ads.refresh_token.get_secret_value()
        if settings.google_ads.refresh_token
        else None
    )

    print(f"Client ID: {'✅ Present' if client_id else '❌ Missing'}")
    print(f"Client Secret: {'✅ Present' if client_secret else '❌ Missing'}")
    print(f"Refresh Token: {'✅ Present' if refresh_token else '❌ Missing'}")

    if not refresh_token:
        print("❌ No refresh token available")
        return False

    # Try to create credentials and refresh
    try:
        print("\n🔄 Attempting to refresh token...")
        credentials = Credentials(
            token=None,  # Access token will be refreshed
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

        # Try to refresh
        request = Request()
        credentials.refresh(request)

        print("✅ Token refresh successful!")
        print("✅ New access token obtained")
        return True

    except Exception as e:
        print(f"❌ Token refresh failed: {e}")
        print("\n🔧 Possible solutions:")
        print(
            "1. The refresh token may have expired (they can expire after ~6 months of inactivity)"
        )
        print(
            "2. The client credentials may not match those used to generate the refresh token"
        )
        print("3. You may need to re-authorize and generate a new refresh token")
        print("\n📝 To generate a new refresh token:")
        print("1. Go to: https://developers.google.com/oauthplayground/")
        print("2. Select 'Google Ads API' scopes")
        print("3. Authorize and exchange authorization code for tokens")
        return False


def test_google_ads_client_direct():
    """Test Google Ads client creation with direct parameters."""
    print("\n🚀 Testing Google Ads client with direct authentication...")

    settings = Settings.from_env()
    if not settings.google_ads:
        print("❌ No Google Ads configuration found")
        return False

    try:
        from google.ads.googleads.client import GoogleAdsClient

        # Create client configuration
        credentials_dict = {
            "developer_token": settings.google_ads.developer_token.get_secret_value(),
            "client_id": settings.google_ads.client_id,
            "client_secret": settings.google_ads.client_secret.get_secret_value(),
            "refresh_token": settings.google_ads.refresh_token.get_secret_value()
            if settings.google_ads.refresh_token
            else None,
            "login_customer_id": settings.google_ads.login_customer_id,
            "use_proto_plus": True,  # Required setting
        }

        print("🔧 Creating Google Ads client...")
        client = GoogleAdsClient.load_from_dict(
            credentials_dict, version=settings.google_ads.api_version
        )
        print("✅ Google Ads client created successfully")

        # Try to list accessible customers
        print("👥 Listing accessible customers...")
        customer_service = client.get_service("CustomerService")
        customers = customer_service.list_accessible_customers()

        print(f"✅ Found {len(customers.resource_names)} accessible customers:")
        for customer_resource in customers.resource_names:
            print(f"   - {customer_resource}")

        return True

    except Exception as e:
        print(f"❌ Google Ads client test failed: {e}")
        return False


def main():
    """Run all diagnostic tests."""
    print("🧪 Google Ads API Authentication Diagnostics\n")

    # Test 1: Direct OAuth2 refresh
    oauth_success = test_oauth_token_refresh()

    # Test 2: Google Ads client direct
    if oauth_success:
        client_success = test_google_ads_client_direct()
        if client_success:
            print("\n🎉 All authentication tests passed!")
        else:
            print("\n⚠️  OAuth refresh works but Google Ads client failed")
    else:
        print("\n❌ OAuth refresh failed - need to regenerate refresh token")


if __name__ == "__main__":
    main()
