"""Unit tests for metadata tracker."""

import pytest

from paidsearchnav.core.models.file_management import FileCategory, FileMetadata
from paidsearchnav.core.models.file_metadata import (
    AuditFileMetadata,
    FileOperationMetadata,
    FileProcessingMetadata,
    FileVersionMetadata,
)
from paidsearchnav.services.metadata_tracker import MetadataTracker


@pytest.fixture
def metadata_tracker():
    """Create metadata tracker instance."""
    return MetadataTracker()


class TestMetadataTracker:
    """Test suite for MetadataTracker."""

    def test_create_file_metadata(self, metadata_tracker):
        """Test creation of file metadata."""
        metadata = metadata_tracker.create_file_metadata(
            file_path="s3://bucket/path/file.csv",
            file_size=1000,
            content_type="text/csv",
            checksum="abc123",
            audit_run_id="audit123",
            file_category=FileCategory.INPUT,
            customer_id="123",
            google_ads_account_id="456",
            audit_date="2024-01-15",
            file_type="keywords",
        )

        assert isinstance(metadata, FileMetadata)
        assert metadata.file_path == "s3://bucket/path/file.csv"
        assert metadata.file_size == 1000
        assert metadata.content_type == "text/csv"
        assert metadata.checksum == "abc123"
        assert metadata.audit_run_id == "audit123"
        assert metadata.file_category == FileCategory.INPUT
        assert metadata.file_type == "keywords"
        assert metadata.customer_id == "123"
        assert metadata.google_ads_account_id == "456"
        assert metadata.audit_date == "2024-01-15"

    def test_create_audit_file_metadata(self, metadata_tracker):
        """Test creation of comprehensive audit file metadata."""
        s3_result = {
            "bucket": "test-bucket",
            "key": "path/to/file.csv",
            "etag": "etag123",
            "version_id": "v123",
            "metadata": {"tag1": "value1"},
        }

        metadata = metadata_tracker.create_audit_file_metadata(
            file_name="keywords.csv",
            file_path="s3://bucket/path/file.csv",
            file_size=2000,
            content_type="text/csv",
            checksum="def456",
            audit_run_id="audit456",
            file_category="input",
            file_type="keywords",
            customer_id="789",
            google_ads_account_id="012",
            audit_date="2024-01-20",
            s3_result=s3_result,
            custom_metadata={"custom": "value"},
        )

        assert isinstance(metadata, AuditFileMetadata)
        assert metadata.file_name == "keywords.csv"
        assert metadata.file_size == 2000
        assert metadata.audit_run_id == "audit456"
        assert metadata.s3_metadata is not None
        assert metadata.s3_metadata.bucket == "test-bucket"
        assert metadata.s3_metadata.etag == "etag123"
        assert metadata.custom_metadata == {"custom": "value"}

        cached = metadata_tracker.get_file_metadata(metadata.file_id)
        assert cached == metadata

    def test_track_operation(self, metadata_tracker):
        """Test tracking file operations."""
        operation = metadata_tracker.track_operation(
            operation_type="upload",
            success=True,
            duration_ms=1500,
            user_id="user123",
            client_info={"app": "test"},
        )

        assert isinstance(operation, FileOperationMetadata)
        assert operation.operation_type == "upload"
        assert operation.success is True
        assert operation.duration_ms == 1500
        assert operation.user_id == "user123"
        assert operation.client_info == {"app": "test"}

        history = metadata_tracker.get_operation_history(limit=10)
        assert len(history) == 1
        assert history[0] == operation

    def test_track_operation_failure(self, metadata_tracker):
        """Test tracking failed operations."""
        operation = metadata_tracker.track_operation(
            operation_type="download",
            success=False,
            error_message="File not found",
        )

        assert operation.success is False
        assert operation.error_message == "File not found"

    def test_track_processing(self, metadata_tracker):
        """Test tracking file processing metadata."""
        processing = metadata_tracker.track_processing(
            processor_name="CSVProcessor",
            processor_version="1.0.0",
            input_checksum="input123",
            processing_time_ms=500,
            output_checksum="output456",
            records_processed=100,
            records_skipped=5,
            processing_errors={"row_10": "Invalid data"},
        )

        assert isinstance(processing, FileProcessingMetadata)
        assert processing.processor_name == "CSVProcessor"
        assert processing.processor_version == "1.0.0"
        assert processing.processing_time_ms == 500
        assert processing.records_processed == 100
        assert processing.records_skipped == 5
        assert processing.processing_errors == {"row_10": "Invalid data"}

    def test_create_version_metadata(self, metadata_tracker):
        """Test creation of version metadata."""
        version = metadata_tracker.create_version_metadata(
            version_number=2,
            created_by="user123",
            change_summary="Updated columns",
            previous_version_id="v1",
        )

        assert isinstance(version, FileVersionMetadata)
        assert version.version_number == 2
        assert version.created_by == "user123"
        assert version.change_summary == "Updated columns"
        assert version.previous_version_id == "v1"
        assert version.is_current is True

    def test_update_access_metadata(self, metadata_tracker):
        """Test updating access metadata."""
        metadata = metadata_tracker.create_audit_file_metadata(
            file_name="test.csv",
            file_path="s3://bucket/test.csv",
            file_size=100,
            content_type="text/csv",
            checksum="abc",
            audit_run_id="audit1",
            file_category="input",
            file_type="keywords",
            customer_id="123",
            google_ads_account_id="456",
            audit_date="2024-01-15",
        )

        initial_access_count = metadata.access_metadata.access_count

        updated = metadata_tracker.update_access_metadata(
            metadata.file_id, accessed_by="user456"
        )

        assert updated is not None
        assert updated.access_count == initial_access_count + 1
        assert updated.last_accessed is not None

    def test_update_access_metadata_not_found(self, metadata_tracker):
        """Test updating access metadata for non-existent file."""
        result = metadata_tracker.update_access_metadata(
            "non_existent_id", accessed_by="user"
        )
        assert result is None

    def test_get_operation_history_with_filter(self, metadata_tracker):
        """Test getting filtered operation history."""
        metadata_tracker.track_operation("upload", True)
        metadata_tracker.track_operation("download", True)
        metadata_tracker.track_operation("upload", False)
        metadata_tracker.track_operation("delete", True)

        all_ops = metadata_tracker.get_operation_history(limit=10)
        assert len(all_ops) == 4

        upload_ops = metadata_tracker.get_operation_history(
            limit=10, operation_type="upload"
        )
        assert len(upload_ops) == 2

        download_ops = metadata_tracker.get_operation_history(
            limit=10, operation_type="download"
        )
        assert len(download_ops) == 1

    def test_operation_history_limit(self, metadata_tracker):
        """Test operation history limit enforcement."""
        for i in range(1500):
            metadata_tracker.track_operation(f"op_{i}", True)

        history = metadata_tracker.get_operation_history(limit=100)
        assert len(history) == 100

        all_history = metadata_tracker._operation_history
        assert len(all_history) <= 1000

    def test_export_metadata(self, metadata_tracker):
        """Test exporting metadata as dictionary."""
        metadata = metadata_tracker.create_audit_file_metadata(
            file_name="export_test.csv",
            file_path="s3://bucket/export.csv",
            file_size=500,
            content_type="text/csv",
            checksum="xyz789",
            audit_run_id="audit_export",
            file_category="input",
            file_type="keywords",
            customer_id="export123",
            google_ads_account_id="export456",
            audit_date="2024-01-25",
        )

        exported = metadata_tracker.export_metadata(metadata.file_id)

        assert exported is not None
        assert isinstance(exported, dict)
        assert exported["file_name"] == "export_test.csv"
        assert exported["file_size"] == 500
        assert exported["audit_run_id"] == "audit_export"

    def test_export_metadata_not_found(self, metadata_tracker):
        """Test exporting metadata for non-existent file."""
        exported = metadata_tracker.export_metadata("non_existent")
        assert exported is None

    def test_import_metadata(self, metadata_tracker):
        """Test importing metadata from dictionary."""
        metadata_dict = {
            "file_id": "imported123",
            "audit_run_id": "audit_import",
            "customer_id": "cust123",
            "google_ads_account_id": "gads456",
            "audit_date": "2024-01-30",
            "file_category": "input",
            "file_type": "keywords",
            "file_name": "imported.csv",
            "file_size": 750,
            "content_type": "text/csv",
            "checksum": "import_check",
        }

        imported = metadata_tracker.import_metadata(metadata_dict)

        assert isinstance(imported, AuditFileMetadata)
        assert imported.file_id == "imported123"
        assert imported.file_name == "imported.csv"

        cached = metadata_tracker.get_file_metadata("imported123")
        assert cached == imported

    def test_clear_cache(self, metadata_tracker):
        """Test clearing metadata cache."""
        for i in range(5):
            metadata_tracker.create_audit_file_metadata(
                file_name=f"file{i}.csv",
                file_path=f"s3://bucket/file{i}.csv",
                file_size=100,
                content_type="text/csv",
                checksum=f"check{i}",
                audit_run_id=f"audit{i}",
                file_category="input",
                file_type="keywords",
                customer_id="123",
                google_ads_account_id="456",
                audit_date="2024-01-15",
            )

        assert metadata_tracker.get_cache_size() == 5

        cleared = metadata_tracker.clear_cache()
        assert cleared == 5
        assert metadata_tracker.get_cache_size() == 0

    def test_get_stats(self, metadata_tracker):
        """Test getting tracker statistics."""
        for i in range(3):
            metadata_tracker.create_audit_file_metadata(
                file_name=f"stat{i}.csv",
                file_path=f"s3://bucket/stat{i}.csv",
                file_size=200,
                content_type="text/csv",
                checksum=f"stat{i}",
                audit_run_id=f"audit_stat{i}",
                file_category="input",
                file_type="keywords",
                customer_id="123",
                google_ads_account_id="456",
                audit_date="2024-01-15",
            )

        metadata_tracker.track_operation("upload", True)
        metadata_tracker.track_operation("upload", True)
        metadata_tracker.track_operation("download", True)
        metadata_tracker.track_operation("delete", False, error_message="Failed")

        stats = metadata_tracker.get_stats()

        assert stats["cache_size"] == 3
        assert stats["total_operations"] == 4
        assert stats["successful_operations"] == 3
        assert stats["failed_operations"] == 1
        assert stats["operation_types"]["upload"] == 2
        assert stats["operation_types"]["download"] == 1
        assert stats["operation_types"]["delete"] == 1
