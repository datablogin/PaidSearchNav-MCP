"""Integration tests for S3 client with mocked AWS services."""

import tempfile
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from pydantic import SecretStr

from paidsearchnav.core.config import S3Config
from paidsearchnav.integrations.s3 import S3Client, S3ClientError


class TestS3Integration:
    """Integration tests using moto for S3 mocking."""

    @pytest.fixture
    def s3_config(self):
        """Create S3 configuration for testing."""
        return S3Config(
            enabled=True,
            bucket_name="test-bucket",
            region="us-east-1",
            access_key_id="testing",
            secret_access_key=SecretStr("testing"),
        )

    @pytest.fixture
    def s3_client(self, s3_config):
        """Create S3 client with mocked AWS."""
        with mock_aws():
            # Create the bucket in moto with credentials
            s3 = boto3.client(
                "s3",
                region_name="us-east-1",
                aws_access_key_id="testing",
                aws_secret_access_key="testing",
            )
            s3.create_bucket(Bucket="test-bucket")

            # Return the PSN S3 client
            yield S3Client(s3_config)

    def test_upload_and_download_file(self, s3_client):
        """Test uploading and downloading a file."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "name,email,age\nJohn,john@example.com,30\nJane,jane@example.com,25"
            )
            temp_file = Path(f.name)

        try:
            # Upload the file
            result = s3_client.upload_file(
                file_path=temp_file,
                customer_name="Test Company",
                customer_number="12345",
                date="2024-01-01",
                folder="inputs",
                filename="customers.csv",
            )

            assert (
                result.key
                == "PaidSearchNav/Test_Company/12345/2024-01-01/inputs/customers.csv"
            )
            assert result.bucket == "test-bucket"
            assert result.size > 0

            # Download the file
            with tempfile.TemporaryDirectory() as temp_dir:
                download_path = Path(temp_dir) / "downloaded.csv"

                downloaded_size = s3_client.download_file(
                    s3_object_key=result.key, local_path=download_path
                )

                assert downloaded_size == result.size
                assert download_path.exists()

                # Verify content
                content = download_path.read_text()
                assert "John,john@example.com,30" in content
                assert "Jane,jane@example.com,25" in content

        finally:
            # Clean up
            temp_file.unlink(missing_ok=True)

    def test_upload_and_download_content(self, s3_client):
        """Test uploading and downloading content directly."""
        content = "This is a test document.\nWith multiple lines.\n"

        # Upload content
        result = s3_client.upload_content(
            content=content,
            customer_name="TestCorp",
            customer_number="54321",
            date="2024-02-15",
            folder="outputs/reports",
            filename="summary.txt",
        )

        assert (
            result.key
            == "PaidSearchNav/TestCorp/54321/2024-02-15/outputs/reports/summary.txt"
        )
        assert result.size == len(content.encode("utf-8"))

        # Download as bytes
        downloaded_bytes = s3_client.download_content(result.key)
        assert downloaded_bytes == content.encode("utf-8")

        # Download as text
        downloaded_text = s3_client.download_content(result.key, as_text=True)
        assert downloaded_text == content

    def test_list_objects_functionality(self, s3_client):
        """Test object listing with various filters."""
        # Upload multiple test files
        test_files = [
            ("TestCorp", "11111", "2024-01-01", "inputs", "data1.csv"),
            ("TestCorp", "11111", "2024-01-01", "outputs/reports", "report1.pdf"),
            ("TestCorp", "22222", "2024-01-01", "inputs", "data2.csv"),
            ("AnotherCorp", "33333", "2024-01-15", "inputs", "data3.csv"),
        ]

        for customer, number, date, folder, filename in test_files:
            s3_client.upload_content(
                content=f"Test content for {filename}",
                customer_name=customer,
                customer_number=number,
                date=date,
                folder=folder,
                filename=filename,
            )

        # List all objects
        all_objects = s3_client.list_objects()
        assert len(all_objects) == 4

        # Filter by customer
        testcorp_objects = s3_client.list_objects(customer_name="TestCorp")
        assert len(testcorp_objects) == 3

        # Filter by customer and number
        specific_customer = s3_client.list_objects(
            customer_name="TestCorp", customer_number="11111"
        )
        assert len(specific_customer) == 2

        # Filter by date
        date_filtered = s3_client.list_objects(date="2024-01-15")
        assert len(date_filtered) == 1
        assert "AnotherCorp" in date_filtered[0].key

    def test_object_existence_and_deletion(self, s3_client):
        """Test object existence checking and deletion."""
        s3_object_key = "PaidSearchNav/TestCorp/99999/2024-03-01/inputs/test.csv"

        # Object shouldn't exist initially
        assert not s3_client.object_exists(s3_object_key)

        # Upload a file
        s3_client.upload_content(
            content="test,data\n1,2\n",
            customer_name="TestCorp",
            customer_number="99999",
            date="2024-03-01",
            folder="inputs",
            filename="test.csv",
        )

        # Object should exist now
        assert s3_client.object_exists(s3_object_key)

        # Get object metadata
        metadata = s3_client.get_object_metadata(s3_object_key)
        assert metadata.key == s3_object_key
        assert metadata.size == len("test,data\n1,2\n".encode("utf-8"))
        # Content type should be text/plain for string upload, not text/csv
        assert metadata.content_type == "text/plain; charset=utf-8"

        # Delete the object
        result = s3_client.delete_object(s3_object_key)
        assert result is True

        # Object shouldn't exist anymore
        assert not s3_client.object_exists(s3_object_key)

    def test_folder_structure_creation(self, s3_client):
        """Test creating standardized folder structure."""
        folders = s3_client.create_folder_structure(
            customer_name="New Corp", customer_number="77777", date="2024-04-01"
        )

        expected_folders = [
            "PaidSearchNav/New_Corp/77777/2024-04-01/inputs/",
            "PaidSearchNav/New_Corp/77777/2024-04-01/outputs/",
            "PaidSearchNav/New_Corp/77777/2024-04-01/outputs/reports/",
            "PaidSearchNav/New_Corp/77777/2024-04-01/outputs/actionable_files/",
        ]

        assert folders == expected_folders

        # Verify folders exist
        for folder in folders:
            assert s3_client.object_exists(folder)

            # Check folder metadata
            metadata = s3_client.get_object_metadata(folder)
            assert metadata.content_type == "application/x-directory"
            assert "customer-name" in metadata.metadata
            assert metadata.metadata["customer-name"] == "New Corp"

    def test_upload_with_custom_metadata(self, s3_client):
        """Test uploading with custom metadata."""
        custom_metadata = {
            "audit-type": "quarterly",
            "generated-by": "psn-system",
            "priority": "high",
        }

        result = s3_client.upload_content(
            content="Audit data here...",
            customer_name="MetaCorp",
            customer_number="88888",
            date="2024-05-01",
            folder="outputs/reports",
            filename="audit.txt",
            metadata=custom_metadata,
        )

        # Verify metadata was stored
        obj_metadata = s3_client.get_object_metadata(result.key)

        # Check custom metadata
        for key, value in custom_metadata.items():
            assert obj_metadata.metadata[key] == value

        # Check automatic metadata
        assert obj_metadata.metadata["customer-name"] == "MetaCorp"
        assert obj_metadata.metadata["customer-number"] == "88888"
        assert obj_metadata.metadata["folder"] == "outputs/reports"
        assert "upload-date" in obj_metadata.metadata

    def test_multipart_upload_threshold(self, s3_client):
        """Test upload behavior with large content."""
        # Create large content (bigger than default multipart threshold)
        large_content = "x" * (200 * 1024 * 1024)  # 200MB

        result = s3_client.upload_content(
            content=large_content,
            customer_name="BigDataCorp",
            customer_number="99999",
            date="2024-06-01",
            folder="inputs",
            filename="large_data.txt",
        )

        assert result.size == len(large_content.encode("utf-8"))

        # Verify we can download it back
        downloaded = s3_client.download_content(result.key, as_text=True)
        assert len(downloaded) == len(large_content)
        assert downloaded[:100] == "x" * 100  # Check first 100 chars

    def test_error_handling(self, s3_client):
        """Test various error conditions."""
        # Try to download non-existent object
        with pytest.raises(S3ClientError, match="S3 object not found"):
            s3_client.download_content("nonexistent/key.txt")

        # Try to get metadata for non-existent object
        with pytest.raises(S3ClientError, match="S3 object not found"):
            s3_client.get_object_metadata("nonexistent/key.txt")

    def test_disabled_client_operations(self):
        """Test operations with disabled S3 client."""
        disabled_config = S3Config(enabled=False)
        disabled_client = S3Client(disabled_config)

        with pytest.raises(S3ClientError, match="S3 client is not enabled"):
            disabled_client.upload_content(
                "test", "Corp", "123", "2024-01-01", "inputs", "test.txt"
            )

        with pytest.raises(S3ClientError, match="S3 client is not enabled"):
            disabled_client.download_content("test/key.txt")

        # object_exists should return False for disabled client
        assert not disabled_client.object_exists("any/key.txt")
