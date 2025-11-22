#!/usr/bin/env python3
"""Generate a new Google Ads API refresh token."""

import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from paidsearchnav.core.config import Settings


def generate_refresh_token():
    """Generate a new refresh token for Google Ads API."""
    print("🔐 Google Ads API Refresh Token Generator\n")

    settings = Settings.from_env()
    if not settings.google_ads:
        print("❌ Google Ads configuration not found in .env file")
        return

    client_id = settings.google_ads.client_id
    client_secret = settings.google_ads.client_secret.get_secret_value()

    print(f"Using Client ID: {client_id}")
    print(f"Using Client Secret: {client_secret[:10]}...\n")

    # Step 1: Create authorization URL
    auth_base_url = "https://accounts.google.com/o/oauth2/auth"
    redirect_uri = "http://localhost:8080"  # Simple localhost redirect
    scope = "https://www.googleapis.com/auth/adwords"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "response_type": "code",
        "access_type": "offline",  # This is required to get a refresh token
        "prompt": "consent",  # Force consent screen to ensure refresh token
    }

    auth_url = f"{auth_base_url}?{urlencode(auth_params)}"

    print("📋 STEP 1: Authorization")
    print("=" * 50)
    print("I'll open your browser to authorize the application.")
    print("After authorization, you'll be redirected to localhost (which will fail).")
    print("Copy the ENTIRE URL from your browser's address bar after the redirect.\n")

    input("Press Enter to open the browser...")

    # Open browser
    webbrowser.open(auth_url)

    # Step 2: Get authorization code from user
    print("\n📋 STEP 2: Get Authorization Code")
    print("=" * 50)
    print("After authorizing, you'll be redirected to a localhost URL that won't load.")
    print("Copy the ENTIRE URL from your browser's address bar and paste it here.")
    print("It should look like: http://localhost:8080?code=...")
    print()

    redirect_url = input("Paste the redirect URL here: ").strip()

    # Parse authorization code
    try:
        parsed_url = urlparse(redirect_url)
        query_params = parse_qs(parsed_url.query)
        auth_code = query_params.get("code", [None])[0]

        if not auth_code:
            print("❌ No authorization code found in URL. Please try again.")
            return

        print(f"✅ Authorization code extracted: {auth_code[:20]}...")

    except Exception as e:
        print(f"❌ Error parsing URL: {e}")
        return

    # Step 3: Exchange authorization code for tokens
    print("\n📋 STEP 3: Exchange Code for Tokens")
    print("=" * 50)

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        tokens = response.json()

        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")

        if not refresh_token:
            print("❌ No refresh token received. This might happen if:")
            print("   - You've already authorized this app before")
            print("   - The OAuth client isn't configured for offline access")
            print(
                "   - Try revoking access at: https://myaccount.google.com/permissions"
            )
            return

        print("✅ Tokens received successfully!")
        print(f"Access Token: {access_token[:20]}...")
        print(f"Refresh Token: {refresh_token[:20]}...")

        # Step 4: Update .env file
        print("\n📋 STEP 4: Update .env File")
        print("=" * 50)
        print("Add this line to your .env file:")
        print(f"PSN_GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")

        # Test the refresh token
        print("\n🧪 Testing the new refresh token...")
        test_credentials = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

        refresh_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if refresh_response.status_code == 200:
            print("✅ Refresh token test successful!")
            print("\n🎉 Setup complete! You can now run: python test_simple_api.py")
        else:
            print(f"❌ Refresh token test failed: {refresh_response.text}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Token exchange failed: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Response: {e.response.text}")


def check_oauth_client_config():
    """Check if OAuth client needs redirect URI configuration."""
    print("\n🔧 OAuth Client Configuration Check")
    print("=" * 50)
    print("If you get a 'redirect_uri_mismatch' error, you need to:")
    print("1. Go to: https://console.cloud.google.com/apis/credentials")
    print("2. Find your OAuth 2.0 Client ID")
    print("3. Click on it to edit")
    print("4. Under 'Authorized redirect URIs', add:")
    print("   - http://localhost:8080")
    print(
        "   - https://developers.google.com/oauthplayground (if using OAuth Playground)"
    )
    print("5. Save the changes")
    print()


if __name__ == "__main__":
    check_oauth_client_config()
    input("Press Enter after updating your OAuth client configuration...")
    generate_refresh_token()
