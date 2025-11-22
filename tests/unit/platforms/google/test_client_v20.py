"""Unit tests for Google Ads API v20 compatibility fixes."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


class TestGoogleAdsClientV20Fixes:
    """Test v20 compatibility fixes in Google Ads client."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        with patch("paidsearchnav.platforms.google.client.GoogleAdsClient"):
            client = GoogleAdsAPIClient(
                developer_token="test",
                client_id="test",
                client_secret="test",
                refresh_token="test",
            )
            client._initialized = True
            client._client = MagicMock()
            return client

    @pytest.mark.asyncio
    async def test_conversion_value_not_multiplied_in_geographic(self, client):
        """Test that conversions_value is NOT multiplied by 1,000,000 in geographic_performance."""
        mock_service = MagicMock()
        client._client.get_service.return_value = mock_service
        client._client.get_type.return_value = MagicMock()

        # Mock response with conversions_value already in micros
        mock_row = MagicMock()
        mock_row.campaign.id = 123
        mock_row.campaign.name = "Test"
        mock_row.geographic_view.resource_name = (
            "customers/123/geographicViews/456~CITY"
        )
        mock_row.metrics.conversions_value = 1000000  # 1 dollar in micros

        # Mock the response iterator properly
        mock_response = MagicMock()
        mock_response.__iter__ = lambda x: iter([mock_row])

        # get_geographic_performance makes 2 API calls
        mock_service.search.side_effect = [
            mock_response,  # First call for geo data
            MagicMock(__iter__=lambda x: iter([])),  # Second call for location names
        ]

        result = await client.get_geographic_performance(
            customer_id="1234567890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(result) == 1
        # Should be 1000000, NOT 1000000000000
        assert result[0]["conversion_value_micros"] == 1000000

    @pytest.mark.asyncio
    async def test_conversion_value_not_multiplied_in_distance(self, client):
        """Test that conversions_value is NOT multiplied by 1,000,000 in distance_performance."""
        mock_service = MagicMock()
        client._client.get_service.return_value = mock_service
        client._client.get_type.return_value = MagicMock()

        # Mock response with conversions_value already in micros
        mock_row = MagicMock()
        mock_row.campaign.id = 123
        mock_row.campaign.name = "Test"
        mock_row.distance_view.distance_bucket = "WITHIN_5KM"
        mock_row.metrics.conversions_value = 2000000  # 2 dollars in micros

        # Mock the response iterator properly
        mock_response = MagicMock()
        mock_response.__iter__ = lambda x: iter([mock_row])
        mock_service.search.return_value = mock_response

        result = await client.get_distance_performance(
            customer_id="1234567890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(result) == 1
        # Should be 2000000, NOT 2000000000000
        assert result[0]["conversion_value_micros"] == 2000000

    @pytest.mark.asyncio
    async def test_keyword_metrics_cost_conversion(self, client):
        """Test that cost_micros is properly converted to currency in keyword metrics."""
        mock_service = MagicMock()
        client._client.get_service.return_value = mock_service

        # Mock keyword response
        mock_keyword = MagicMock()
        mock_keyword.ad_group_criterion.criterion_id = 123
        mock_keyword.ad_group.id = 456
        mock_keyword.ad_group_criterion.keyword.text = "test"
        mock_keyword.ad_group_criterion.keyword.match_type.name = "EXACT"
        mock_keyword.ad_group_criterion.status.name = "ENABLED"
        mock_keyword.campaign.id = 789
        mock_keyword.campaign.name = "Campaign"
        mock_keyword.ad_group.name = "Ad Group"

        # Mock metrics response
        mock_metrics = MagicMock()
        mock_metrics.ad_group.id = 456
        mock_metrics.ad_group_criterion.criterion_id = 123
        mock_metrics.metrics.cost_micros = 5500000  # $5.50 in micros

        mock_service.search.side_effect = [
            [mock_keyword],
            [mock_metrics],
        ]

        result = await client.get_keywords(
            customer_id="1234567890",
            include_metrics=True,
        )

        assert len(result) == 1
        # Cost should be converted from micros to currency
        assert result[0].cost == 5.5  # $5.50, not 5500000

    @pytest.mark.asyncio
    async def test_null_safety_geographic_fields(self, client):
        """Test null safety for geographic view fields."""
        mock_service = MagicMock()
        client._client.get_service.return_value = mock_service
        client._client.get_type.return_value = MagicMock()

        # Mock response with missing optional fields
        # Use a simple approach - just return None for missing attributes
        mock_row = MagicMock()
        mock_row.campaign.id = 123
        mock_row.campaign.name = "Test"
        mock_row.geographic_view.resource_name = "customers/123/geographicViews/456"

        # Configure missing attributes to return None (simulating missing proto fields)
        mock_row.geographic_view.country_criterion_id = None
        mock_row.geographic_view.location_type = None
        mock_row.metrics.conversions_value = None
        mock_row.metrics.impressions = 100
        mock_row.metrics.clicks = 10
        mock_row.metrics.conversions = 1
        mock_row.metrics.cost_micros = 50000

        # Mock the response iterator properly
        mock_response = MagicMock()
        mock_response.__iter__ = lambda x: iter([mock_row])

        # get_geographic_performance makes 2 API calls
        mock_service.search.side_effect = [
            mock_response,  # First call for geo data
            MagicMock(__iter__=lambda x: iter([])),  # Second call for location names
        ]

        # Should not raise AttributeError
        result = await client.get_geographic_performance(
            customer_id="1234567890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(result) == 1
        assert result[0]["country_criterion_id"] == 0  # Default value
        assert result[0]["location_type"] == ""  # Default value
        assert result[0]["conversion_value_micros"] == 0  # Default value

    @pytest.mark.asyncio
    async def test_location_name_resolution_parsing(self, client):
        """Test location name parsing from canonical names."""
        mock_service = MagicMock()
        client._client.get_service.return_value = mock_service
        client._client.get_type.return_value = MagicMock()

        # Mock geographic view
        mock_geo = MagicMock()
        mock_geo.campaign.id = 123
        mock_geo.campaign.name = "Test"
        mock_geo.geographic_view.resource_name = (
            "customers/123/geographicViews/1023191~CITY"
        )
        mock_geo.metrics.impressions = 100

        # Mock location constant for New York
        mock_location = MagicMock()
        mock_location.geo_target_constant.id = 1023191
        mock_location.geo_target_constant.name = "New York"
        mock_location.geo_target_constant.target_type.name = "City"
        mock_location.geo_target_constant.canonical_name = (
            "New York, New York, United States"
        )

        # Mock the response iterators properly
        mock_geo_response = MagicMock()
        mock_geo_response.__iter__ = lambda x: iter([mock_geo])

        mock_location_response = MagicMock()
        mock_location_response.__iter__ = lambda x: iter([mock_location])

        mock_service.search.side_effect = [
            mock_geo_response,  # First call for geo data
            mock_location_response,  # Second call for location names
        ]

        result = await client.get_geographic_performance(
            customer_id="1234567890",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        assert len(result) == 1
        # Verify location name parsing
        assert result[0]["city_name"] == "New York"
        assert result[0]["region_name"] == "New York"
        assert result[0]["country_name"] == "United States"
