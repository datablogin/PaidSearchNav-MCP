"""Tests for BigQuery exporter circuit breaker integration."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav_mcp.core.config import CircuitBreakerConfig
from paidsearchnav_mcp.exports.base import ExportConfig, ExportFormat, ExportStatus
from paidsearchnav_mcp.exports.bigquery import BigQueryExporter


@pytest.fixture
def export_config():
    """Create test export configuration."""
    return ExportConfig(
        destination_type=ExportFormat.BIGQUERY,
        project_id="test-project",
        dataset="test_dataset",
        credentials={
            "service_account_json": '{"type":"service_account","project_id":"test"}'
        },
    )


@pytest.fixture
def circuit_breaker_config():
    """Create test circuit breaker configuration."""
    return CircuitBreakerConfig(
        enabled=True,
        failure_threshold=2,
        recovery_timeout=30,
    )


class TestBigQueryExporterCircuitBreaker:
    """Test BigQuery exporter with circuit breaker integration."""

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_exporter_initialization_with_circuit_breaker(
        self, export_config, circuit_breaker_config
    ):
        """Test BigQuery exporter initializes with circuit breaker."""
        exporter = BigQueryExporter(export_config, circuit_breaker_config)

        assert exporter.circuit_breaker is not None
        assert exporter.retry_handler is not None
        assert exporter._circuit_breaker_config == circuit_breaker_config
        assert exporter.circuit_breaker.config == circuit_breaker_config

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_should_use_csv_fallback_when_circuit_open(self, export_config):
        """Test CSV fallback detection when circuit breaker is open."""
        circuit_config = CircuitBreakerConfig(enabled=True, failure_threshold=1)
        exporter = BigQueryExporter(export_config, circuit_config)

        # Initially circuit should be closed
        assert exporter.should_use_csv_fallback is False
        assert exporter.is_circuit_breaker_open is False

        # Simulate circuit breaker opening
        exporter.circuit_breaker._breaker._state = "open"

        assert exporter.should_use_csv_fallback is True
        assert exporter.is_circuit_breaker_open is True

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", False)
    def test_should_use_csv_fallback_when_bigquery_unavailable(self, export_config):
        """Test CSV fallback when BigQuery is not available."""
        with pytest.raises(ImportError):
            BigQueryExporter(export_config)

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_get_csv_fallback_exporter(self, export_config):
        """Test CSV fallback exporter creation."""
        exporter = BigQueryExporter(export_config)

        # Initially should be None
        assert exporter._csv_fallback_exporter is None

        # Should create CSV exporter when requested
        csv_exporter = exporter._get_csv_fallback_exporter()

        assert csv_exporter is not None
        assert exporter._csv_fallback_exporter == csv_exporter

        # Should return same instance on subsequent calls
        csv_exporter2 = exporter._get_csv_fallback_exporter()
        assert csv_exporter2 == csv_exporter

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_validate_connection_with_circuit_breaker_open(self, export_config):
        """Test connection validation skips when circuit breaker is open."""
        exporter = BigQueryExporter(export_config)

        # Force circuit breaker to open state
        exporter.circuit_breaker._breaker._state = "open"

        result = await exporter.validate_connection()

        # Should return True (skip validation) when circuit is open
        assert result is True

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @patch("paidsearchnav.exports.bigquery.bigquery")
    @pytest.mark.asyncio
    async def test_export_audit_results_csv_fallback_when_circuit_open(
        self, mock_bigquery, export_config
    ):
        """Test audit results export falls back to CSV when circuit is open."""
        exporter = BigQueryExporter(export_config)

        # Mock CSV fallback exporter
        mock_csv_exporter = Mock()
        mock_csv_result = Mock()
        mock_csv_result.status = ExportStatus.COMPLETED
        mock_csv_result.records_exported = 10
        mock_csv_result.completed_at = datetime.now(timezone.utc)
        mock_csv_result.metadata = {"csv_export": True}
        mock_csv_exporter.export_batch = AsyncMock(return_value=mock_csv_result)
        exporter._csv_fallback_exporter = mock_csv_exporter

        # Force circuit breaker to open state
        exporter.circuit_breaker._breaker._state = "open"

        # Test data
        audit_data = [
            {"audit_id": "test1", "audit_date": "2023-01-01", "analyzer_name": "test"}
        ]

        result = await exporter.export_audit_results("customer123", audit_data)

        # Should use CSV fallback
        assert result.destination == ExportFormat.CSV
        assert result.status == ExportStatus.COMPLETED
        assert "fallback_reason" in result.metadata
        assert result.metadata["fallback_reason"] == "BigQuery circuit breaker open"
        assert "original_destination" in result.metadata
        assert result.metadata["original_destination"] == "BigQuery"

        # CSV exporter should have been called
        mock_csv_exporter.export_batch.assert_called_once()

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @patch("paidsearchnav.exports.bigquery.bigquery")
    @pytest.mark.asyncio
    async def test_export_audit_results_fallback_on_bigquery_failure(
        self, mock_bigquery, export_config
    ):
        """Test audit results export falls back to CSV on BigQuery failure."""
        exporter = BigQueryExporter(export_config)

        # Mock BigQuery to fail
        mock_client = Mock()
        mock_bigquery.Client.return_value = mock_client
        exporter.client = mock_client

        # Mock the ensure table exists method to fail
        def failing_ensure_table(*args, **kwargs):
            from google.cloud.exceptions import GoogleCloudError

            raise GoogleCloudError("BigQuery service unavailable")

        exporter._ensure_table_exists = failing_ensure_table

        # Mock CSV fallback exporter
        mock_csv_exporter = Mock()
        mock_csv_result = Mock()
        mock_csv_result.status = ExportStatus.COMPLETED
        mock_csv_result.records_exported = 10
        mock_csv_result.completed_at = datetime.now(timezone.utc)
        mock_csv_result.metadata = {"csv_export": True}
        mock_csv_exporter.export_batch = AsyncMock(return_value=mock_csv_result)
        exporter._csv_fallback_exporter = mock_csv_exporter

        # Test data
        audit_data = [
            {"audit_id": "test1", "audit_date": "2023-01-01", "analyzer_name": "test"}
        ]

        result = await exporter.export_audit_results("customer123", audit_data)

        # Should fallback to CSV after BigQuery failure
        assert result.destination == ExportFormat.CSV
        assert result.status == ExportStatus.COMPLETED
        assert "fallback_reason" in result.metadata

        # CSV exporter should have been called
        mock_csv_exporter.export_batch.assert_called_once()

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_get_circuit_breaker_health(self, export_config):
        """Test circuit breaker health information."""
        exporter = BigQueryExporter(export_config)

        health_info = exporter.get_circuit_breaker_health()

        assert "service" in health_info
        assert health_info["service"] == "BigQuery"
        assert "state" in health_info
        assert "is_healthy" in health_info
        assert "failure_rate" in health_info
        assert "error_breakdown" in health_info

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_get_retry_metrics(self, export_config):
        """Test retry handler metrics."""
        exporter = BigQueryExporter(export_config)

        metrics = exporter.get_retry_metrics()

        assert "total_retries" in metrics
        assert "successful_retries" in metrics
        assert "failed_retries" in metrics
        assert "retry_config" in metrics

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    def test_get_service_health(self, export_config):
        """Test comprehensive service health information."""
        exporter = BigQueryExporter(export_config)

        health_info = exporter.get_service_health()

        assert "timestamp" in health_info
        assert "bigquery" in health_info
        assert "csv_fallback" in health_info
        assert "configuration" in health_info

        bigquery_info = health_info["bigquery"]
        assert "available" in bigquery_info
        assert "circuit_breaker" in bigquery_info
        assert "retry_handler" in bigquery_info

        csv_info = health_info["csv_fallback"]
        assert "enabled" in csv_info
        assert "exporter_initialized" in csv_info

        config_info = health_info["configuration"]
        assert "batch_size" in config_info
        assert "circuit_breaker_enabled" in config_info

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_health_check_when_circuit_open(self, export_config):
        """Test health check when circuit breaker is open."""
        exporter = BigQueryExporter(export_config)

        # Force circuit breaker to open state
        exporter.circuit_breaker._breaker._state = "open"

        health_info = await exporter.health_check()

        assert health_info["service"] == "BigQuery Export"
        assert health_info["status"] == "degraded"
        assert "BigQuery circuit breaker open" in health_info["message"]
        assert health_info["fallback_available"] is True
        assert "circuit_breaker" in health_info

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_health_check_when_healthy(self, export_config):
        """Test health check when service is healthy."""
        exporter = BigQueryExporter(export_config)

        # Mock validate_connection to return True
        exporter.validate_connection = AsyncMock(return_value=True)

        health_info = await exporter.health_check()

        assert health_info["service"] == "BigQuery Export"
        assert health_info["status"] == "healthy"
        assert "successfully" in health_info["message"].lower()
        assert "circuit_breaker" in health_info
        assert "retry_metrics" in health_info

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_health_check_when_validation_fails(self, export_config):
        """Test health check when validation fails."""
        exporter = BigQueryExporter(export_config)

        # Mock validate_connection to raise exception
        exporter.validate_connection = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        health_info = await exporter.health_check()

        assert health_info["service"] == "BigQuery Export"
        assert health_info["status"] == "unhealthy"
        assert "Health check failed" in health_info["message"]
        assert "error" in health_info
        assert "circuit_breaker" in health_info

    @patch("paidsearchnav.exports.bigquery.BIGQUERY_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_csv_fallback_export_failure(self, export_config):
        """Test behavior when both BigQuery and CSV fallback fail."""
        exporter = BigQueryExporter(export_config)

        # Force circuit breaker to open state
        exporter.circuit_breaker._breaker._state = "open"

        # Mock CSV fallback to fail
        exporter._get_csv_fallback_exporter = Mock(
            side_effect=Exception("CSV setup failed")
        )

        # Test data
        audit_data = [{"audit_id": "test1", "audit_date": "2023-01-01"}]

        result = await exporter._export_audit_results_to_csv(
            "customer123", audit_data, None, "export123", datetime.now(timezone.utc)
        )

        assert result.status == ExportStatus.FAILED
        assert result.destination == ExportFormat.CSV
        assert "CSV fallback failed" in result.error_message
