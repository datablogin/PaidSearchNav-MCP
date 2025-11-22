"""Unit tests for GoogleAdsDataProvider rate limiting."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.data_providers.google_ads import GoogleAdsDataProvider
from paidsearchnav.security.rate_limiting import RateLimitError


@pytest.fixture
def mock_api_client():
    """Create a mock GoogleAdsAPIClient."""
    client = MagicMock()
    client.get_search_terms = AsyncMock(return_value=[])
    client.get_keywords = AsyncMock(return_value=[])
    client.get_campaigns = AsyncMock(return_value=[])
    client.get_negative_keywords = AsyncMock(return_value=[])
    client.get_placement_data = AsyncMock(return_value=[])
    client.get_geographic_performance = AsyncMock(return_value=[])
    client.get_distance_performance = AsyncMock(return_value=[])
    return client


@pytest.fixture
def data_provider(mock_api_client):
    """Create a GoogleAdsDataProvider with mock client."""
    return GoogleAdsDataProvider(mock_api_client)


class TestGoogleAdsDataProviderRateLimiting:
    """Test rate limiting in GoogleAdsDataProvider."""

    @pytest.mark.asyncio
    async def test_get_search_terms_valid_id_lists(
        self, data_provider, mock_api_client
    ):
        """Test get_search_terms with valid ID lists."""
        campaigns = ["123", "456", "789"]
        ad_groups = ["abc", "def"]

        await data_provider.get_search_terms(
            customer_id="test-customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Verify the API client was called with validated lists
        mock_api_client.get_search_terms.assert_called_once()
        call_args = mock_api_client.get_search_terms.call_args
        assert call_args.kwargs["campaigns"] == campaigns
        assert call_args.kwargs["ad_groups"] == ad_groups

    @pytest.mark.asyncio
    async def test_get_search_terms_exceeds_campaign_limit(self, data_provider):
        """Test get_search_terms when campaigns list exceeds limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=5,
        ):
            campaigns = ["1", "2", "3", "4", "5", "6"]  # Exceeds limit of 5

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_search_terms(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    campaigns=campaigns,
                )

            assert "Too many campaigns provided: 6 exceeds maximum of 5" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_get_search_terms_exceeds_ad_groups_limit(self, data_provider):
        """Test get_search_terms when ad_groups list exceeds limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=3,
        ):
            ad_groups = ["a", "b", "c", "d"]  # Exceeds limit of 3

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_search_terms(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    ad_groups=ad_groups,
                )

            assert "Too many ad_groups provided: 4 exceeds maximum of 3" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_get_keywords_valid_id_lists(self, data_provider, mock_api_client):
        """Test get_keywords with valid ID lists."""
        campaigns = ["123", "456"]
        ad_groups = ["abc", "def", "ghi"]

        await data_provider.get_keywords(
            customer_id="test-customer",
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Verify the API client was called with validated lists
        mock_api_client.get_keywords.assert_called_once()
        call_args = mock_api_client.get_keywords.call_args
        assert call_args.kwargs["campaigns"] == campaigns
        assert call_args.kwargs["ad_groups"] == ad_groups

    @pytest.mark.asyncio
    async def test_get_keywords_exceeds_limit(self, data_provider):
        """Test get_keywords when lists exceed limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=2,
        ):
            campaigns = ["1", "2", "3"]  # Exceeds limit of 2

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_keywords(
                    customer_id="test-customer",
                    campaigns=campaigns,
                )

            assert "Too many campaigns provided: 3 exceeds maximum of 2" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_none_lists_pass_through(self, data_provider, mock_api_client):
        """Test that None lists are passed through correctly."""
        await data_provider.get_search_terms(
            customer_id="test-customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=None,
            ad_groups=None,
        )

        call_args = mock_api_client.get_search_terms.call_args
        assert call_args.kwargs["campaigns"] is None
        assert call_args.kwargs["ad_groups"] is None

    @pytest.mark.asyncio
    async def test_empty_lists_allowed(self, data_provider, mock_api_client):
        """Test that empty lists are allowed."""
        await data_provider.get_keywords(
            customer_id="test-customer",
            campaigns=[],
            ad_groups=[],
        )

        call_args = mock_api_client.get_keywords.call_args
        assert call_args.kwargs["campaigns"] == []
        assert call_args.kwargs["ad_groups"] == []

    @pytest.mark.asyncio
    async def test_rate_limit_uses_env_var(self, data_provider):
        """Test that rate limiting respects PSN_MAX_IDS_PER_REQUEST env var."""
        # Test that the rate limiting uses the configured value
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=10,
        ):
            campaigns = list(range(11))  # Exceeds env var limit of 10

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_search_terms(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    campaigns=[str(i) for i in campaigns],
                )

            assert "11 exceeds maximum of 10" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_placement_data_valid_id_lists(
        self, data_provider, mock_api_client
    ):
        """Test get_placement_data with valid ID lists."""
        campaigns = ["123", "456"]
        ad_groups = ["abc", "def"]

        await data_provider.get_placement_data(
            customer_id="test-customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Verify the API client was called with validated lists
        mock_api_client.get_placement_data.assert_called_once()
        call_args = mock_api_client.get_placement_data.call_args
        assert call_args.kwargs["campaigns"] == campaigns
        assert call_args.kwargs["ad_groups"] == ad_groups

    @pytest.mark.asyncio
    async def test_get_placement_data_exceeds_limit(self, data_provider):
        """Test get_placement_data when lists exceed limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=3,
        ):
            campaigns = ["1", "2", "3", "4"]  # Exceeds limit of 3

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_placement_data(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    campaigns=campaigns,
                )

            assert "Too many campaigns provided: 4 exceeds maximum of 3" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_get_geographic_performance_valid_id_lists(
        self, data_provider, mock_api_client
    ):
        """Test get_geographic_performance with valid ID lists."""
        campaigns = ["123", "456", "789"]
        ad_groups = ["abc"]

        await data_provider.get_geographic_performance(
            customer_id="test-customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Verify the API client was called with validated lists
        mock_api_client.get_geographic_performance.assert_called_once()
        call_args = mock_api_client.get_geographic_performance.call_args
        assert call_args.kwargs["campaigns"] == campaigns
        assert call_args.kwargs["ad_groups"] == ad_groups

    @pytest.mark.asyncio
    async def test_get_geographic_performance_exceeds_limit(self, data_provider):
        """Test get_geographic_performance when lists exceed limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=2,
        ):
            ad_groups = ["a", "b", "c"]  # Exceeds limit of 2

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_geographic_performance(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    ad_groups=ad_groups,
                )

            assert "Too many ad_groups provided: 3 exceeds maximum of 2" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_get_distance_performance_valid_id_list(
        self, data_provider, mock_api_client
    ):
        """Test get_distance_performance with valid ID list."""
        campaigns = ["123", "456", "789", "abc"]

        await data_provider.get_distance_performance(
            customer_id="test-customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=campaigns,
        )

        # Verify the API client was called with validated list
        mock_api_client.get_distance_performance.assert_called_once()
        call_args = mock_api_client.get_distance_performance.call_args
        assert call_args.kwargs["campaigns"] == campaigns

    @pytest.mark.asyncio
    async def test_get_distance_performance_exceeds_limit(self, data_provider):
        """Test get_distance_performance when list exceeds limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=5,
        ):
            campaigns = ["1", "2", "3", "4", "5", "6"]  # Exceeds limit of 5

            with pytest.raises(RateLimitError) as exc_info:
                await data_provider.get_distance_performance(
                    customer_id="test-customer",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                    campaigns=campaigns,
                )

            assert "Too many campaigns provided: 6 exceeds maximum of 5" in str(
                exc_info.value
            )
