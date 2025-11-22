"""Tests for S3 Security Manager."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Mock ClientError if botocore not available
try:
    from botocore.exceptions import ClientError
except ImportError:

    class ClientError(Exception):
        """Mock ClientError for testing."""

        def __init__(self, error_response, operation_name):
            self.response = error_response
            self.operation_name = operation_name
            super().__init__(str(error_response))


from paidsearchnav.core.config import S3Config
from paidsearchnav.security.s3_security_manager import (
    PreSignedURLConfig,
    S3BucketPolicy,
    S3SecurityManager,
)


@pytest.fixture
def s3_config():
    """Create S3 configuration for testing."""
    config = S3Config(
        enabled=True,
        bucket_name="test-bucket",
        region="us-east-1",
        prefix="customer-data",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
    )
    return config


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client."""
    return MagicMock()


@pytest.fixture
def mock_iam_client():
    """Create mock IAM client."""
    return MagicMock()


@pytest.fixture
def mock_sts_client():
    """Create mock STS client."""
    return MagicMock()


@pytest.fixture
def security_manager(s3_config, mock_s3_client, mock_iam_client, mock_sts_client):
    """Create S3SecurityManager with mocked clients."""
    with patch(
        "paidsearchnav.security.s3_security_manager.AWSConfigHelper"
    ) as mock_helper:
        mock_helper.get_s3_client.return_value = mock_s3_client

        manager = S3SecurityManager(s3_config)
        manager._s3_client = mock_s3_client
        manager._iam_client = mock_iam_client
        manager._sts_client = mock_sts_client

        return manager


class TestS3SecurityManager:
    """Test S3 Security Manager functionality."""

    def test_initialization(self, s3_config):
        """Test manager initialization."""
        with patch(
            "paidsearchnav.security.s3_security_manager.AWSConfigHelper"
        ) as mock_helper:
            mock_helper.get_s3_client.return_value = MagicMock()

            manager = S3SecurityManager(s3_config)

            assert manager.config == s3_config
            mock_helper.get_s3_client.assert_called_once()

    def test_generate_customer_iam_policy(self, security_manager):
        """Test IAM policy generation for customer."""
        customer_id = "cust-123"
        customer_name = "Test Customer"

        policy = security_manager.generate_customer_iam_policy(
            customer_id=customer_id, customer_name=customer_name
        )

        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) == 2

        # Check first statement (object access)
        stmt1 = policy["Statement"][0]
        assert stmt1["Effect"] == "Allow"
        assert "s3:GetObject" in stmt1["Action"]
        assert "s3:PutObject" in stmt1["Action"]

        expected_resource = (
            f"arn:aws:s3:::test-bucket/customer-data/Test_Customer/{customer_id}/*"
        )
        assert expected_resource in stmt1["Resource"]

        # Check conditions
        assert "StringEquals" in stmt1["Condition"]
        # IpAddress should not be present when no IP ranges are configured
        assert "IpAddress" not in stmt1["Condition"]

        # Check second statement (list bucket)
        stmt2 = policy["Statement"][1]
        assert stmt2["Effect"] == "Allow"
        assert "s3:ListBucket" in stmt2["Action"]

    def test_generate_customer_iam_policy_custom_permissions(self, security_manager):
        """Test IAM policy generation with custom permissions."""
        customer_id = "cust-456"
        customer_name = "Test Customer"
        permissions = ["s3:GetObject"]  # Read-only

        policy = security_manager.generate_customer_iam_policy(
            customer_id=customer_id,
            customer_name=customer_name,
            permissions=permissions,
        )

        stmt1 = policy["Statement"][0]
        assert stmt1["Action"] == permissions
        assert "s3:PutObject" not in stmt1["Action"]

    def test_configure_bucket_security(self, security_manager):
        """Test bucket security configuration."""
        result = security_manager.configure_bucket_security()

        assert result is True

        # Verify all security methods were called
        security_manager._s3_client.put_public_access_block.assert_called_once()
        security_manager._s3_client.put_bucket_versioning.assert_called_once()
        security_manager._s3_client.put_bucket_encryption.assert_called_once()
        security_manager._s3_client.put_bucket_policy.assert_called_once()
        security_manager._s3_client.put_bucket_lifecycle_configuration.assert_called_once()

    def test_configure_bucket_security_with_custom_policy(self, security_manager):
        """Test bucket security configuration with custom policy."""
        bucket_policy = S3BucketPolicy(
            enforce_ssl=False,
            block_public_access=True,
            versioning_enabled=False,
            lifecycle_enabled=False,
            server_access_logging=False,
            encryption_type="SSE-KMS",
            kms_key_id="test-kms-key",
        )

        result = security_manager.configure_bucket_security(bucket_policy)

        assert result is True

        # Verify SSL policy was not applied
        security_manager._s3_client.put_bucket_policy.assert_not_called()

        # Verify versioning was not enabled
        security_manager._s3_client.put_bucket_versioning.assert_not_called()

        # Verify KMS encryption was configured
        encryption_call = security_manager._s3_client.put_bucket_encryption.call_args
        rules = encryption_call[1]["ServerSideEncryptionConfiguration"]["Rules"]
        assert (
            rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
        )
        assert (
            rules[0]["ApplyServerSideEncryptionByDefault"]["KMSMasterKeyID"]
            == "test-kms-key"
        )

    def test_configure_bucket_security_failure(self, security_manager):
        """Test bucket security configuration failure handling."""
        security_manager._s3_client.put_public_access_block.side_effect = Exception(
            "Access Denied"
        )

        result = security_manager.configure_bucket_security()

        assert result is False

    def test_generate_presigned_url(self, security_manager):
        """Test pre-signed URL generation."""
        object_key = "customer-data/Test_Customer/cust-123/file.csv"
        expiration = 3600

        security_manager._s3_client.generate_presigned_url.return_value = (
            "https://test-url"
        )

        url, expiry_time = security_manager.generate_presigned_url(
            object_key=object_key,
            operation="GET",
            expiration=expiration,
            customer_id="cust-123",
        )

        assert url == "https://test-url"
        assert isinstance(expiry_time, datetime)

        # Verify S3 client was called correctly
        security_manager._s3_client.generate_presigned_url.assert_called_once()
        call_args = security_manager._s3_client.generate_presigned_url.call_args
        assert call_args[1]["ClientMethod"] == "get_object"
        assert call_args[1]["ExpiresIn"] == expiration

    def test_generate_presigned_url_with_encryption(self, security_manager):
        """Test pre-signed URL generation with encryption requirement."""
        object_key = "customer-data/Test_Customer/cust-123/file.csv"

        security_manager._s3_client.generate_presigned_url.return_value = (
            "https://test-url"
        )

        url, _ = security_manager.generate_presigned_url(
            object_key=object_key, operation="PUT", enforce_encryption=True
        )

        # Verify encryption was required for PUT
        call_args = security_manager._s3_client.generate_presigned_url.call_args
        params = call_args[1]["Params"]
        assert params["ServerSideEncryption"] == "AES256"

    def test_generate_presigned_url_max_expiration(self, security_manager):
        """Test pre-signed URL generation with expiration limit."""
        object_key = "test-file.csv"
        max_expiration = PreSignedURLConfig().max_expiration

        security_manager._s3_client.generate_presigned_url.return_value = (
            "https://test-url"
        )

        # Try to set expiration beyond maximum
        url, _ = security_manager.generate_presigned_url(
            object_key=object_key, expiration=max_expiration + 3600
        )

        # Verify expiration was capped at maximum
        call_args = security_manager._s3_client.generate_presigned_url.call_args
        assert call_args[1]["ExpiresIn"] == max_expiration

    def test_generate_presigned_url_invalid_operation(self, security_manager):
        """Test pre-signed URL generation with invalid operation."""
        with pytest.raises(ValueError, match="Unsupported operation"):
            security_manager.generate_presigned_url(
                object_key="test-file.csv", operation="INVALID"
            )

    def test_validate_customer_access_allowed(self, security_manager):
        """Test customer access validation when allowed."""
        customer_id = "cust-123"
        object_key = "customer-data/Test_Customer/cust-123/2024-01-01/file.csv"

        result = security_manager.validate_customer_access(
            customer_id=customer_id, object_key=object_key
        )

        assert result is True

    def test_validate_customer_access_denied(self, security_manager):
        """Test customer access validation when denied."""
        customer_id = "cust-123"
        object_key = "customer-data/Test_Customer/cust-456/2024-01-01/file.csv"

        result = security_manager.validate_customer_access(
            customer_id=customer_id, object_key=object_key
        )

        assert result is False

    def test_validate_customer_access_invalid_path(self, security_manager):
        """Test customer access validation with invalid path."""
        customer_id = "cust-123"
        object_key = "invalid/path"

        result = security_manager.validate_customer_access(
            customer_id=customer_id, object_key=object_key
        )

        assert result is False

    def test_create_cross_account_role(self, security_manager):
        """Test cross-account role creation."""
        customer_account_id = "123456789012"
        role_name = "CustomerAccessRole"
        external_id = "unique-external-id"

        security_manager._iam_client.create_role.return_value = {
            "Role": {
                "RoleName": role_name,
                "Arn": f"arn:aws:iam::111111111111:role/{role_name}",
            }
        }

        result = security_manager.create_cross_account_role(
            customer_account_id=customer_account_id,
            role_name=role_name,
            external_id=external_id,
        )

        assert result["RoleName"] == role_name

        # Verify IAM client was called
        security_manager._iam_client.create_role.assert_called_once()
        call_args = security_manager._iam_client.create_role.call_args

        # Verify trust policy
        trust_policy = json.loads(call_args[1]["AssumeRolePolicyDocument"])
        assert (
            trust_policy["Statement"][0]["Principal"]["AWS"]
            == f"arn:aws:iam::{customer_account_id}:root"
        )
        assert (
            trust_policy["Statement"][0]["Condition"]["StringEquals"]["sts:ExternalId"]
            == external_id
        )

    def test_create_cross_account_role_failure(self, security_manager):
        """Test cross-account role creation failure."""
        security_manager._iam_client.create_role.side_effect = ClientError(
            {"Error": {"Code": "EntityAlreadyExists"}}, "CreateRole"
        )

        with pytest.raises(ClientError):
            security_manager.create_cross_account_role(
                customer_account_id="123456789012",
                role_name="ExistingRole",
                external_id="test-id",
            )

    def test_revoke_customer_access(self, security_manager):
        """Test customer access revocation."""
        customer_id = "cust-123"

        result = security_manager.revoke_customer_access(customer_id)

        assert result is True

    def test_get_bucket_compliance_status(self, security_manager):
        """Test bucket compliance status check."""
        # Mock S3 responses
        security_manager._s3_client.get_bucket_versioning.return_value = {
            "Status": "Enabled"
        }

        security_manager._s3_client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            }
        }

        security_manager._s3_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }

        compliance = security_manager.get_bucket_compliance_status()

        assert compliance["bucket"] == "test-bucket"
        assert compliance["checks"]["versioning"] is True
        assert compliance["checks"]["encryption"] is True
        assert compliance["checks"]["public_access_blocked"] is True
        assert compliance["is_compliant"] is True
        assert compliance["compliance_score"] == "3/3"

    def test_get_bucket_compliance_status_non_compliant(self, security_manager):
        """Test bucket compliance status when non-compliant."""
        # Mock S3 responses
        security_manager._s3_client.get_bucket_versioning.return_value = {}

        security_manager._s3_client.get_bucket_encryption.side_effect = Exception(
            "No encryption configuration"
        )

        security_manager._s3_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            }
        }

        compliance = security_manager.get_bucket_compliance_status()

        assert compliance["checks"]["versioning"] is False
        assert compliance["checks"]["encryption"] is False
        assert compliance["checks"]["public_access_blocked"] is False
        assert compliance["is_compliant"] is False
        assert compliance["compliance_score"] == "0/3"

    def test_no_s3_client_initialized(self):
        """Test behavior when S3 client is not initialized."""
        config = S3Config(enabled=False)
        manager = S3SecurityManager(config)

        # Test various methods return appropriate defaults
        assert manager.configure_bucket_security() is False

        with pytest.raises(ValueError):
            manager.generate_presigned_url("test-key")

        compliance = manager.get_bucket_compliance_status()
        assert "error" in compliance
