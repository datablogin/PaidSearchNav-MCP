# Google Ads API Integration

This document describes the Google Ads API integration for PaidSearchNav.

## Overview

The Google Ads API client (`paidsearchnav.platforms.google.client.GoogleAdsAPIClient`) implements the `DataProvider` interface to fetch campaign data from Google Ads accounts. It supports:

- Campaign data retrieval
- Keyword performance analysis
- Search term reports
- Negative keyword management
- Geographic performance data (coming soon)

## Configuration

The API client requires the following credentials:

```python
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

client = GoogleAdsAPIClient(
    developer_token="YOUR_DEVELOPER_TOKEN",
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    refresh_token="YOUR_REFRESH_TOKEN",
    login_customer_id="MCC_ACCOUNT_ID"  # Optional, for MCC access
)
```

### Environment Variables

When using with the configuration system (Issue #13), set these environment variables:

```bash
PSN_GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
PSN_GOOGLE_ADS_CLIENT_ID=your-client-id
PSN_GOOGLE_ADS_CLIENT_SECRET=your-client-secret
PSN_GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token
PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID=your-mcc-id  # Optional
```

## Authentication

PaidSearchNav supports two authentication methods for Google Ads API:

### Browser-based Authentication (Interactive)

In interactive environments with a browser available, the default authentication flow opens a browser window for user consent:

```python
from paidsearchnav.platforms.google.auth import OAuth2TokenManager
from paidsearchnav.core.config import Settings

# Initialize with settings
settings = Settings()
token_manager = OAuth2TokenManager(settings)

# Authenticate for a customer
creds = token_manager.get_credentials("1234567890")
```

### Device Flow Authentication (Server/Headless)

For server environments, CI/CD pipelines, Docker containers, and other headless deployments, PaidSearchNav automatically detects the environment and uses the OAuth2 device flow:

```python
# In a headless environment (auto-detected)
creds = token_manager.get_credentials("1234567890")

# This will:
# 1. Display a URL and verification code
# 2. Wait for user to complete authentication in any browser
# 3. Return valid credentials once authorized
```

You can also force a specific authentication method:

```python
# Force device flow (for servers)
creds = token_manager.get_credentials(
    "1234567890",
    force_auth_method="device"
)

# Force browser flow (for local development)
creds = token_manager.get_credentials(
    "1234567890", 
    force_auth_method="browser"
)
```

### Headless Environment Detection

The following conditions trigger automatic device flow authentication:

1. **CI/CD Environments**: When running in CI (GitHub Actions, Jenkins, Travis, etc.)
2. **Docker Containers**: When running inside Docker
3. **No Display**: When `DISPLAY` environment variable is not set
4. **Explicit Flag**: When `PSN_HEADLESS=true` is set
5. **Non-TTY**: When stdin/stdout are not TTY devices

### Service Account Authentication

For fully automated server-to-server communication, you can use Google service accounts (future enhancement).

### Authentication Performance Comparison

| Method | Initial Auth Time | Token Refresh | User Interaction | Use Case |
|--------|------------------|---------------|------------------|----------|
| **Browser Flow** | 5-15 seconds | <1 second | Required (browser) | Local development |
| **Device Flow** | 30-120 seconds* | <1 second | Required (any device) | Servers, CI/CD |
| **Service Account** | <1 second | <1 second | Not required | Fully automated |

*Device flow time depends on how quickly the user completes authentication on another device

**Key Performance Characteristics:**
- Both methods cache tokens after initial authentication
- Token refresh is automatic and near-instantaneous for both methods
- Device flow adds 5-second polling intervals to check authorization status
- Browser flow requires local port 8080 to be available
- Device flow works behind firewalls and in restricted networks

## Usage Examples

### Fetching Campaigns

```python
import asyncio
from datetime import datetime

async def get_campaigns_example():
    # Initialize client
    client = GoogleAdsAPIClient(...)
    
    # Fetch all campaigns
    campaigns = await client.get_campaigns("1234567890")
    
    # Fetch only search campaigns
    search_campaigns = await client.get_campaigns(
        "1234567890",
        campaign_types=["SEARCH"]
    )
    
    for campaign in campaigns:
        print(f"{campaign.name}: ${campaign.cost:.2f} spent, {campaign.conversions} conversions")
```

### Analyzing Keywords

```python
async def analyze_keywords():
    client = GoogleAdsAPIClient(...)
    
    # Get all keywords
    keywords = await client.get_keywords("1234567890")
    
    # Filter by match type
    broad_keywords = [k for k in keywords if k.match_type == MatchType.BROAD]
    
    # Find low quality score keywords
    low_quality = [k for k in keywords if k.quality_score and k.quality_score < 7]
    
    print(f"Found {len(low_quality)} keywords with quality score < 7")
```

### Search Terms Analysis

```python
from datetime import datetime, timedelta

async def analyze_search_terms():
    client = GoogleAdsAPIClient(...)
    
    # Last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    search_terms = await client.get_search_terms(
        "1234567890",
        start_date,
        end_date
    )
    
    # Find high-performing queries not added as keywords
    high_performers = [
        st for st in search_terms
        if st.conversions > 2 
        and st.cpa < 50
        and st.status == "NONE"
    ]
    
    # Find queries to add as negatives
    negative_candidates = [
        st for st in search_terms
        if st.clicks > 10
        and st.conversions == 0
    ]
```

### Negative Keyword Management

```python
async def check_negative_conflicts():
    client = GoogleAdsAPIClient(...)
    
    # Get all negative keywords
    negatives = await client.get_negative_keywords("1234567890")
    
    # Group by level
    campaign_negatives = [n for n in negatives if n["level"] == "campaign"]
    ad_group_negatives = [n for n in negatives if n["level"] == "ad_group"]
    
    print(f"Campaign level negatives: {len(campaign_negatives)}")
    print(f"Ad group level negatives: {len(ad_group_negatives)}")
```

## Data Models

### Campaign
- `campaign_id`: Unique identifier
- `name`: Campaign name
- `status`: ENABLED, PAUSED, REMOVED
- `campaign_type`: SEARCH, PERFORMANCE_MAX, SHOPPING, etc.
- `budget_amount`: Daily budget in account currency
- `bidding_strategy`: TARGET_CPA, TARGET_ROAS, MAXIMIZE_CONVERSIONS, etc.
- Performance metrics: impressions, clicks, cost, conversions, conversion_value

### Keyword
- `keyword_id`: Unique identifier
- `text`: Keyword text
- `match_type`: EXACT, PHRASE, BROAD
- `status`: ENABLED, PAUSED, REMOVED
- `quality_score`: 1-10 (nullable)
- `cpc_bid`: Max CPC bid
- Performance metrics with calculated properties (CTR, CPA, ROAS)

### SearchTerm
- `query`: The actual search query
- `status`: ADDED, EXCLUDED, NONE
- `keyword_id`: Matched keyword (if any)
- `match_type`: How the query matched
- Performance metrics with calculated properties

## Error Handling

The client handles several types of errors:

```python
from paidsearchnav.core.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError
)

try:
    campaigns = await client.get_campaigns("1234567890")
except AuthenticationError:
    # Handle authentication issues
    print("Check your credentials")
except RateLimitError:
    # Handle rate limiting
    print("Too many requests, please wait")
except APIError as e:
    # Handle other API errors
    print(f"API error: {e}")
```

## Performance Considerations

1. **Batch Operations**: The client fetches data in batches to minimize API calls
2. **Async/Await**: All methods are async for concurrent operations
3. **Rate Limiting**: Respects Google Ads API rate limits
4. **Large Datasets**: Handles pagination automatically

## Testing

The integration includes comprehensive test coverage:

- **Unit Tests**: Test individual methods with mocked Google Ads client
- **Integration Tests**: Test complete workflows with mocked API responses

Run tests:
```bash
pytest tests/unit/platforms/google/test_client.py
pytest tests/integration/test_google_ads_api.py
```

## Future Enhancements

1. **Geographic Performance**: Add `get_geo_performance()` method
2. **Performance Max**: Enhanced support for PMax campaign analysis
3. **Caching**: Add response caching for frequently accessed data
4. **Bulk Operations**: Support for bulk updates and modifications
5. **Real-time Monitoring**: WebSocket support for live data

## Dependencies

- `google-ads`: Official Google Ads Python client library
- `pydantic`: Data validation and models
- `asyncio`: Asynchronous operations

## Related Documentation

- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)
- [OAuth2 Token Manager](./oauth2-token-manager.md) (Issue #11)
- [Architecture Overview](../ARCHITECTURE.md)