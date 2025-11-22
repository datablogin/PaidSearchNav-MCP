"""Unit tests for S3 client service."""

from datetime import datetime, timezone
from unittest.mock import Mock, mock_open, patch

import pytest

from paidsearchnav_mcp.core.circuit_breaker import CircuitBreakerConfig
from paidsearchnav_mcp.core.config import S3Config
from paidsearchnav_mcp.integrations.s3 import (
    S3Client,
    S3ClientError,
    S3Object,
    S3UploadResult,
)


class TestS3Object:
    """Test S3Object model."""

    def test_s3_object_creation(self):
        """Test S3Object creation with required fields."""
        obj = S3Object(
            key="test/key.txt",
            size=1024,
            last_modified=datetime.now(timezone.utc),
            etag="abc123",
        )

        assert obj.key == "test/key.txt"
        assert obj.size == 1024
        assert obj.etag == "abc123"
        assert obj.content_type is None
        assert obj.metadata == {}

    def test_s3_object_with_metadata(self):
        """Test S3Object creation with metadata."""
        metadata = {"customer-name": "TestCorp", "upload-type": "csv"}

        obj = S3Object(
            key="test/key.txt",
            size=2048,
            last_modified=datetime.now(timezone.utc),
            etag="def456",
            content_type="text/csv",
            metadata=metadata,
        )

        assert obj.content_type == "text/csv"
        assert obj.metadata == metadata


class TestS3UploadResult:
    """Test S3UploadResult model."""

    def test_upload_result_creation(self):
        """Test S3UploadResult creation."""
        result = S3UploadResult(
            key="test/upload.csv", bucket="test-bucket", size=1024, etag="abc123"
        )

        assert result.key == "test/upload.csv"
        assert result.bucket == "test-bucket"
        assert result.size == 1024
        assert result.etag == "abc123"
        assert result.version_id is None


class TestS3Client:
    """Test S3Client service."""

    def test_s3_client_disabled(self):
        """Test S3Client with disabled configuration."""
        config = S3Config(enabled=False)
        client = S3Client(config)

        assert client.config.enabled is False
        assert client._client is None

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_s3_client_initialization_success(self, mock_validate, mock_get_client):
        """Test successful S3Client initialization."""
        config = S3Config(enabled=True, bucket_name="test-bucket", region="us-west-2")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        client = S3Client(config)

        assert client.config == config
        assert client._client == mock_s3_client
        mock_get_client.assert_called_once_with(config)
        mock_validate.assert_called_once_with(mock_s3_client, "test-bucket")

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    def test_s3_client_initialization_failure(self, mock_get_client):
        """Test S3Client initialization failure."""
        from paidsearchnav.integrations.aws_config import AWSCredentialError

        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_get_client.side_effect = AWSCredentialError("Invalid credentials")

        with pytest.raises(S3ClientError, match="Failed to initialize S3 client"):
            S3Client(config)

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_s3_client_with_circuit_breaker(self, mock_validate, mock_get_client):
        """Test S3Client with circuit breaker configuration."""
        config = S3Config(enabled=True, bucket_name="test-bucket")
        circuit_config = CircuitBreakerConfig(
            enabled=True, failure_threshold=3, recovery_timeout=60
        )

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        client = S3Client(config, circuit_config)

        assert client._circuit_breaker is not None
        assert client._circuit_breaker._failure_threshold == 3

    def test_get_content_type_explicit(self):
        """Test content type determination with explicit type."""
        config = S3Config(enabled=False)
        client = S3Client(config)

        content_type = client._get_content_type("test.csv", "application/json")
        assert content_type == "application/json"

    def test_get_content_type_guessed(self):
        """Test content type determination with guessing."""
        config = S3Config(enabled=False)
        client = S3Client(config)

        content_type = client._get_content_type("test.csv")
        assert content_type == "text/csv"

        content_type = client._get_content_type("test.pdf")
        assert content_type == "application/pdf"

    def test_get_content_type_unknown(self):
        """Test content type determination for unknown extension."""
        config = S3Config(enabled=False)
        client = S3Client(config)

        content_type = client._get_content_type("test.unknown")
        assert content_type == "application/octet-stream"

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test,data,csv")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.stat")
    def test_upload_file_success(
        self, mock_stat, mock_exists, mock_file, mock_validate, mock_get_client
    ):
        """Test successful file upload."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        # Mock file system
        mock_exists.return_value = True
        mock_stat_obj = Mock()
        mock_stat_obj.st_size = 13  # Length of test data
        mock_stat.return_value = mock_stat_obj

        # Mock S3 client
        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock S3 responses
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}
        mock_s3_client.head_object.return_value = {
            "ETag": '"abc123"',
            "ContentLength": 13,
        }

        client = S3Client(config)

        result = client.upload_file(
            file_path="/tmp/test.csv",
            customer_name="Test Corp",
            customer_number="12345",
            date="2024-01-01",
            folder="inputs",
            filename="data.csv",
        )

        assert isinstance(result, S3UploadResult)
        assert result.key == "PaidSearchNav/Test_Corp/12345/2024-01-01/inputs/data.csv"
        assert result.bucket == "test-bucket"
        assert result.size == 13
        assert result.etag == "abc123"

    def test_upload_file_disabled_client(self):
        """Test file upload with disabled client."""
        config = S3Config(enabled=False)
        client = S3Client(config)

        with pytest.raises(
            S3ClientError, match="S3 client is not enabled or initialized"
        ):
            client.upload_file(
                "/tmp/test.csv", "TestCorp", "12345", "2024-01-01", "inputs"
            )

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    @patch("pathlib.Path.exists")
    def test_upload_file_not_exists(self, mock_exists, mock_validate, mock_get_client):
        """Test file upload when file doesn't exist."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_exists.return_value = False

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        client = S3Client(config)

        with pytest.raises(S3ClientError, match="File does not exist"):
            client.upload_file(
                "/tmp/nonexistent.csv", "TestCorp", "12345", "2024-01-01", "inputs"
            )

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_upload_content_string(self, mock_validate, mock_get_client):
        """Test content upload with string content."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock S3 response
        mock_s3_client.put_object.return_value = {"ETag": '"def456"'}

        client = S3Client(config)

        result = client.upload_content(
            content="Hello, World!",
            customer_name="TestCorp",
            customer_number="54321",
            date="2024-01-15",
            folder="outputs",
            filename="greeting.txt",
        )

        assert (
            result.key == "PaidSearchNav/TestCorp/54321/2024-01-15/outputs/greeting.txt"
        )
        assert result.size == 13
        assert result.etag == "def456"

        # Verify put_object was called with UTF-8 encoded content
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Body"] == b"Hello, World!"
        assert call_args[1]["ContentType"] == "text/plain; charset=utf-8"

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_upload_content_bytes(self, mock_validate, mock_get_client):
        """Test content upload with bytes content."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        mock_s3_client.put_object.return_value = {"ETag": '"ghi789"'}

        client = S3Client(config)

        binary_data = b"\x89PNG\r\n\x1a\n"  # PNG header
        result = client.upload_content(
            content=binary_data,
            customer_name="TestCorp",
            customer_number="99999",
            date="2024-02-01",
            folder="outputs/reports",
            filename="image.png",
        )

        assert result.size == len(binary_data)

        # Verify put_object was called with binary data
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Body"] == binary_data
        assert call_args[1]["ContentType"] == "image/png"

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_download_content_success(self, mock_validate, mock_get_client):
        """Test successful content download."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock S3 response with streaming body
        mock_body = Mock()
        mock_body.read.return_value = b"Downloaded content"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        client = S3Client(config)

        content = client.download_content("test/file.txt")

        assert content == b"Downloaded content"
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_download_content_as_text(self, mock_validate, mock_get_client):
        """Test content download as text."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock S3 response
        mock_body = Mock()
        mock_body.read.return_value = b"Hello, World!"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        client = S3Client(config)

        content = client.download_content("test/file.txt", as_text=True)

        assert content == "Hello, World!"
        assert isinstance(content, str)

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_download_content_decode_error(self, mock_validate, mock_get_client):
        """Test content download with decode error."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock S3 response with non-UTF8 content
        mock_body = Mock()
        mock_body.read.return_value = b"\x89PNG\r\n\x1a\n"  # Binary PNG data
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        client = S3Client(config)

        with pytest.raises(S3ClientError, match="Cannot decode S3 object as text"):
            client.download_content("test/image.png", as_text=True)

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_list_objects_success(self, mock_validate, mock_get_client):
        """Test successful object listing."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        # Mock paginator response
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        test_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "PaidSearchNav/TestCorp/12345/2024-01-01/inputs/data.csv",
                        "Size": 1024,
                        "LastModified": test_time,
                        "ETag": '"abc123"',
                    },
                    {
                        "Key": "PaidSearchNav/TestCorp/12345/2024-01-01/outputs/report.pdf",
                        "Size": 2048,
                        "LastModified": test_time,
                        "ETag": '"def456"',
                    },
                ]
            }
        ]

        client = S3Client(config)

        objects = client.list_objects(customer_name="TestCorp", customer_number="12345")

        assert len(objects) == 2
        assert all(isinstance(obj, S3Object) for obj in objects)
        assert (
            objects[0].key == "PaidSearchNav/TestCorp/12345/2024-01-01/inputs/data.csv"
        )
        assert objects[0].size == 1024
        assert (
            objects[1].key
            == "PaidSearchNav/TestCorp/12345/2024-01-01/outputs/report.pdf"
        )
        assert objects[1].size == 2048

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_object_exists_true(self, mock_validate, mock_get_client):
        """Test object existence check when object exists."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        mock_s3_client.head_object.return_value = {}

        client = S3Client(config)

        exists = client.object_exists("test/file.txt")

        assert exists is True
        mock_s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_object_exists_false(self, mock_validate, mock_get_client):
        """Test object existence check when object doesn't exist."""
        from botocore.exceptions import ClientError

        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        error = ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject",
        )
        mock_s3_client.head_object.side_effect = error

        client = S3Client(config)

        exists = client.object_exists("test/nonexistent.txt")

        assert exists is False

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_delete_object_success(self, mock_validate, mock_get_client):
        """Test successful object deletion."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        mock_s3_client.delete_object.return_value = {}

        client = S3Client(config)

        result = client.delete_object("test/file.txt")

        assert result is True
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.get_s3_client")
    @patch("paidsearchnav.integrations.s3.AWSConfigHelper.validate_bucket_access")
    def test_create_folder_structure(self, mock_validate, mock_get_client):
        """Test folder structure creation."""
        config = S3Config(enabled=True, bucket_name="test-bucket")

        mock_s3_client = Mock()
        mock_get_client.return_value = mock_s3_client
        mock_validate.return_value = True

        mock_s3_client.put_object.return_value = {}

        client = S3Client(config)

        folders = client.create_folder_structure(
            customer_name="TestCorp", customer_number="12345", date="2024-01-01"
        )

        expected_folders = [
            "PaidSearchNav/TestCorp/12345/2024-01-01/inputs/",
            "PaidSearchNav/TestCorp/12345/2024-01-01/outputs/",
            "PaidSearchNav/TestCorp/12345/2024-01-01/outputs/reports/",
            "PaidSearchNav/TestCorp/12345/2024-01-01/outputs/actionable_files/",
        ]

        assert folders == expected_folders
        assert mock_s3_client.put_object.call_count == 4

        # Verify each folder was created with correct parameters
        for call in mock_s3_client.put_object.call_args_list:
            assert call[1]["Body"] == b""
            assert call[1]["ContentType"] == "application/x-directory"
            assert "customer-name" in call[1]["Metadata"]
