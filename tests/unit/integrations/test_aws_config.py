"""Unit tests for AWS configuration helpers."""

import os
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.core.config import S3Config
from paidsearchnav_mcp.integrations.aws_config import AWSConfigHelper, AWSCredentialError


class TestAWSConfigHelper:
    """Test AWS configuration helper methods."""

    def test_build_s3_key(self):
        """Test S3 key building with standardized folder structure."""
        key = AWSConfigHelper.build_s3_key(
            prefix="PaidSearchNav",
            customer_name="Test Company",
            customer_number="12345",
            date="2024-01-01",
            folder="inputs",
            filename="data.csv",
        )

        expected = "PaidSearchNav/Test_Company/12345/2024-01-01/inputs/data.csv"
        assert key == expected

    def test_build_s3_key_with_special_chars(self):
        """Test S3 key building with special characters in customer name."""
        key = AWSConfigHelper.build_s3_key(
            prefix="PaidSearchNav",
            customer_name="Test/Company & Co",
            customer_number="12345",
            date="2024-01-01",
            folder="outputs/reports",
            filename="report.pdf",
        )

        expected = "PaidSearchNav/Test_Company_&_Co/12345/2024-01-01/outputs/reports/report.pdf"
        assert key == expected

    def test_build_s3_key_with_nested_folder(self):
        """Test S3 key building with nested folder structure."""
        key = AWSConfigHelper.build_s3_key(
            prefix="PaidSearchNav",
            customer_name="TestCorp",
            customer_number="67890",
            date="2024-12-31",
            folder="outputs/actionable_files",
            filename="negatives.csv",
        )

        expected = "PaidSearchNav/TestCorp/67890/2024-12-31/outputs/actionable_files/negatives.csv"
        assert key == expected

    def test_parse_s3_uri_valid(self):
        """Test parsing valid S3 URIs."""
        bucket, key = AWSConfigHelper.parse_s3_uri("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_parse_s3_uri_root_file(self):
        """Test parsing S3 URI with file at root level."""
        bucket, key = AWSConfigHelper.parse_s3_uri("s3://my-bucket/file.txt")
        assert bucket == "my-bucket"
        assert key == "file.txt"

    def test_parse_s3_uri_invalid_format(self):
        """Test parsing invalid S3 URI formats."""
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            AWSConfigHelper.parse_s3_uri("http://example.com/file.txt")

        with pytest.raises(ValueError, match="Invalid S3 URI format - missing key"):
            AWSConfigHelper.parse_s3_uri("s3://my-bucket")

        with pytest.raises(
            ValueError, match="Invalid S3 URI format - empty bucket name"
        ):
            AWSConfigHelper.parse_s3_uri("s3:///path/to/file.txt")

    def test_get_environment_credentials_complete(self):
        """Test getting complete environment credentials."""
        with patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "test-key-id",
                "AWS_SECRET_ACCESS_KEY": "test-secret-key",
                "AWS_SESSION_TOKEN": "test-session-token",
            },
        ):
            creds = AWSConfigHelper.get_environment_credentials()

            assert creds is not None
            assert creds["access_key_id"] == "test-key-id"
            assert creds["secret_access_key"] == "test-secret-key"
            assert creds["session_token"] == "test-session-token"

    def test_get_environment_credentials_without_session_token(self):
        """Test getting environment credentials without session token."""
        with patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "test-key-id",
                "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            },
            clear=True,
        ):
            creds = AWSConfigHelper.get_environment_credentials()

            assert creds is not None
            assert creds["access_key_id"] == "test-key-id"
            assert creds["secret_access_key"] == "test-secret-key"
            assert "session_token" not in creds

    def test_get_environment_credentials_missing(self):
        """Test getting environment credentials when missing."""
        with patch.dict(os.environ, {}, clear=True):
            creds = AWSConfigHelper.get_environment_credentials()
            assert creds is None

    def test_get_environment_credentials_partial(self):
        """Test getting partial environment credentials."""
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test-key-id"}, clear=True):
            creds = AWSConfigHelper.get_environment_credentials()
            assert creds is None

    @patch("urllib.request.urlopen")
    def test_is_running_on_ec2_true(self, mock_urlopen):
        """Test EC2 detection when running on EC2."""
        mock_response = Mock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = AWSConfigHelper.is_running_on_ec2()
        assert result is True

    @patch("urllib.request.urlopen")
    def test_is_running_on_ec2_false(self, mock_urlopen):
        """Test EC2 detection when not running on EC2."""
        mock_urlopen.side_effect = OSError("Connection failed")

        result = AWSConfigHelper.is_running_on_ec2()
        assert result is False

    @patch("boto3.Session")
    def test_get_boto3_session_with_credentials(self, mock_session_class):
        """Test creating boto3 session with explicit credentials."""
        from pydantic import SecretStr

        config = S3Config(
            enabled=True,
            bucket_name="test-bucket",
            region="us-west-2",
            access_key_id="test-key",
            secret_access_key=SecretStr("test-secret"),
        )

        # Mock STS client for credential validation
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_session_class.return_value = mock_session

        session = AWSConfigHelper.get_boto3_session(config)

        assert session == mock_session
        mock_session_class.assert_called_once_with(
            region_name="us-west-2",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )
        mock_session.client.assert_called_once_with("sts")
        mock_sts_client.get_caller_identity.assert_called_once()

    @patch("boto3.Session")
    def test_get_boto3_session_with_session_token(self, mock_session_class):
        """Test creating boto3 session with session token."""
        from pydantic import SecretStr

        config = S3Config(
            enabled=True,
            bucket_name="test-bucket",
            region="us-west-2",
            access_key_id="test-key",
            secret_access_key=SecretStr("test-secret"),
            session_token=SecretStr("test-token"),
        )

        # Mock STS client for credential validation
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_session_class.return_value = mock_session

        session = AWSConfigHelper.get_boto3_session(config)

        mock_session_class.assert_called_once_with(
            region_name="us-west-2",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            aws_session_token="test-token",
        )

    @patch("boto3.Session")
    def test_get_boto3_session_without_credentials(self, mock_session_class):
        """Test creating boto3 session without explicit credentials (IAM role)."""
        config = S3Config(enabled=True, bucket_name="test-bucket", region="us-east-1")

        # Mock STS client for credential validation
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_session_class.return_value = mock_session

        session = AWSConfigHelper.get_boto3_session(config)

        mock_session_class.assert_called_once_with(region_name="us-east-1")

    @patch("boto3.Session")
    def test_get_boto3_session_credential_error(self, mock_session_class):
        """Test boto3 session creation with credential errors."""
        from botocore.exceptions import NoCredentialsError

        config = S3Config(enabled=True, bucket_name="test-bucket", region="us-east-1")

        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()
        mock_session.client.return_value = mock_sts_client
        mock_session_class.return_value = mock_session

        with pytest.raises(
            AWSCredentialError, match="Invalid or missing AWS credentials"
        ):
            AWSConfigHelper.get_boto3_session(config)

    def test_validate_bucket_access_success(self):
        """Test successful bucket access validation."""
        mock_s3_client = Mock()
        mock_s3_client.head_bucket.return_value = {}

        result = AWSConfigHelper.validate_bucket_access(mock_s3_client, "test-bucket")

        assert result is True
        mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_validate_bucket_access_not_found(self):
        """Test bucket access validation when bucket doesn't exist."""
        from botocore.exceptions import ClientError

        mock_s3_client = Mock()
        error = ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadBucket",
        )
        mock_s3_client.head_bucket.side_effect = error

        with pytest.raises(
            AWSCredentialError, match="S3 bucket 'test-bucket' does not exist"
        ):
            AWSConfigHelper.validate_bucket_access(mock_s3_client, "test-bucket")

    def test_validate_bucket_access_denied(self):
        """Test bucket access validation when access is denied."""
        from botocore.exceptions import ClientError

        mock_s3_client = Mock()
        error = ClientError(
            error_response={"Error": {"Code": "403", "Message": "Forbidden"}},
            operation_name="HeadBucket",
        )
        mock_s3_client.head_bucket.side_effect = error

        with pytest.raises(
            AWSCredentialError, match="Access denied to S3 bucket 'test-bucket'"
        ):
            AWSConfigHelper.validate_bucket_access(mock_s3_client, "test-bucket")
