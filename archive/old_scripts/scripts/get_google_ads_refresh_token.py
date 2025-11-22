#!/usr/bin/env python3
"""
Get Google Ads API refresh token through OAuth flow
Run this once to get the refresh token, then add it to your .env file
"""

import os
import webbrowser

from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

# Load environment variables
load_dotenv()

# Google Ads API OAuth2 settings - include all scopes Google might add
SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:8080/callback"


def get_refresh_token():
    """Get refresh token for Google Ads API access."""

    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ Missing Google Ads credentials in .env file")
        print("Required: PSN_GOOGLE_ADS_CLIENT_ID and PSN_GOOGLE_ADS_CLIENT_SECRET")
        return None

    print(f"🔑 Using Client ID: {client_id}")

    # Create OAuth2 flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = REDIRECT_URI

    # Generate authorization URL
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Force consent to ensure refresh token
    )

    print("\n🌐 Opening browser for Google Ads API authorization...")
    print(f"📋 Authorization URL: {auth_url}")

    # Open browser
    webbrowser.open(auth_url)

    print("\n📝 Instructions:")
    print("1. Browser should open automatically")
    print("2. Sign in to your Google account that has Google Ads access")
    print("3. Grant permissions to access Google Ads")
    print("4. Copy the authorization code from the callback URL")
    print(
        "5. The URL will look like: http://localhost:8080/callback?code=AUTHORIZATION_CODE"
    )
    print("6. Copy just the AUTHORIZATION_CODE part")

    # Get authorization code from user
    auth_code = input("\n🔑 Enter the authorization code: ").strip()

    if not auth_code:
        print("❌ No authorization code provided")
        return None

    try:
        # Exchange authorization code for tokens
        print("🔄 Exchanging authorization code for tokens...")
        flow.fetch_token(code=auth_code)

        credentials = flow.credentials

        print("\n✅ Successfully obtained tokens!")
        print(f"🔄 Refresh Token: {credentials.refresh_token}")
        print(f"🎫 Access Token: {credentials.token[:50]}...")
        print(f"⏰ Token Expires: {credentials.expiry}")

        # Validate we got the adwords scope
        if credentials.granted_scopes:
            print(f"📋 Granted Scopes: {list(credentials.granted_scopes)}")
            if (
                "https://www.googleapis.com/auth/adwords"
                not in credentials.granted_scopes
            ):
                print("⚠️  Warning: Google Ads scope may not be properly granted")

        # Add to .env instructions
        print("\n📝 Add this to your .env file:")
        print(f"PSN_GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}")

        return credentials.refresh_token

    except Exception as e:
        print(f"❌ Error exchanging code for tokens: {e}")
        print("💡 Common fixes:")
        print("  - Make sure you copied the full authorization code")
        print("  - Try the process again (codes expire quickly)")
        print("  - Check that your Google account has Google Ads access")
        return None


def test_credentials(refresh_token):
    """Test the credentials by making a simple API call."""

    try:
        from google.ads.googleads.client import GoogleAdsClient

        # Create client config
        client_config = {
            "developer_token": os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN"),
            "client_id": os.getenv("PSN_GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }

        # Initialize Google Ads client
        client = GoogleAdsClient.load_from_dict(client_config)

        # Test with a simple customer list call
        customer_service = client.get_service("CustomerService")
        customers = customer_service.list_accessible_customers()

        print("\n🎉 Credentials test successful!")
        print(f"📊 Found {len(customers.resource_names)} accessible customers:")

        for customer_resource in customers.resource_names:
            customer_id = customer_resource.split("/")[-1]
            print(f"  - Customer ID: {customer_id}")

        return True

    except Exception as e:
        print(f"❌ Credentials test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Google Ads API Refresh Token Generator")
    print("=" * 50)

    refresh_token = get_refresh_token()

    if refresh_token:
        print("\n🧪 Testing credentials...")
        if test_credentials(refresh_token):
            print(
                "\n✅ All set! You can now run live analyzers with Google Ads API access."
            )
        else:
            print(
                "\n⚠️  Token obtained but test failed. Check your developer token and permissions."
            )
    else:
        print("\n❌ Failed to obtain refresh token. Please try again.")
