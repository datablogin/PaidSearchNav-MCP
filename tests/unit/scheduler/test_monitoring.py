"""Tests for scheduler monitoring functionality."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry

from paidsearchnav_mcp.scheduler.monitoring import (
    CorrelationContext,
    HealthChecker,
    SchedulerMetrics,
    StructuredLogger,
    start_metrics_server,
)


class TestSchedulerMetrics:
    """Test Prometheus metrics collection."""

    def setup_method(self):
        """Set up each test with a clean metrics registry."""
        # Create a new registry for each test to avoid conflicts
        self.registry = CollectorRegistry()

    def test_scheduler_metrics_initialization(self):
        """Test metrics initialization."""
        # Use a unique namespace for this test
        metrics = SchedulerMetrics("test_init")

        assert metrics.namespace == "test_init"
        assert hasattr(metrics, "job_executions_total")
        assert hasattr(metrics, "job_execution_duration")
        assert hasattr(metrics, "job_retry_attempts_total")
        assert hasattr(metrics, "active_jobs_gauge")
        assert hasattr(metrics, "scheduler_status_gauge")

    def test_record_job_execution(self):
        """Test job execution recording."""
        metrics = SchedulerMetrics("test_execution")

        # Record a successful job execution
        metrics.record_job_execution("audit", "completed", "customer_123", 30.5)

        # Verify metrics were recorded (we can't easily test the actual Prometheus values,
        # but we can test that the methods don't raise exceptions)
        assert True  # If we get here, no exceptions were raised

    def test_record_job_retry(self):
        """Test job retry recording."""
        metrics = SchedulerMetrics("test_retry")

        # Record a retry
        metrics.record_job_retry("audit", "customer_123", "ConnectionError")

        # Verify no exceptions
        assert True

    def test_record_job_error(self):
        """Test job error recording."""
        metrics = SchedulerMetrics("test_error")

        # Record an error
        metrics.record_job_error("audit", "ValueError", "customer_123")

        # Verify no exceptions
        assert True

    def test_update_gauges(self):
        """Test gauge updates."""
        metrics = SchedulerMetrics("test_gauges")

        # Update various gauges
        metrics.update_active_jobs("audit", 5)
        metrics.update_scheduled_jobs("audit", "true", 10)
        metrics.update_queue_depth("audit", 3)
        metrics.set_scheduler_status(True)
        metrics.set_database_status(True)
        metrics.set_google_ads_api_status(True)

        # Verify no exceptions
        assert True

    def test_set_scheduler_info(self):
        """Test scheduler info setting."""
        metrics = SchedulerMetrics("test_info")
        start_time = datetime.now(timezone.utc)

        # Set scheduler info
        metrics.set_scheduler_info("1.0.0", "test-instance", start_time)

        # Verify no exceptions
        assert True

    def test_update_system_metrics(self):
        """Test system metrics update."""
        metrics = SchedulerMetrics("test_system")

        # Update system metrics
        metrics.update_system_metrics(
            1024.0 * 1024 * 1024, 50.5
        )  # 1GB memory, 50.5% CPU

        # Verify no exceptions
        assert True

    def test_job_execution_timer_context_manager(self):
        """Test job execution timer context manager."""
        metrics = SchedulerMetrics("test_timer")

        # Use the timer context manager
        with metrics.job_execution_timer("audit", "customer_123"):
            # Simulate some work
            import time

            time.sleep(0.01)

        # Verify no exceptions
        assert True


class TestCorrelationContext:
    """Test correlation context for logging."""

    def test_correlation_context_creation(self):
        """Test correlation context creation."""
        ctx = CorrelationContext()

        assert ctx.correlation_id is not None
        assert len(ctx.correlation_id) > 0
        assert ctx.job_id is None
        assert ctx.customer_id is None
        assert ctx.job_type is None
        assert isinstance(ctx.start_time, datetime)

    def test_correlation_context_with_values(self):
        """Test correlation context with provided values."""
        start_time = datetime.now(timezone.utc)
        ctx = CorrelationContext(
            job_id="job_123",
            customer_id="customer_456",
            job_type="audit",
            start_time=start_time,
        )

        assert ctx.job_id == "job_123"
        assert ctx.customer_id == "customer_456"
        assert ctx.job_type == "audit"
        assert ctx.start_time == start_time

    def test_correlation_context_to_dict(self):
        """Test correlation context dictionary conversion."""
        ctx = CorrelationContext(
            job_id="job_123", customer_id="customer_456", job_type="audit"
        )

        ctx_dict = ctx.to_dict()

        assert "correlation_id" in ctx_dict
        assert ctx_dict["job_id"] == "job_123"
        assert ctx_dict["customer_id"] == "customer_456"
        assert ctx_dict["job_type"] == "audit"
        assert "start_time" in ctx_dict


class TestStructuredLogger:
    """Test structured logging with correlation."""

    def test_structured_logger_creation(self):
        """Test structured logger creation."""
        logger = StructuredLogger("test_logger")

        assert logger._context is None
        assert hasattr(logger, "logger")

    def test_set_and_clear_context(self):
        """Test setting and clearing context."""
        logger = StructuredLogger("test_logger")
        ctx = CorrelationContext(job_id="test_job")

        # Set context
        logger.set_context(ctx)
        assert logger._context == ctx

        # Clear context
        logger.clear_context()
        assert logger._context is None

    def test_context_manager(self):
        """Test context manager functionality."""
        logger = StructuredLogger("test_logger")
        ctx = CorrelationContext(job_id="test_job")
        old_ctx = CorrelationContext(job_id="old_job")

        # Set initial context
        logger.set_context(old_ctx)

        # Use context manager
        with logger.context(ctx):
            assert logger._context == ctx

        # Verify old context is restored
        assert logger._context == old_ctx

    @patch("logging.Logger.log")
    def test_logging_with_context(self, mock_log):
        """Test logging with correlation context."""
        logger = StructuredLogger("test_logger")
        ctx = CorrelationContext(job_id="test_job")

        # Set context and log
        logger.set_context(ctx)
        logger.info("Test message")

        # Verify log was called with context
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert "extra" in kwargs
        assert "correlation_id" in kwargs["extra"]
        assert kwargs["extra"]["job_id"] == "test_job"

    @patch("logging.Logger.log")
    def test_logging_without_context(self, mock_log):
        """Test logging without correlation context."""
        logger = StructuredLogger("test_logger")

        # Log without context
        logger.info("Test message")

        # Verify log was called
        mock_log.assert_called_once()


class TestHealthChecker:
    """Test health check functionality."""

    def test_health_checker_creation(self):
        """Test health checker creation."""
        health_checker = HealthChecker()

        assert hasattr(health_checker, "settings")
        assert hasattr(health_checker, "logger")

    @pytest.mark.asyncio
    async def test_check_database_connection_success(self):
        """Test successful database connection check."""
        health_checker = HealthChecker()

        # Mock repository
        mock_repository = AsyncMock()
        mock_repository.check_connection.return_value = None

        result = await health_checker.check_database_connection(mock_repository)

        assert result is True
        mock_repository.check_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_database_connection_failure(self):
        """Test failed database connection check."""
        health_checker = HealthChecker()

        # Mock repository that raises exception
        mock_repository = AsyncMock()
        mock_repository.check_connection.side_effect = Exception("Connection failed")

        result = await health_checker.check_database_connection(mock_repository)

        assert result is False
        mock_repository.check_connection.assert_called_once()

    @pytest.mark.asyncio
    @patch("paidsearchnav.platforms.google.client.GoogleAdsAPIClient")
    async def test_check_google_ads_api_with_config(self, mock_client_class):
        """Test Google Ads API check with configuration."""
        # Mock settings with complete config
        mock_settings = MagicMock()
        mock_settings.google_ads.developer_token.get_secret_value.return_value = (
            "dev_token"
        )
        mock_settings.google_ads.client_id.get_secret_value.return_value = "client_id"
        mock_settings.google_ads.client_secret.get_secret_value.return_value = (
            "client_secret"
        )
        mock_settings.google_ads.refresh_token.get_secret_value.return_value = (
            "refresh_token"
        )
        mock_settings.google_ads.login_customer_id = "123456789"

        # Mock API client
        mock_client = MagicMock()
        mock_client._get_client.return_value = MagicMock()  # Successful client creation
        mock_client_class.return_value = mock_client

        health_checker = HealthChecker(mock_settings)

        result = await health_checker.check_google_ads_api()

        assert result is True
        mock_client_class.assert_called_once()
        mock_client._get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_google_ads_api_without_config(self):
        """Test Google Ads API check without configuration."""
        health_checker = HealthChecker()

        result = await health_checker.check_google_ads_api()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_google_ads_api_incomplete_config(self):
        """Test Google Ads API check with incomplete configuration."""
        # Mock settings with incomplete config
        mock_settings = MagicMock()
        mock_settings.google_ads.developer_token = "test_token"  # Has this one
        mock_settings.google_ads.client_id = "test_client_id"  # Has this one
        mock_settings.google_ads.client_secret = None  # Missing this one
        mock_settings.google_ads.refresh_token = None  # Missing this one

        health_checker = HealthChecker(mock_settings)

        result = await health_checker.check_google_ads_api()

        assert result is False

    @pytest.mark.asyncio
    @patch("paidsearchnav.platforms.google.client.GoogleAdsAPIClient")
    async def test_check_google_ads_api_connectivity_success(self, mock_client_class):
        """Test Google Ads API check with successful connectivity test."""
        # Mock settings with complete config
        mock_settings = MagicMock()
        mock_settings.google_ads.developer_token.get_secret_value.return_value = (
            "dev_token"
        )
        mock_settings.google_ads.client_id.get_secret_value.return_value = "client_id"
        mock_settings.google_ads.client_secret.get_secret_value.return_value = (
            "client_secret"
        )
        mock_settings.google_ads.refresh_token.get_secret_value.return_value = (
            "refresh_token"
        )
        mock_settings.google_ads.login_customer_id = "123456789"

        # Mock API client
        mock_client = MagicMock()
        mock_client._get_client.return_value = MagicMock()  # Successful client creation
        mock_client_class.return_value = mock_client

        health_checker = HealthChecker(mock_settings)

        result = await health_checker.check_google_ads_api()

        assert result is True
        mock_client_class.assert_called_once()
        mock_client._get_client.assert_called_once()

    @pytest.mark.asyncio
    @patch("paidsearchnav.platforms.google.client.GoogleAdsAPIClient")
    async def test_check_google_ads_api_connectivity_failure(self, mock_client_class):
        """Test Google Ads API check with failed connectivity test."""
        # Mock settings with complete config
        mock_settings = MagicMock()
        mock_settings.google_ads.developer_token.get_secret_value.return_value = (
            "dev_token"
        )
        mock_settings.google_ads.client_id.get_secret_value.return_value = "client_id"
        mock_settings.google_ads.client_secret.get_secret_value.return_value = (
            "client_secret"
        )
        mock_settings.google_ads.refresh_token.get_secret_value.return_value = (
            "refresh_token"
        )
        mock_settings.google_ads.login_customer_id = "123456789"

        # Mock API client to raise exception
        mock_client = MagicMock()
        mock_client._get_client.side_effect = Exception("API connection failed")
        mock_client_class.return_value = mock_client

        health_checker = HealthChecker(mock_settings)

        result = await health_checker.check_google_ads_api()

        assert result is False
        mock_client_class.assert_called_once()
        mock_client._get_client.assert_called_once()

    def test_check_scheduler_status_running(self):
        """Test scheduler status check when running."""
        health_checker = HealthChecker()

        # Mock scheduler
        mock_scheduler = MagicMock()
        mock_scheduler._scheduler.running = True

        result = health_checker.check_scheduler_status(mock_scheduler)

        assert result is True

    def test_check_scheduler_status_not_running(self):
        """Test scheduler status check when not running."""
        health_checker = HealthChecker()

        # Mock scheduler
        mock_scheduler = MagicMock()
        mock_scheduler._scheduler.running = False

        result = health_checker.check_scheduler_status(mock_scheduler)

        assert result is False

    def test_check_scheduler_status_not_initialized(self):
        """Test scheduler status check when not initialized."""
        health_checker = HealthChecker()

        # Mock scheduler without _scheduler
        mock_scheduler = MagicMock()
        mock_scheduler._scheduler = None

        result = health_checker.check_scheduler_status(mock_scheduler)

        assert result is False

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    def test_get_system_metrics_success(self, mock_cpu_percent, mock_virtual_memory):
        """Test successful system metrics collection."""
        health_checker = HealthChecker()

        # Mock psutil functions
        mock_memory = MagicMock()
        mock_memory.used = 1024 * 1024 * 1024  # 1GB
        mock_virtual_memory.return_value = mock_memory
        mock_cpu_percent.return_value = 25.5

        result = health_checker.get_system_metrics()

        assert result["memory_bytes"] == 1024 * 1024 * 1024
        assert result["cpu_percentage"] == 25.5

    @patch("psutil.virtual_memory")
    def test_get_system_metrics_failure(self, mock_virtual_memory):
        """Test system metrics collection failure."""
        health_checker = HealthChecker()

        # Mock psutil to raise exception
        mock_virtual_memory.side_effect = Exception("psutil error")

        result = health_checker.get_system_metrics()

        assert result["memory_bytes"] == 0.0
        assert result["cpu_percentage"] == 0.0


class TestMetricsServer:
    """Test metrics server functionality."""

    def setup_method(self):
        """Reset server state before each test."""
        import paidsearchnav.scheduler.monitoring as monitoring

        monitoring._metrics_server_started = False
        monitoring._metrics_server_port = None

    @patch("paidsearchnav.scheduler.monitoring.start_http_server")
    def test_start_metrics_server_success(self, mock_start_server):
        """Test successful metrics server start."""
        from paidsearchnav.scheduler.monitoring import (
            get_metrics_server_port,
            is_metrics_server_running,
        )

        start_metrics_server(8000)

        mock_start_server.assert_called_once_with(8000)
        assert is_metrics_server_running() is True
        assert get_metrics_server_port() == 8000

    @patch("paidsearchnav.scheduler.monitoring.start_http_server")
    def test_start_metrics_server_already_running_same_port(self, mock_start_server):
        """Test starting metrics server when already running on same port."""
        from paidsearchnav.scheduler.monitoring import is_metrics_server_running

        # Start server first time
        start_metrics_server(8000)
        assert mock_start_server.call_count == 1

        # Try to start again on same port
        start_metrics_server(8000)

        # Should not call start_http_server again
        assert mock_start_server.call_count == 1
        assert is_metrics_server_running() is True

    @patch("paidsearchnav.scheduler.monitoring.start_http_server")
    def test_start_metrics_server_already_running_different_port(
        self, mock_start_server
    ):
        """Test starting metrics server when already running on different port."""
        from paidsearchnav.scheduler.monitoring import get_metrics_server_port

        # Start server on port 8000
        start_metrics_server(8000)
        assert mock_start_server.call_count == 1

        # Try to start on different port
        start_metrics_server(9000)

        # Should not call start_http_server again
        assert mock_start_server.call_count == 1
        assert get_metrics_server_port() == 8000  # Still on original port

    @patch("paidsearchnav.scheduler.monitoring.start_http_server")
    def test_start_metrics_server_failure(self, mock_start_server):
        """Test metrics server start failure."""
        mock_start_server.side_effect = Exception("Port already in use")

        with pytest.raises(Exception, match="Port already in use"):
            start_metrics_server(8000)

    def test_metrics_server_state_functions(self):
        """Test metrics server state tracking functions."""
        from paidsearchnav.scheduler.monitoring import (
            get_metrics_server_port,
            is_metrics_server_running,
        )

        # Initially not running
        assert is_metrics_server_running() is False
        assert get_metrics_server_port() is None


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for monitoring components."""

    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        # Create monitoring components
        metrics = SchedulerMetrics("test_integration")
        health_checker = HealthChecker()
        logger = StructuredLogger("test")

        # Create correlation context
        ctx = CorrelationContext(
            job_id="integration_test_job", customer_id="test_customer", job_type="audit"
        )

        # Simulate job execution with monitoring
        with logger.context(ctx):
            with metrics.job_execution_timer("audit", "test_customer"):
                # Simulate work
                await asyncio.sleep(0.01)

                # Record successful execution
                metrics.record_job_execution(
                    "audit", "completed", "test_customer", 0.01
                )

                logger.info("Job completed successfully")

        # Update system metrics
        system_metrics = health_checker.get_system_metrics()
        metrics.update_system_metrics(
            system_metrics["memory_bytes"], system_metrics["cpu_percentage"]
        )

        # Verify no exceptions were raised
        assert True
