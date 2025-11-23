"""Tests for the GoogleAdsDataProvider."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav_mcp.models.campaign import Campaign
from paidsearchnav_mcp.models.keyword import Keyword
from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.data_providers.google_ads import GoogleAdsDataProvider


class TestGoogleAdsDataProvider:
    """Test the Google Ads data provider implementation."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock GoogleAdsAPIClient."""
        client = Mock()

        # Set up async mocks for all methods
        client.get_search_terms = AsyncMock()
        client.get_keywords = AsyncMock()
        client.get_negative_keywords = AsyncMock()
        client.get_campaigns = AsyncMock()
        client.get_shared_negative_lists = AsyncMock()
        client.get_campaign_shared_sets = AsyncMock()
        client.get_shared_set_negatives = AsyncMock()
        client.get_placement_data = AsyncMock()
        client.get_geographic_performance = AsyncMock()
        client.get_distance_performance = AsyncMock()
        client.get_performance_max_data = AsyncMock()
        client.get_performance_max_search_terms = AsyncMock()

        return client

    @pytest.fixture
    def provider(self, mock_api_client):
        """Create a GoogleAdsDataProvider with mock client."""
        return GoogleAdsDataProvider(api_client=mock_api_client)

    @pytest.fixture
    def date_range(self):
        """Create a standard date range for testing."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date

    @pytest.mark.asyncio
    async def test_get_search_terms_delegates_to_client(
        self, provider, mock_api_client, date_range
    ):
        """Test that get_search_terms delegates to the API client."""
        start_date, end_date = date_range
        customer_id = "123-456-7890"
        campaigns = ["Campaign 1", "Campaign 2"]
        ad_groups = ["Ad Group 1"]

        # Set up mock return value
        expected_terms = [
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
                search_term="test term",
                match_type="EXACT",
                metrics={
                    "impressions": 100,
                    "clicks": 10,
                    "cost": 5.0,
                    "conversions": 1.0,
                    "conversion_value": 50.0,
                },
            )
        ]
        mock_api_client.get_search_terms.return_value = expected_terms

        # Call the method
        result = await provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Verify delegation
        mock_api_client.get_search_terms.assert_called_once_with(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
            page_size=None,
            max_results=None,
        )

        assert result == expected_terms

    @pytest.mark.asyncio
    async def test_get_keywords_delegates_to_client(self, provider, mock_api_client):
        """Test that get_keywords delegates to the API client."""
        customer_id = "123-456-7890"
        campaigns = ["Campaign 1"]
        campaign_id = "camp_1"

        # Set up mock return value
        expected_keywords = [
            Keyword(
                keyword_id="kw_1",
                text="test keyword",
                match_type="EXACT",
                status="ENABLED",
                campaign_id=campaign_id,
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
            )
        ]
        mock_api_client.get_keywords.return_value = expected_keywords

        # Call the method
        result = await provider.get_keywords(
            customer_id=customer_id,
            campaigns=campaigns,
            campaign_id=campaign_id,
        )

        # Verify delegation
        mock_api_client.get_keywords.assert_called_once_with(
            customer_id=customer_id,
            campaigns=campaigns,
            ad_groups=None,
            campaign_id=campaign_id,
            include_metrics=True,
            start_date=None,
            end_date=None,
            page_size=None,
            max_results=None,
        )

        assert result == expected_keywords

    @pytest.mark.asyncio
    async def test_get_negative_keywords_delegates_to_client(
        self, provider, mock_api_client
    ):
        """Test that get_negative_keywords delegates to the API client."""
        customer_id = "123-456-7890"

        # Set up mock return value
        expected_negatives = [
            {
                "text": "free",
                "match_type": "BROAD",
                "level": "CAMPAIGN",
                "campaign_name": "Campaign 1",
            }
        ]
        mock_api_client.get_negative_keywords.return_value = expected_negatives

        # Call the method
        result = await provider.get_negative_keywords(
            customer_id=customer_id,
            include_shared_sets=True,
        )

        # Verify delegation
        mock_api_client.get_negative_keywords.assert_called_once_with(
            customer_id=customer_id,
            include_shared_sets=True,
            page_size=None,
            max_results=None,
        )

        assert result == expected_negatives

    @pytest.mark.asyncio
    async def test_get_campaigns_delegates_to_client(
        self, provider, mock_api_client, date_range
    ):
        """Test that get_campaigns delegates to the API client."""
        customer_id = "123-456-7890"
        start_date, end_date = date_range
        campaign_types = ["SEARCH"]

        # Set up mock return value
        expected_campaigns = [
            Campaign(
                campaign_id="camp_1",
                customer_id=customer_id,
                name="Campaign 1",
                status="ENABLED",
                type="SEARCH",
                budget_amount=1000.0,
                budget_currency="USD",
                bidding_strategy="TARGET_CPA",
            )
        ]
        mock_api_client.get_campaigns.return_value = expected_campaigns

        # Call the method
        result = await provider.get_campaigns(
            customer_id=customer_id,
            campaign_types=campaign_types,
            start_date=start_date,
            end_date=end_date,
        )

        # Verify delegation
        mock_api_client.get_campaigns.assert_called_once_with(
            customer_id=customer_id,
            campaign_types=campaign_types,
            start_date=start_date,
            end_date=end_date,
            page_size=None,
            max_results=None,
        )

        assert result == expected_campaigns

    @pytest.mark.asyncio
    async def test_get_shared_negative_lists_delegates_to_client(
        self, provider, mock_api_client
    ):
        """Test that get_shared_negative_lists delegates to the API client."""
        customer_id = "123-456-7890"

        # Set up mock return value
        expected_lists = [
            {
                "id": "snl_1",
                "name": "Universal Negatives",
                "negative_count": 25,
            }
        ]
        mock_api_client.get_shared_negative_lists.return_value = expected_lists

        # Call the method
        result = await provider.get_shared_negative_lists(customer_id=customer_id)

        # Verify delegation
        mock_api_client.get_shared_negative_lists.assert_called_once_with(
            customer_id=customer_id,
        )

        assert result == expected_lists

    @pytest.mark.asyncio
    async def test_get_placement_data_delegates_to_client(
        self, provider, mock_api_client, date_range
    ):
        """Test that get_placement_data delegates to the API client."""
        customer_id = "123-456-7890"
        start_date, end_date = date_range
        campaigns = ["Campaign 1"]

        # Set up mock return value
        expected_placements = [
            {
                "placement_id": "pl_1",
                "placement_name": "example.com",
                "impressions": 1000,
                "clicks": 50,
                "cost": 25.0,
            }
        ]
        mock_api_client.get_placement_data.return_value = expected_placements

        # Call the method
        result = await provider.get_placement_data(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
        )

        # Verify delegation
        mock_api_client.get_placement_data.assert_called_once_with(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=None,
            page_size=None,
            max_results=None,
        )

        assert result == expected_placements

    @pytest.mark.asyncio
    async def test_additional_google_ads_methods(
        self, provider, mock_api_client, date_range
    ):
        """Test additional Google Ads specific methods."""
        customer_id = "123-456-7890"
        start_date, end_date = date_range

        # Test get_geographic_performance
        expected_geo = [{"location": "US", "impressions": 1000}]
        mock_api_client.get_geographic_performance.return_value = expected_geo

        result = await provider.get_geographic_performance(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert result == expected_geo

        # Test get_performance_max_data
        expected_pmax = [{"campaign": "PMax Campaign", "conversions": 100}]
        mock_api_client.get_performance_max_data.return_value = expected_pmax

        result = await provider.get_performance_max_data(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert result == expected_pmax

    def test_provider_wraps_api_client(self, provider, mock_api_client):
        """Test that the provider properly wraps the API client."""
        assert provider.api_client is mock_api_client
