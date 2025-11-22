"""Tests for monitoring and observability components."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    TracerProvider = None
    SimpleSpanProcessor = None
    InMemorySpanExporter = None

from paidsearchnav_mcp.api.monitoring import TracingConfig, setup_tracing
from paidsearchnav_mcp.api.monitoring.health import HealthChecker
from paidsearchnav_mcp.api.monitoring.metrics import get_metrics_collector


@pytest.fixture
def metrics_collector():
    """Get the metrics collector instance."""
    return get_metrics_collector()


@pytest.fixture
def in_memory_exporter():
    """Create an in-memory span exporter for testing."""
    if OPENTELEMETRY_AVAILABLE:
        return InMemorySpanExporter()
    return None


@pytest.fixture
def tracer_provider(in_memory_exporter):
    """Create a tracer provider with in-memory exporter."""
    if OPENTELEMETRY_AVAILABLE and in_memory_exporter:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(in_memory_exporter))
        trace.set_tracer_provider(provider)
        return provider
    return None


class TestMetricsCollector:
    """Test the metrics collector."""

    def test_record_request(self, metrics_collector):
        """Test recording request metrics."""
        # Record a request
        metrics_collector.record_request(
            method="GET",
            endpoint="/api/v1/health",
            status_code=200,
            duration=0.123,
            request_size=100,
            response_size=250,
        )

        # Verify metrics were recorded
        # Note: In a real test, we'd query Prometheus metrics
        assert metrics_collector.request_count._metrics
        assert metrics_collector.request_duration._metrics

    def test_record_auth_metrics(self, metrics_collector):
        """Test recording authentication metrics."""
        # Record successful auth
        metrics_collector.record_auth_attempt("password", success=True)

        # Record failed auth
        metrics_collector.record_auth_attempt("password", success=False)
        metrics_collector.record_auth_failure("invalid_credentials")

        # Verify metrics were recorded
        assert metrics_collector.auth_attempts._metrics
        assert metrics_collector.auth_failures._metrics

    def test_record_business_metrics(self, metrics_collector):
        """Test recording business metrics."""
        # Record audit creation
        metrics_collector.record_audit_created("customer-123", "keyword_audit")

        # Record audit completion
        metrics_collector.record_audit_completed(
            "customer-123", "keyword_audit", "success", 120.5
        )

        # Record keywords processed
        metrics_collector.record_keywords_processed("customer-123", "audit-456", 1500)

        # Record issues found
        metrics_collector.record_issue_found("customer-123", "negative_conflict")

        # Verify metrics were recorded
        assert metrics_collector.audits_created._metrics
        assert metrics_collector.audits_completed._metrics
        assert metrics_collector.keywords_processed._metrics
        assert metrics_collector.issues_found._metrics

    def test_record_cache_metrics(self, metrics_collector):
        """Test recording cache metrics."""
        # Record cache operations
        metrics_collector.record_cache_hit("redis", "audit:*")
        metrics_collector.record_cache_miss("redis", "audit:*")

        # Verify metrics were recorded
        assert metrics_collector.cache_hits._metrics
        assert metrics_collector.cache_misses._metrics


class TestTracing:
    """Test OpenTelemetry tracing."""

    @pytest.mark.skipif(
        not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed"
    )
    def test_setup_tracing_enabled(self, in_memory_exporter):
        """Test setting up tracing when enabled."""
        config = TracingConfig(
            enabled=True,
            service_name="test-service",
            console_export=False,
        )

        provider = setup_tracing(config)
        assert provider is not None

        # Create a test span
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test", True)

        # Verify span was created
        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) >= 1
        assert spans[-1].name == "test_span"
        assert spans[-1].attributes["test"] is True

    def test_setup_tracing_disabled(self):
        """Test setting up tracing when disabled."""
        config = TracingConfig(enabled=False)
        provider = setup_tracing(config)
        assert provider is None


class TestCorrelationID:
    """Test correlation ID middleware."""

    @pytest.mark.asyncio
    async def test_correlation_id_middleware(self, async_client):
        """Test correlation ID is added to requests."""
        correlation_id = "test-correlation-id-123"

        # Make request with correlation ID
        response = await async_client.get(
            "/api/v1/health", headers={"X-Correlation-ID": correlation_id}
        )

        # Verify correlation ID in response
        assert response.headers.get("X-Correlation-ID") == correlation_id

    @pytest.mark.asyncio
    async def test_correlation_id_generated(self, async_client):
        """Test correlation ID is generated if not provided."""
        # Make request without correlation ID
        response = await async_client.get("/api/v1/health")

        # Verify correlation ID was generated
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert len(correlation_id) == 36  # UUID format


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self, async_client):
        """Test comprehensive health check endpoint."""
        response = await async_client.get("/api/v1/health/full")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "components" in data
        assert "system_resources" in data

        # Check component structure
        for component in data["components"]:
            assert "name" in component
            assert "status" in component
            assert component["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_liveness_probe(self, async_client):
        """Test Kubernetes liveness probe."""
        response = await async_client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_probe(self, async_client):
        """Test Kubernetes readiness probe."""
        response = await async_client.get("/api/v1/health/ready")
        # May be 200 or 503 depending on database state
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_health_checker_components(self, mock_settings):
        """Test individual health check components."""
        checker = HealthChecker(mock_settings)

        # Test database check with proper session mock
        mock_repo = AsyncMock()
        mock_repo.check_connection = AsyncMock()

        # Mock the session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=1))
        )
        mock_repo.session = MagicMock(return_value=mock_session)

        health = await checker.check_database(mock_repo)
        assert health.name == "database"
        assert health.status == "healthy"

        # Test failed database check
        mock_repo.check_connection = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        health = await checker.check_database(mock_repo)
        assert health.status == "unhealthy"
        assert "Connection failed" in health.error


class TestMonitoringEndpoints:
    """Test monitoring-specific endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, async_client):
        """Test Prometheus metrics endpoint."""
        response = await async_client.get("/metrics")
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/plain; version=0.0.4; charset=utf-8"
        )

        # Verify some metrics are present
        content = response.text
        assert "api_requests_total" in content
        assert "api_request_duration_seconds" in content

    @pytest.mark.asyncio
    async def test_trace_status_endpoint(self, async_client):
        """Test trace status endpoint."""
        response = await async_client.get("/api/v1/trace/status")
        assert response.status_code == 200

        data = response.json()
        assert "enabled" in data
        assert "service_name" in data

        # When OpenTelemetry is not installed, we get an error field instead
        if not data["enabled"]:
            assert "error" in data
        else:
            assert "tracer_provider" in data
            assert "instrumented_libraries" in data

    @pytest.mark.asyncio
    async def test_correlation_test_endpoint(self, async_client):
        """Test correlation ID test endpoint."""
        correlation_id = "test-correlation-456"
        response = await async_client.post(
            "/api/v1/debug/correlation-test",
            headers={"X-Correlation-ID": correlation_id},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["correlation_id"] == correlation_id
        assert "trace_id" in data
        assert "span_id" in data

        # When OpenTelemetry is not installed, trace/span IDs will be "not_available"
        if "error" in data:
            assert data["trace_id"] == "not_available"
            assert data["span_id"] == "not_available"


class TestStructuredLogging:
    """Test structured logging functionality."""

    def test_log_format(self, caplog):
        """Test that logs are structured with correlation ID."""
        from paidsearchnav.api.monitoring.correlation import (
            CorrelationIDFilter,
            correlation_id_var,
        )

        # Set up correlation ID
        test_correlation_id = "test-log-correlation-789"
        correlation_id_var.set(test_correlation_id)

        # Create logger with filter
        logger = logging.getLogger("test_logger")
        filter = CorrelationIDFilter()
        logger.addFilter(filter)

        # Log a message
        with caplog.at_level(logging.INFO):
            logger.info("Test log message")

        # Verify correlation ID was added
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == test_correlation_id


class TestMetricsMiddleware:
    """Test metrics middleware."""

    @pytest.mark.asyncio
    async def test_metrics_middleware_records_requests(self, async_client):
        """Test that middleware records request metrics."""
        # Make several requests
        await async_client.get("/api/v1/health")
        await async_client.post("/api/v1/audits", json={"test": "data"})
        await async_client.get("/api/v1/health", headers={"X-Test": "value"})

        # Verify metrics were recorded
        # Note: In integration tests, we'd query actual Prometheus metrics


@pytest.mark.asyncio
async def test_monitoring_integration(async_client):
    """Integration test for monitoring features."""
    # Make request with correlation ID
    correlation_id = "integration-test-123"
    response = await async_client.get(
        "/api/v1/health/full", headers={"X-Correlation-ID": correlation_id}
    )

    # Verify response
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == correlation_id

    # Verify health data
    data = response.json()
    assert data["status"] in ["healthy", "degraded", "unhealthy"]

    # Check metrics endpoint
    metrics_response = await async_client.get("/metrics")
    assert metrics_response.status_code == 200

    # Verify request was counted in metrics
    metrics_text = metrics_response.text
    assert "api_requests_total" in metrics_text
