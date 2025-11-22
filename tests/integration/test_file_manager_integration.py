"""Integration tests for S3 file management service."""

import asyncio
import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from moto import mock_s3

from paidsearchnav.core.config import S3Config
from paidsearchnav.integrations.s3 import S3Client
from paidsearchnav.services.file_manager import AuditFileManagerService


@pytest.fixture
def s3_config():
    """Create S3 configuration for integration testing."""
    return S3Config(
        enabled=True,
        bucket_name="test-audit-bucket",
        prefix="PaidSearchNav",
        region="us-east-1",
        multipart_threshold=100 * 1024 * 1024,
    )


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials for testing."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SECURITY_TOKEN": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    ):
        yield


@pytest.mark.integration
class TestAuditFileManagerIntegration:
    """Integration tests for AuditFileManagerService with S3."""

    @mock_s3
    @pytest.mark.asyncio
    async def test_upload_and_retrieve_audit_files(
        self, s3_config, mock_aws_credentials
    ):
        """Test complete workflow of uploading and retrieving audit files."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        customer_id = "12345"
        google_ads_account_id = "67890"
        audit_date = date(2024, 1, 15)

        keywords_csv = b"""Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type
123,456,789,ENABLED,dentist near me,EXACT
124,456,790,ENABLED,emergency dental,PHRASE"""

        search_terms_csv = b"""Search term,Campaign ID,Ad group ID,Impressions,Clicks,Cost
dentist open now,456,789,1000,50,25.50
dental emergency,456,790,500,30,18.75"""

        input_result1 = await file_manager.upload_input_csv(
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
            file_content=keywords_csv,
            filename="keywords.csv",
            audit_run_id="test_run_001",
        )

        assert input_result1.validation_status == "valid"
        assert input_result1.row_count == 2

        input_result2 = await file_manager.upload_input_csv(
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
            file_content=search_terms_csv,
            filename="search_terms.csv",
            audit_run_id="test_run_001",
        )

        assert input_result2.validation_status == "valid"

        reports = {
            "analysis_summary.md": "# Analysis Summary\n\nFound 5 optimization opportunities.",
            "recommendations.md": "# Recommendations\n\n1. Pause low-performing keywords",
        }

        actionable_files = {
            "changes.csv": b"Campaign ID,Action\n456,UPDATE",
            "negative_keywords.csv": b"Keyword,Match Type\nbad keyword,EXACT",
        }

        output_result = await file_manager.store_analysis_outputs(
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
            reports=reports,
            actionable_files=actionable_files,
            audit_run_id="test_run_001",
        )

        assert len(output_result.report_files) == 2
        assert len(output_result.actionable_files) == 2

        audit_files = await file_manager.get_audit_files(
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
        )

        assert audit_files.customer_id == customer_id
        assert len(audit_files.input_files) == 2
        assert audit_files.output_files is not None
        assert len(audit_files.output_files.report_files) == 2
        assert len(audit_files.output_files.actionable_files) == 2
        assert audit_files.total_file_count == 6

    @mock_s3
    @pytest.mark.asyncio
    async def test_cleanup_old_audits_integration(
        self, s3_config, mock_aws_credentials
    ):
        """Test cleanup of old audit files."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        old_date = date.today() - timedelta(days=100)
        recent_date = date.today() - timedelta(days=30)

        old_csv = b"Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n123,456,789,ENABLED,old,EXACT"
        recent_csv = b"Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n124,457,790,ENABLED,recent,EXACT"

        await file_manager.upload_input_csv(
            customer_id="old_customer",
            google_ads_account_id="111",
            audit_date=old_date,
            file_content=old_csv,
            filename="old_keywords.csv",
        )

        await file_manager.upload_input_csv(
            customer_id="recent_customer",
            google_ads_account_id="222",
            audit_date=recent_date,
            file_content=recent_csv,
            filename="recent_keywords.csv",
        )

        cleanup_report = await file_manager.cleanup_old_audits(retention_days=90)

        assert cleanup_report.files_deleted == 1
        assert cleanup_report.bytes_freed > 0
        assert cleanup_report.customers_affected == 1

        old_files = await file_manager.get_audit_files(
            customer_id="old_customer",
            google_ads_account_id="111",
            audit_date=old_date,
        )
        assert old_files.total_file_count == 0

        recent_files = await file_manager.get_audit_files(
            customer_id="recent_customer",
            google_ads_account_id="222",
            audit_date=recent_date,
        )
        assert recent_files.total_file_count == 1

    @mock_s3
    @pytest.mark.asyncio
    async def test_invalid_csv_upload(self, s3_config, mock_aws_credentials):
        """Test handling of invalid CSV upload."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        invalid_csv = b"Wrong,Headers\ndata1,data2"

        with pytest.raises(ValueError) as exc_info:
            await file_manager.upload_input_csv(
                customer_id="123",
                google_ads_account_id="456",
                audit_date=date(2024, 1, 15),
                file_content=invalid_csv,
                filename="keywords.csv",
            )

        assert "File validation failed" in str(exc_info.value)

    @mock_s3
    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, s3_config, mock_aws_credentials):
        """Test concurrent file uploads."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        csv_files = [
            (
                f"file_{i}.csv",
                f"Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n{i},456,789,ENABLED,keyword{i},EXACT".encode(),
            )
            for i in range(5)
        ]

        upload_tasks = [
            file_manager.upload_input_csv(
                customer_id="concurrent_test",
                google_ads_account_id="999",
                audit_date=date(2024, 1, 20),
                file_content=content,
                filename=filename,
            )
            for filename, content in csv_files
        ]

        results = await asyncio.gather(*upload_tasks)

        assert len(results) == 5
        assert all(r.validation_status == "valid" for r in results)

        audit_files = await file_manager.get_audit_files(
            customer_id="concurrent_test",
            google_ads_account_id="999",
            audit_date=date(2024, 1, 20),
        )

        assert audit_files.total_file_count == 5

    @mock_s3
    @pytest.mark.asyncio
    async def test_large_file_handling(self, s3_config, mock_aws_credentials):
        """Test handling of large files."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        header = b"Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n"
        rows = b"\n".join(
            [f"{i},456,789,ENABLED,keyword{i},EXACT".encode() for i in range(10000)]
        )
        large_csv = header + rows

        result = await file_manager.upload_input_csv(
            customer_id="large_file_test",
            google_ads_account_id="888",
            audit_date=date(2024, 1, 25),
            file_content=large_csv,
            filename="large_keywords.csv",
        )

        assert result.validation_status == "valid"
        assert result.row_count == 10000
        assert result.file_metadata.file_size == len(large_csv)

    @mock_s3
    @pytest.mark.asyncio
    async def test_metadata_tracking_integration(self, s3_config, mock_aws_credentials):
        """Test metadata tracking during file operations."""
        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=s3_config.bucket_name)

        s3_client = S3Client(s3_config)
        s3_client._client = s3
        file_manager = AuditFileManagerService(s3_client, s3_config)

        csv_content = b"Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n123,456,789,ENABLED,test,EXACT"

        await file_manager.upload_input_csv(
            customer_id="metadata_test",
            google_ads_account_id="777",
            audit_date=date(2024, 1, 30),
            file_content=csv_content,
            filename="metadata_test.csv",
        )

        stats = file_manager.metadata_tracker.get_stats()
        assert stats["total_operations"] > 0
        assert stats["successful_operations"] > 0

        history = file_manager.metadata_tracker.get_operation_history(limit=10)
        assert len(history) > 0
        assert history[-1].operation_type == "upload"
        assert history[-1].success is True
