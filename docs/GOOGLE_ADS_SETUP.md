# Google Ads API Setup Guide

This guide walks you through setting up Google Ads API credentials for the PaidSearchNav MCP server.

## Prerequisites

- A Google Ads account with API access enabled
- A Google Cloud Platform (GCP) project
- Access to Google Ads Manager account (recommended for managing multiple client accounts)

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your Project ID for later use

## Step 2: Enable Google Ads API

1. In your GCP project, go to **APIs & Services > Library**
2. Search for "Google Ads API"
3. Click **Enable**

## Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** user type
   - Fill in the required fields (App name, User support email, Developer contact)
   - Add the scope: `https://www.googleapis.com/auth/adwords`
   - Add your email as a test user
4. For Application type, select **Desktop app**
5. Give it a name (e.g., "PaidSearchNav MCP")
6. Click **Create**
7. Download the JSON file and save the `client_id` and `client_secret`

## Step 4: Get a Developer Token

1. Sign in to your [Google Ads account](https://ads.google.com/)
2. Click the tools icon in the upper right
3. Under **Setup**, click **API Center**
4. If you don't have a developer token:
   - Click **Apply for access** and complete the form
   - Your token will initially have "Test Account" access (sufficient for development)
5. Copy your **Developer Token**

**Note**: Test account access allows you to connect to your own accounts and test accounts. For production access to client accounts, you'll need to apply for standard or higher access.

## Step 5: Generate a Refresh Token

The refresh token allows the MCP server to authenticate without manual intervention.

### Option A: Using the Official Generate Refresh Token Script

1. Install the Google Ads Python library:
   ```bash
   pip install google-ads
   ```

2. Download Google's official script:
   ```bash
   curl -o generate_refresh_token.py \
     https://raw.githubusercontent.com/googleads/google-ads-python/main/examples/authentication/generate_user_credentials.py
   ```

3. Run the script:
   ```bash
   python generate_refresh_token.py \
     --client_id YOUR_CLIENT_ID \
     --client_secret YOUR_CLIENT_SECRET
   ```

4. Follow the prompts:
   - A browser window will open asking you to authorize the application
   - Sign in with the Google account that has access to your Google Ads account
   - Grant the requested permissions
   - Copy the authorization code from the browser
   - Paste it into the terminal

5. The script will output your `refresh_token`. Save this securely.

### Option B: Manual OAuth Flow

If the script doesn't work, you can generate a refresh token manually:

1. Build the authorization URL:
   ```
   https://accounts.google.com/o/oauth2/v2/auth?
   client_id=YOUR_CLIENT_ID&
   redirect_uri=urn:ietf:wg:oauth:2.0:oob&
   response_type=code&
   access_type=offline&
   scope=https://www.googleapis.com/auth/adwords
   ```

2. Visit this URL in your browser and authorize the application

3. Copy the authorization code from the browser

4. Exchange the code for a refresh token using curl:
   ```bash
   curl -X POST https://oauth2.googleapis.com/token \
     -d "code=YOUR_AUTH_CODE" \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob" \
     -d "grant_type=authorization_code"
   ```

5. The response will contain your `refresh_token`

## Step 6: Get Your Login Customer ID

The Login Customer ID is your Google Ads Manager account ID (without dashes).

1. Sign in to [Google Ads](https://ads.google.com/)
2. Look at the top right corner for your customer ID (format: 123-456-7890)
3. Remove the dashes: `1234567890`

**Important**:
- If you have a Manager (MCC) account, use that ID
- If you only have a single account, use that account's ID
- The Login Customer ID must have access to all accounts you want to query

## Step 7: Configure Your Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```bash
   # Google Ads API Configuration
   GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here
   GOOGLE_ADS_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
   GOOGLE_ADS_CLIENT_SECRET=your_client_secret_here
   GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token_here
   GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
   GOOGLE_ADS_API_VERSION=v17
   ```

3. Verify your configuration:
   ```bash
   # Check that all required variables are set
   grep GOOGLE_ADS .env
   ```

## Step 8: Test Your API Connection

### Quick Test with Python

Create a test script to verify your credentials:

```python
from google.ads.googleads.client import GoogleAdsClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create client
client = GoogleAdsClient.load_from_env()

# Test connection
customer_service = client.get_service("CustomerService")
accessible_customers = customer_service.list_accessible_customers()

print("Successfully connected to Google Ads API!")
print(f"Accessible customer IDs: {accessible_customers.resource_names}")
```

Run the test:
```bash
python test_connection.py
```

### Test with the MCP Server

1. Start the MCP server:
   ```bash
   python -m paidsearchnav_mcp.server
   ```

2. In another terminal, use the MCP client to test a tool:
   ```bash
   # Example: Get campaigns for a customer
   echo '{"tool": "get_campaigns", "arguments": {"customer_id": "1234567890"}}' | \
     python -m mcp.client stdio python -m paidsearchnav_mcp.server
   ```

## Troubleshooting

### Common Issues

#### "UNAUTHENTICATED: Request is missing required authentication credential"

**Solution**: Check that all credentials are correctly set in your `.env` file, especially:
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`

#### "PERMISSION_DENIED: User doesn't have permission to access customer"

**Solution**: Verify that:
- Your `GOOGLE_ADS_LOGIN_CUSTOMER_ID` has access to the customer account you're querying
- The Google account used to generate the refresh token has access to the Manager account
- You're using the correct customer ID format (no dashes)

#### "INVALID_ARGUMENT: Deadline Exceeded"

**Solution**:
- Check your internet connection
- Verify that the Google Ads API is not experiencing outages
- Try increasing timeout settings in your client configuration

#### "Developer token is not approved for production access"

**Solution**:
- This is expected for new developer tokens
- Test account access allows you to query your own accounts
- For production access to client accounts, apply for standard access in the API Center

#### "Invalid refresh token"

**Solution**:
- The refresh token may have expired or been revoked
- Generate a new refresh token following Step 5
- Ensure you're using `access_type=offline` when generating the token

### Testing in Docker

If you're running the MCP server in Docker, ensure your `.env` file is properly mounted:

```bash
# Test with docker-compose
docker-compose up mcp-server

# Check logs for connection errors
docker-compose logs -f mcp-server
```

### Debugging Tips

1. **Enable detailed logging**: Set `ENVIRONMENT=development` in your `.env` file for verbose output

2. **Check API quotas**: Monitor your usage in the [Google Cloud Console](https://console.cloud.google.com/apis/dashboard)

3. **Verify account access**: Use the Google Ads UI to confirm you can access the accounts programmatically

4. **Test with official examples**: Run examples from the [google-ads-python repository](https://github.com/googleads/google-ads-python/tree/main/examples) to isolate MCP-specific issues

## Additional Resources

- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)
- [OAuth 2.0 Guide](https://developers.google.com/google-ads/api/docs/oauth/overview)
- [Python Client Library](https://github.com/googleads/google-ads-python)
- [API Support Forum](https://groups.google.com/g/adwords-api)

## Security Best Practices

1. **Never commit credentials**: Ensure `.env` is in your `.gitignore`
2. **Rotate tokens regularly**: Generate new refresh tokens periodically
3. **Use environment-specific tokens**: Keep separate credentials for development and production
4. **Limit OAuth scope**: Only request the `adwords` scope, nothing more
5. **Monitor API usage**: Set up alerts for unusual activity in GCP Console
6. **Use Manager accounts**: Connect via a Manager (MCC) account for better security and management

## Next Steps

Once you have your credentials configured and tested:

1. Explore the available MCP tools (see main [README.md](/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/README.md))
2. Configure BigQuery access for historical data analysis
3. Set up Redis for caching frequently accessed data
4. Start building Claude Skills that use the MCP server

## Support

If you encounter issues not covered in this guide:

- Check the [GitHub Issues](https://github.com/datablogin/PaidSearchNav-MCP/issues)
- Review the [Google Ads API support resources](https://developers.google.com/google-ads/api/docs/support)
- Consult the [troubleshooting section](#troubleshooting) above
