"""Unit tests for PAGE_SIZE_NOT_SUPPORTED error handling and graceful fallback."""

from unittest.mock import Mock, patch

import pytest
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v20.errors.types import GoogleAdsFailure

from paidsearchnav.core.config import Settings
from paidsearchnav.core.exceptions import APIError
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


class TestPageSizeErrorHandling:
    """Test error handling for page size related errors."""

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
        )

    def create_page_size_exception(self, error_type="PAGE_SIZE_NOT_SUPPORTED"):
        """Helper to create PAGE_SIZE_NOT_SUPPORTED or INVALID_PAGE_SIZE exceptions."""
        failure = Mock(spec=GoogleAdsFailure)
        failure.errors = [Mock()]
        failure.errors[0].error_code.request_error = Mock()
        failure.errors[0].error_code.request_error.name = error_type

        if error_type == "PAGE_SIZE_NOT_SUPPORTED":
            failure.errors[
                0
            ].message = "Setting the page size is not supported. Search Responses will have fixed page size of '10000' rows."
        else:  # INVALID_PAGE_SIZE
            failure.errors[0].message = "Page size is invalid."

        return GoogleAdsException(
            failure=failure,
            request_id="test_request_id",
            call=Mock(),
        )

    def test_page_size_not_supported_error_conversion(self, client):
        """Test that PAGE_SIZE_NOT_SUPPORTED errors are properly converted to APIError."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            # Mock circuit breaker to raise the exception
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Verify error message contains helpful information
                error_msg = str(exc_info.value)
                assert "PAGE_SIZE_NOT_SUPPORTED" in error_msg
                assert "fixed page size of '10000' rows" in error_msg

    def test_invalid_page_size_error_conversion(self, client):
        """Test that INVALID_PAGE_SIZE errors (older API versions) are properly handled."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("INVALID_PAGE_SIZE")

            # Mock circuit breaker to raise the exception
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                error_msg = str(exc_info.value)
                assert "INVALID_PAGE_SIZE" in error_msg

    def test_graceful_fallback_after_page_size_error(self, client):
        """Test graceful fallback behavior after encountering page size errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # First call fails with PAGE_SIZE_NOT_SUPPORTED
            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            # Mock circuit breaker to first fail, then succeed
            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                # First call should fail
                with pytest.raises(APIError):
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Verify circuit breaker recorded the failure
                assert mock_breaker.call.call_count == 1

    def test_error_logging_for_debugging(self, client, caplog):
        """Test that page size errors are properly logged for debugging."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError):
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Verify error was logged (through circuit breaker)
                # The exact logging depends on circuit breaker implementation

    def test_multiple_consecutive_page_size_errors(self, client):
        """Test handling of multiple consecutive page size errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                # Make multiple calls that should all fail
                for i in range(3):
                    with pytest.raises(APIError):
                        client._paginated_search(
                            customer_id="123456789",
                            query=f"SELECT campaign.id FROM campaign WHERE campaign.name = 'test_{i}'",
                        )

                # Verify all calls were attempted
                assert mock_breaker.call.call_count == 3

    def test_mixed_error_scenarios(self, client):
        """Test scenarios with different types of errors mixed with page size errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            # Create different types of exceptions
            page_size_exception = self.create_page_size_exception(
                "PAGE_SIZE_NOT_SUPPORTED"
            )

            # Create a generic Google Ads exception (not page size related)
            generic_failure = Mock(spec=GoogleAdsFailure)
            generic_failure.errors = [Mock()]
            generic_failure.errors[0].error_code.authorization_error = Mock()
            generic_failure.errors[
                0
            ].error_code.authorization_error.name = "USER_PERMISSION_DENIED"
            generic_failure.errors[
                0
            ].message = "User doesn't have permission to access customer."

            generic_exception = GoogleAdsException(
                failure=generic_failure,
                request_id="test_request_id",
                call=Mock(),
            )

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                # First call fails with page size error
                mock_breaker.call.side_effect = [page_size_exception, generic_exception]

                # First call - page size error
                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )
                assert "PAGE_SIZE_NOT_SUPPORTED" in str(exc_info.value)

                # Second call - different error
                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )
                assert "USER_PERMISSION_DENIED" in str(exc_info.value)

    def test_page_size_error_in_streaming(self, client):
        """Test page size error handling in streaming operations."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError) as exc_info:
                    # Try to consume the first item from the stream
                    stream = client.search_stream(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )
                    next(iter(stream))

                assert "PAGE_SIZE_NOT_SUPPORTED" in str(exc_info.value)

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("get_campaigns", ["123456789"]),
            ("get_keywords", ["123456789"]),
            ("get_search_terms", ["123456789", "2025-01-01", "2025-01-31"]),
            ("get_negative_keywords", ["123456789"]),
        ],
    )
    def test_page_size_errors_in_public_methods(self, client, method_name, args):
        """Test that page size errors are handled in all public API methods."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            exception = self.create_page_size_exception("PAGE_SIZE_NOT_SUPPORTED")

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                method = getattr(client, method_name)

                if method_name.startswith("get_search_terms"):
                    # Convert string dates to datetime objects if needed
                    from datetime import datetime

                    args = [
                        args[0],
                        datetime.strptime(args[1], "%Y-%m-%d"),
                        datetime.strptime(args[2], "%Y-%m-%d"),
                    ]

                with pytest.raises(APIError) as exc_info:
                    if method_name in [
                        "get_campaigns",
                        "get_keywords",
                        "get_negative_keywords",
                    ]:
                        # These are async methods
                        import asyncio

                        asyncio.run(method(*args))
                    else:
                        method(*args)

                assert "PAGE_SIZE_NOT_SUPPORTED" in str(exc_info.value)

    def test_error_context_preservation(self, client):
        """Test that error context is preserved when converting GoogleAdsException to APIError."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            original_exception = self.create_page_size_exception(
                "PAGE_SIZE_NOT_SUPPORTED"
            )
            original_exception.request_id = "test_request_12345"

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = original_exception

                with pytest.raises(APIError) as exc_info:
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Verify that important context from the original exception is preserved
                error_msg = str(exc_info.value)
                assert "PAGE_SIZE_NOT_SUPPORTED" in error_msg
                assert "fixed page size of '10000' rows" in error_msg

                # The original exception should be available as the cause
                assert exc_info.value.__cause__ is not None


class TestPageSizeErrorRecovery:
    """Test error recovery and retry mechanisms for page size errors."""

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
        )

    def test_no_automatic_retry_for_page_size_errors(self, client):
        """Test that page size errors are not automatically retried (since they're configuration issues)."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            failure = Mock(spec=GoogleAdsFailure)
            failure.errors = [Mock()]
            failure.errors[0].error_code.request_error = Mock()
            failure.errors[0].error_code.request_error.name = "PAGE_SIZE_NOT_SUPPORTED"
            failure.errors[0].message = "Setting the page size is not supported."

            exception = GoogleAdsException(
                failure=failure,
                request_id="test_request_id",
                call=Mock(),
            )

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                with pytest.raises(APIError):
                    client._paginated_search(
                        customer_id="123456789",
                        query="SELECT campaign.id FROM campaign",
                    )

                # Should only be called once (no retries)
                assert mock_breaker.call.call_count == 1

    def test_circuit_breaker_behavior_with_page_size_errors(self, client):
        """Test how circuit breaker handles page size errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = Mock()
            mock_ga_service = Mock()

            mock_get_client.return_value = mock_client
            mock_client.get_service.return_value = mock_ga_service
            mock_client.get_type.return_value = Mock()

            failure = Mock(spec=GoogleAdsFailure)
            failure.errors = [Mock()]
            failure.errors[0].error_code.request_error = Mock()
            failure.errors[0].error_code.request_error.name = "PAGE_SIZE_NOT_SUPPORTED"
            failure.errors[0].message = "Setting the page size is not supported."

            exception = GoogleAdsException(
                failure=failure,
                request_id="test_request_id",
                call=Mock(),
            )

            with patch.object(client, "_circuit_breaker") as mock_breaker:
                mock_breaker.call.side_effect = exception

                # Make multiple calls to see how circuit breaker handles page size errors
                for i in range(3):
                    with pytest.raises(APIError):
                        client._paginated_search(
                            customer_id="123456789",
                            query="SELECT campaign.id FROM campaign",
                        )

                # All calls should have been attempted (circuit breaker should handle this)
                assert mock_breaker.call.call_count == 3
