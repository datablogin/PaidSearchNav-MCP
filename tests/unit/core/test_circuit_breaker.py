"""Tests for circuit breaker functionality."""

import time
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.core.circuit_breaker import (
    GoogleAdsCircuitBreaker,
    create_google_ads_circuit_breaker,
)
from paidsearchnav_mcp.core.config import CircuitBreakerConfig
from paidsearchnav_mcp.core.exceptions import APIError, RateLimitError


class TestGoogleAdsCircuitBreaker:
    """Test GoogleAdsCircuitBreaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes with correct configuration."""
        config = CircuitBreakerConfig(
            enabled=True, failure_threshold=3, recovery_timeout=30, success_threshold=2
        )

        breaker = GoogleAdsCircuitBreaker(config)

        assert breaker.config == config
        assert breaker.state == "closed"
        assert breaker.metrics["total_calls"] == 0
        assert breaker.metrics["failed_calls"] == 0
        assert breaker.metrics["circuit_opened_count"] == 0

    def test_circuit_breaker_disabled_passthrough(self):
        """Test circuit breaker passes through when disabled."""
        config = CircuitBreakerConfig(enabled=False)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def test_function():
            return "success"

        # Should work normally even if circuit breaker is disabled
        result = test_function()
        assert result == "success"

    def test_circuit_breaker_success_tracking(self):
        """Test circuit breaker tracks successful calls."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=3)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def successful_function():
            return "success"

        # Call function successfully
        result = successful_function()
        assert result == "success"
        assert breaker.metrics["total_calls"] == 1
        assert breaker.metrics["failed_calls"] == 0
        assert breaker.state == "closed"

    def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker tracks failed calls."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=3)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def failing_function():
            raise APIError("Test API error")

        # Test single failure
        with pytest.raises(APIError):
            failing_function()

        assert breaker.metrics["total_calls"] == 1
        assert breaker.metrics["failed_calls"] == 1
        assert breaker.state == "closed"  # Should still be closed after 1 failure

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold is reached."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=2)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def failing_function():
            raise RateLimitError("Rate limit exceeded")

        # First failure
        with pytest.raises(RateLimitError):
            failing_function()
        assert breaker.state == "closed"

        # Second failure should open the circuit
        with pytest.raises(RateLimitError):
            failing_function()

        assert breaker.metrics["circuit_opened_count"] == 1
        assert breaker.state == "open"

    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when open."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def failing_function():
            raise APIError("Test error")

        # Trigger circuit breaker to open
        with pytest.raises(APIError):
            failing_function()

        # Now circuit should be open and reject calls immediately
        with pytest.raises(Exception):  # Circuit breaker exception
            failing_function()

    def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker recovery after timeout."""
        config = CircuitBreakerConfig(
            enabled=True,
            failure_threshold=1,
            recovery_timeout=1,  # 1 second for fast test
        )
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def test_function(should_fail=True):
            if should_fail:
                raise APIError("Test error")
            return "success"

        # Open the circuit
        with pytest.raises(APIError):
            test_function(should_fail=True)

        assert breaker.state == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Circuit should allow one test call (half-open state)
        # If it succeeds, circuit should close
        result = test_function(should_fail=False)
        assert result == "success"

    def test_circuit_breaker_metrics_collection(self):
        """Test circuit breaker collects detailed metrics."""
        config = CircuitBreakerConfig(enabled=True, collect_metrics=True)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def mixed_function(should_fail):
            if should_fail:
                raise APIError("Test error")
            return "success"

        # Test successful call
        mixed_function(should_fail=False)

        # Test failed call
        with pytest.raises(APIError):
            mixed_function(should_fail=True)

        metrics = breaker.metrics
        assert metrics["total_calls"] == 2
        assert metrics["failed_calls"] == 1
        assert "failure_threshold" in metrics
        assert "recovery_timeout" in metrics
        assert "current_state" in metrics

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def failing_function():
            raise APIError("Test error")

        # Open the circuit
        with pytest.raises(APIError):
            failing_function()

        assert breaker.state == "open"

        # Reset circuit breaker
        breaker.reset()

        assert breaker.state == "closed"
        assert breaker.metrics["current_state"] == "closed"

    def test_circuit_breaker_handles_unexpected_exceptions(self):
        """Test circuit breaker handles unexpected exceptions."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=2)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def unexpected_error_function():
            raise ValueError("Unexpected error")

        # Circuit breaker should still trigger on unexpected exceptions
        with pytest.raises(ValueError):
            unexpected_error_function()

        assert breaker.metrics["total_calls"] == 1
        assert breaker.metrics["failed_calls"] == 1


class TestCircuitBreakerFactory:
    """Test circuit breaker factory function."""

    def test_create_google_ads_circuit_breaker(self):
        """Test factory function creates proper circuit breaker."""
        config = CircuitBreakerConfig(
            enabled=True, failure_threshold=5, recovery_timeout=120
        )

        breaker = create_google_ads_circuit_breaker(config)

        assert isinstance(breaker, GoogleAdsCircuitBreaker)
        assert breaker.config == config
        assert breaker.state == "closed"


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration scenarios."""

    @patch("paidsearchnav.core.circuit_breaker.logger")
    def test_circuit_breaker_logging(self, mock_logger):
        """Test circuit breaker logs important events."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def failing_function():
            raise RateLimitError("Rate limit exceeded")

        # Trigger circuit to open
        with pytest.raises(RateLimitError):
            failing_function()

        # Verify warning was logged for the categorized error
        mock_logger.warning.assert_called()
        assert "Google Ads circuit breaker triggered by RateLimitError" in str(
            mock_logger.warning.call_args
        )

        # Also verify error was logged when circuit opened
        mock_logger.error.assert_called()
        assert "circuit breaker OPENED" in str(mock_logger.error.call_args)

    def test_circuit_breaker_with_rate_limit_error(self):
        """Test circuit breaker specifically with rate limit errors."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def rate_limited_function():
            raise RateLimitError("Rate limit exceeded")

        # Rate limit error should trigger circuit breaker
        with pytest.raises(RateLimitError):
            rate_limited_function()

        assert breaker.state == "open"
        assert breaker.metrics["failed_calls"] == 1

    def test_circuit_breaker_with_api_error(self):
        """Test circuit breaker specifically with API errors."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = GoogleAdsCircuitBreaker(config)

        @breaker
        def api_error_function():
            raise APIError("API error occurred")

        # API error should trigger circuit breaker
        with pytest.raises(APIError):
            api_error_function()

        assert breaker.state == "open"
        assert breaker.metrics["failed_calls"] == 1
