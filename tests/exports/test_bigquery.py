"""Tests for BigQuery export implementation."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from paidsearchnav_mcp.exports.base import (
    ExportConfig,
    ExportConnectionError,
    ExportFormat,
    ExportStatus,
)
from paidsearchnav_mcp.exports.bigquery import BIGQUERY_AVAILABLE, BigQueryExporter

# Import GoogleCloudError for proper exception testing
try:
    from google.cloud.exceptions import GoogleCloudError
except ImportError:
    GoogleCloudError = Exception

# Skip all BigQuery tests if BigQuery is not available
pytestmark = pytest.mark.skipif(
    not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not installed"
)


class TestBigQueryExporter:
    """Test BigQueryExporter class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock BigQuery config."""
        return ExportConfig(
            destination_type=ExportFormat.BIGQUERY,
            credentials={
                "service_account_json": json.dumps(
                    {
                        "type": "service_account",
                        "project_id": "test-project",
                        "private_key_id": "key123",
                        "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                        "client_email": "test@test-project.iam.gserviceaccount.com",
                        "client_id": "123456789",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                )
            },
            project_id="test-project",
            dataset="test_dataset",
        )

    @pytest.fixture
    def exporter(self, mock_config):
        """Create BigQuery exporter instance."""
        return BigQueryExporter(mock_config)

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, exporter):
        """Test successful connection validation."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation
        mock_client.get_dataset.return_value = mock_dataset

        # Mock the table() method on dataset_ref
        mock_table_ref = MagicMock()
        mock_dataset.table.return_value = mock_table_ref

        mock_table = MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_client.delete_table.return_value = None

        # Test validation
        result = await exporter.validate_connection()

        assert result is True
        mock_client.get_dataset.assert_called_once()
        mock_client.create_table.assert_called_once()
        mock_client.delete_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, exporter):
        """Test connection validation failure."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        # Setup dataset mock that will raise exception
        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset

        # Make get_dataset raise GoogleCloudError
        mock_client.get_dataset.side_effect = GoogleCloudError("Access denied")

        # Test validation
        with pytest.raises(ExportConnectionError) as exc_info:
            await exporter.validate_connection()

        assert "Failed to connect to BigQuery" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_export_audit_results(self, exporter):
        """Test exporting audit results."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation

        # Mock the table() method on dataset_ref
        mock_table_ref = MagicMock()
        mock_dataset.table.return_value = mock_table_ref

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table
        mock_client.insert_rows_json.return_value = []  # No errors

        # Test data
        audit_data = [
            {
                "audit_id": "audit-123",
                "audit_date": "2024-01-15",
                "analyzer_name": "keyword_analyzer",
                "keywords_analyzed": 500,
                "issues_found": 10,
                "cost_savings": 1500.0,
                "created_at": datetime.utcnow().isoformat(),
            }
        ]

        # Export data
        result = await exporter.export_audit_results("customer123", audit_data)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 1
        assert result.destination == ExportFormat.BIGQUERY
        assert "table" in result.metadata
        assert result.error_message is None

        # Verify insert was called
        mock_client.insert_rows_json.assert_called_once()
        call_args = mock_client.insert_rows_json.call_args
        assert call_args[0][0] == mock_table  # First arg is table
        assert len(call_args[0][1]) == 1  # Second arg is rows list

    @pytest.mark.asyncio
    async def test_export_audit_results_with_errors(self, exporter):
        """Test exporting audit results with insert errors."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation

        # Mock the table() method on dataset_ref
        mock_table_ref = MagicMock()
        mock_dataset.table.return_value = mock_table_ref

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table
        mock_client.insert_rows_json.return_value = [
            {"errors": [{"message": "Invalid row"}]}
        ]

        # Test data - needs to pass validation but fail on insert
        audit_data = [{"audit_id": "invalid", "audit_date": "2024-01-15"}]

        # Export data
        result = await exporter.export_audit_results("customer123", audit_data)

        assert result.status == ExportStatus.FAILED
        assert result.records_exported == 0
        assert "Failed to insert" in result.error_message

    @pytest.mark.asyncio
    async def test_export_recommendations(self, exporter):
        """Test exporting recommendations."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation

        # Mock the table() method on dataset_ref
        mock_table_ref = MagicMock()
        mock_dataset.table.return_value = mock_table_ref

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table
        mock_client.insert_rows_json.return_value = []  # No errors

        # Test data
        recommendations = [
            {
                "recommendation_id": "rec-123",
                "audit_id": "audit-123",
                "type": "negative_keyword",
                "priority": "high",
                "title": "Add negative keywords",
                "description": "Reduce wasted spend",
                "estimated_impact": 1000.0,
                "metadata": {"keywords": ["free", "cheap"]},
                "created_at": datetime.utcnow().isoformat(),
            }
        ]

        # Export data
        result = await exporter.export_recommendations("customer123", recommendations)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 1
        assert result.destination == ExportFormat.BIGQUERY
        assert "recommendations" in result.metadata["table"]

    @pytest.mark.asyncio
    async def test_export_metrics(self, exporter):
        """Test exporting metrics."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation

        # Mock the table() method on dataset_ref
        mock_table_ref = MagicMock()
        mock_dataset.table.return_value = mock_table_ref

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table
        mock_client.insert_rows_json.return_value = []  # No errors

        # Test data
        metrics = [
            {
                "metric_name": "total_spend",
                "metric_value": 5000.0,
                "metric_type": "currency",
                "dimensions": {"campaign": "Summer Sale"},
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "metric_name": "conversions",
                "metric_value": 150,
                "metric_type": "count",
                "dimensions": {"campaign": "Summer Sale"},
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        # Export data
        result = await exporter.export_metrics("customer123", metrics)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 2
        assert result.destination == ExportFormat.BIGQUERY
        assert "metrics" in result.metadata["table"]

    @pytest.mark.asyncio
    async def test_table_creation(self, exporter):
        """Test table creation when table doesn't exist."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = (
            mock_client  # Set the client directly to bypass credential validation
        )
        exporter._validated_credentials = True  # Mark credentials as validated

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        exporter.dataset_ref = mock_dataset  # Set dataset_ref to bypass creation

        # First call to get_table raises exception (table doesn't exist)
        mock_client.get_table.side_effect = GoogleCloudError("Table not found")

        mock_table = MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_client.insert_rows_json.return_value = []

        # Export data
        result = await exporter.export_audit_results("customer123", [{"audit_id": "1"}])

        # Verify table was created
        mock_client.create_table.assert_called_once()
        create_call = mock_client.create_table.call_args[0][0]

        # Check that partitioning was set
        assert hasattr(create_call, "time_partitioning")

    @pytest.mark.asyncio
    async def test_check_export_status(self, exporter):
        """Test checking export status."""
        result = await exporter.check_export_status("export-123")

        assert result.export_id == "export-123"
        assert result.status == ExportStatus.COMPLETED
        assert result.destination == ExportFormat.BIGQUERY
        assert "synchronous" in result.metadata["message"]

    def test_get_schemas(self, exporter):
        """Test schema generation methods."""
        # Test audit results schema
        audit_schema = exporter._get_audit_results_schema()
        field_names = [field.name for field in audit_schema]
        assert "audit_id" in field_names
        assert "customer_id" in field_names
        assert "metrics" in field_names

        # Test recommendations schema
        rec_schema = exporter._get_recommendations_schema()
        field_names = [field.name for field in rec_schema]
        assert "recommendation_id" in field_names
        assert "audit_id" in field_names
        assert "metadata" in field_names

        # Test metrics schema
        metrics_schema = exporter._get_metrics_schema()
        field_names = [field.name for field in metrics_schema]
        assert "metric_id" in field_names
        assert "metric_name" in field_names
        assert "dimensions" in field_names
