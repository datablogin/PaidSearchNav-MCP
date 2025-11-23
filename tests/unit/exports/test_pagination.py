"""Tests for export pagination functionality."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav_mcp.exports.base import (
    ExportFormat,
    ExportProgress,
    ExportRequest,
    ExportStatus,
    PaginationConfig,
)
from paidsearchnav_mcp.exports.csv import CSVExporter
from paidsearchnav_mcp.exports.hybrid import HybridExportManager


class TestPaginationConfig:
    """Test pagination configuration."""

    def test_default_pagination_config(self):
        """Test default pagination configuration values."""
        config = PaginationConfig()

        assert config.batch_size == 10000
        assert config.max_memory_mb == 100
        assert config.enable_streaming is True
        assert config.progress_callback_interval == 1000

    def test_custom_pagination_config(self):
        """Test custom pagination configuration."""
        config = PaginationConfig(
            batch_size=5000,
            max_memory_mb=200,
            enable_streaming=False,
            progress_callback_interval=500,
        )

        assert config.batch_size == 5000
        assert config.max_memory_mb == 200
        assert config.enable_streaming is False
        assert config.progress_callback_interval == 500


class TestExportProgress:
    """Test export progress tracking."""

    def test_export_progress_creation(self):
        """Test export progress object creation."""
        progress = ExportProgress(
            export_id="test-export",
            current_records=500,
            total_records=1000,
            current_batch=1,
            total_batches=2,
            memory_usage_mb=50.0,
            started_at=datetime.now(timezone.utc),
        )

        assert progress.export_id == "test-export"
        assert progress.current_records == 500
        assert progress.total_records == 1000
        assert progress.progress_percentage == 50.0

    def test_progress_percentage_none_when_no_total(self):
        """Test progress percentage is None when total is unknown."""
        progress = ExportProgress(
            export_id="test-export",
            current_records=500,
            total_records=None,
            current_batch=1,
            total_batches=None,
            memory_usage_mb=50.0,
            started_at=datetime.now(timezone.utc),
        )

        assert progress.progress_percentage is None

    def test_progress_percentage_caps_at_100(self):
        """Test progress percentage caps at 100%."""
        progress = ExportProgress(
            export_id="test-export",
            current_records=1200,
            total_records=1000,
            current_batch=2,
            total_batches=2,
            memory_usage_mb=50.0,
            started_at=datetime.now(timezone.utc),
        )

        assert progress.progress_percentage == 100.0


class TestCSVExporterPagination:
    """Test CSV exporter with pagination support."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def csv_exporter(self, temp_dir):
        """Create CSV exporter with pagination config."""
        pagination_config = PaginationConfig(
            batch_size=100,  # Small batch size for testing
            max_memory_mb=500,  # Higher limit for tests to avoid interference
            enable_streaming=True,
            progress_callback_interval=10,
        )
        return CSVExporter(output_dir=temp_dir, pagination_config=pagination_config)

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for testing."""
        return {
            "audit_results": [
                {
                    "audit_id": f"audit_{i}",
                    "customer_id": "test_customer",
                    "audit_date": f"2023-01-{i:02d}",
                    "keywords_analyzed": i * 10,
                    "issues_found": i,
                    "cost_savings": i * 5.5,
                }
                for i in range(1, 251)  # 250 records to test batching
            ]
        }

    @pytest.mark.asyncio
    async def test_csv_export_batch_with_progress(
        self, csv_exporter, sample_data, temp_dir
    ):
        """Test CSV export with progress tracking."""
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        result = await csv_exporter.export_batch(
            customer_id="test_customer",
            data=sample_data,
            progress_callback=progress_callback,
        )

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 250
        assert len(result.metadata["files_created"]) == 1

        # Check that progress was tracked
        assert len(progress_calls) > 0
        assert progress_calls[-1] == (250, 250)  # Final progress should be complete

        # Verify file was created
        csv_file = Path(result.metadata["files_created"][0])
        assert csv_file.exists()
        assert csv_file.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_csv_export_streaming_mode(self, temp_dir):
        """Test CSV export with streaming enabled for large datasets."""
        pagination_config = PaginationConfig(
            batch_size=50,  # Small batch to force streaming
            max_memory_mb=500,  # Reasonable limit for tests
            enable_streaming=True,
        )
        exporter = CSVExporter(output_dir=temp_dir, pagination_config=pagination_config)

        # Create large dataset that should trigger streaming
        large_data = {
            "large_table": [
                {"id": i, "value": f"value_{i}", "data": "x" * 100} for i in range(200)
            ]
        }

        result = await exporter.export_batch(
            customer_id="test_customer", data=large_data
        )

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 200
        assert result.metadata["streaming_enabled"] is True

    @pytest.mark.asyncio
    async def test_csv_export_memory_usage_tracking(self, csv_exporter, sample_data):
        """Test memory usage is tracked during export."""
        result = await csv_exporter.export_batch(
            customer_id="test_customer", data=sample_data
        )

        assert result.status == ExportStatus.COMPLETED
        assert "peak_memory_mb" in result.metadata
        assert result.metadata["peak_memory_mb"] > 0

    @pytest.mark.asyncio
    async def test_update_pagination_config(self, csv_exporter):
        """Test updating pagination configuration."""
        new_config = PaginationConfig(
            batch_size=5000, max_memory_mb=200, enable_streaming=False
        )

        csv_exporter.update_pagination_config(new_config)

        assert csv_exporter.pagination_config.batch_size == 5000
        assert csv_exporter.pagination_config.max_memory_mb == 200
        assert csv_exporter.pagination_config.enable_streaming is False


class TestHybridExportManagerPagination:
    """Test hybrid export manager with pagination support."""

    @pytest.fixture
    def hybrid_manager(self):
        """Create hybrid export manager."""
        return HybridExportManager()

    @pytest.fixture
    def export_request(self):
        """Create export request with pagination config."""
        return ExportRequest(
            export_id="test-export-123",
            customer_id="test_customer",
            destination=ExportFormat.CSV,
            pagination_config=PaginationConfig(batch_size=100, max_memory_mb=50),
        )

    @pytest.fixture
    def sample_export_data(self):
        """Sample data for export testing."""
        return {
            "audit_results": [
                {"audit_id": f"audit_{i}", "customer_id": "test_customer"}
                for i in range(150)
            ],
            "recommendations": [
                {"recommendation_id": f"rec_{i}", "audit_id": f"audit_{i}"}
                for i in range(75)
            ],
        }

    def test_hybrid_config_with_pagination(self, hybrid_manager):
        """Test hybrid config includes pagination settings based on customer tier."""
        # Test standard tier
        config_standard = hybrid_manager.get_hybrid_config("standard_customer")
        assert config_standard.pagination_config.batch_size == 10000
        assert config_standard.pagination_config.max_memory_mb == 100

        # Mock customer tier lookup for premium
        with patch.object(hybrid_manager, "get_customer_tier", return_value="premium"):
            config_premium = hybrid_manager.get_hybrid_config("premium_customer")
            assert config_premium.pagination_config.batch_size == 25000
            assert config_premium.pagination_config.max_memory_mb == 500

        # Mock customer tier lookup for enterprise
        with patch.object(
            hybrid_manager, "get_customer_tier", return_value="enterprise"
        ):
            config_enterprise = hybrid_manager.get_hybrid_config("enterprise_customer")
            assert config_enterprise.pagination_config.batch_size == 50000
            assert config_enterprise.pagination_config.max_memory_mb == 1000

    @pytest.mark.asyncio
    async def test_export_progress_tracking(
        self, hybrid_manager, export_request, sample_export_data
    ):
        """Test export progress is tracked during hybrid export."""
        progress_updates = []

        def progress_callback(current, total):
            progress_updates.append((current, total))

        export_request.progress_callback = progress_callback

        # Mock the CSV exporter to avoid file I/O
        with patch.object(hybrid_manager, "_export_to_csv") as mock_csv_export:
            mock_csv_export.return_value = AsyncMock()
            mock_csv_export.return_value.status = ExportStatus.COMPLETED
            mock_csv_export.return_value.records_exported = 225

            results = await hybrid_manager.export_data_hybrid_paginated(
                export_request, sample_export_data
            )

            # Verify progress was tracked
            progress = hybrid_manager.get_export_progress(export_request.export_id)
            assert progress is not None
            assert progress.total_records == 225
            assert progress.export_id == export_request.export_id

    def test_progress_tracker_cleanup(self, hybrid_manager):
        """Test progress tracker cleanup."""
        export_id = "test-export-cleanup"
        progress = ExportProgress(
            export_id=export_id,
            current_records=100,
            total_records=200,
            current_batch=1,
            total_batches=2,
            memory_usage_mb=50.0,
            started_at=datetime.now(timezone.utc),
        )

        hybrid_manager.progress_trackers[export_id] = progress

        # Verify progress exists
        assert hybrid_manager.get_export_progress(export_id) is not None

        # Cleanup
        hybrid_manager.cleanup_progress_tracker(export_id)

        # Verify progress was removed
        assert hybrid_manager.get_export_progress(export_id) is None

    @pytest.mark.asyncio
    async def test_large_dataset_streaming(self, hybrid_manager):
        """Test streaming export for large datasets."""

        async def mock_data_provider(batch_size):
            """Mock data provider that yields batches."""
            for i in range(3):  # 3 batches
                yield {
                    "test_data": [
                        {"id": j + i * batch_size, "value": f"batch_{i}_record_{j}"}
                        for j in range(batch_size)
                    ]
                }

        request = ExportRequest(
            export_id="streaming-test", customer_id="streaming_customer"
        )

        # Mock the export methods to avoid actual I/O
        with patch.object(hybrid_manager, "export_data_hybrid") as mock_export:
            mock_export.return_value = [AsyncMock()]

            results = await hybrid_manager.export_large_dataset_streaming(
                request=request, data_provider=mock_data_provider, batch_size=100
            )

            # Should have called export_data_hybrid 3 times (one per batch)
            assert mock_export.call_count == 3


class TestPaginationIntegration:
    """Integration tests for pagination across different export formats."""

    @pytest.fixture
    def large_dataset(self):
        """Create a large dataset for integration testing."""
        return {
            "audit_results": [
                {
                    "audit_id": f"audit_{i}",
                    "customer_id": "integration_test",
                    "audit_date": "2023-01-01",
                    "keywords_analyzed": i * 10,
                    "issues_found": i % 5,
                    "cost_savings": i * 2.5,
                }
                for i in range(10000)  # 10k records
            ],
            "recommendations": [
                {
                    "recommendation_id": f"rec_{i}",
                    "audit_id": f"audit_{i}",
                    "type": "keyword_optimization",
                    "priority": "medium",
                    "title": f"Recommendation {i}",
                    "description": f"Optimize keyword {i}",
                    "estimated_impact": i * 0.1,
                }
                for i in range(5000)  # 5k records
            ],
        }

    @pytest.mark.asyncio
    async def test_memory_efficient_export(self, large_dataset):
        """Test that large datasets can be exported without excessive memory usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Configure for memory efficiency
            pagination_config = PaginationConfig(
                batch_size=1000,  # Process in smaller batches
                max_memory_mb=500,  # Reasonable limit for tests
                enable_streaming=True,
            )

            exporter = CSVExporter(
                output_dir=Path(tmpdir), pagination_config=pagination_config
            )

            memory_usage_samples = []

            def track_memory_progress(current, total):
                # This would be called during export
                memory_usage_samples.append((current, total))

            result = await exporter.export_batch(
                customer_id="memory_test",
                data=large_dataset,
                progress_callback=track_memory_progress,
            )

            assert result.status == ExportStatus.COMPLETED
            assert result.records_exported == 15000  # 10k + 5k
            assert len(memory_usage_samples) > 0

            # Verify files were created and contain data
            files_created = result.metadata["files_created"]
            assert len(files_created) == 2  # One per data type

            for file_path in files_created:
                assert Path(file_path).exists()
                assert Path(file_path).stat().st_size > 0

    def test_pagination_config_validation(self):
        """Test pagination configuration validation."""
        # Test valid configuration
        config = PaginationConfig(
            batch_size=1000,
            max_memory_mb=100,
            enable_streaming=True,
            progress_callback_interval=100,
        )

        assert config.batch_size > 0
        assert config.max_memory_mb > 0
        assert config.progress_callback_interval > 0

        # Test edge cases
        min_config = PaginationConfig(
            batch_size=1,
            max_memory_mb=1,
            enable_streaming=False,
            progress_callback_interval=1,
        )

        assert min_config.batch_size == 1
        assert min_config.max_memory_mb == 1
        assert min_config.enable_streaming is False

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """Test that memory limits are enforced during export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create exporter with very low memory limit to trigger enforcement
            pagination_config = PaginationConfig(
                batch_size=50,
                max_memory_mb=1,  # Very low limit to trigger error
                enable_streaming=True,
            )
            exporter = CSVExporter(
                output_dir=Path(tmpdir), pagination_config=pagination_config
            )

            # Create data that should trigger memory limit
            large_data = {
                "memory_test": [{"id": i, "data": "x" * 1000} for i in range(100)]
            }

            # Mock memory usage to exceed limit
            original_check = exporter._check_memory_usage

            async def mock_memory_check():
                # Simulate high memory usage
                exporter._process.memory_info = lambda: type(
                    "obj", (object,), {"rss": 5 * 1024 * 1024}
                )()  # 5MB
                await original_check()

            exporter._check_memory_usage = mock_memory_check

            # Should raise MemoryError
            with pytest.raises(MemoryError) as exc_info:
                await exporter._check_memory_usage()

            assert "Memory usage exceeded limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_progress_callback_error_handling(self):
        """Test that progress callback errors don't interrupt export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pagination_config = PaginationConfig(batch_size=100, max_memory_mb=500)
            exporter = CSVExporter(
                output_dir=Path(tmpdir), pagination_config=pagination_config
            )

            sample_data = {
                "test_table": [{"id": i, "value": f"test_{i}"} for i in range(10)]
            }

            progress_calls = []
            call_count = 0

            def failing_progress_callback(current, total):
                nonlocal call_count
                call_count += 1
                if call_count == 2:  # Fail on second call
                    raise ValueError("Progress callback failed")
                progress_calls.append((current, total))

            # Export should complete despite callback failure
            result = await exporter.export_batch(
                customer_id="test_customer",
                data=sample_data,
                progress_callback=failing_progress_callback,
            )

            assert result.status == ExportStatus.COMPLETED
            # Should have at least one successful progress call
            assert len(progress_calls) >= 1

    @pytest.mark.asyncio
    async def test_partial_export_cleanup(self):
        """Test cleanup of partial files when export fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pagination_config = PaginationConfig(batch_size=100, max_memory_mb=500)
            exporter = CSVExporter(
                output_dir=Path(tmpdir), pagination_config=pagination_config
            )

            # Create data with one table that will succeed and one that will fail
            test_data = {
                "good_table": [{"id": 1, "value": "test"}],
                "bad_table": [{"id": 2, "value": "test"}],
            }

            # Mock the _write_csv_file method to fail on the second table
            original_write = exporter._write_csv_file
            call_count = 0

            async def mock_write_csv_file(filepath, records, progress_callback=None):
                nonlocal call_count
                call_count += 1
                if call_count == 2:  # Fail on second table
                    # Create a partial file first
                    filepath.touch()
                    raise ValueError("Simulated write failure")
                return await original_write(filepath, records, progress_callback)

            exporter._write_csv_file = mock_write_csv_file

            # Export should fail and clean up files
            result = await exporter.export_batch(
                customer_id="cleanup_test",
                data=test_data,
            )

            assert result.status == ExportStatus.FAILED
            assert "Simulated write failure" in result.error_message
            assert result.metadata.get("partial_export") is True

            # Check that no CSV files remain in the directory
            csv_files = list(Path(tmpdir).glob("*.csv"))
            assert len(csv_files) == 0, f"Found remaining files: {csv_files}"

    @pytest.mark.asyncio
    async def test_streaming_memory_efficiency(self):
        """Test that streaming mode properly releases memory between batches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pagination_config = PaginationConfig(
                batch_size=10,  # Small batches
                max_memory_mb=500,  # Reasonable limit for tests
                enable_streaming=True,
            )
            exporter = CSVExporter(
                output_dir=Path(tmpdir), pagination_config=pagination_config
            )

            # Create data that would use significant memory if not streamed
            large_data = {
                "streaming_test": [
                    {"id": i, "large_field": "x" * 100} for i in range(50)
                ]
            }

            memory_samples = []

            # Mock memory monitoring to track usage
            original_check = exporter._check_memory_usage

            async def track_memory():
                memory_info = exporter._process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                memory_samples.append(memory_mb)
                await original_check()

            exporter._check_memory_usage = track_memory

            result = await exporter.export_batch(
                customer_id="streaming_test",
                data=large_data,
            )

            assert result.status == ExportStatus.COMPLETED
            assert result.metadata["streaming_enabled"] is True
            # Should have collected memory samples during processing
            assert len(memory_samples) > 0
