"""Comprehensive integration tests for Google Ads API v20 compatibility.

This test suite verifies all Google Ads API queries work correctly with v20,
including proper field names, resource relationships, and data handling.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if imports are not available
pytest.importorskip("paidsearchnav.platforms.google.client")

from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient


@pytest.fixture
def mock_client():
    """Create a mock Google Ads client for testing."""
    with patch("paidsearchnav.platforms.google.client.GoogleAdsClient") as mock:
        yield mock


@pytest.fixture
def api_client(mock_client):
    """Create a GoogleAdsAPIClient instance with mocked dependencies."""
    client = GoogleAdsAPIClient(
        developer_token="test-token",
        client_id="test-client-id",
        client_secret="test-secret",
        refresh_token="test-refresh",
        login_customer_id="123-456-7890",
    )
    # Mock the internal client
    client._client = mock_client
    client._initialized = True
    return client


class TestGoogleAdsAPIv20Compatibility:
    """Test suite for Google Ads API v20 compatibility."""

    @pytest.mark.asyncio
    async def test_search_term_view_query_compatibility(self, api_client, mock_client):
        """Test that search_term_view queries are v20 compatible."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock search term response
        mock_search_term = MagicMock()
        mock_search_term.search_term_view.search_term = "running shoes"
        mock_search_term.search_term_view.status.name = "NONE"
        mock_search_term.campaign.id = 123
        mock_search_term.campaign.name = "Test Campaign"
        mock_search_term.ad_group.id = 456
        mock_search_term.ad_group.name = "Test Ad Group"
        mock_search_term.metrics.impressions = 1000
        mock_search_term.metrics.clicks = 100
        mock_search_term.metrics.cost_micros = 5000000
        mock_search_term.metrics.conversions = 10
        mock_search_term.metrics.conversions_value = 500.0

        # Mock the _paginated_search_async method instead of direct service calls
        original_paginated_search = api_client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            return [mock_search_term]

        api_client._paginated_search_async = mock_paginated_search

        try:
            # Test search terms fetching
            search_terms = await api_client.get_search_terms(
                customer_id="123-456-7890",
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
            )

            # Verify we captured the query
            assert len(captured_queries) == 1
            query = captured_queries[0]

            # Verify v20 compatible fields in query
            assert "search_term_view.search_term" in query
            assert "search_term_view.status" in query
            assert "metrics.conversions_value" in query
            assert "FROM search_term_view" in query

            # Verify no incompatible fields
            assert "ad_group_criterion" not in query
            assert "keyword_view" not in query
        finally:
            # Restore original method
            api_client._paginated_search_async = original_paginated_search

        # Verify results
        assert len(search_terms) == 1
        assert search_terms[0].search_term == "running shoes"

    @pytest.mark.asyncio
    async def test_keyword_metrics_separate_query(self, api_client, mock_client):
        """Test that keyword metrics are fetched separately in v20."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock keyword response (without metrics)
        mock_keyword = MagicMock()
        mock_keyword.ad_group_criterion.criterion_id = 789
        mock_keyword.ad_group_criterion.keyword.text = "test keyword"
        mock_keyword.ad_group_criterion.keyword.match_type.name = "EXACT"
        mock_keyword.ad_group_criterion.status.name = "ENABLED"
        mock_keyword.ad_group_criterion.cpc_bid_micros = 1000000
        mock_keyword.ad_group_criterion.quality_info = None
        mock_keyword.campaign.id = 123
        mock_keyword.campaign.name = "Test Campaign"
        mock_keyword.ad_group.id = 456
        mock_keyword.ad_group.name = "Test Ad Group"

        # Mock metrics response (from keyword_view)
        mock_metrics = MagicMock()
        mock_metrics.ad_group.id = 456
        mock_metrics.ad_group_criterion.criterion_id = 789
        mock_metrics.metrics.impressions = 5000
        mock_metrics.metrics.clicks = 250
        mock_metrics.metrics.cost_micros = 12500000
        mock_metrics.metrics.conversions = 25
        mock_metrics.metrics.conversions_value = 2500.0

        # Mock the _paginated_search_async method to capture separate calls
        original_paginated_search = api_client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            if "FROM ad_group_criterion" in query:
                return [mock_keyword]  # Keywords query
            elif "FROM keyword_view" in query:
                return [mock_metrics]  # Metrics query
            else:
                return []

        api_client._paginated_search_async = mock_paginated_search

        try:
            # Test with metrics enabled
            keywords = await api_client.get_keywords(
                customer_id="123-456-7890",
                include_metrics=True,
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
            )

            # Verify two separate queries were made
            assert len(captured_queries) == 2

            # Check first query (keywords)
            first_query = captured_queries[0]
            assert "FROM ad_group_criterion" in first_query
            assert "metrics." not in first_query  # No metrics in keyword query

            # Check second query (metrics)
            second_query = captured_queries[1]
            assert "FROM keyword_view" in second_query
            assert "metrics.impressions" in second_query
            assert "metrics.conversions_value" in second_query
        finally:
            # Restore original method
            api_client._paginated_search_async = original_paginated_search

        # Verify results
        assert len(keywords) == 1
        assert keywords[0].text == "test keyword"
        assert keywords[0].impressions == 5000
        assert keywords[0].cost == 12.5

    @pytest.mark.asyncio
    async def test_shared_negative_keyword_sets(self, api_client, mock_client):
        """Test shared negative keyword sets functionality."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock campaign negative keyword
        mock_campaign_negative = MagicMock()
        mock_campaign_negative.campaign.id = 123
        mock_campaign_negative.campaign.name = "Test Campaign"
        mock_campaign_negative.campaign_criterion.criterion_id = 111
        mock_campaign_negative.campaign_criterion.keyword.text = "cheap"
        mock_campaign_negative.campaign_criterion.keyword.match_type.name = "BROAD"

        # Mock shared criterion
        mock_shared_criterion = MagicMock()
        mock_shared_criterion.shared_set.id = 999
        mock_shared_criterion.shared_set.name = "Brand Protection"
        mock_shared_criterion.shared_set.type.name = "NEGATIVE_KEYWORDS"
        mock_shared_criterion.shared_set.status.name = "ENABLED"
        mock_shared_criterion.shared_criterion.criterion_id = 222
        mock_shared_criterion.shared_criterion.keyword.text = "competitor"
        mock_shared_criterion.shared_criterion.keyword.match_type.name = "EXACT"

        # Mock campaign shared set association
        mock_campaign_shared_set = MagicMock()
        mock_campaign_shared_set.campaign.id = 123
        mock_campaign_shared_set.campaign.name = "Test Campaign"
        mock_campaign_shared_set.shared_set.id = 999

        # Set up mock responses for different queries
        def mock_search(request=None, customer_id=None, query=None):
            # Handle both old-style (customer_id, query) and new-style (request) calls
            if request is not None:
                query = request.query
            if "FROM ad_group_criterion" in query:
                return []  # No ad group negatives
            elif "FROM campaign_criterion" in query:
                return [mock_campaign_negative]
            elif "FROM shared_criterion" in query:
                return [mock_shared_criterion]
            elif "FROM campaign_shared_set" in query:
                return [mock_campaign_shared_set]
            return []

        mock_ga_service.search.side_effect = mock_search

        # Test with shared sets enabled
        negatives = await api_client.get_negative_keywords(
            customer_id="123-456-7890",
            include_shared_sets=True,
        )

        # Verify all queries were made
        assert mock_ga_service.search.call_count == 4

        # Verify results include both campaign and shared negatives
        assert len(negatives) == 2

        # Check campaign negative
        campaign_neg = next(n for n in negatives if n["level"] == "campaign")
        assert campaign_neg["text"] == "cheap"
        assert campaign_neg["match_type"] == "BROAD"

        # Check shared set negative
        shared_neg = next(n for n in negatives if n["level"] == "shared_set")
        assert shared_neg["text"] == "competitor"
        assert shared_neg["match_type"] == "EXACT"
        assert shared_neg["shared_set_name"] == "Brand Protection"

    @pytest.mark.asyncio
    async def test_geographic_view_location_resolution(self, api_client, mock_client):
        """Test geographic view with location name resolution."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock geographic view response
        mock_geo_view = MagicMock()
        mock_geo_view.campaign.id = 123
        mock_geo_view.campaign.name = "Test Campaign"
        mock_geo_view.geographic_view.resource_name = (
            "customers/123/geographicViews/1023191~CITY"
        )
        mock_geo_view.geographic_view.country_criterion_id = 2840  # USA
        mock_geo_view.geographic_view.location_type.name = "CITY"
        mock_geo_view.metrics.impressions = 10000
        mock_geo_view.metrics.clicks = 500
        mock_geo_view.metrics.conversions = 50
        mock_geo_view.metrics.cost_micros = 25000000
        mock_geo_view.metrics.conversions_value = 5000.0

        # Mock location constant response
        mock_location = MagicMock()
        mock_location.geo_target_constant.id = 1023191
        mock_location.geo_target_constant.name = "New York"
        mock_location.geo_target_constant.country_code = "US"
        mock_location.geo_target_constant.target_type.name = "City"
        mock_location.geo_target_constant.canonical_name = (
            "New York, New York, United States"
        )

        # First call returns geo data, second call returns location names
        mock_ga_service.search.side_effect = [
            [mock_geo_view],  # Geographic view query
            [mock_location],  # Location constant query
        ]

        # Mock the get_type method
        api_client._client.get_type.return_value = MagicMock()

        # Test geographic performance
        geo_data = await api_client.get_geographic_performance(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        )

        # Verify two queries were made
        assert mock_ga_service.search.call_count == 2

        # Check first query (geographic view)
        first_call = mock_ga_service.search.call_args_list[0]
        # The search method is called with request= parameter
        first_request = first_call[1]["request"]
        first_query = first_request.query
        assert "FROM geographic_view" in first_query
        assert "geographic_view.resource_name" in first_query
        assert "metrics.conversions_value" in first_query

        # Check second query (location names)
        second_call = mock_ga_service.search.call_args_list[1]
        # The second call uses standard parameters (customer_id, query)
        second_query = second_call[1]["query"]
        assert "FROM geo_target_constant" in second_query
        assert "geo_target_constant.canonical_name" in second_query

        # Verify results
        assert len(geo_data) == 1
        assert geo_data[0]["city_name"] == "New York"
        assert geo_data[0]["region_name"] == "New York"
        assert geo_data[0]["country_name"] == "United States"
        assert geo_data[0]["conversion_value_micros"] == 5000.0  # Not multiplied

    @pytest.mark.asyncio
    async def test_performance_max_campaign_data(self, api_client, mock_client):
        """Test Performance Max campaign data fetching."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock Performance Max campaign
        mock_pmax = MagicMock()
        mock_pmax.campaign.id = 789
        mock_pmax.campaign.name = "Performance Max - Retail"
        mock_pmax.campaign.status.name = "ENABLED"
        mock_pmax.campaign.performance_max_upgrade = MagicMock()
        mock_pmax.campaign.performance_max_upgrade.status.name = "UPGRADED"
        mock_pmax.campaign.performance_max_upgrade.performance_max_campaign = (
            "customers/123/campaigns/789"
        )
        mock_pmax.campaign_budget.amount_micros = 50000000  # $50
        mock_pmax.metrics.impressions = 50000
        mock_pmax.metrics.clicks = 2500
        mock_pmax.metrics.cost_micros = 45000000  # $45
        mock_pmax.metrics.conversions = 250
        mock_pmax.metrics.conversions_value = 25000.0
        mock_pmax.metrics.video_views = 1000
        mock_pmax.metrics.interactions = 3000
        mock_pmax.segments.asset_group_asset_field_type = MagicMock()
        mock_pmax.segments.asset_group_asset_field_type.name = "HEADLINE"
        mock_pmax.segments.conversion_action = "customers/123/conversionActions/456"

        mock_ga_service.search.return_value = [mock_pmax]

        # Test Performance Max data fetching
        pmax_data = await api_client.get_performance_max_data(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        )

        # Verify query
        assert mock_ga_service.search.called
        query = mock_ga_service.search.call_args[1]["query"]
        assert "FROM campaign" in query
        assert "campaign.advertising_channel_type = 'PERFORMANCE_MAX'" in query
        assert "campaign.performance_max_upgrade" in query
        assert "metrics.video_views" in query
        assert "segments.asset_group_asset_field_type" in query

        # Verify results
        assert len(pmax_data) == 1
        data = pmax_data[0]
        assert data["campaign_name"] == "Performance Max - Retail"
        assert data["budget_amount"] == 50.0
        assert data["cost"] == 45.0
        assert data["video_views"] == 1000
        assert data["performance_max_upgrade_status"] == "UPGRADED"

    @pytest.mark.asyncio
    async def test_performance_max_search_terms(self, api_client, mock_client):
        """Test Performance Max search terms fetching."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock Performance Max search term
        mock_search_term = MagicMock()
        mock_search_term.campaign.id = 789
        mock_search_term.campaign.name = "Performance Max - Retail"
        mock_search_term.campaign_search_term_insight.search_term = "buy shoes near me"
        mock_search_term.campaign_search_term_insight.category_label = "Local"
        mock_search_term.metrics.impressions = 5000
        mock_search_term.metrics.clicks = 500
        mock_search_term.metrics.cost_micros = 25000000  # $25
        mock_search_term.metrics.conversions = 50
        mock_search_term.metrics.conversions_value = 5000.0

        mock_ga_service.search.return_value = [mock_search_term]

        # Test Performance Max search terms
        search_terms = await api_client.get_performance_max_search_terms(
            customer_id="123-456-7890",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            campaign_ids=["789"],
        )

        # Verify query
        assert mock_ga_service.search.called
        query = mock_ga_service.search.call_args[1]["query"]
        assert "FROM campaign_search_term_insight" in query
        assert "campaign_search_term_insight.search_term" in query
        assert "campaign_search_term_insight.category_label" in query
        assert "campaign.advertising_channel_type = 'PERFORMANCE_MAX'" in query

        # Verify results
        assert len(search_terms) == 1
        term = search_terms[0]
        assert term["search_term"] == "buy shoes near me"
        assert term["category_label"] == "Local"
        assert term["cost"] == 25.0
        assert term["ctr"] == 0.1  # 500/5000
        assert term["cpa"] == 0.5  # 25/50

    @pytest.mark.asyncio
    async def test_null_field_safety(self, api_client, mock_client):
        """Test that all methods handle null/missing fields gracefully."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Mock response with missing optional fields
        mock_row = MagicMock()
        mock_row.campaign.id = 123
        mock_row.campaign.name = "Test"

        # Simulate missing fields
        mock_row.metrics.conversions_value = None
        mock_row.geographic_view.location_type = None
        mock_row.campaign.performance_max_upgrade = None

        # For different resource types
        mock_ga_service.search.return_value = [mock_row]

        # Test should not raise AttributeError
        try:
            # Test with geographic view
            api_client._client.get_type.return_value = MagicMock()
            geo_data = await api_client.get_geographic_performance(
                customer_id="123-456-7890",
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
            )
            # Should handle nulls gracefully
            assert geo_data is not None

        except AttributeError as e:
            pytest.fail(f"Method failed to handle null fields: {e}")

    @pytest.mark.asyncio
    async def test_api_version_in_queries(self, api_client, mock_client):
        """Test that all queries use v20-compatible syntax."""
        # Mock the GoogleAdsService
        mock_ga_service = MagicMock()
        api_client._client.get_service.return_value = mock_ga_service

        # Track all queries made
        queries = []

        def capture_query(request=None, customer_id=None, query=None):
            # Handle both old-style (customer_id, query) and new-style (request) calls
            if request is not None:
                query = request.query
            queries.append(query)
            return []

        mock_ga_service.search.side_effect = capture_query

        # Make various API calls to capture queries
        await api_client.get_campaigns("123-456-7890")
        await api_client.get_keywords("123-456-7890", include_metrics=False)
        await api_client.get_search_terms(
            "123-456-7890",
            datetime.now() - timedelta(days=7),
            datetime.now(),
        )
        await api_client.get_negative_keywords("123-456-7890")

        # Verify all queries use correct field names
        for query in queries:
            # Check for v20 field names
            if "metrics." in query and "conversions_value" in query:
                # Should use conversions_value, not conversion_value_micros
                assert "metrics.conversions_value" in query
                assert "metrics.conversion_value_micros" not in query

            # Check for correct resource usage
            if "keyword" in query.lower() and "metrics" in query:
                # Metrics should come from keyword_view, not ad_group_criterion
                assert (
                    "FROM keyword_view" in query or "FROM ad_group_criterion" in query
                )

            # Check for proper geographic view usage
            if "geographic_view" in query:
                assert "geographic_view.resource_name" in query
                # Location names should not be directly queried
                assert "geographic_view.city_name" not in query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
