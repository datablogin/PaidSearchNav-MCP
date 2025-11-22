"""Tests for base export classes."""

from datetime import datetime

import pytest

from paidsearchnav_mcp.exports.base import (
    ExportConfig,
    ExportConnectionError,
    ExportDestination,
    ExportError,
    ExportFormat,
    ExportRequest,
    ExportResult,
    ExportStatus,
    ExportTimeoutError,
    ExportValidationError,
)


class TestExportConfig:
    """Test ExportConfig dataclass."""

    def test_create_bigquery_config(self):
        """Test creating BigQuery export config."""
        config = ExportConfig(
            destination_type=ExportFormat.BIGQUERY,
            credentials={"service_account_json": "{}"},
            project_id="test-project",
            dataset="test_dataset",
            schedule="0 */6 * * *",
            enabled=True,
        )

        assert config.destination_type == ExportFormat.BIGQUERY
        assert config.project_id == "test-project"
        assert config.dataset == "test_dataset"
        assert config.schedule == "0 */6 * * *"
        assert config.enabled is True

    def test_create_snowflake_config(self):
        """Test creating Snowflake export config."""
        config = ExportConfig(
            destination_type=ExportFormat.SNOWFLAKE,
            credentials={"username": "test", "password": "test"},
            account="test.us-east-1",
            warehouse="COMPUTE_WH",
            database="ANALYTICS",
            schema="PUBLIC",
        )

        assert config.destination_type == ExportFormat.SNOWFLAKE
        assert config.account == "test.us-east-1"
        assert config.warehouse == "COMPUTE_WH"
        assert config.database == "ANALYTICS"
        assert config.schema == "PUBLIC"

    def test_create_file_export_config(self):
        """Test creating file export config."""
        config = ExportConfig(
            destination_type=ExportFormat.PARQUET,
            credentials={},
            output_path="s3://bucket/path",
            compression="snappy",
        )

        assert config.destination_type == ExportFormat.PARQUET
        assert config.output_path == "s3://bucket/path"
        assert config.compression == "snappy"


class TestExportRequest:
    """Test ExportRequest dataclass."""

    def test_create_request_with_defaults(self):
        """Test creating export request with defaults."""
        request = ExportRequest(customer_id="123456")

        assert request.customer_id == "123456"
        assert request.destination == ExportFormat.BIGQUERY
        assert request.include_historical is False
        assert request.date_range is None
        assert request.export_id  # Should have UUID
        assert isinstance(request.requested_at, datetime)

    def test_create_request_with_date_range(self):
        """Test creating export request with date range."""
        request = ExportRequest(
            customer_id="123456",
            destination=ExportFormat.SNOWFLAKE,
            date_range={"start": "2024-01-01", "end": "2024-01-31"},
            include_historical=True,
            requested_by="user123",
        )

        assert request.customer_id == "123456"
        assert request.destination == ExportFormat.SNOWFLAKE
        assert request.date_range == {"start": "2024-01-01", "end": "2024-01-31"}
        assert request.include_historical is True
        assert request.requested_by == "user123"


class TestExportResult:
    """Test ExportResult dataclass."""

    def test_create_successful_result(self):
        """Test creating successful export result."""
        started = datetime.utcnow()
        completed = datetime.utcnow()

        result = ExportResult(
            export_id="test-123",
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=1000,
            files_created=["table1", "table2"],
            started_at=started,
            completed_at=completed,
        )

        assert result.export_id == "test-123"
        assert result.status == ExportStatus.COMPLETED
        assert result.destination == ExportFormat.BIGQUERY
        assert result.records_exported == 1000
        assert result.files_created == ["table1", "table2"]
        assert result.error_message is None
        assert result.duration_seconds is not None

    def test_create_failed_result(self):
        """Test creating failed export result."""
        result = ExportResult(
            export_id="test-456",
            status=ExportStatus.FAILED,
            destination=ExportFormat.SNOWFLAKE,
            error_message="Connection timeout",
        )

        assert result.export_id == "test-456"
        assert result.status == ExportStatus.FAILED
        assert result.destination == ExportFormat.SNOWFLAKE
        assert result.error_message == "Connection timeout"
        assert result.records_exported == 0
        assert result.duration_seconds is None


class MockExportDestination(ExportDestination):
    """Mock implementation of ExportDestination for testing."""

    async def validate_connection(self) -> bool:
        return True

    async def export_audit_results(self, customer_id, audit_data, metadata=None):
        return ExportResult(
            export_id="mock-audit",
            status=ExportStatus.COMPLETED,
            destination=self.config.destination_type,
            records_exported=len(audit_data),
        )

    async def export_recommendations(self, customer_id, recommendations, metadata=None):
        return ExportResult(
            export_id="mock-recs",
            status=ExportStatus.COMPLETED,
            destination=self.config.destination_type,
            records_exported=len(recommendations),
        )

    async def export_metrics(self, customer_id, metrics, metadata=None):
        return ExportResult(
            export_id="mock-metrics",
            status=ExportStatus.COMPLETED,
            destination=self.config.destination_type,
            records_exported=len(metrics),
        )

    async def check_export_status(self, export_id):
        return ExportResult(
            export_id=export_id,
            status=ExportStatus.COMPLETED,
            destination=self.config.destination_type,
        )


class TestExportDestination:
    """Test ExportDestination abstract base class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock export config."""
        return ExportConfig(destination_type=ExportFormat.BIGQUERY, credentials={})

    @pytest.fixture
    def mock_destination(self, mock_config):
        """Create mock export destination."""
        return MockExportDestination(mock_config)

    @pytest.mark.asyncio
    async def test_export_batch_all_types(self, mock_destination):
        """Test exporting batch with all data types."""
        data = {
            "audit_results": [{"id": "1"}, {"id": "2"}],
            "recommendations": [{"id": "r1"}],
            "metrics": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        }

        result = await mock_destination.export_batch("customer123", data)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 6  # 2 + 1 + 3
        assert len(result.files_created) == 0  # Mock doesn't create files

    @pytest.mark.asyncio
    async def test_export_batch_partial_data(self, mock_destination):
        """Test exporting batch with partial data."""
        data = {"audit_results": [{"id": "1"}], "metrics": [{"id": "m1"}]}

        result = await mock_destination.export_batch("customer123", data)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 2

    @pytest.mark.asyncio
    async def test_export_batch_empty_data(self, mock_destination):
        """Test exporting batch with empty data."""
        data = {}

        result = await mock_destination.export_batch("customer123", data)

        # Should handle empty data gracefully
        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 0


class TestExportExceptions:
    """Test export exception classes."""

    def test_export_error_hierarchy(self):
        """Test exception hierarchy."""
        assert issubclass(ExportConnectionError, ExportError)
        assert issubclass(ExportValidationError, ExportError)
        assert issubclass(ExportTimeoutError, ExportError)

    def test_raise_connection_error(self):
        """Test raising connection error."""
        with pytest.raises(ExportConnectionError) as exc_info:
            raise ExportConnectionError("Failed to connect")

        assert "Failed to connect" in str(exc_info.value)

    def test_raise_validation_error(self):
        """Test raising validation error."""
        with pytest.raises(ExportValidationError) as exc_info:
            raise ExportValidationError("Invalid data format")

        assert "Invalid data format" in str(exc_info.value)

    def test_raise_timeout_error(self):
        """Test raising timeout error."""
        with pytest.raises(ExportTimeoutError) as exc_info:
            raise ExportTimeoutError("Export timed out after 300s")

        assert "Export timed out after 300s" in str(exc_info.value)
