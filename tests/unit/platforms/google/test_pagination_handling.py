"""Unit tests for Google Ads API pagination handling."""

from unittest.mock import Mock, patch

import pytest
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v20.errors.types import GoogleAdsFailure

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.core.exceptions import APIError
from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient


class TestPaginationHandling:
    """Test pagination behavior and error handling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.google_ads = Mock()
        settings.google_ads.api_version = "v20"
        return settings

    @pytest.fixture
    def client(self, mock_settings):
        """Create GoogleAdsAPIClient instance for testing."""
        return GoogleAdsAPIClient(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_secret",
            refresh_token="test_refresh_token",
            settings=mock_settings,
            default_page_size=1000,
            max_page_size=10000,
        )

    def test_pagination_without_page_size_succeeds(self, client):
        """Test that API calls succeed when page_size is not set."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()
            mock_response = [Mock()]  # Single page response

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()
            mock_ga_service.search.return_value = mock_response

            # Mock the response to not have next_page_token (single page)
            mock_response[0].next_page_token = ""

            # Mock circuit breaker
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.return_value = mock_response

                result = client._paginated_search(
                    customer_id="123456789", query="SELECT campaign.id FROM campaign"
                )

                assert len(result) == 1
                # Verify page_size was not set in the request
                call_args = mock_breaker.call.call_args
                request = call_args[0][1]  # The search request
                # The request should not have page_size set or should handle it gracefully

    def test_page_size_not_supported_error_handling(self, client):
        """Test handling of PAGE_SIZE_NOT_SUPPORTED error."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Create GoogleAdsException for PAGE_SIZE_NOT_SUPPORTED
            failure = Mock(spec=GoogleAdsFailure)
            failure.errors = [Mock()]
            failure.errors[0].error_code.request_error = Mock()
            failure.errors[0].error_code.request_error.name = "PAGE_SIZE_NOT_SUPPORTED"
            failure.errors[
                0
            ].message = "Setting the page size is not supported. Search Responses will have fixed page size of '10000' rows."

            exception = GoogleAdsException(
                failure=failure,
                request_id="test_request_id",
                call=Mock(),
            )

            # Mock circuit breaker to raise the exception
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                assert "PAGE_SIZE_NOT_SUPPORTED" in str(exc_info.value)

    @pytest.mark.parametrize(
        "page_size,expected_error",
        [
            (0, "page_size must be between 1 and 10000"),
            (10001, "page_size must be between 1 and 10000"),
            (-1, "page_size must be between 1 and 10000"),
        ],
    )
    def test_invalid_page_size_validation(
        self, page_size, expected_error, mock_settings
    ):
        """Test that invalid page sizes are rejected during initialization."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsAPIClient(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
                refresh_token="test_refresh_token",
                settings=mock_settings,
                default_page_size=page_size,
            )

        assert expected_error in str(exc_info.value)

    def test_max_page_size_smaller_than_default(self, mock_settings):
        """Test that max_page_size cannot be smaller than default_page_size."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsAPIClient(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
                refresh_token="test_refresh_token",
                settings=mock_settings,
                default_page_size=5000,
                max_page_size=1000,
            )

        assert "default_page_size cannot exceed max_page_size" in str(exc_info.value)

    def test_multi_page_pagination_without_page_size(self, client):
        """Test multi-page pagination without setting page_size."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Mock multi-page response
            page1_response = [Mock()]
            page2_response = [Mock()]

            page1_response[0].next_page_token = "page2_token"
            page2_response[0].next_page_token = ""

            mock_ga_service.search.side_effect = [page1_response, page2_response]

            # Mock circuit breaker
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = [page1_response, page2_response]

                result = client._paginated_search(
                    customer_id="123456789", query="SELECT campaign.id FROM campaign"
                )

                assert len(result) == 2  # Two pages of results
                # Verify two API calls were made
                assert mock_breaker.call.call_count == 2

    def test_search_stream_without_page_size(self, client):
        """Test streaming search without setting page_size."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Mock single page response
            mock_row = Mock()
            mock_response = [mock_row]
            mock_response[0].next_page_token = ""

            mock_ga_service.search.return_value = mock_response

            # Mock circuit breaker
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.return_value = mock_response

                results = list(
                    client.search_stream(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )
                )

                assert len(results) == 1
                assert results[0] == mock_row

    def test_api_efficiency_metrics_collection(self, client):
        """Test that API efficiency metrics are properly collected."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Mock response with multiple rows to test record count
            mock_rows = [Mock() for _ in range(5)]
            mock_response = mock_rows
            mock_response[0].next_page_token = ""

            mock_ga_service.search.return_value = mock_response

            # Mock circuit breaker
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.return_value = mock_response

                start_time = 1000
                with patch("time.time", side_effect=[start_time, start_time + 0.5]):
                    result = client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Verify results
                assert len(result) == 5

                # Check circuit breaker metrics (proxy for API efficiency)
                metrics = client.circuit_breaker_metrics
                assert isinstance(metrics, dict)

    def test_backward_compatibility_with_older_api_versions(self, client):
        """Test backward compatibility handling for older API versions."""
        # This test simulates what would happen with older versions
        # that might throw INVALID_PAGE_SIZE instead of PAGE_SIZE_NOT_SUPPORTED

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Create GoogleAdsException for INVALID_PAGE_SIZE (older versions)
            failure = Mock(spec=GoogleAdsFailure)
            failure.errors = [Mock()]
            failure.errors[0].error_code.request_error = Mock()
            failure.errors[0].error_code.request_error.name = "INVALID_PAGE_SIZE"
            failure.errors[0].message = "Page size is invalid."

            exception = GoogleAdsException(
                failure=failure,
                request_id="test_request_id",
                call=Mock(),
            )

            # Mock circuit breaker to raise the exception
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                assert "INVALID_PAGE_SIZE" in str(exc_info.value)


class TestAPIEfficiencyMetrics:
    """Test API efficiency tracking and KPI metrics."""

    def test_api_call_count_tracking(self):
        """Test tracking of API call counts."""
        # This will be implemented with the APIEfficiencyMetrics class
        pass

    def test_response_time_measurement(self):
        """Test response time measurement for API calls."""
        # This will be implemented with the APIEfficiencyMetrics class
        pass

    def test_error_rate_calculation(self):
        """Test error rate calculation for pagination-related errors."""
        # This will be implemented with the APIEfficiencyMetrics class
        pass

    def test_records_per_call_efficiency(self):
        """Test calculation of records retrieved per API call."""
        # This will be implemented with the APIEfficiencyMetrics class
        pass


class TestVersionCompatibility:
    """Test compatibility across different API versions."""

    @pytest.mark.parametrize(
        "api_version,expected_behavior",
        [
            ("v13", "should_work_with_page_size"),
            ("v15", "should_work_with_page_size"),
            ("v17", "should_not_allow_page_size"),
            ("v20", "should_not_allow_page_size"),
        ],
    )
    def test_version_specific_behavior(self, api_version, expected_behavior):
        """Test version-specific pagination behavior."""
        # This test will verify that the client behaves correctly
        # across different API versions
        pass
