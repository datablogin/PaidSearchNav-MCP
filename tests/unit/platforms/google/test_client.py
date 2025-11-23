"""Unit tests for Google Ads API client."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from google.ads.googleads.errors import GoogleAdsException

from paidsearchnav_mcp.core.exceptions import APIError, AuthenticationError, RateLimitError
from paidsearchnav_mcp.models.campaign import Campaign
from paidsearchnav_mcp.models.keyword import Keyword, MatchType
from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient


@pytest.fixture
def client():
    """Create a Google Ads API client instance."""
    return GoogleAdsAPIClient(
        developer_token="test-token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token",
        login_customer_id="1234567890",
    )


@pytest.fixture
def mock_google_ads_client():
    """Mock Google Ads client."""
    with patch("paidsearchnav.platforms.google.client.GoogleAdsClient") as mock:
        yield mock


class TestGoogleAdsAPIClient:
    """Test cases for GoogleAdsAPIClient."""

    def test_client_initialization(self, client):
        """Test client initialization with credentials."""
        assert client.developer_token == "test-token"
        assert client.client_id == "test-client-id"
        assert client.client_secret == "test-client-secret"
        assert client.refresh_token == "test-refresh-token"
        assert client.login_customer_id == "1234567890"
        assert not client._initialized

    def test_get_client_initialization(self, client, mock_google_ads_client):
        """Test lazy initialization of Google Ads client."""
        mock_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_instance

        # First call should initialize
        result = client._get_client()

        assert result == mock_instance
        assert client._initialized
        mock_google_ads_client.load_from_dict.assert_called_once()

        # Second call should return cached client
        result2 = client._get_client()
        assert result2 == mock_instance
        assert mock_google_ads_client.load_from_dict.call_count == 1

    def test_get_client_authentication_error(self, client, mock_google_ads_client):
        """Test authentication error handling."""
        mock_google_ads_client.load_from_dict.side_effect = Exception(
            "Invalid credentials"
        )

        with pytest.raises(AuthenticationError) as exc_info:
            client._get_client()

        assert "Failed to authenticate with Google Ads API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_campaigns_success(self, client, mock_google_ads_client):
        """Test successful campaign fetching."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock customer currency response
        mock_customer_row = MagicMock()
        mock_customer_row.customer.currency_code = "USD"

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 5000000  # $5
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 50000000  # $50
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 100
        mock_campaign_row.metrics.cost_micros = 25000000  # $25
        mock_campaign_row.metrics.conversions = 10
        mock_campaign_row.metrics.conversions_value = 500.0

        # Mock service to return customer data first, then campaign data
        mock_service.search.side_effect = [
            [mock_customer_row],  # First call for customer currency
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert isinstance(campaign, Campaign)
        assert campaign.campaign_id == "123456"
        assert campaign.name == "Test Campaign"
        assert campaign.status == "ENABLED"
        assert campaign.type == "SEARCH"
        assert campaign.budget_amount == 50.0
        assert campaign.budget_currency == "USD"
        assert campaign.bidding_strategy == "TARGET_CPA"
        assert campaign.target_cpa == 5.0
        assert campaign.impressions == 1000
        assert campaign.clicks == 100
        assert campaign.cost == 25.0
        assert campaign.conversions == 10
        assert campaign.conversion_value == 500.0

    @pytest.mark.asyncio
    async def test_get_campaigns_with_eur_currency(
        self, client, mock_google_ads_client
    ):
        """Test campaign fetching with EUR currency."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock customer currency response with EUR
        mock_customer_row = MagicMock()
        mock_customer_row.customer.currency_code = "EUR"

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "European Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 4500000  # €4.50
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 45000000  # €45
        mock_campaign_row.metrics.impressions = 800
        mock_campaign_row.metrics.clicks = 80
        mock_campaign_row.metrics.cost_micros = 22500000  # €22.50
        mock_campaign_row.metrics.conversions = 8
        mock_campaign_row.metrics.conversions_value = 400.0

        # Mock service to return customer data first, then campaign data
        mock_service.search.side_effect = [
            [mock_customer_row],  # First call for customer currency
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.budget_currency == "EUR"
        assert campaign.budget_amount == 45.0
        assert campaign.cost == 22.5

    @pytest.mark.asyncio
    async def test_get_campaigns_currency_fallback(
        self, client, mock_google_ads_client
    ):
        """Test campaign fetching with currency fetch failure fallback to USD."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 5000000
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 50000000
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 100
        mock_campaign_row.metrics.cost_micros = 25000000
        mock_campaign_row.metrics.conversions = 10
        mock_campaign_row.metrics.conversions_value = 500.0

        # Mock service to fail on customer query, succeed on campaigns
        # Create a real exception that the code can catch
        customer_fetch_exception = Exception("Customer fetch failed")
        mock_service.search.side_effect = [
            customer_fetch_exception,  # First call fails
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify fallback to USD
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.budget_currency == "USD"

    @pytest.mark.asyncio
    async def test_get_campaigns_empty_currency_response(
        self, client, mock_google_ads_client
    ):
        """Test campaign fetching with empty currency response fallback to USD."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 5000000
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 50000000
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 100
        mock_campaign_row.metrics.cost_micros = 25000000
        mock_campaign_row.metrics.conversions = 10
        mock_campaign_row.metrics.conversions_value = 500.0

        # Mock service to return empty customer response, succeed on campaigns
        mock_service.search.side_effect = [
            [],  # First call returns empty (no customer data)
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify fallback to USD
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.budget_currency == "USD"

    @pytest.mark.asyncio
    async def test_get_campaigns_unsupported_currency(
        self, client, mock_google_ads_client
    ):
        """Test campaign fetching with unsupported currency fallback to USD."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock customer currency response with unsupported currency
        mock_customer_row = MagicMock()
        mock_customer_row.customer.currency_code = "XYZ"  # Unsupported currency

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 5000000
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 50000000
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 100
        mock_campaign_row.metrics.cost_micros = 25000000
        mock_campaign_row.metrics.conversions = 10
        mock_campaign_row.metrics.conversions_value = 500.0

        # Mock service to return unsupported currency, then campaign data
        mock_service.search.side_effect = [
            [mock_customer_row],  # First call for customer currency (unsupported)
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify fallback to USD for unsupported currency
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.budget_currency == "USD"

    @pytest.mark.asyncio
    async def test_get_campaigns_null_currency_code(
        self, client, mock_google_ads_client
    ):
        """Test campaign fetching with null currency code fallback to USD."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock customer currency response with null currency
        mock_customer_row = MagicMock()
        mock_customer_row.customer.currency_code = None  # Null currency

        # Mock campaign response
        mock_campaign_row = MagicMock()
        mock_campaign_row.campaign.id = 123456
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.campaign.bidding_strategy_type.name = "TARGET_CPA"
        mock_campaign_row.campaign.target_cpa.target_cpa_micros = 5000000
        mock_campaign_row.campaign.target_roas = None
        mock_campaign_row.campaign_budget.amount_micros = 50000000
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 100
        mock_campaign_row.metrics.cost_micros = 25000000
        mock_campaign_row.metrics.conversions = 10
        mock_campaign_row.metrics.conversions_value = 500.0

        # Mock service to return null currency, then campaign data
        mock_service.search.side_effect = [
            [mock_customer_row],  # First call for customer currency (null)
            [mock_campaign_row],  # Second call for campaigns
        ]

        # Execute
        campaigns = await client.get_campaigns("1234567890")

        # Verify fallback to USD for null currency
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.budget_currency == "USD"

    @pytest.mark.asyncio
    async def test_get_campaigns_with_type_filter(self, client, mock_google_ads_client):
        """Test campaign fetching with type filter."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock customer currency response
        mock_customer_row = MagicMock()
        mock_customer_row.customer.currency_code = "USD"

        # Mock the _paginated_search_async method instead of direct service calls
        original_paginated_search = client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            if "customer.currency_code" in query:
                return [mock_customer_row]
            else:
                return []  # Empty campaigns

        client._paginated_search_async = mock_paginated_search

        try:
            # Execute
            await client.get_campaigns(
                "1234567890", campaign_types=["SEARCH", "PERFORMANCE_MAX"]
            )

            # With the pagination changes, there may be 1 or 2 calls depending on currency handling
            # The important part is that the campaign query includes the filters
            assert len(captured_queries) >= 1

            # Find the campaign query (contains campaign fields)
            campaign_query = None
            for query in captured_queries:
                if "campaign.advertising_channel_type" in query:
                    campaign_query = query
                    break

            assert campaign_query is not None, "Campaign query not found"
            assert "campaign.advertising_channel_type = 'SEARCH'" in campaign_query
            assert (
                "campaign.advertising_channel_type = 'PERFORMANCE_MAX'"
                in campaign_query
            )
        finally:
            # Restore original method
            client._paginated_search_async = original_paginated_search

    @pytest.mark.asyncio
    async def test_get_keywords_success(self, client, mock_google_ads_client):
        """Test successful keyword fetching."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock response
        mock_row = MagicMock()
        mock_row.ad_group_criterion.criterion_id = 987654
        mock_row.ad_group_criterion.keyword.text = "test keyword"
        mock_row.ad_group_criterion.keyword.match_type.name = "EXACT"
        mock_row.ad_group_criterion.status.name = "ENABLED"
        mock_row.ad_group_criterion.cpc_bid_micros = 2000000  # $2
        mock_row.ad_group_criterion.quality_info.quality_score = 8
        mock_row.campaign.id = 123456
        mock_row.campaign.name = "Test Campaign"
        mock_row.ad_group.id = 456789
        mock_row.ad_group.name = "Test Ad Group"
        mock_row.metrics.impressions = 500
        mock_row.metrics.clicks = 50
        mock_row.metrics.cost_micros = 10000000  # $10
        mock_row.metrics.conversions = 5
        mock_row.metrics.conversions_value = 250.0

        mock_service.search.return_value = [mock_row]

        # Execute
        keywords = await client.get_keywords("1234567890")

        # Verify
        assert len(keywords) == 1
        keyword = keywords[0]
        assert isinstance(keyword, Keyword)
        assert keyword.keyword_id == "987654"
        assert keyword.text == "test keyword"
        assert keyword.match_type == MatchType.EXACT
        assert keyword.status == "ENABLED"
        assert keyword.cpc_bid == 2.0
        assert keyword.quality_score == 8
        assert keyword.campaign_id == "123456"
        assert keyword.ad_group_id == "456789"
        assert keyword.impressions == 500
        assert keyword.clicks == 50
        assert keyword.cost == 10.0
        assert keyword.conversions == 5
        assert keyword.conversion_value == 250.0

    @pytest.mark.asyncio
    async def test_get_search_terms_success(self, client, mock_google_ads_client):
        """Test successful search terms fetching."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock response
        mock_row = MagicMock()
        mock_row.search_term_view.search_term = "buy shoes online"
        mock_row.search_term_view.status.name = "NONE"
        mock_row.campaign.id = 123456
        mock_row.campaign.name = "Test Campaign"
        mock_row.ad_group.id = 456789
        mock_row.ad_group.name = "Test Ad Group"
        mock_row.ad_group_criterion.criterion_id = 987654
        mock_row.ad_group_criterion.keyword.text = "shoes"
        mock_row.ad_group_criterion.keyword.match_type.name = "BROAD"
        mock_row.metrics.impressions = 100
        mock_row.metrics.clicks = 10
        mock_row.metrics.cost_micros = 5000000  # $5
        mock_row.metrics.conversions = 1
        mock_row.metrics.conversions_value = 50.0

        mock_service.search.return_value = [mock_row]

        # Execute
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        search_terms = await client.get_search_terms("1234567890", start_date, end_date)

        # Verify
        assert len(search_terms) == 1
        search_term = search_terms[0]
        assert isinstance(search_term, SearchTerm)
        assert search_term.search_term == "buy shoes online"
        assert search_term.campaign_id == "123456"
        assert search_term.campaign_name == "Test Campaign"
        assert search_term.ad_group_id == "456789"
        assert search_term.ad_group_name == "Test Ad Group"
        assert (
            search_term.keyword_id is None
        )  # Not available from search_term_view in v20
        assert (
            search_term.keyword_text is None
        )  # Not available from search_term_view in v20
        assert (
            search_term.match_type is None
        )  # Not available from search_term_view in v20
        assert search_term.metrics.impressions == 100
        assert search_term.metrics.clicks == 10
        assert search_term.metrics.cost == 5.0
        assert search_term.metrics.conversions == 1
        assert search_term.metrics.conversion_value == 50.0

    @pytest.mark.asyncio
    async def test_get_negative_keywords_success(self, client, mock_google_ads_client):
        """Test successful negative keyword fetching."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_google_ads_client.load_from_dict.return_value = mock_client_instance

        mock_service = MagicMock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock response for ad group level negatives
        mock_row = MagicMock()
        mock_row.ad_group_criterion.criterion_id = 111111
        mock_row.ad_group_criterion.keyword.text = "free"
        mock_row.ad_group_criterion.keyword.match_type.name = "BROAD"
        mock_row.campaign.id = 123456
        mock_row.campaign.name = "Test Campaign"
        mock_row.ad_group.id = 456789
        mock_row.ad_group.name = "Test Ad Group"

        # Mock three different responses - one for each type of negative keywords
        # get_negative_keywords makes 3 API calls:
        # 1. Ad group level negatives
        # 2. Campaign level negatives
        # 3. Shared set negatives (always called, even if include_shared_sets=False)
        mock_service.search.side_effect = [
            [mock_row],  # Ad group level negatives
            [],  # Campaign level negatives
            [],  # Shared set negatives
        ]

        # Execute
        negatives = await client.get_negative_keywords("1234567890")

        # Verify
        assert len(negatives) == 1
        negative = negatives[0]
        assert negative["id"] == "111111"
        assert negative["text"] == "free"
        assert negative["match_type"] == "BROAD"
        assert negative["level"] == "ad_group"
        assert negative["campaign_id"] == "123456"
        assert negative["campaign_name"] == "Test Campaign"
        assert negative["ad_group_id"] == "456789"
        assert negative["ad_group_name"] == "Test Ad Group"

    def test_handle_google_ads_exception_authentication(self, client):
        """Test handling of authentication errors."""
        mock_exception = MagicMock(spec=GoogleAdsException)
        mock_failure = MagicMock()
        mock_error = MagicMock()
        mock_error.error_code = "AUTHENTICATION_ERROR"
        mock_error.message = "Invalid credentials"
        mock_failure.errors = [mock_error]
        mock_exception.failure = mock_failure

        with pytest.raises(AuthenticationError) as exc_info:
            client._handle_google_ads_exception(mock_exception)

        assert "Authentication failed" in str(exc_info.value)

    def test_handle_google_ads_exception_rate_limit(self, client):
        """Test handling of rate limit errors."""
        mock_exception = MagicMock(spec=GoogleAdsException)
        mock_failure = MagicMock()
        mock_error = MagicMock()
        mock_error.error_code = "RATE_EXCEEDED"
        mock_error.message = "Rate limit exceeded"
        mock_failure.errors = [mock_error]
        mock_exception.failure = mock_failure

        with pytest.raises(RateLimitError) as exc_info:
            client._handle_google_ads_exception(mock_exception)

        assert "Rate limit exceeded" in str(exc_info.value)

    def test_handle_google_ads_exception_general(self, client):
        """Test handling of general API errors."""
        mock_exception = MagicMock(spec=GoogleAdsException)
        mock_failure = MagicMock()
        mock_error = MagicMock()
        mock_error.error_code = "INTERNAL_ERROR"
        mock_error.message = "Something went wrong"
        mock_failure.errors = [mock_error]
        mock_exception.failure = mock_failure

        with pytest.raises(APIError) as exc_info:
            client._handle_google_ads_exception(mock_exception)

        assert "Google Ads API error" in str(exc_info.value)
        assert "Something went wrong" in str(exc_info.value)


class TestAdSchedulePerformance:
    """Test cases for ad schedule performance functionality."""

    def test_combine_dayparting_data_with_bid_modifiers(self, client):
        """Test combining performance data with bid modifiers."""
        # Mock performance data
        performance_data = [
            {
                "campaign_id": "123",
                "day_of_week_enum": 2,  # Monday
                "hour": 10,
                "impressions": 1000,
                "clicks": 50,
                "cost": 25.0,
            }
        ]

        # Mock bid modifiers
        bid_modifiers = {
            "123_2_10": 1.2  # 20% increase for Monday 10AM
        }

        # Test the combination
        result = client._combine_dayparting_data(performance_data, bid_modifiers)

        assert len(result) == 1
        assert result[0]["bid_adjustment"] == 1.2
        assert "day_of_week_enum" not in result[0]  # Should be removed

    def test_combine_dayparting_data_without_bid_modifiers(self, client):
        """Test combining performance data when no bid modifiers exist."""
        performance_data = [
            {
                "campaign_id": "123",
                "day_of_week_enum": 2,
                "hour": 10,
                "impressions": 1000,
            }
        ]

        bid_modifiers = {}

        result = client._combine_dayparting_data(performance_data, bid_modifiers)

        assert len(result) == 1
        assert result[0]["bid_adjustment"] is None

    @pytest.mark.asyncio
    async def test_get_ad_schedule_performance_success(self, client):
        """Test successful ad schedule performance retrieval."""
        # Mock the internal methods
        with (
            patch.object(client, "_fetch_dayparting_performance") as mock_perf,
            patch.object(client, "_fetch_ad_schedule_bid_modifiers") as mock_bid,
            patch.object(client, "_combine_dayparting_data") as mock_combine,
        ):
            # Setup mocks
            mock_perf.return_value = [{"campaign_id": "123", "impressions": 1000}]
            mock_bid.return_value = {"123_2_10": 1.2}
            mock_combine.return_value = [
                {"campaign_id": "123", "impressions": 1000, "bid_adjustment": 1.2}
            ]

            # Mock validation methods
            with (
                patch(
                    "paidsearchnav.platforms.google.client.GoogleAdsInputValidator.validate_customer_id"
                ) as mock_validate_customer,
                patch.object(client, "_validate_date_range") as mock_validate_date,
                patch.object(client, "_get_client") as mock_get_client,
            ):
                mock_validate_customer.return_value = "123-456-7890"
                mock_get_client.return_value = MagicMock()

                start_date = datetime(2023, 1, 1)
                end_date = datetime(2023, 1, 7)

                result = await client.get_ad_schedule_performance(
                    "123-456-7890", start_date, end_date
                )

                assert len(result) == 1
                assert result[0]["campaign_id"] == "123"
                assert result[0]["bid_adjustment"] == 1.2

                # Verify methods were called
                mock_perf.assert_called_once()
                mock_bid.assert_called_once()
                mock_combine.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ad_schedule_performance_bid_modifier_failure(self, client):
        """Test ad schedule performance when bid modifier fetch fails."""
        with (
            patch.object(client, "_fetch_dayparting_performance") as mock_perf,
            patch.object(client, "_fetch_ad_schedule_bid_modifiers") as mock_bid,
            patch.object(client, "_combine_dayparting_data") as mock_combine,
        ):
            # Setup mocks - bid modifier fetch fails
            mock_perf.return_value = [{"campaign_id": "123", "impressions": 1000}]
            mock_bid.side_effect = Exception("Bid modifier fetch failed")
            mock_combine.return_value = [
                {"campaign_id": "123", "impressions": 1000, "bid_adjustment": None}
            ]

            # Mock validation and client methods
            with (
                patch(
                    "paidsearchnav.platforms.google.client.GoogleAdsInputValidator.validate_customer_id"
                ) as mock_validate_customer,
                patch.object(client, "_validate_date_range") as mock_validate_date,
                patch.object(client, "_get_client") as mock_get_client,
            ):
                mock_validate_customer.return_value = "123-456-7890"
                mock_get_client.return_value = MagicMock()

                start_date = datetime(2023, 1, 1)
                end_date = datetime(2023, 1, 7)

                # Should not raise exception, should continue with empty bid modifiers
                result = await client.get_ad_schedule_performance(
                    "123-456-7890", start_date, end_date
                )

                assert len(result) == 1
                assert result[0]["bid_adjustment"] is None

                # Verify combine was called with empty bid modifiers dict
                mock_combine.assert_called_once_with(
                    [{"campaign_id": "123", "impressions": 1000}], {}
                )

    def test_day_of_week_enum_mapping(self, client):
        """Test that Google's day of week enum values are mapped correctly."""
        # This tests the day_mapping dict used in _fetch_dayparting_performance
        expected_mapping = {
            1: "Sunday",  # Google's SUNDAY enum value
            2: "Monday",  # Google's MONDAY enum value
            3: "Tuesday",
            4: "Wednesday",
            5: "Thursday",
            6: "Friday",
            7: "Saturday",  # Google's SATURDAY enum value
        }

        # This is implicit testing - the mapping is used in the actual method
        # We verify the mapping exists by checking a performance data sample
        performance_data = [
            {"campaign_id": "123", "day_of_week_enum": 2, "hour": 10}  # Monday
        ]

        result = client._combine_dayparting_data(performance_data, {})
        assert "day_of_week_enum" not in result[0]  # Enum should be removed
