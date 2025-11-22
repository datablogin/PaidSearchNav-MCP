"""Integration tests for MCP server tools.

Tests all 5 implemented MCP tools with mocked Google Ads API client:
- get_search_terms
- get_keywords
- get_campaigns
- get_negative_keywords
- get_geo_performance
"""

import os
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from paidsearchnav_mcp.server import (
    CampaignsRequest,
    KeywordsRequest,
    NegativeKeywordsRequest,
    SearchTermsRequest,
    get_campaigns,
    get_geo_performance,
    get_keywords,
    get_negative_keywords,
    get_search_terms,
    reset_client_for_testing,
)


# Mock the data classes since we're testing the MCP server layer, not the Google Ads client
class MockMatchType:
    """Mock MatchType enum."""
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


class MockSearchTermMetrics:
    """Mock SearchTermMetrics."""
    def __init__(self, impressions=0, clicks=0, cost=0.0, conversions=0.0,
                 conversion_value=0.0, ctr=0.0, avg_cpc=0.0, conversion_rate=0.0):
        self.impressions = impressions
        self.clicks = clicks
        self.cost = cost
        self.conversions = conversions
        self.conversion_value = conversion_value
        self.ctr = ctr
        self.avg_cpc = avg_cpc
        self.conversion_rate = conversion_rate


class MockSearchTerm:
    """Mock SearchTerm."""
    def __init__(self, customer_id, campaign_id, campaign_name, ad_group_id,
                 ad_group_name, search_term, keyword_text, match_type, metrics):
        self.customer_id = customer_id
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.ad_group_id = ad_group_id
        self.ad_group_name = ad_group_name
        self.search_term = search_term
        self.keyword_text = keyword_text
        self.match_type = match_type
        self.metrics = metrics


class MockKeyword:
    """Mock Keyword."""
    def __init__(self, keyword_id, customer_id, campaign_id, campaign_name,
                 ad_group_id, ad_group_name, keyword_text, match_type, status,
                 max_cpc, quality_score, impressions, clicks, cost, conversions,
                 conversion_value):
        self.keyword_id = keyword_id
        self.customer_id = customer_id
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.ad_group_id = ad_group_id
        self.ad_group_name = ad_group_name
        self.keyword_text = keyword_text
        self.match_type = match_type
        self.status = status
        self.max_cpc = max_cpc
        self.quality_score = quality_score
        self.impressions = impressions
        self.clicks = clicks
        self.cost = cost
        self.conversions = conversions
        self.conversion_value = conversion_value


class MockCampaign:
    """Mock Campaign."""
    def __init__(self, campaign_id, customer_id, name, status, type,
                 budget_amount, budget_currency, bidding_strategy, target_cpa,
                 target_roas, impressions, clicks, cost, conversions,
                 conversion_value):
        self.campaign_id = campaign_id
        self.customer_id = customer_id
        self.name = name
        self.status = status
        self.type = type
        self.budget_amount = budget_amount
        self.budget_currency = budget_currency
        self.bidding_strategy = bidding_strategy
        self.target_cpa = target_cpa
        self.target_roas = target_roas
        self.impressions = impressions
        self.clicks = clicks
        self.cost = cost
        self.conversions = conversions
        self.conversion_value = conversion_value


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton_client():
    """Reset the singleton client instance before each test."""
    reset_client_for_testing()
    yield
    reset_client_for_testing()


@pytest.fixture
def mock_env_credentials(monkeypatch):
    """Set up mock environment variables for Google Ads credentials."""
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "test_dev_token")
    monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("GOOGLE_ADS_REFRESH_TOKEN", "test_refresh_token")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1234567890")


@pytest.fixture
def mock_search_terms():
    """Create mock search terms data."""
    return [
        MockSearchTerm(
            customer_id="1234567890",
            campaign_id="111",
            campaign_name="Test Campaign",
            ad_group_id="222",
            ad_group_name="Test Ad Group",
            search_term="running shoes",
            keyword_text="shoes",
            match_type=MockMatchType.BROAD,
            metrics=MockSearchTermMetrics(
                impressions=100,
                clicks=10,
                cost=5.50,
                conversions=2.0,
                conversion_value=50.0,
                ctr=0.1,
                avg_cpc=0.55,
                conversion_rate=0.2,
            ),
        ),
        MockSearchTerm(
            customer_id="1234567890",
            campaign_id="111",
            campaign_name="Test Campaign",
            ad_group_id="222",
            ad_group_name="Test Ad Group",
            search_term="nike shoes",
            keyword_text="shoes",
            match_type=MockMatchType.BROAD,
            metrics=MockSearchTermMetrics(
                impressions=50,
                clicks=5,
                cost=3.00,
                conversions=1.0,
                conversion_value=25.0,
                ctr=0.1,
                avg_cpc=0.60,
                conversion_rate=0.2,
            ),
        ),
    ]


@pytest.fixture
def mock_keywords():
    """Create mock keywords data."""
    return [
        MockKeyword(
            keyword_id="k1",
            customer_id="1234567890",
            campaign_id="111",
            campaign_name="Test Campaign",
            ad_group_id="222",
            ad_group_name="Test Ad Group",
            keyword_text="running shoes",
            match_type=MockMatchType.EXACT,
            status="ENABLED",
            max_cpc=1.50,
            quality_score=8,
            impressions=1000,
            clicks=100,
            cost=150.0,
            conversions=10.0,
            conversion_value=500.0,
        ),
        MockKeyword(
            keyword_id="k2",
            customer_id="1234567890",
            campaign_id="111",
            campaign_name="Test Campaign",
            ad_group_id="222",
            ad_group_name="Test Ad Group",
            keyword_text="shoes",
            match_type=MockMatchType.BROAD,
            status="ENABLED",
            max_cpc=1.00,
            quality_score=7,
            impressions=500,
            clicks=50,
            cost=50.0,
            conversions=5.0,
            conversion_value=250.0,
        ),
    ]


@pytest.fixture
def mock_campaigns():
    """Create mock campaigns data."""
    return [
        MockCampaign(
            campaign_id="111",
            customer_id="1234567890",
            name="Test Campaign 1",
            status="ENABLED",
            type="SEARCH",
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy="TARGET_CPA",
            target_cpa=10.0,
            target_roas=None,
            impressions=10000,
            clicks=1000,
            cost=500.0,
            conversions=50.0,
            conversion_value=2500.0,
        ),
        MockCampaign(
            campaign_id="112",
            customer_id="1234567890",
            name="Test Campaign 2",
            status="ENABLED",
            type="PERFORMANCE_MAX",
            budget_amount=200.0,
            budget_currency="USD",
            bidding_strategy="MAXIMIZE_CONVERSIONS",
            target_cpa=None,
            target_roas=4.0,
            impressions=20000,
            clicks=2000,
            cost=1000.0,
            conversions=100.0,
            conversion_value=5000.0,
        ),
    ]


@pytest.fixture
def mock_negative_keywords():
    """Create mock negative keywords data."""
    return [
        {
            "id": "nk1",
            "text": "free",
            "match_type": "BROAD",
            "level": "campaign",
            "campaign_id": "111",
            "campaign_name": "Test Campaign",
            "ad_group_id": None,
            "ad_group_name": None,
            "shared_set_id": None,
            "shared_set_name": None,
        },
        {
            "id": "nk2",
            "text": "cheap",
            "match_type": "PHRASE",
            "level": "ad_group",
            "campaign_id": "111",
            "campaign_name": "Test Campaign",
            "ad_group_id": "222",
            "ad_group_name": "Test Ad Group",
            "shared_set_id": None,
            "shared_set_name": None,
        },
    ]


@pytest.fixture
def mock_geo_performance():
    """Create mock geographic performance data."""
    return [
        {
            "campaign_id": "111",
            "location_id": "1023191",
            "location_name": "New York, NY",
            "location_type": "CITY",
            "country_code": "US",
            "state": "New York",
            "city": "New York",
            "postal_code": None,
            "impressions": 5000,
            "clicks": 500,
            "cost": 250.0,
            "conversions": 25.0,
            "conversion_value": 1250.0,
            "distance_miles": None,
            "store_visits": 10.0,
        },
        {
            "campaign_id": "111",
            "location_id": "1014044",
            "location_name": "Los Angeles, CA",
            "location_type": "CITY",
            "country_code": "US",
            "state": "California",
            "city": "Los Angeles",
            "postal_code": None,
            "impressions": 3000,
            "clicks": 300,
            "cost": 150.0,
            "conversions": 15.0,
            "conversion_value": 750.0,
            "distance_miles": None,
            "store_visits": 5.0,
        },
    ]


# ============================================================================
# Tests - get_search_terms
# ============================================================================


@pytest.mark.asyncio
async def test_get_search_terms_success(mock_env_credentials, mock_search_terms):
    """Test successful search terms retrieval."""
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
        campaign_id="111",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_search_terms = AsyncMock(return_value=mock_search_terms)
        mock_client_class.return_value = mock_client

        result = await get_search_terms.fn(request)

        # Verify response structure
        assert result["status"] == "success"
        assert "message" in result
        assert "Retrieved 2 search terms" in result["message"]
        assert "metadata" in result
        assert "data" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["customer_id"] == "1234567890"
        assert metadata["start_date"] == "2024-01-01"
        assert metadata["end_date"] == "2024-01-31"
        assert metadata["campaign_id"] == "111"
        assert metadata["record_count"] == 2

        # Verify data structure
        data = result["data"]
        assert len(data) == 2
        assert data[0]["search_term"] == "running shoes"
        assert data[0]["keyword_text"] == "shoes"
        assert data[0]["match_type"] == MockMatchType.BROAD
        assert data[0]["metrics"]["impressions"] == 100
        assert data[0]["metrics"]["clicks"] == 10
        assert data[0]["metrics"]["cost"] == 5.50

        # Verify API client was called correctly
        mock_client.get_search_terms.assert_awaited_once()
        call_args = mock_client.get_search_terms.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"
        assert call_args.kwargs["campaigns"] == ["111"]


@pytest.mark.asyncio
async def test_get_search_terms_no_campaign_filter(
    mock_env_credentials, mock_search_terms
):
    """Test search terms retrieval without campaign filter."""
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_search_terms = AsyncMock(return_value=mock_search_terms)
        mock_client_class.return_value = mock_client

        result = await get_search_terms.fn(request)

        assert result["status"] == "success"
        mock_client.get_search_terms.assert_awaited_once()
        call_args = mock_client.get_search_terms.call_args
        assert call_args.kwargs["campaigns"] is None


@pytest.mark.asyncio
async def test_get_search_terms_invalid_date_format(mock_env_credentials):
    """Test search terms with invalid date format."""
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="invalid-date",
        end_date="2024-01-31",
    )

    with patch("paidsearchnav_mcp.server.GoogleAdsAPIClient"):
        result = await get_search_terms.fn(request)

        assert result["status"] == "error"
        assert "Invalid input" in result["message"]
        assert result["data"] == []


@pytest.mark.asyncio
async def test_get_search_terms_missing_credentials(monkeypatch):
    """Test search terms with missing credentials."""
    # Clear environment variables
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    result = await get_search_terms.fn(request)

    assert result["status"] == "error"
    assert "Missing required environment variables" in result["message"]
    assert result["data"] == []


@pytest.mark.asyncio
async def test_get_search_terms_api_error(mock_env_credentials):
    """Test search terms with API error."""
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_search_terms = AsyncMock(
            side_effect=Exception("API connection failed")
        )
        mock_client_class.return_value = mock_client

        result = await get_search_terms.fn(request)

        assert result["status"] == "error"
        assert "unexpected error occurred" in result["message"].lower()
        assert result["data"] == []


# ============================================================================
# Tests - get_keywords
# ============================================================================


@pytest.mark.asyncio
async def test_get_keywords_success(mock_env_credentials, mock_keywords):
    """Test successful keywords retrieval."""
    request = KeywordsRequest(
        customer_id="1234567890",
        campaign_id="111",
        ad_group_id="222",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_keywords = AsyncMock(return_value=mock_keywords)
        mock_client_class.return_value = mock_client

        result = await get_keywords.fn(request)

        # Verify response structure
        assert result["status"] == "success"
        assert "Retrieved 2 keywords" in result["message"]
        assert "metadata" in result
        assert "data" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["customer_id"] == "1234567890"
        assert metadata["campaign_id"] == "111"
        assert metadata["ad_group_id"] == "222"
        assert metadata["record_count"] == 2

        # Verify data structure
        data = result["data"]
        assert len(data) == 2
        assert data[0]["keyword_id"] == "k1"
        assert data[0]["keyword_text"] == "running shoes"
        assert data[0]["match_type"] == MockMatchType.EXACT
        assert data[0]["status"] == "ENABLED"
        assert data[0]["max_cpc"] == 1.50
        assert data[0]["quality_score"] == 8
        assert data[0]["impressions"] == 1000
        assert data[0]["clicks"] == 100

        # Verify API client was called correctly
        mock_client.get_keywords.assert_awaited_once()
        call_args = mock_client.get_keywords.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"
        assert call_args.kwargs["campaign_id"] == "111"
        assert call_args.kwargs["ad_groups"] == ["222"]


@pytest.mark.asyncio
async def test_get_keywords_no_filters(mock_env_credentials, mock_keywords):
    """Test keywords retrieval without campaign or ad group filters."""
    request = KeywordsRequest(customer_id="1234567890")

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_keywords = AsyncMock(return_value=mock_keywords)
        mock_client_class.return_value = mock_client

        result = await get_keywords.fn(request)

        assert result["status"] == "success"
        mock_client.get_keywords.assert_awaited_once()
        call_args = mock_client.get_keywords.call_args
        assert call_args.kwargs["campaign_id"] is None
        assert call_args.kwargs["ad_groups"] is None


@pytest.mark.asyncio
async def test_get_keywords_missing_credentials(monkeypatch):
    """Test keywords with missing credentials."""
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

    request = KeywordsRequest(customer_id="1234567890")

    result = await get_keywords.fn(request)

    assert result["status"] == "error"
    assert "Missing required environment variables" in result["message"]
    assert result["data"] == []


@pytest.mark.asyncio
async def test_get_keywords_api_error(mock_env_credentials):
    """Test keywords with API error."""
    request = KeywordsRequest(customer_id="1234567890")

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_keywords = AsyncMock(
            side_effect=Exception("Network timeout")
        )
        mock_client_class.return_value = mock_client

        result = await get_keywords.fn(request)

        assert result["status"] == "error"
        assert "unexpected error occurred" in result["message"].lower()
        assert "Network timeout" in result["message"]
        assert result["data"] == []


# ============================================================================
# Tests - get_campaigns
# ============================================================================


@pytest.mark.asyncio
async def test_get_campaigns_success(mock_env_credentials, mock_campaigns):
    """Test successful campaigns retrieval."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_campaigns = AsyncMock(return_value=mock_campaigns)
        mock_client_class.return_value = mock_client

        result = await get_campaigns.fn(request)

        # Verify response structure
        assert result["status"] == "success"
        assert "Retrieved 2 campaigns" in result["message"]
        assert "metadata" in result
        assert "data" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["customer_id"] == "1234567890"
        assert metadata["start_date"] == "2024-01-01"
        assert metadata["end_date"] == "2024-01-31"
        assert metadata["record_count"] == 2

        # Verify data structure
        data = result["data"]
        assert len(data) == 2
        assert data[0]["campaign_id"] == "111"
        assert data[0]["name"] == "Test Campaign 1"
        assert data[0]["status"] == "ENABLED"
        assert data[0]["type"] == "SEARCH"
        assert data[0]["budget_amount"] == 100.0
        assert data[0]["budget_currency"] == "USD"
        assert data[0]["bidding_strategy"] == "TARGET_CPA"
        assert data[0]["target_cpa"] == 10.0

        assert data[1]["type"] == "PERFORMANCE_MAX"
        assert data[1]["target_roas"] == 4.0

        # Verify API client was called correctly
        mock_client.get_campaigns.assert_awaited_once()
        call_args = mock_client.get_campaigns.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"


@pytest.mark.asyncio
async def test_get_campaigns_invalid_date_format(mock_env_credentials):
    """Test campaigns with invalid date format."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="not-a-date",
    )

    with patch("paidsearchnav_mcp.server.GoogleAdsAPIClient"):
        result = await get_campaigns.fn(request)

        assert result["status"] == "error"
        assert "Invalid input" in result["message"]
        assert result["data"] == []


@pytest.mark.asyncio
async def test_get_campaigns_missing_credentials(monkeypatch):
    """Test campaigns with missing credentials."""
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    result = await get_campaigns.fn(request)

    assert result["status"] == "error"
    assert "Missing required environment variables" in result["message"]
    assert result["data"] == []


@pytest.mark.asyncio
async def test_get_campaigns_api_error(mock_env_credentials):
    """Test campaigns with API error."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_campaigns = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )
        mock_client_class.return_value = mock_client

        result = await get_campaigns.fn(request)

        assert result["status"] == "error"
        assert "unexpected error occurred" in result["message"].lower()
        assert "Rate limit exceeded" in result["message"]
        assert result["data"] == []


# ============================================================================
# Tests - get_negative_keywords
# ============================================================================


@pytest.mark.asyncio
async def test_get_negative_keywords_success(
    mock_env_credentials, mock_negative_keywords
):
    """Test successful negative keywords retrieval."""
    request = NegativeKeywordsRequest(
        customer_id="1234567890",
        campaign_id="111",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_negative_keywords = AsyncMock(
            return_value=mock_negative_keywords
        )
        mock_client_class.return_value = mock_client

        result = await get_negative_keywords.fn(request)

        # Verify response structure
        assert result["status"] == "success"
        assert "Retrieved 2 negative keywords" in result["message"]
        assert "metadata" in result
        assert "data" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["customer_id"] == "1234567890"
        assert metadata["campaign_id"] == "111"
        assert metadata["record_count"] == 2

        # Verify data structure
        data = result["data"]
        assert len(data) == 2
        assert data[0]["id"] == "nk1"
        assert data[0]["text"] == "free"
        assert data[0]["match_type"] == "BROAD"
        assert data[0]["level"] == "campaign"

        # Verify API client was called correctly
        mock_client.get_negative_keywords.assert_awaited_once()
        call_args = mock_client.get_negative_keywords.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"
        assert call_args.kwargs["include_shared_sets"] is True


@pytest.mark.asyncio
async def test_get_negative_keywords_no_campaign_filter(
    mock_env_credentials, mock_negative_keywords
):
    """Test negative keywords retrieval without campaign filter."""
    request = NegativeKeywordsRequest(customer_id="1234567890")

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        # Add a negative keyword from a different campaign
        all_negative_keywords = mock_negative_keywords + [
            {
                "id": "nk3",
                "text": "discount",
                "match_type": "EXACT",
                "level": "campaign",
                "campaign_id": "999",
                "campaign_name": "Other Campaign",
                "ad_group_id": None,
                "ad_group_name": None,
                "shared_set_id": None,
                "shared_set_name": None,
            }
        ]
        mock_client.get_negative_keywords = AsyncMock(
            return_value=all_negative_keywords
        )
        mock_client_class.return_value = mock_client

        result = await get_negative_keywords.fn(request)

        assert result["status"] == "success"
        # Should return all negative keywords without filtering
        assert len(result["data"]) == 3


@pytest.mark.asyncio
async def test_get_negative_keywords_campaign_filter(
    mock_env_credentials, mock_negative_keywords
):
    """Test negative keywords with campaign filter applied."""
    request = NegativeKeywordsRequest(
        customer_id="1234567890",
        campaign_id="111",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        # Add a negative keyword from a different campaign
        all_negative_keywords = mock_negative_keywords + [
            {
                "id": "nk3",
                "text": "discount",
                "match_type": "EXACT",
                "level": "campaign",
                "campaign_id": "999",
                "campaign_name": "Other Campaign",
                "ad_group_id": None,
                "ad_group_name": None,
                "shared_set_id": None,
                "shared_set_name": None,
            }
        ]
        mock_client.get_negative_keywords = AsyncMock(
            return_value=all_negative_keywords
        )
        mock_client_class.return_value = mock_client

        result = await get_negative_keywords.fn(request)

        assert result["status"] == "success"
        # Should filter to only campaign_id=111
        assert len(result["data"]) == 2
        assert all(nk.get("campaign_id") == "111" for nk in result["data"])


@pytest.mark.asyncio
async def test_get_negative_keywords_missing_credentials(monkeypatch):
    """Test negative keywords with missing credentials."""
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

    request = NegativeKeywordsRequest(customer_id="1234567890")

    result = await get_negative_keywords.fn(request)

    assert result["status"] == "error"
    assert "Missing required environment variables" in result["message"]
    assert result["data"] == []


@pytest.mark.asyncio
async def test_get_negative_keywords_api_error(mock_env_credentials):
    """Test negative keywords with API error."""
    request = NegativeKeywordsRequest(customer_id="1234567890")

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_negative_keywords = AsyncMock(
            side_effect=Exception("Permission denied")
        )
        mock_client_class.return_value = mock_client

        result = await get_negative_keywords.fn(request)

        assert result["status"] == "error"
        assert "unexpected error occurred" in result["message"].lower()
        assert "Permission denied" in result["message"]
        assert result["data"] == []


# ============================================================================
# Tests - get_geo_performance
# ============================================================================


@pytest.mark.asyncio
async def test_get_geo_performance_success(
    mock_env_credentials, mock_geo_performance
):
    """Test successful geo performance retrieval."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_geographic_performance = AsyncMock(
            return_value=mock_geo_performance
        )
        mock_client_class.return_value = mock_client

        result = await get_geo_performance.fn(request)

        # Verify response structure
        assert result["status"] == "success"
        assert (
            "Retrieved 2 geographic performance records" in result["message"]
        )
        assert "metadata" in result
        assert "data" in result

        # Verify metadata
        metadata = result["metadata"]
        assert metadata["customer_id"] == "1234567890"
        assert metadata["start_date"] == "2024-01-01"
        assert metadata["end_date"] == "2024-01-31"
        assert metadata["geographic_level"] == "CITY"
        assert metadata["record_count"] == 2

        # Verify data structure
        data = result["data"]
        assert len(data) == 2
        assert data[0]["campaign_id"] == "111"
        assert data[0]["location_name"] == "New York, NY"
        assert data[0]["location_type"] == "CITY"
        assert data[0]["country_code"] == "US"
        assert data[0]["impressions"] == 5000
        assert data[0]["clicks"] == 500
        assert data[0]["store_visits"] == 10.0

        # Verify API client was called correctly
        mock_client.get_geographic_performance.assert_awaited_once()
        call_args = mock_client.get_geographic_performance.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"
        assert call_args.kwargs["geographic_level"] == "CITY"


@pytest.mark.asyncio
async def test_get_geo_performance_invalid_date_format(mock_env_credentials):
    """Test geo performance with invalid date format."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="invalid",
        end_date="2024-01-31",
    )

    with patch("paidsearchnav_mcp.server.GoogleAdsAPIClient"):
        result = await get_geo_performance.fn(request)

        assert result["status"] == "error"
        assert "Invalid input" in result["message"]
        assert result["data"] == []


@pytest.mark.asyncio
async def test_get_geo_performance_missing_credentials(monkeypatch):
    """Test geo performance with missing credentials."""
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    result = await get_geo_performance.fn(request)

    assert result["status"] == "error"
    assert "Missing required environment variables" in result["message"]
    assert result["data"] == []


@pytest.mark.asyncio
async def test_get_geo_performance_api_error(mock_env_credentials):
    """Test geo performance with API error."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    with patch(
        "paidsearchnav_mcp.server.GoogleAdsAPIClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get_geographic_performance = AsyncMock(
            side_effect=Exception("Database unavailable")
        )
        mock_client_class.return_value = mock_client

        result = await get_geo_performance.fn(request)

        assert result["status"] == "error"
        assert "unexpected error occurred" in result["message"].lower()
        assert "Database unavailable" in result["message"]
        assert result["data"] == []


# ============================================================================
# Tests - Request Validation
# ============================================================================


@pytest.mark.asyncio
async def test_search_terms_request_validation():
    """Test SearchTermsRequest model validation."""
    # Valid request
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )
    assert request.customer_id == "1234567890"
    assert request.start_date == "2024-01-01"
    assert request.end_date == "2024-01-31"
    assert request.campaign_id is None

    # With optional campaign_id
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
        campaign_id="111",
    )
    assert request.campaign_id == "111"


@pytest.mark.asyncio
async def test_keywords_request_validation():
    """Test KeywordsRequest model validation."""
    # Valid request with minimal fields
    request = KeywordsRequest(customer_id="1234567890")
    assert request.customer_id == "1234567890"
    assert request.campaign_id is None
    assert request.ad_group_id is None

    # With all optional fields
    request = KeywordsRequest(
        customer_id="1234567890",
        campaign_id="111",
        ad_group_id="222",
    )
    assert request.campaign_id == "111"
    assert request.ad_group_id == "222"


@pytest.mark.asyncio
async def test_campaigns_request_validation():
    """Test CampaignsRequest model validation."""
    request = CampaignsRequest(
        customer_id="1234567890",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )
    assert request.customer_id == "1234567890"
    assert request.start_date == "2024-01-01"
    assert request.end_date == "2024-01-31"


@pytest.mark.asyncio
async def test_negative_keywords_request_validation():
    """Test NegativeKeywordsRequest model validation."""
    # Valid request with minimal fields
    request = NegativeKeywordsRequest(customer_id="1234567890")
    assert request.customer_id == "1234567890"
    assert request.campaign_id is None

    # With optional campaign_id
    request = NegativeKeywordsRequest(
        customer_id="1234567890",
        campaign_id="111",
    )
    assert request.campaign_id == "111"
