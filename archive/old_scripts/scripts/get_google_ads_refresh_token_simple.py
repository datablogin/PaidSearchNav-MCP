#!/usr/bin/env python3
"""
Simplified Google Ads API refresh token generator
Uses direct OAuth2 flow without strict scope validation
"""

import json
import os
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_refresh_token_simple():
    """Get refresh token using direct OAuth2 flow."""

    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ Missing Google Ads credentials in .env file")
        print("Required: PSN_GOOGLE_ADS_CLIENT_ID and PSN_GOOGLE_ADS_CLIENT_SECRET")
        return None

    print(f"🔑 Using Client ID: {client_id}")

    # Step 1: Generate authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": "http://localhost:8080/callback",
        "scope": "https://www.googleapis.com/auth/adwords",
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",  # Force consent to get refresh token
        "include_granted_scopes": "true",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(auth_params)

    print("\n🌐 Opening browser for Google Ads API authorization...")
    print(f"📋 Authorization URL: {auth_url}")

    # Open browser
    webbrowser.open(auth_url)

    print("\n📝 Instructions:")
    print("1. Browser should open automatically")
    print("2. Sign in to your Google account that has Google Ads access")
    print("3. Grant permissions to access Google Ads")
    print("4. You'll be redirected to a 'This site can't be reached' page")
    print("5. Copy the FULL URL from the address bar")
    print(
        "6. It will look like: http://localhost:8080/callback?code=LONG_CODE&scope=..."
    )

    # Get the full callback URL from user
    callback_url = input("\n🔗 Paste the full callback URL here: ").strip()

    if not callback_url:
        print("❌ No callback URL provided")
        return None

    try:
        # Parse authorization code from URL
        parsed_url = urlparse(callback_url)
        query_params = parse_qs(parsed_url.query)

        if "code" not in query_params:
            print("❌ No authorization code found in URL")
            print("Make sure you copied the full callback URL")
            return None

        auth_code = query_params["code"][0]
        print(f"✅ Found authorization code: {auth_code[:20]}...")

        # Step 2: Exchange code for tokens
        token_params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8080/callback",
        }

        print("🔄 Exchanging authorization code for tokens...")

        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data=token_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        token_data = response.json()

        if "refresh_token" not in token_data:
            print("❌ No refresh token in response")
            print("This might happen if you've already authorized this app before.")
            print(
                "Try revoking access at https://myaccount.google.com/permissions and try again."
            )
            print(f"Response: {json.dumps(token_data, indent=2)}")
            return None

        refresh_token = token_data["refresh_token"]
        access_token = token_data["access_token"]

        print("\n✅ Successfully obtained tokens!")
        print(f"🔄 Refresh Token: {refresh_token}")
        print(f"🎫 Access Token: {access_token[:50]}...")

        if "scope" in token_data:
            print(f"📋 Granted Scopes: {token_data['scope']}")

        # Add to .env instructions
        print("\n📝 Add this to your .env file:")
        print(f"PSN_GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")

        return refresh_token

    except Exception as e:
        print(f"❌ Error processing callback: {e}")
        print("💡 Make sure you pasted the complete callback URL")
        return None


def test_credentials_simple(refresh_token):
    """Test credentials with a simple token refresh."""

    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET")

    try:
        # Test refresh token by getting a new access token
        refresh_params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        print("🧪 Testing refresh token...")

        response = requests.post(
            "https://oauth2.googleapis.com/token", data=refresh_params
        )

        if response.status_code == 200:
            token_data = response.json()
            print("✅ Refresh token test successful!")
            print(f"🎫 Got new access token: {token_data['access_token'][:50]}...")
            return True
        else:
            print(f"❌ Refresh token test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Refresh token test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Simplified Google Ads API Refresh Token Generator")
    print("=" * 60)

    refresh_token = get_refresh_token_simple()

    if refresh_token:
        print("\n🧪 Testing refresh token...")
        if test_credentials_simple(refresh_token):
            print(
                "\n✅ All set! You can now run live analyzers with Google Ads API access."
            )
            print("\n🔄 Don't forget to add the refresh token to your .env file!")
        else:
            print(
                "\n⚠️  Token obtained but test failed. Check your developer token and permissions."
            )
    else:
        print("\n❌ Failed to obtain refresh token.")
        print(
            "💡 Try the alternative method or check your Google Ads account permissions."
        )
