"""Tests for export manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.exports.base import (
    ExportConfig,
    ExportError,
    ExportFormat,
    ExportRequest,
    ExportResult,
    ExportStatus,
)
from paidsearchnav.exports.config import ExportConfigManager
from paidsearchnav.exports.manager import ExportManager


class TestExportManager:
    """Test ExportManager class."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager."""
        manager = MagicMock(spec=ExportConfigManager)
        manager.get_enabled_configs.return_value = [
            ExportConfig(
                destination_type=ExportFormat.BIGQUERY,
                credentials={"test": "creds"},
                project_id="test-project",
                dataset="test_dataset",
            )
        ]
        return manager

    @pytest.fixture
    def export_manager(self, mock_config_manager):
        """Create export manager instance."""
        return ExportManager(config_manager=mock_config_manager)

    @pytest.mark.asyncio
    async def test_validate_all_connections(self, export_manager, mock_config_manager):
        """Test validating all connections."""
        # Mock exporter
        mock_exporter = AsyncMock()
        mock_exporter.validate_connection.return_value = True

        with patch.object(export_manager, "_get_exporter", return_value=mock_exporter):
            results = await export_manager.validate_all_connections("customer123")

        assert results[ExportFormat.BIGQUERY.value] is True
        mock_exporter.validate_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_connections_with_failure(
        self, export_manager, mock_config_manager
    ):
        """Test validating connections with failure."""
        # Mock exporter that fails
        mock_exporter = AsyncMock()
        mock_exporter.validate_connection.side_effect = Exception("Connection failed")

        with patch.object(export_manager, "_get_exporter", return_value=mock_exporter):
            results = await export_manager.validate_all_connections("customer123")

        assert results[ExportFormat.BIGQUERY.value] is False

    @pytest.mark.asyncio
    async def test_export_data(self, export_manager, mock_config_manager):
        """Test exporting data."""
        # Setup test data
        request = ExportRequest(
            customer_id="customer123", destination=ExportFormat.BIGQUERY
        )

        data = {"audit_results": [{"id": "1"}], "recommendations": [{"id": "r1"}]}

        # Mock exporter
        mock_exporter = AsyncMock()
        mock_result = ExportResult(
            export_id=request.export_id,
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=2,
        )
        mock_exporter.export_batch.return_value = mock_result

        with patch.object(export_manager, "_get_exporter", return_value=mock_exporter):
            results = await export_manager.export_data(request, data)

        assert len(results) == 1
        assert results[0].status == ExportStatus.COMPLETED
        assert results[0].records_exported == 2

        # Verify request was tracked
        assert request.export_id not in export_manager.active_exports

    @pytest.mark.asyncio
    async def test_export_data_with_multiple_destinations(
        self, export_manager, mock_config_manager
    ):
        """Test exporting to multiple destinations."""
        # Configure multiple destinations
        mock_config_manager.get_enabled_configs.return_value = [
            ExportConfig(
                destination_type=ExportFormat.BIGQUERY,
                credentials={"test": "creds"},
                project_id="test-project",
                dataset="test_dataset",
            ),
            ExportConfig(
                destination_type=ExportFormat.PARQUET,
                credentials={},
                output_path="/tmp/exports",
            ),
        ]

        request = ExportRequest(
            customer_id="customer123",
            destination=None,  # Export to all
        )

        data = {"audit_results": [{"id": "1"}]}

        # Mock exporters
        mock_bq_exporter = AsyncMock()
        mock_bq_exporter.export_batch.return_value = ExportResult(
            export_id=request.export_id,
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=1,
        )

        mock_parquet_exporter = AsyncMock()
        mock_parquet_exporter.export_batch.return_value = ExportResult(
            export_id=request.export_id,
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.PARQUET,
            records_exported=1,
        )

        def get_exporter_side_effect(config):
            if config.destination_type == ExportFormat.BIGQUERY:
                return mock_bq_exporter
            return mock_parquet_exporter

        with patch.object(
            export_manager, "_get_exporter", side_effect=get_exporter_side_effect
        ):
            results = await export_manager.export_data(request, data)

        assert len(results) == 2
        assert all(r.status == ExportStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_export_data_with_failure(self, export_manager, mock_config_manager):
        """Test export with failure handling."""
        request = ExportRequest(customer_id="customer123")
        data = {"audit_results": [{"id": "1"}]}

        # Mock exporter that fails
        mock_exporter = AsyncMock()
        mock_exporter.export_batch.side_effect = ExportError("Export failed")

        with patch.object(export_manager, "_get_exporter", return_value=mock_exporter):
            results = await export_manager.export_data(request, data)

        assert len(results) == 1
        assert results[0].status == ExportStatus.FAILED
        assert "Export failed" in results[0].error_message

    @pytest.mark.asyncio
    async def test_export_data_no_configs(self, export_manager, mock_config_manager):
        """Test export with no configurations."""
        mock_config_manager.get_enabled_configs.return_value = []

        request = ExportRequest(customer_id="customer123")
        data = {"audit_results": [{"id": "1"}]}

        results = await export_manager.export_data(request, data)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_trigger_export(self, export_manager):
        """Test triggering manual export."""
        request = await export_manager.trigger_export(
            customer_id="customer123",
            destination=ExportFormat.BIGQUERY,
            date_range={"start": "2024-01-01", "end": "2024-01-31"},
            include_historical=True,
        )

        assert request.customer_id == "customer123"
        assert request.destination == ExportFormat.BIGQUERY
        assert request.date_range == {"start": "2024-01-01", "end": "2024-01-31"}
        assert request.include_historical is True
        assert request.export_id  # Should have generated ID

    def test_get_active_exports(self, export_manager):
        """Test getting active exports."""
        # Add some active exports
        request1 = ExportRequest(export_id="export-1", customer_id="customer1")
        request2 = ExportRequest(export_id="export-2", customer_id="customer2")

        export_manager.active_exports["export-1"] = request1
        export_manager.active_exports["export-2"] = request2

        active = export_manager.get_active_exports()

        assert len(active) == 2
        assert any(r.export_id == "export-1" for r in active)
        assert any(r.export_id == "export-2" for r in active)

    def test_cancel_export(self, export_manager):
        """Test cancelling export."""
        # Add active export
        request = ExportRequest(export_id="export-123", customer_id="customer123")
        export_manager.active_exports["export-123"] = request

        # Cancel it
        result = export_manager.cancel_export("export-123")

        assert result is True
        assert "export-123" not in export_manager.active_exports

    def test_cancel_nonexistent_export(self, export_manager):
        """Test cancelling non-existent export."""
        result = export_manager.cancel_export("does-not-exist")
        assert result is False

    def test_get_exporter_caching(self, export_manager):
        """Test exporter caching."""
        config = ExportConfig(
            destination_type=ExportFormat.BIGQUERY,
            credentials={},
            project_id="test-project",
            dataset="test_dataset",
        )

        with patch("paidsearchnav.exports.manager.BigQueryExporter") as mock_bq_class:
            mock_instance = MagicMock()
            mock_bq_class.return_value = mock_instance

            # Get exporter twice
            exporter1 = export_manager._get_exporter(config)
            exporter2 = export_manager._get_exporter(config)

            # Should only create one instance
            assert exporter1 is exporter2
            mock_bq_class.assert_called_once()

    def test_get_unsupported_exporter(self, export_manager):
        """Test getting unsupported exporter type."""
        config = ExportConfig(
            destination_type=ExportFormat.SNOWFLAKE,  # Not implemented yet
            credentials={},
        )

        with pytest.raises(ValueError) as exc_info:
            export_manager._get_exporter(config)

        assert "Unsupported export destination" in str(exc_info.value)
