"""Integration tests for Google Ads API v20 compatibility."""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if imports are not available
pytest.importorskip("paidsearchnav.platforms.google.client")

from paidsearchnav_mcp.models.keyword import MatchType
from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient


class TestGoogleAdsAPIV20Compatibility:
    """Test Google Ads API v20 field compatibility."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        with patch("paidsearchnav.platforms.google.client.GoogleAdsClient") as mock:
            yield mock

    @pytest.fixture
    def api_client(self, mock_client):
        """Create an API client instance."""
        client = GoogleAdsAPIClient(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
        )
        # Mock the internal client
        mock_instance = MagicMock()
        mock_client.load_from_dict.return_value = mock_instance
        client._client = mock_instance
        client._initialized = True
        return client

    @pytest.mark.asyncio
    async def test_get_keywords_with_metrics_v20(self, api_client, mock_client):
        """Test get_keywords with separate metrics fetching for v20 compatibility."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock keyword response (without metrics)
        mock_keyword_row = MagicMock()
        mock_keyword_row.ad_group_criterion.criterion_id = 123456
        mock_keyword_row.ad_group_criterion.keyword.text = "test keyword"
        mock_keyword_row.ad_group_criterion.keyword.match_type.name = "EXACT"
        mock_keyword_row.ad_group_criterion.status.name = "ENABLED"
        mock_keyword_row.ad_group_criterion.cpc_bid_micros = 1000000
        mock_keyword_row.ad_group_criterion.quality_info.quality_score = 8
        mock_keyword_row.campaign.id = 111
        mock_keyword_row.campaign.name = "Test Campaign"
        mock_keyword_row.ad_group.id = 222
        mock_keyword_row.ad_group.name = "Test Ad Group"

        # Mock metrics response from keyword_view
        mock_metrics_row = MagicMock()
        mock_metrics_row.ad_group.id = 222
        mock_metrics_row.ad_group_criterion.criterion_id = 123456
        mock_metrics_row.metrics.impressions = 1000
        mock_metrics_row.metrics.clicks = 50
        mock_metrics_row.metrics.cost_micros = 25000000
        mock_metrics_row.metrics.conversions = 5
        mock_metrics_row.metrics.conversions_value = 500

        # Set up mock search responses
        mock_ga_service.search.side_effect = [
            [mock_keyword_row],  # First call for keywords
            [mock_metrics_row],  # Second call for metrics
        ]

        # Test with metrics
        keywords = await api_client.get_keywords(
            customer_id="123-456-7890",
            include_metrics=True,
        )

        assert len(keywords) == 1
        keyword = keywords[0]
        assert keyword.keyword_id == "123456"
        assert keyword.text == "test keyword"
        assert keyword.match_type == MatchType.EXACT

        # Verify metrics were fetched and applied
        assert keyword.impressions == 1000
        assert keyword.clicks == 50
        assert keyword.cost == 25.0  # micros converted to currency
        assert keyword.conversions == 5
        assert keyword.conversion_value == 500

        # Verify two API calls were made
        assert mock_ga_service.search.call_count == 2

    @pytest.mark.asyncio
    async def test_get_keywords_without_metrics_v20(self, api_client, mock_client):
        """Test get_keywords without metrics for v20 compatibility."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock keyword response
        mock_keyword_row = MagicMock()
        mock_keyword_row.ad_group_criterion.criterion_id = 123456
        mock_keyword_row.ad_group_criterion.keyword.text = "test keyword"
        mock_keyword_row.ad_group_criterion.keyword.match_type.name = "BROAD"
        mock_keyword_row.ad_group_criterion.status.name = "ENABLED"
        mock_keyword_row.ad_group_criterion.cpc_bid_micros = None
        mock_keyword_row.ad_group_criterion.quality_info = None
        mock_keyword_row.campaign.id = 111
        mock_keyword_row.campaign.name = "Test Campaign"
        mock_keyword_row.ad_group.id = 222
        mock_keyword_row.ad_group.name = "Test Ad Group"

        mock_ga_service.search.return_value = [mock_keyword_row]

        # Test without metrics
        keywords = await api_client.get_keywords(
            customer_id="123-456-7890",
            include_metrics=False,
        )

        assert len(keywords) == 1
        keyword = keywords[0]

        # Verify metrics are zero when not fetched
        assert keyword.impressions == 0
        assert keyword.clicks == 0
        assert keyword.cost == 0.0
        assert keyword.conversions == 0.0
        assert keyword.conversion_value == 0.0

        # Verify only one API call was made
        assert mock_ga_service.search.call_count == 1

    @pytest.mark.asyncio
    async def test_get_geographic_performance_v20(self, api_client, mock_client):
        """Test get_geographic_performance with v20 field names and location resolution."""
        # Mock services
        mock_ga_service = MagicMock()
        mock_search_request = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service
        api_client._client.get_type.return_value = mock_search_request

        # Mock geographic view response
        mock_geo_row = MagicMock()
        mock_geo_row.campaign.id = 111
        mock_geo_row.campaign.name = "Test Campaign"
        mock_geo_row.geographic_view.resource_name = (
            "customers/123/geographicViews/1023191~CITY"
        )
        mock_geo_row.geographic_view.country_criterion_id = 2840
        mock_geo_row.geographic_view.location_type.name = "CITY"
        mock_geo_row.metrics.impressions = 5000
        mock_geo_row.metrics.clicks = 250
        mock_geo_row.metrics.conversions = 25
        mock_geo_row.metrics.cost_micros = 125000000
        mock_geo_row.metrics.conversions_value = 2500000000  # Already in micros

        # Mock location constant response
        mock_location_row = MagicMock()
        mock_location_row.geo_target_constant.id = 1023191
        mock_location_row.geo_target_constant.name = "New York"
        mock_location_row.geo_target_constant.country_code = "US"
        mock_location_row.geo_target_constant.target_type.name = "City"
        mock_location_row.geo_target_constant.canonical_name = (
            "New York, New York, United States"
        )

        # Set up mock search responses
        mock_geo_response = MagicMock()
        mock_geo_response.__iter__ = lambda x: iter([mock_geo_row])

        mock_location_response = MagicMock()
        mock_location_response.__iter__ = lambda x: iter([mock_location_row])

        mock_ga_service.search.side_effect = [
            mock_geo_response,  # First call for geo data
            mock_location_response,  # Second call for location names
        ]

        # Test geographic performance
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now() - timedelta(days=1)

        geo_data = await api_client.get_geographic_performance(
            customer_id="123-456-7890",
            start_date=start_date,
            end_date=end_date,
        )

        assert len(geo_data) == 1
        data = geo_data[0]

        # Verify v20 fields
        assert data["campaign_id"] == "111"
        assert data["country_criterion_id"] == 2840
        assert data["location_type"] == "CITY"

        # Verify metrics (conversions_value should NOT be multiplied)
        assert data["conversion_value_micros"] == 2500000000
        assert data["cost_micros"] == 125000000

        # Verify location resolution
        assert data["city_name"] == "New York"
        assert data["region_name"] == "New York"
        assert data["country_name"] == "United States"

    @pytest.mark.asyncio
    async def test_get_geographic_performance_null_safety(
        self, api_client, mock_client
    ):
        """Test geographic performance with missing/null fields."""
        # Mock services
        mock_ga_service = MagicMock()
        mock_search_request = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service
        api_client._client.get_type.return_value = mock_search_request

        # Mock response with missing fields
        mock_geo_row = MagicMock()
        mock_geo_row.campaign.id = 111
        mock_geo_row.campaign.name = "Test Campaign"
        mock_geo_row.geographic_view.resource_name = (
            "customers/123/geographicViews/unknown"
        )

        # Simulate missing fields by setting them to None
        mock_geo_row.geographic_view.country_criterion_id = None
        mock_geo_row.geographic_view.location_type = None
        mock_geo_row.metrics.conversions_value = None
        mock_geo_row.metrics.impressions = 100
        mock_geo_row.metrics.clicks = 10
        mock_geo_row.metrics.conversions = 1
        mock_geo_row.metrics.cost_micros = 50000

        mock_response = MagicMock()
        mock_response.__iter__ = lambda x: iter([mock_geo_row])

        # get_geographic_performance makes 2 API calls: geo data and location names
        mock_ga_service.search.side_effect = [
            mock_response,  # First call for geo data
            MagicMock(
                __iter__=lambda x: iter([])
            ),  # Second call for location names (empty)
        ]

        # Test should not raise exception
        geo_data = await api_client.get_geographic_performance(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(geo_data) == 1
        data = geo_data[0]

        # Verify defaults for missing fields
        assert data["country_criterion_id"] == 0
        assert data["location_type"] == ""
        assert data["conversion_value_micros"] == 0

    @pytest.mark.asyncio
    async def test_keyword_metrics_aggregation(self, api_client, mock_client):
        """Test that keyword metrics are properly aggregated across date segments."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock multiple metrics rows for same keyword (different dates)
        mock_metrics_rows = []
        for i in range(3):
            row = MagicMock()
            row.ad_group.id = 222
            row.ad_group_criterion.criterion_id = 123456
            row.metrics.impressions = 100
            row.metrics.clicks = 10
            row.metrics.cost_micros = 5000000
            row.metrics.conversions = 1
            row.metrics.conversions_value = 100
            mock_metrics_rows.append(row)

        # Mock keyword response
        mock_keyword_row = MagicMock()
        mock_keyword_row.ad_group_criterion.criterion_id = 123456
        mock_keyword_row.ad_group_criterion.keyword.text = "aggregated keyword"
        mock_keyword_row.ad_group_criterion.keyword.match_type.name = "PHRASE"
        mock_keyword_row.ad_group_criterion.status.name = "ENABLED"
        mock_keyword_row.ad_group_criterion.cpc_bid_micros = 1000000
        mock_keyword_row.ad_group_criterion.quality_info = None
        mock_keyword_row.campaign.id = 111
        mock_keyword_row.campaign.name = "Test Campaign"
        mock_keyword_row.ad_group.id = 222
        mock_keyword_row.ad_group.name = "Test Ad Group"

        # Set up mock responses
        mock_ga_service.search.side_effect = [
            [mock_keyword_row],  # Keywords
            mock_metrics_rows,  # Metrics (3 rows)
        ]

        keywords = await api_client.get_keywords(
            customer_id="123-456-7890",
            include_metrics=True,
        )

        assert len(keywords) == 1
        keyword = keywords[0]

        # Verify metrics are aggregated (3 rows * values per row)
        assert keyword.impressions == 300  # 3 * 100
        assert keyword.clicks == 30  # 3 * 10
        assert keyword.cost == 15.0  # 3 * 5
        assert keyword.conversions == 3  # 3 * 1
        assert keyword.conversion_value == 300  # 3 * 100

    @pytest.mark.skipif(
        not os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        reason="Requires Google Ads API credentials",
    )
    @pytest.mark.asyncio
    async def test_real_api_v20_compatibility(self):
        """Test against real Google Ads API v20 (requires credentials)."""
        client = GoogleAdsAPIClient(
            developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            client_id=os.getenv("GOOGLE_ADS_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
            login_customer_id=os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        )

        customer_id = os.getenv("GOOGLE_ADS_TEST_CUSTOMER_ID")
        if not customer_id:
            pytest.skip("No test customer ID provided")

        # Test campaigns (should work without issues)
        campaigns = await client.get_campaigns(customer_id)
        assert isinstance(campaigns, list)

        # Test keywords with metrics
        keywords = await client.get_keywords(
            customer_id=customer_id,
            include_metrics=True,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now() - timedelta(days=1),
        )
        assert isinstance(keywords, list)
        if keywords:
            # Verify at least one keyword has metrics
            assert any(k.impressions > 0 for k in keywords)

        # Test geographic performance
        geo_data = await client.get_geographic_performance(
            customer_id=customer_id,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now() - timedelta(days=1),
        )
        assert isinstance(geo_data, list)
        if geo_data:
            # Verify location names are populated
            assert any(g.get("city_name") or g.get("country_name") for g in geo_data)

    @pytest.mark.asyncio
    async def test_get_performance_max_data_v20(self, api_client, mock_client):
        """Test Performance Max campaign data fetching for v20 compatibility."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock Performance Max campaign response
        mock_pmax_row = MagicMock()
        mock_pmax_row.campaign.id = 999
        mock_pmax_row.campaign.name = "Performance Max Campaign"
        mock_pmax_row.campaign.status.name = "ENABLED"
        mock_pmax_row.campaign.performance_max_upgrade = MagicMock()
        mock_pmax_row.campaign.performance_max_upgrade.status.name = "UPGRADED"
        mock_pmax_row.campaign.performance_max_upgrade.performance_max_campaign = (
            "customers/123/campaigns/999"
        )
        mock_pmax_row.campaign_budget.amount_micros = 10000000  # $10
        mock_pmax_row.metrics.impressions = 5000
        mock_pmax_row.metrics.clicks = 250
        mock_pmax_row.metrics.cost_micros = 8000000  # $8
        mock_pmax_row.metrics.conversions = 20
        mock_pmax_row.metrics.conversions_value = 400.0
        mock_pmax_row.metrics.video_views = 100
        mock_pmax_row.metrics.interactions = 300
        mock_pmax_row.segments.asset_group_asset_field_type = MagicMock()
        mock_pmax_row.segments.asset_group_asset_field_type.name = "HEADLINE"
        mock_pmax_row.segments.conversion_action = "customers/123/conversionActions/456"

        mock_ga_service.search.return_value = [mock_pmax_row]

        # Test Performance Max data fetching
        pmax_data = await api_client.get_performance_max_data(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(pmax_data) == 1
        data = pmax_data[0]

        # Verify data structure
        assert data["campaign_id"] == "999"
        assert data["campaign_name"] == "Performance Max Campaign"
        assert data["status"] == "ENABLED"
        assert data["budget_amount"] == 10.0
        assert data["performance_max_upgrade_status"] == "UPGRADED"
        assert (
            data["performance_max_campaign_resource"] == "customers/123/campaigns/999"
        )

        # Verify metrics
        assert data["impressions"] == 5000
        assert data["clicks"] == 250
        assert data["cost"] == 8.0
        assert data["conversions"] == 20
        assert data["conversion_value"] == 400.0
        assert data["video_views"] == 100
        assert data["interactions"] == 300

        # Verify segments
        assert data["asset_group_asset_field_type"] == "HEADLINE"
        assert data["conversion_action"] == "customers/123/conversionActions/456"

    @pytest.mark.asyncio
    async def test_get_performance_max_search_terms_v20(self, api_client, mock_client):
        """Test Performance Max search terms fetching for v20 compatibility."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock Performance Max search terms response
        mock_search_term_rows = []
        search_terms = [
            ("buy shoes online", "Shopping", 1000, 50, 3000000),
            ("running shoes near me", "Local", 800, 80, 4000000),
            ("best athletic footwear", "Research", 500, 25, 1500000),
        ]

        for term, category, impressions, clicks, cost_micros in search_terms:
            row = MagicMock()
            row.campaign.id = 999
            row.campaign.name = "Performance Max Campaign"
            row.campaign_search_term_insight.search_term = term
            row.campaign_search_term_insight.category_label = category
            row.metrics.impressions = impressions
            row.metrics.clicks = clicks
            row.metrics.cost_micros = cost_micros
            row.metrics.conversions = clicks * 0.05  # 5% conversion rate
            row.metrics.conversions_value = clicks * 2.0  # $2 per conversion
            mock_search_term_rows.append(row)

        mock_ga_service.search.return_value = mock_search_term_rows

        # Test Performance Max search terms fetching
        search_terms = await api_client.get_performance_max_search_terms(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
            campaign_ids=["999"],
        )

        assert len(search_terms) == 3

        # Verify first search term
        term1 = search_terms[0]
        assert term1["campaign_id"] == "999"
        assert term1["search_term"] == "buy shoes online"
        assert term1["category_label"] == "Shopping"
        assert term1["impressions"] == 1000
        assert term1["clicks"] == 50
        assert term1["cost"] == 3.0
        assert term1["conversions"] == 2.5  # 50 * 0.05
        assert term1["conversion_value"] == 100.0  # 50 * 2.0
        assert term1["ctr"] == 0.05  # 50/1000
        assert term1["cpc"] == 0.06  # 3.0/50
        assert term1["conversion_rate"] == 0.05  # 2.5/50
        assert term1["cpa"] == pytest.approx(1.2, rel=1e-2)  # 3.0/2.5

        # Verify local intent search term
        term2 = search_terms[1]
        assert term2["search_term"] == "running shoes near me"
        assert term2["category_label"] == "Local"
        assert term2["ctr"] == 0.1  # 80/800

        # Test zero conversion case - add a search term with no conversions
        mock_zero_conv_row = MagicMock()
        mock_zero_conv_row.campaign.id = 999
        mock_zero_conv_row.campaign.name = "Performance Max Campaign"
        mock_zero_conv_row.campaign_search_term_insight.search_term = "zero conversions"
        mock_zero_conv_row.campaign_search_term_insight.category_label = "Research"
        mock_zero_conv_row.metrics.impressions = 100
        mock_zero_conv_row.metrics.clicks = 10
        mock_zero_conv_row.metrics.cost_micros = 500000
        mock_zero_conv_row.metrics.conversions = 0  # Zero conversions
        mock_zero_conv_row.metrics.conversions_value = 0

        # Add to response
        mock_search_term_rows.append(mock_zero_conv_row)
        mock_ga_service.search.return_value = mock_search_term_rows

        # Re-fetch with the additional row
        search_terms = await api_client.get_performance_max_search_terms(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        # Verify the zero conversion case
        zero_conv_term = search_terms[-1]
        assert zero_conv_term["cpa"] is None  # Should be None when no conversions

    @pytest.mark.asyncio
    async def test_performance_max_null_safety(self, api_client, mock_client):
        """Test Performance Max methods with missing/null fields."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock response with missing fields
        mock_pmax_row = MagicMock()
        mock_pmax_row.campaign.id = 999
        mock_pmax_row.campaign.name = "PMax Campaign"
        mock_pmax_row.campaign.status.name = "ENABLED"
        mock_pmax_row.campaign.performance_max_upgrade = None  # No upgrade info
        mock_pmax_row.campaign_budget = None  # No budget
        mock_pmax_row.metrics.impressions = 100
        mock_pmax_row.metrics.clicks = 10
        mock_pmax_row.metrics.cost_micros = 50000
        mock_pmax_row.metrics.conversions = 1
        mock_pmax_row.metrics.conversions_value = 20.0
        # Missing video_views and interactions
        delattr(mock_pmax_row.metrics, "video_views")
        delattr(mock_pmax_row.metrics, "interactions")
        # Missing segments
        mock_pmax_row.segments = MagicMock()
        delattr(mock_pmax_row.segments, "asset_group_asset_field_type")
        delattr(mock_pmax_row.segments, "conversion_action")

        mock_ga_service.search.return_value = [mock_pmax_row]

        # Test should not raise exception
        pmax_data = await api_client.get_performance_max_data(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(pmax_data) == 1
        data = pmax_data[0]

        # Verify defaults for missing fields
        assert data["budget_amount"] == 0
        assert data["performance_max_upgrade_status"] is None
        assert data["performance_max_campaign_resource"] is None
        assert data["video_views"] == 0
        assert data["interactions"] == 0
        assert data["asset_group_asset_field_type"] is None
        assert data["conversion_action"] is None
