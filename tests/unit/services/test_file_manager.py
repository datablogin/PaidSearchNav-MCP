"""Unit tests for the file manager service."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from paidsearchnav_mcp.core.config import S3Config
from paidsearchnav_mcp.models.file_management import (
    AuditFileSet,
    CleanupReport,
    FileCategory,
    FileMetadata,
    InputFileRecord,
    OutputFileRecord,
)

# Mock botocore before importing S3 related modules
with patch.dict(
    "sys.modules", {"botocore": MagicMock(), "botocore.exceptions": MagicMock()}
):
    from paidsearchnav.integrations.s3 import (
        S3Client,
        S3ClientError,
        S3Object,
        S3UploadResult,
    )
    from paidsearchnav.services.file_manager import AuditFileManagerService


@pytest.fixture
def s3_config():
    """Create S3 configuration for testing."""
    return S3Config(
        enabled=True,
        bucket_name="test-bucket",
        prefix="PaidSearchNav",
        region="us-east-1",
        multipart_threshold=100 * 1024 * 1024,
    )


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client."""
    client = Mock(spec=S3Client)
    client.upload_content = Mock()
    client.list_objects = Mock()
    client.delete_object = Mock()
    client.get_object_metadata = Mock()
    return client


@pytest.fixture
def file_manager(mock_s3_client, s3_config):
    """Create file manager service instance."""
    return AuditFileManagerService(mock_s3_client, s3_config)


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return b"""Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type
123,456,789,ENABLED,test keyword,EXACT
124,456,790,ENABLED,another keyword,PHRASE"""


@pytest.fixture
def sample_report_content():
    """Sample report content for testing."""
    return """# Analysis Summary

## Key Findings
- Found 10 optimization opportunities
- Potential cost savings: $500/month
"""


class TestAuditFileManagerService:
    """Test suite for AuditFileManagerService."""

    @pytest.mark.asyncio
    async def test_upload_input_csv_success(
        self, file_manager, mock_s3_client, sample_csv_content
    ):
        """Test successful upload of input CSV file."""
        mock_s3_client.upload_content.return_value = S3UploadResult(
            key="PaidSearchNav/customer_123/123/2024-01-15/inputs/20240115_120000_keywords.csv",
            bucket="test-bucket",
            size=len(sample_csv_content),
            etag="abc123",
            version_id=None,
        )

        result = await file_manager.upload_input_csv(
            customer_id="123",
            google_ads_account_id="456",
            audit_date=date(2024, 1, 15),
            file_content=sample_csv_content,
            filename="keywords.csv",
            audit_run_id="audit123",
        )

        assert isinstance(result, InputFileRecord)
        assert result.validation_status == "valid"
        assert len(result.validation_errors) == 0
        assert result.row_count == 2
        assert "Keyword ID" in result.column_names
        mock_s3_client.upload_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_input_csv_validation_failure(
        self, file_manager, mock_s3_client
    ):
        """Test upload with invalid CSV content."""
        invalid_csv = b"invalid,csv,content\nno,matching,columns"

        with pytest.raises(ValueError) as exc_info:
            await file_manager.upload_input_csv(
                customer_id="123",
                google_ads_account_id="456",
                audit_date=date(2024, 1, 15),
                file_content=invalid_csv,
                filename="keywords.csv",
            )

        assert "File validation failed" in str(exc_info.value)
        mock_s3_client.upload_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_input_csv_s3_error(
        self, file_manager, mock_s3_client, sample_csv_content
    ):
        """Test upload with S3 error."""
        mock_s3_client.upload_content.side_effect = S3ClientError("S3 upload failed")

        with pytest.raises(S3ClientError):
            await file_manager.upload_input_csv(
                customer_id="123",
                google_ads_account_id="456",
                audit_date=date(2024, 1, 15),
                file_content=sample_csv_content,
                filename="keywords.csv",
            )

    @pytest.mark.asyncio
    async def test_store_analysis_outputs_success(
        self, file_manager, mock_s3_client, sample_report_content
    ):
        """Test successful storage of analysis outputs."""
        mock_s3_client.upload_content.return_value = S3UploadResult(
            key="test-key",
            bucket="test-bucket",
            size=100,
            etag="abc123",
            version_id=None,
        )

        reports = {"analysis_summary.md": sample_report_content}
        actionable_files = {"changes.csv": b"Campaign ID,Action\n123,PAUSE"}

        result = await file_manager.store_analysis_outputs(
            customer_id="123",
            google_ads_account_id="456",
            audit_date=date(2024, 1, 15),
            reports=reports,
            actionable_files=actionable_files,
            audit_run_id="audit123",
        )

        assert isinstance(result, OutputFileRecord)
        assert len(result.report_files) == 1
        assert len(result.actionable_files) == 1
        assert result.total_size_bytes == 200
        assert mock_s3_client.upload_content.call_count == 2

    @pytest.mark.asyncio
    async def test_store_analysis_outputs_partial_failure(
        self, file_manager, mock_s3_client
    ):
        """Test storage with partial upload failure."""
        mock_s3_client.upload_content.side_effect = [
            S3UploadResult(
                key="test-key-1",
                bucket="test-bucket",
                size=100,
                etag="abc123",
                version_id=None,
            ),
            S3ClientError("Upload failed"),
        ]

        reports = {"report1.md": "content1", "report2.md": "content2"}

        with pytest.raises(S3ClientError):
            await file_manager.store_analysis_outputs(
                customer_id="123",
                google_ads_account_id="456",
                audit_date=date(2024, 1, 15),
                reports=reports,
                actionable_files={},
            )

    @pytest.mark.asyncio
    async def test_get_audit_files_success(self, file_manager, mock_s3_client):
        """Test successful retrieval of audit files."""
        mock_objects = [
            S3Object(
                key="PaidSearchNav/customer_123/123/2024-01-15/inputs/file1.csv",
                size=1000,
                last_modified=datetime.now(timezone.utc),
                etag="etag1",
                content_type="text/csv",
            ),
            S3Object(
                key="PaidSearchNav/customer_123/123/2024-01-15/outputs/reports/report.md",
                size=2000,
                last_modified=datetime.now(timezone.utc),
                etag="etag2",
                content_type="text/markdown",
            ),
            S3Object(
                key="PaidSearchNav/customer_123/123/2024-01-15/outputs/actionable_files/changes.csv",
                size=500,
                last_modified=datetime.now(timezone.utc),
                etag="etag3",
                content_type="text/csv",
            ),
        ]
        mock_s3_client.list_objects.return_value = mock_objects

        result = await file_manager.get_audit_files(
            customer_id="123",
            google_ads_account_id="456",
            audit_date=date(2024, 1, 15),
        )

        assert isinstance(result, AuditFileSet)
        assert result.customer_id == "123"
        assert result.audit_date == "2024-01-15"
        assert len(result.input_files) == 1
        assert result.output_files is not None
        assert len(result.output_files.report_files) == 1
        assert len(result.output_files.actionable_files) == 1
        assert result.total_file_count == 3
        assert result.total_size_bytes == 3500

    @pytest.mark.asyncio
    async def test_get_audit_files_empty(self, file_manager, mock_s3_client):
        """Test retrieval when no files exist."""
        mock_s3_client.list_objects.return_value = []

        result = await file_manager.get_audit_files(
            customer_id="123",
            google_ads_account_id="456",
            audit_date=date(2024, 1, 15),
        )

        assert isinstance(result, AuditFileSet)
        assert len(result.input_files) == 0
        assert result.output_files is None
        assert result.total_file_count == 0
        assert result.total_size_bytes == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_audits_success(self, file_manager, mock_s3_client):
        """Test successful cleanup of old audit files."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=100)
        recent_date = datetime.now(timezone.utc) - timedelta(days=50)

        mock_objects = [
            S3Object(
                key="PaidSearchNav/customer_123/123/2023-01-01/inputs/old_file.csv",
                size=1000,
                last_modified=cutoff_date - timedelta(days=10),
                etag="etag1",
            ),
            S3Object(
                key="PaidSearchNav/customer_456/456/2023-01-01/inputs/old_file2.csv",
                size=2000,
                last_modified=cutoff_date - timedelta(days=5),
                etag="etag2",
            ),
            S3Object(
                key="PaidSearchNav/customer_123/123/2024-01-01/inputs/recent_file.csv",
                size=500,
                last_modified=recent_date,
                etag="etag3",
            ),
        ]
        mock_s3_client.list_objects.return_value = mock_objects
        mock_s3_client.delete_object.return_value = True

        result = await file_manager.cleanup_old_audits(retention_days=90)

        assert isinstance(result, CleanupReport)
        assert result.files_deleted == 2
        assert result.bytes_freed == 3000
        assert result.customers_affected == 2
        assert result.oldest_file_date is not None
        assert result.newest_file_date is not None
        assert len(result.errors) == 0
        assert mock_s3_client.delete_object.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_old_audits_with_errors(self, file_manager, mock_s3_client):
        """Test cleanup with some deletion failures."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=100)

        mock_objects = [
            S3Object(
                key="PaidSearchNav/customer_123/123/2023-01-01/inputs/file1.csv",
                size=1000,
                last_modified=cutoff_date - timedelta(days=10),
                etag="etag1",
            ),
            S3Object(
                key="PaidSearchNav/customer_123/123/2023-01-01/inputs/file2.csv",
                size=2000,
                last_modified=cutoff_date - timedelta(days=5),
                etag="etag2",
            ),
        ]
        mock_s3_client.list_objects.return_value = mock_objects
        mock_s3_client.delete_object.side_effect = [
            True,
            Exception("Delete failed"),
        ]

        result = await file_manager.cleanup_old_audits(retention_days=90)

        assert result.files_deleted == 1
        assert result.bytes_freed == 1000
        assert len(result.errors) == 1
        assert "Delete failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_cleanup_old_audits_no_old_files(self, file_manager, mock_s3_client):
        """Test cleanup when no files are old enough."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)

        mock_objects = [
            S3Object(
                key="PaidSearchNav/customer_123/123/2024-01-01/inputs/recent.csv",
                size=1000,
                last_modified=recent_date,
                etag="etag1",
            ),
        ]
        mock_s3_client.list_objects.return_value = mock_objects

        result = await file_manager.cleanup_old_audits(retention_days=90)

        assert result.files_deleted == 0
        assert result.bytes_freed == 0
        assert result.customers_affected == 0
        mock_s3_client.delete_object.assert_not_called()

    def test_determine_file_type(self, file_manager):
        """Test file type determination from filename."""
        assert file_manager._determine_file_type("keywords.csv") == "keywords"
        assert file_manager._determine_file_type("search_terms.csv") == "search_terms"
        assert file_manager._determine_file_type("campaigns.csv") == "campaigns"
        assert file_manager._determine_file_type("ad_groups.csv") == "ad_groups"
        assert file_manager._determine_file_type("random.csv") == "unknown"

    def test_sanitize_path_input(self, file_manager):
        """Test path input sanitization for security."""
        # Test path traversal attempts
        assert file_manager._sanitize_path_input("../../../etc/passwd") == "etc/passwd"
        assert (
            file_manager._sanitize_path_input("..\\..\\windows\\system32")
            == "windows\\system32"
        )

        # Test special characters
        assert file_manager._sanitize_path_input('customer<>:"|?*123') == "customer123"

        # Test double slashes
        assert file_manager._sanitize_path_input("customer//123") == "customer/123"

        # Test empty after sanitization
        assert file_manager._sanitize_path_input("../") == "unknown"

        # Test normal input
        assert file_manager._sanitize_path_input("customer_123") == "customer_123"

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, file_manager):
        """Test conversion of S3Object to FileMetadata."""
        s3_obj = S3Object(
            key="PaidSearchNav/customer_123/123/2024-01-15/inputs/file.csv",
            size=1000,
            last_modified=datetime.now(timezone.utc),
            etag="etag123",
            content_type="text/csv",
        )

        metadata = await file_manager._get_file_metadata(s3_obj)

        assert isinstance(metadata, FileMetadata)
        assert metadata.file_path == s3_obj.key
        assert metadata.file_size == 1000
        assert metadata.content_type == "text/csv"
        assert metadata.file_category == FileCategory.INPUT
        assert metadata.customer_id == "123"
        assert metadata.audit_date == "2024-01-15"
