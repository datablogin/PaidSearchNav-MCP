"""Integration tests for circuit breaker with Google Ads API client."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav.core.config import CircuitBreakerConfig
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


@pytest.fixture
def circuit_breaker_config():
    """Circuit breaker configuration for testing."""
    return CircuitBreakerConfig(
        enabled=True,
        failure_threshold=2,
        recovery_timeout=5,
        success_threshold=1,
        collect_metrics=True,
    )


@pytest.fixture
def google_ads_client(circuit_breaker_config):
    """Google Ads API client with circuit breaker for testing."""
    return GoogleAdsAPIClient(
        developer_token="test-token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token",
        login_customer_id="1234567890",
        circuit_breaker_config=circuit_breaker_config,
    )


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with Google Ads API client."""

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    def test_circuit_breaker_protects_api_calls(
        self, mock_client_class, google_ads_client
    ):
        """Test that circuit breaker protects Google Ads API calls."""
        # Setup mock
        mock_service = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_client_class.load_from_dict.return_value = mock_client_instance

        # Mock successful API response
        mock_service.search.return_value = []

        # Test that API call works normally
        result = google_ads_client._execute_with_circuit_breaker(
            "test_operation",
            lambda: mock_service.search(
                customer_id="123", query="SELECT * FROM campaign"
            ),
        )

        assert result == []
        assert google_ads_client.circuit_breaker_metrics["total_calls"] == 1
        assert google_ads_client.circuit_breaker_metrics["failed_calls"] == 0

    def test_circuit_breaker_handles_exceptions(self, google_ads_client):
        """Test circuit breaker handles exceptions properly."""

        # Test that exceptions are properly caught and recorded
        def failing_operation():
            raise Exception("API failure")

        with pytest.raises(Exception):
            google_ads_client._execute_with_circuit_breaker(
                "test_operation", failing_operation
            )

        assert google_ads_client.circuit_breaker_metrics["failed_calls"] == 1

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    def test_circuit_breaker_opens_after_failures(
        self, mock_client_class, google_ads_client
    ):
        """Test circuit breaker opens after consecutive failures."""
        # Setup mock to consistently fail
        mock_service = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_client_class.load_from_dict.return_value = mock_client_instance

        mock_service.search.side_effect = Exception("API failure")

        # First failure
        with pytest.raises(Exception):
            google_ads_client._execute_with_circuit_breaker(
                "test_operation",
                lambda: mock_service.search(
                    customer_id="123", query="SELECT * FROM campaign"
                ),
            )

        # Circuit should still be closed
        assert google_ads_client._circuit_breaker.state == "closed"

        # Second failure should open circuit
        with pytest.raises(Exception):
            google_ads_client._execute_with_circuit_breaker(
                "test_operation",
                lambda: mock_service.search(
                    customer_id="123", query="SELECT * FROM campaign"
                ),
            )

        # Circuit should now be open
        assert google_ads_client._circuit_breaker.state == "open"
        assert google_ads_client.circuit_breaker_metrics["circuit_opened_count"] == 1

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    def test_circuit_breaker_rejects_calls_when_open(
        self, mock_client_class, google_ads_client
    ):
        """Test circuit breaker rejects calls when circuit is open."""
        # Force circuit to open by failing twice
        mock_service = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_client_class.load_from_dict.return_value = mock_client_instance

        mock_service.search.side_effect = Exception("API failure")

        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                google_ads_client._execute_with_circuit_breaker(
                    "test_operation",
                    lambda: mock_service.search(
                        customer_id="123", query="SELECT * FROM campaign"
                    ),
                )

        # Verify circuit is open
        assert google_ads_client._circuit_breaker.state == "open"

        # Now try to make a call - should be rejected by circuit breaker
        with pytest.raises(
            Exception
        ) as exc_info:  # Circuit breaker throws its own exception type
            google_ads_client._execute_with_circuit_breaker(
                "test_operation",
                lambda: mock_service.search(
                    customer_id="123", query="SELECT * FROM campaign"
                ),
            )

        # Should get circuit breaker exception
        assert "Circuit" in str(exc_info.value) and "OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    async def test_circuit_breaker_with_async_api_calls(
        self, mock_client_class, google_ads_client
    ):
        """Test circuit breaker works with async API calls."""
        # Setup mock
        mock_service = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_client_class.load_from_dict.return_value = mock_client_instance

        # Mock successful response
        mock_service.search.return_value = [Mock(customer=Mock(currency_code="USD"))]

        # Test async method that uses circuit breaker
        result = await google_ads_client._get_customer_currency("123", mock_service)

        assert result == "USD"
        assert google_ads_client.circuit_breaker_metrics["total_calls"] == 1

    def test_circuit_breaker_metrics_exposed(self, google_ads_client):
        """Test that circuit breaker metrics are properly exposed."""
        metrics = google_ads_client.circuit_breaker_metrics

        assert isinstance(metrics, dict)
        assert "total_calls" in metrics
        assert "failed_calls" in metrics
        assert "circuit_opened_count" in metrics
        assert "current_state" in metrics
        assert "failure_threshold" in metrics
        assert "recovery_timeout" in metrics

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    def test_circuit_breaker_disabled_bypass(self, mock_client_class):
        """Test that circuit breaker can be disabled."""
        # Create client with disabled circuit breaker
        disabled_config = CircuitBreakerConfig(enabled=False)
        client = GoogleAdsAPIClient(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            circuit_breaker_config=disabled_config,
        )

        # Setup mock
        mock_service = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_client_class.load_from_dict.return_value = mock_client_instance

        mock_service.search.return_value = []

        # Should work normally even with disabled circuit breaker
        result = client._execute_with_circuit_breaker(
            "test_operation",
            lambda: mock_service.search(
                customer_id="123", query="SELECT * FROM campaign"
            ),
        )

        assert result == []


class TestCircuitBreakerWithRealGoogleAdsClient:
    """Test circuit breaker behavior with simpler scenarios."""

    def test_circuit_breaker_metrics_tracking(self, google_ads_client):
        """Test that circuit breaker metrics are properly tracked."""

        # Test successful operation
        def successful_operation():
            return "success"

        result = google_ads_client._execute_with_circuit_breaker(
            "test_operation", successful_operation
        )

        assert result == "success"
        metrics = google_ads_client.circuit_breaker_metrics
        assert metrics["total_calls"] == 1
        assert metrics["failed_calls"] == 0

        # Test failed operation
        def failing_operation():
            raise Exception("API failure")

        with pytest.raises(Exception):
            google_ads_client._execute_with_circuit_breaker(
                "test_operation", failing_operation
            )

        metrics = google_ads_client.circuit_breaker_metrics
        assert metrics["total_calls"] == 2
        assert metrics["failed_calls"] == 1
