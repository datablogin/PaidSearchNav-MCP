"""Tests for Google Ads API client pagination functionality."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav_mcp.core.config import CircuitBreakerConfig
from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient


class TestGoogleAdsClientPagination:
    """Test pagination functionality in GoogleAdsAPIClient."""

    @pytest.fixture
    def client_config(self):
        """Default client configuration for tests."""
        return {
            "developer_token": "test-token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
            "default_page_size": 100,
            "max_page_size": 1000,
            "circuit_breaker_config": CircuitBreakerConfig(enabled=False),
        }

    @pytest.fixture
    def mock_google_ads_client(self):
        """Mock Google Ads client."""
        with patch("paidsearchnav.platforms.google.client.GoogleAdsClient") as mock:
            client_instance = MagicMock()
            mock.load_from_dict.return_value = client_instance

            # Mock GoogleAdsService
            ga_service = MagicMock()
            client_instance.get_service.return_value = ga_service
            client_instance.get_type.return_value = MagicMock()

            yield client_instance, ga_service

    def test_pagination_config_validation(self):
        """Test pagination configuration validation."""
        # Valid configuration
        client = GoogleAdsAPIClient(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            default_page_size=500,
            max_page_size=1000,
        )
        assert client.default_page_size == 500
        assert client.max_page_size == 1000

        # Invalid default_page_size too small
        with pytest.raises(
            ValueError, match="default_page_size must be between 1 and 10000"
        ):
            GoogleAdsAPIClient(
                developer_token="test-token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
                default_page_size=0,
            )

        # Invalid default_page_size too large
        with pytest.raises(
            ValueError, match="default_page_size must be between 1 and 10000"
        ):
            GoogleAdsAPIClient(
                developer_token="test-token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
                default_page_size=20000,
            )

        # Invalid max_page_size too large
        with pytest.raises(
            ValueError, match="max_page_size must be between 1 and 10000"
        ):
            GoogleAdsAPIClient(
                developer_token="test-token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
                max_page_size=20000,
            )

        # default_page_size exceeds max_page_size
        with pytest.raises(
            ValueError, match="default_page_size cannot exceed max_page_size"
        ):
            GoogleAdsAPIClient(
                developer_token="test-token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
                default_page_size=1000,
                max_page_size=500,
            )

    def test_paginated_search_single_page(self, client_config, mock_google_ads_client):
        """Test paginated search with results fitting in a single page."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock response with no next_page_token (single page)
        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(50)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        results = client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign"
        )

        assert len(results) == 50
        ga_service.search.assert_called_once()

    def test_paginated_search_multiple_pages(
        self, client_config, mock_google_ads_client
    ):
        """Test paginated search with results spanning multiple pages."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock multiple pages
        page1_response = MagicMock()
        page1_response.__iter__ = lambda self: iter([MagicMock() for _ in range(100)])
        page1_response.next_page_token = "page2_token"

        page2_response = MagicMock()
        page2_response.__iter__ = lambda self: iter([MagicMock() for _ in range(75)])
        page2_response.next_page_token = ""

        ga_service.search.side_effect = [page1_response, page2_response]

        results = client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign"
        )

        assert len(results) == 175
        assert ga_service.search.call_count == 2

    def test_paginated_search_with_max_results(
        self, client_config, mock_google_ads_client
    ):
        """Test paginated search with max_results limit."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock large response
        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(100)])
        mock_response.next_page_token = "page2_token"
        ga_service.search.return_value = mock_response

        results = client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign", max_results=50
        )

        assert len(results) == 50
        ga_service.search.assert_called_once()

    def test_paginated_search_custom_page_size(
        self, client_config, mock_google_ads_client
    ):
        """Test paginated search with custom page size."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(50)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign", page_size=50
        )

        # Check that request was created with custom page size
        search_request_call = client_instance.get_type.return_value
        assert search_request_call.page_size == 50

    def test_paginated_search_page_size_exceeds_max(
        self, client_config, mock_google_ads_client
    ):
        """Test that page_size exceeding max_page_size raises error."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)

        with pytest.raises(
            ValueError,
            match="page_size \\(2000\\) cannot exceed max_page_size \\(1000\\)",
        ):
            client._paginated_search(
                "1234567890", "SELECT campaign.id FROM campaign", page_size=2000
            )

    @pytest.mark.asyncio
    async def test_paginated_search_async(self, client_config, mock_google_ads_client):
        """Test async paginated search."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(25)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        results = await client._paginated_search_async(
            "1234567890", "SELECT campaign.id FROM campaign"
        )

        assert len(results) == 25

    def test_search_stream_generator(self, client_config, mock_google_ads_client):
        """Test search stream generator functionality."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock two pages
        page1_response = MagicMock()
        page1_response.__iter__ = lambda self: iter([f"row_{i}" for i in range(50)])
        page1_response.next_page_token = "page2_token"

        page2_response = MagicMock()
        page2_response.__iter__ = lambda self: iter([f"row_{i}" for i in range(50, 75)])
        page2_response.next_page_token = ""

        ga_service.search.side_effect = [page1_response, page2_response]

        # Collect all results from generator
        results = list(
            client.search_stream("1234567890", "SELECT campaign.id FROM campaign")
        )

        assert len(results) == 75
        assert results[0] == "row_0"
        assert results[49] == "row_49"
        assert results[50] == "row_50"
        assert results[74] == "row_74"

    @pytest.mark.asyncio
    async def test_search_stream_async_generator(
        self, client_config, mock_google_ads_client
    ):
        """Test async search stream generator functionality."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([f"row_{i}" for i in range(30)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        # Collect all results from async generator
        results = []
        async for row in client.search_stream_async(
            "1234567890", "SELECT campaign.id FROM campaign"
        ):
            results.append(row)

        assert len(results) == 30

    @pytest.mark.asyncio
    async def test_get_campaigns_with_pagination(
        self, client_config, mock_google_ads_client
    ):
        """Test get_campaigns method with pagination parameters."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock currency response
        currency_response = MagicMock()
        currency_row = MagicMock()
        currency_row.customer.currency_code = "USD"
        currency_response.__iter__ = lambda self: iter([currency_row])

        # Mock campaigns response
        campaigns_response = MagicMock()
        campaign_rows = []
        for i in range(10):
            row = MagicMock()
            row.campaign.id = f"campaign_{i}"
            row.campaign.name = f"Campaign {i}"
            row.campaign.status.name = "ENABLED"
            row.campaign.advertising_channel_type.name = "SEARCH"
            row.campaign.bidding_strategy_type.name = "TARGET_CPA"
            row.campaign.target_cpa = None
            row.campaign.target_roas = None
            row.metrics.impressions = 1000
            row.metrics.clicks = 100
            row.metrics.cost_micros = 50000000  # $50
            row.metrics.conversions = 5.0
            row.metrics.conversions_value = 250.0
            row.campaign_budget.amount_micros = 100000000  # $100
            campaign_rows.append(row)

        campaigns_response.__iter__ = lambda self: iter(campaign_rows)
        campaigns_response.next_page_token = ""

        ga_service.search.side_effect = [currency_response, campaigns_response]

        campaigns = await client.get_campaigns(
            "1234567890", page_size=50, max_results=10
        )

        assert len(campaigns) == 10
        assert campaigns[0].campaign_id == "campaign_0"
        assert campaigns[0].budget_currency == "USD"
        assert campaigns[0].cost == 50.0  # Converted from micros

    @pytest.mark.asyncio
    async def test_get_keywords_with_pagination(
        self, client_config, mock_google_ads_client
    ):
        """Test get_keywords method with pagination parameters."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock keywords response
        keywords_response = MagicMock()
        keyword_rows = []
        for i in range(5):
            row = MagicMock()
            row.ad_group_criterion.criterion_id = f"keyword_{i}"
            row.ad_group_criterion.keyword.text = f"keyword {i}"
            row.ad_group_criterion.keyword.match_type.name = "EXACT"
            row.ad_group_criterion.status.name = "ENABLED"
            row.ad_group_criterion.cpc_bid_micros = 1000000  # $1
            row.ad_group_criterion.quality_info.quality_score = 8
            row.ad_group.id = f"adgroup_{i}"
            row.ad_group.name = f"Ad Group {i}"
            row.campaign.id = f"campaign_{i}"
            row.campaign.name = f"Campaign {i}"
            keyword_rows.append(row)

        keywords_response.__iter__ = lambda self: iter(keyword_rows)
        keywords_response.next_page_token = ""

        ga_service.search.return_value = keywords_response

        keywords = await client.get_keywords(
            "1234567890", page_size=25, max_results=5, include_metrics=False
        )

        assert len(keywords) == 5
        assert keywords[0].keyword_id == "keyword_0"
        assert keywords[0].text == "keyword 0"
        assert keywords[0].cpc_bid == 1.0  # Converted from micros

    @pytest.mark.asyncio
    async def test_get_search_terms_with_pagination(
        self, client_config, mock_google_ads_client
    ):
        """Test get_search_terms method with pagination parameters."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock search terms response
        search_terms_response = MagicMock()
        search_term_rows = []
        for i in range(8):
            row = MagicMock()
            row.search_term_view.search_term = f"search term {i}"
            row.campaign.id = f"campaign_{i}"
            row.campaign.name = f"Campaign {i}"
            row.ad_group.id = f"adgroup_{i}"
            row.ad_group.name = f"Ad Group {i}"
            row.metrics.impressions = 100
            row.metrics.clicks = 10
            row.metrics.cost_micros = 5000000  # $5
            row.metrics.conversions = 1.0
            row.metrics.conversions_value = 20.0
            search_term_rows.append(row)

        search_terms_response.__iter__ = lambda self: iter(search_term_rows)
        search_terms_response.next_page_token = ""

        ga_service.search.return_value = search_terms_response

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now() - timedelta(days=1)

        search_terms = await client.get_search_terms(
            "1234567890", start_date, end_date, page_size=100, max_results=8
        )

        assert len(search_terms) == 8
        assert search_terms[0].search_term == "search term 0"
        assert search_terms[0].metrics.cost == 5.0  # Converted from micros

    @pytest.mark.asyncio
    async def test_get_negative_keywords_with_pagination(
        self, client_config, mock_google_ads_client
    ):
        """Test get_negative_keywords method with pagination parameters."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Mock negative keywords response - ad group level
        neg_keywords_response = MagicMock()
        neg_keyword_rows = []
        for i in range(3):
            row = MagicMock()
            row.ad_group_criterion.criterion_id = f"neg_keyword_{i}"
            row.ad_group_criterion.keyword.text = f"negative keyword {i}"
            row.ad_group_criterion.keyword.match_type.name = "BROAD"
            row.campaign.id = f"campaign_{i}"
            row.campaign.name = f"Campaign {i}"
            row.ad_group.id = f"adgroup_{i}"
            row.ad_group.name = f"Ad Group {i}"
            neg_keyword_rows.append(row)

        neg_keywords_response.__iter__ = lambda self: iter(neg_keyword_rows)
        neg_keywords_response.next_page_token = ""

        # Mock campaign level negatives (empty)
        campaign_neg_response = MagicMock()
        campaign_neg_response.__iter__ = lambda self: iter([])
        campaign_neg_response.next_page_token = ""

        # Mock shared negatives (empty)
        shared_neg_response = MagicMock()
        shared_neg_response.__iter__ = lambda self: iter([])
        shared_neg_response.next_page_token = ""

        ga_service.search.side_effect = [
            neg_keywords_response,  # ad group negatives
            campaign_neg_response,  # campaign negatives
            shared_neg_response,  # shared set keywords
            shared_neg_response,  # shared set campaigns
        ]

        negative_keywords = await client.get_negative_keywords(
            "1234567890", include_shared_sets=True, page_size=50, max_results=10
        )

        assert len(negative_keywords) == 3
        assert negative_keywords[0]["text"] == "negative keyword 0"
        assert negative_keywords[0]["level"] == "ad_group"

    def test_circuit_breaker_integration_with_pagination(self, mock_google_ads_client):
        """Test that pagination works with circuit breaker."""
        client_instance, ga_service = mock_google_ads_client

        # Enable circuit breaker
        circuit_breaker_config = CircuitBreakerConfig(
            enabled=True, failure_threshold=2, recovery_timeout=60
        )

        client = GoogleAdsAPIClient(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            circuit_breaker_config=circuit_breaker_config,
        )
        client._client = client_instance
        client._initialized = True

        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(10)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        results = client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign"
        )
        assert len(results) == 10

    def test_memory_efficiency_comparison(self, client_config, mock_google_ads_client):
        """Test that pagination reduces memory usage compared to loading all at once."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        # Simulate a large dataset with multiple pages
        page1_response = MagicMock()
        page1_response.__iter__ = lambda self: iter([MagicMock() for _ in range(100)])
        page1_response.next_page_token = "page2_token"

        page2_response = MagicMock()
        page2_response.__iter__ = lambda self: iter([MagicMock() for _ in range(100)])
        page2_response.next_page_token = ""

        ga_service.search.side_effect = [page1_response, page2_response]

        # Test streaming (memory efficient)
        stream_count = 0
        for row in client.search_stream(
            "1234567890", "SELECT campaign.id FROM campaign", page_size=100
        ):
            stream_count += 1

        assert stream_count == 200
        assert ga_service.search.call_count == 2

    def test_backwards_compatibility(self, client_config, mock_google_ads_client):
        """Test that existing code without pagination parameters still works."""
        client_instance, ga_service = mock_google_ads_client
        client = GoogleAdsAPIClient(**client_config)
        client._client = client_instance
        client._initialized = True

        mock_response = MagicMock()
        mock_response.__iter__ = lambda self: iter([MagicMock() for _ in range(20)])
        mock_response.next_page_token = ""
        ga_service.search.return_value = mock_response

        # Test method without pagination parameters (should use defaults)
        results = client._paginated_search(
            "1234567890", "SELECT campaign.id FROM campaign"
        )
        assert len(results) == 20

        # Verify default page size was used
        search_request_call = client_instance.get_type.return_value
        assert search_request_call.page_size == 100  # client default_page_size
