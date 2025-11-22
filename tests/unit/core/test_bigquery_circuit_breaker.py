"""Tests for BigQuery circuit breaker implementation."""

from unittest.mock import patch

import pytest

from paidsearchnav.core.circuit_breaker import (
    BigQueryCircuitBreaker,
    BigQueryRetryHandler,
    RetryConfig,
    create_bigquery_circuit_breaker,
    create_bigquery_retry_handler,
)
from paidsearchnav.core.config import CircuitBreakerConfig


class TestBigQueryCircuitBreaker:
    """Test BigQuery circuit breaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly."""
        config = CircuitBreakerConfig(
            enabled=True,
            failure_threshold=3,
            recovery_timeout=30,
        )

        breaker = BigQueryCircuitBreaker(config)

        assert breaker.config == config
        assert breaker.state == "closed"
        assert breaker.is_healthy is True
        assert breaker.is_open is False
        assert "total_calls" in breaker._metrics
        assert "failed_calls" in breaker._metrics
        assert "circuit_opened_count" in breaker._metrics

    def test_circuit_breaker_disabled(self):
        """Test circuit breaker when disabled."""
        config = CircuitBreakerConfig(enabled=False)
        breaker = BigQueryCircuitBreaker(config)

        def test_func():
            return "success"

        wrapped_func = breaker(test_func)
        result = wrapped_func()

        assert result == "success"
        assert breaker._metrics["total_calls"] == 0  # No tracking when disabled

    def test_circuit_breaker_success_tracking(self):
        """Test circuit breaker tracks successful calls."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=3)
        breaker = BigQueryCircuitBreaker(config)

        @breaker
        def test_func():
            return "success"

        result = test_func()

        assert result == "success"
        assert breaker._metrics["total_calls"] == 1
        assert breaker._metrics["failed_calls"] == 0
        assert breaker.state == "closed"

    def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker tracks failures."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=2)
        breaker = BigQueryCircuitBreaker(config)

        @breaker
        def test_func():
            raise Exception("Test error")

        # First failure
        with pytest.raises(Exception):
            test_func()

        assert breaker._metrics["total_calls"] == 1
        assert breaker._metrics["failed_calls"] == 1
        assert breaker.state == "closed"

        # Second failure should open circuit
        with pytest.raises(Exception):
            test_func()

        assert breaker._metrics["circuit_opened_count"] == 1
        assert breaker.state == "open"
        assert breaker.is_open is True
        assert breaker.is_healthy is False

    @patch("paidsearchnav.core.circuit_breaker.BIGQUERY_AVAILABLE", True)
    def test_bigquery_specific_error_categorization(self):
        """Test BigQuery-specific error categorization."""
        from google.cloud.exceptions import GoogleCloudError

        config = CircuitBreakerConfig(enabled=True, failure_threshold=5)
        breaker = BigQueryCircuitBreaker(config)

        @breaker
        def quota_error_func():
            raise GoogleCloudError("quota exceeded for project")

        @breaker
        def timeout_error_func():
            raise GoogleCloudError("timeout occurred during operation")

        @breaker
        def connection_error_func():
            raise GoogleCloudError("connection failed to server")

        # Test quota error tracking
        with pytest.raises(GoogleCloudError):
            quota_error_func()
        assert breaker._metrics["quota_exceeded_count"] == 1

        # Test timeout error tracking
        with pytest.raises(GoogleCloudError):
            timeout_error_func()
        assert breaker._metrics["timeout_count"] == 1

        # Test connection error tracking
        with pytest.raises(GoogleCloudError):
            connection_error_func()
        assert breaker._metrics["connection_error_count"] == 1

    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=2)
        breaker = BigQueryCircuitBreaker(config)

        metrics = breaker.metrics

        assert "total_calls" in metrics
        assert "failed_calls" in metrics
        assert "current_state" in metrics
        assert "failure_count" in metrics
        assert "failure_threshold" in metrics
        assert "recovery_timeout" in metrics
        assert "health_status" in metrics
        assert metrics["health_status"] == "healthy"

    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset functionality."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        breaker = BigQueryCircuitBreaker(config)

        @breaker
        def failing_func():
            raise Exception("Test error")

        # Trigger circuit breaker to open
        with pytest.raises(Exception):
            failing_func()

        assert breaker.state == "open"

        # Reset circuit breaker
        breaker.reset()

        assert breaker.state == "closed"
        assert breaker.is_healthy is True

    def test_get_health_check_info(self):
        """Test health check information."""
        config = CircuitBreakerConfig(enabled=True, failure_threshold=3)
        breaker = BigQueryCircuitBreaker(config)

        health_info = breaker.get_health_check_info()

        assert health_info["service"] == "BigQuery"
        assert health_info["state"] == "closed"
        assert health_info["is_healthy"] is True
        assert "failure_rate" in health_info
        assert "error_breakdown" in health_info
        assert "quota_exceeded" in health_info["error_breakdown"]
        assert "timeouts" in health_info["error_breakdown"]
        assert "connection_errors" in health_info["error_breakdown"]


class TestBigQueryRetryHandler:
    """Test BigQuery retry handler functionality."""

    def test_retry_config_initialization(self):
        """Test retry configuration initialization."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            backoff_multiplier=3.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.backoff_multiplier == 3.0
        assert config.jitter is False

    def test_retry_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0, max_delay=10.0, backoff_multiplier=2.0, jitter=False
        )

        # Test exponential backoff
        assert config.get_delay(1) == 1.0  # base_delay * 2^0
        assert config.get_delay(2) == 2.0  # base_delay * 2^1
        assert config.get_delay(3) == 4.0  # base_delay * 2^2
        assert config.get_delay(4) == 8.0  # base_delay * 2^3
        assert config.get_delay(5) == 10.0  # Capped at max_delay

    def test_retry_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(
            base_delay=2.0, max_delay=10.0, backoff_multiplier=2.0, jitter=True
        )

        # With jitter, delay should be between 50% and 100% of calculated delay
        delay = config.get_delay(2)  # Expected base: 4.0
        assert 1.0 <= delay <= 4.0  # Should be between 2.0 and 4.0

    def test_retry_handler_initialization(self):
        """Test retry handler initialization."""
        retry_config = RetryConfig(max_retries=3)
        handler = BigQueryRetryHandler(retry_config)

        assert handler.config == retry_config
        assert handler._metrics["total_retries"] == 0
        assert handler._metrics["successful_retries"] == 0
        assert handler._metrics["failed_retries"] == 0

    @patch("paidsearchnav.core.circuit_breaker.BIGQUERY_AVAILABLE", True)
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        from google.cloud.exceptions import GoogleCloudError

        handler = BigQueryRetryHandler(RetryConfig(max_retries=3))

        # Should retry transient BigQuery errors
        quota_error = GoogleCloudError("quota exceeded")
        assert handler.should_retry(quota_error, 1) is True

        timeout_error = GoogleCloudError("timeout occurred")
        assert handler.should_retry(timeout_error, 2) is True

        connection_error = GoogleCloudError("network connection failed")
        assert handler.should_retry(connection_error, 1) is True

        # Should not retry after max attempts
        assert handler.should_retry(quota_error, 3) is False
        assert handler.should_retry(quota_error, 4) is False

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self):
        """Test successful execution on first attempt."""
        handler = BigQueryRetryHandler()

        def success_func():
            return "success"

        result = await handler.execute_with_retry(success_func)

        assert result == "success"
        assert handler._metrics["total_retries"] == 0
        assert handler._metrics["successful_retries"] == 0

    @pytest.mark.asyncio
    @patch("paidsearchnav.core.circuit_breaker.BIGQUERY_AVAILABLE", True)
    async def test_execute_with_retry_success_after_failure(self):
        """Test successful execution after retries."""
        from google.cloud.exceptions import GoogleCloudError

        handler = BigQueryRetryHandler(RetryConfig(max_retries=3, base_delay=0.01))

        attempt_count = 0

        def flaky_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise GoogleCloudError("temporary quota exceeded")
            return "success"

        result = await handler.execute_with_retry(flaky_func)

        assert result == "success"
        assert attempt_count == 3
        assert handler._metrics["successful_retries"] == 1
        assert handler._metrics["total_retries"] == 2

    @pytest.mark.asyncio
    @patch("paidsearchnav.core.circuit_breaker.BIGQUERY_AVAILABLE", True)
    async def test_execute_with_retry_all_attempts_fail(self):
        """Test retry exhaustion."""
        from google.cloud.exceptions import GoogleCloudError

        handler = BigQueryRetryHandler(RetryConfig(max_retries=2, base_delay=0.01))

        def failing_func():
            raise GoogleCloudError("persistent quota exceeded")

        with pytest.raises(GoogleCloudError):
            await handler.execute_with_retry(failing_func)

        assert handler._metrics["total_retries"] == 2
        assert handler._metrics["failed_retries"] == 1
        assert handler._metrics["successful_retries"] == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry_async_function(self):
        """Test retry with async functions."""
        handler = BigQueryRetryHandler()

        async def async_success_func():
            return "async_success"

        result = await handler.execute_with_retry(async_success_func)

        assert result == "async_success"

    def test_retry_metrics(self):
        """Test retry handler metrics."""
        config = RetryConfig(max_retries=3, base_delay=1.0)
        handler = BigQueryRetryHandler(config)

        metrics = handler.metrics

        assert "total_retries" in metrics
        assert "successful_retries" in metrics
        assert "failed_retries" in metrics
        assert "retry_config" in metrics
        assert metrics["retry_config"]["max_retries"] == 3
        assert metrics["retry_config"]["base_delay"] == 1.0
        assert "success_rate" in metrics


class TestFactoryFunctions:
    """Test factory functions for creating circuit breaker and retry handler."""

    def test_create_bigquery_circuit_breaker(self):
        """Test BigQuery circuit breaker factory function."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = create_bigquery_circuit_breaker(config)

        assert isinstance(breaker, BigQueryCircuitBreaker)
        assert breaker.config == config

    def test_create_bigquery_retry_handler(self):
        """Test BigQuery retry handler factory function."""
        handler = create_bigquery_retry_handler(
            max_retries=5, base_delay=2.0, max_delay=30.0
        )

        assert isinstance(handler, BigQueryRetryHandler)
        assert handler.config.max_retries == 5
        assert handler.config.base_delay == 2.0
        assert handler.config.max_delay == 30.0
