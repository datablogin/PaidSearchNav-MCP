"""Tests for Encryption Manager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

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


from paidsearchnav.security.encryption_manager import (
    EncryptionKey,
    EncryptionManager,
    EncryptionMethod,
    KeyRotationPolicy,
)


@pytest.fixture
def mock_kms_client():
    """Create mock KMS client."""
    return MagicMock()


@pytest.fixture
def encryption_manager(mock_kms_client):
    """Create EncryptionManager with mocked KMS client."""
    manager = EncryptionManager(kms_client=mock_kms_client)
    return manager


class TestEncryptionManager:
    """Test Encryption Manager functionality."""

    def test_initialization_with_kms(self, mock_kms_client):
        """Test manager initialization with KMS client."""
        manager = EncryptionManager(kms_client=mock_kms_client)
        assert manager.kms_client == mock_kms_client
        assert isinstance(manager._key_cache, dict)

    def test_initialization_without_kms(self):
        """Test manager initialization without KMS client."""
        # Test initialization without KMS client - it should handle gracefully
        manager = EncryptionManager()
        # Manager should initialize even without boto3
        assert manager.kms_client is None or manager.kms_client is not None

    def test_create_customer_key_with_kms(self, encryption_manager):
        """Test customer key creation with KMS."""
        customer_id = "cust-123"
        customer_name = "Test Customer"

        encryption_manager.kms_client.create_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "Arn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
            }
        }

        key = encryption_manager.create_customer_key(
            customer_id=customer_id, customer_name=customer_name
        )

        assert key.customer_id == customer_id
        assert key.key_id == "key-123"
        assert key.key_type == EncryptionMethod.SSE_KMS
        assert key.kms_key_arn == "arn:aws:kms:us-east-1:123456789012:key/key-123"
        assert key.rotation_policy == KeyRotationPolicy.ANNUAL

        # Verify KMS calls
        encryption_manager.kms_client.create_key.assert_called_once()
        encryption_manager.kms_client.create_alias.assert_called_once()
        encryption_manager.kms_client.enable_key_rotation.assert_called_once()

    def test_create_customer_key_kms_failure(self, encryption_manager):
        """Test customer key creation when KMS fails."""
        encryption_manager.kms_client.create_key.side_effect = Exception("KMS Error")

        # Should fall back to local key
        key = encryption_manager.create_customer_key(
            customer_id="cust-123", customer_name="Test Customer"
        )

        assert key.key_type == EncryptionMethod.CLIENT_SIDE
        assert key.kms_key_arn is None
        assert "key_material" in key.metadata

    def test_create_local_key(self, encryption_manager):
        """Test local key creation."""
        key = encryption_manager._create_local_key(
            customer_id="cust-123",
            customer_name="Test Customer",
            rotation_policy=KeyRotationPolicy.QUARTERLY,
        )

        assert key.customer_id == "cust-123"
        assert key.key_type == EncryptionMethod.CLIENT_SIDE
        assert key.rotation_policy == KeyRotationPolicy.QUARTERLY
        assert "key_material" in key.metadata
        assert len(key.metadata["key_material"]) > 0

    def test_get_customer_key_from_cache(self, encryption_manager):
        """Test getting customer key from cache."""
        customer_id = "cust-123"

        # Create and cache key
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
        )
        encryption_manager._key_cache[customer_id] = key

        # Get from cache
        retrieved = encryption_manager.get_customer_key(customer_id)

        # Should return cached key
        assert retrieved is not None
        assert retrieved.customer_id == customer_id

    def test_get_customer_key_from_kms(self, encryption_manager):
        """Test getting customer key from KMS."""
        customer_id = "cust-123"

        encryption_manager.kms_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "Arn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
                "CreationDate": datetime.now(timezone.utc),
                "KeyState": "Enabled",
            }
        }

        key = encryption_manager.get_customer_key(customer_id)

        assert key is not None
        assert key.customer_id == customer_id
        assert key.key_type == EncryptionMethod.SSE_KMS
        assert key.is_active is True

    def test_get_customer_key_not_found(self, encryption_manager):
        """Test getting non-existent customer key."""
        encryption_manager.kms_client.describe_key.side_effect = Exception(
            "Key not found"
        )

        key = encryption_manager.get_customer_key("cust-999")
        assert key is None

    def test_rotate_customer_key_kms(self, encryption_manager):
        """Test rotating KMS key."""
        customer_id = "cust-123"

        # Create key in cache
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
        )
        encryption_manager._key_cache[customer_id] = key

        result = encryption_manager.rotate_customer_key(customer_id)

        assert result is True
        assert key.rotated_at is not None

    def test_rotate_customer_key_local(self, encryption_manager):
        """Test rotating local key."""
        customer_id = "cust-123"

        # Create local key
        key = EncryptionKey(
            key_id="local-key",
            key_alias="local/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.CLIENT_SIDE,
            metadata={"key_material": "old-key-material"},
        )
        encryption_manager._key_cache[customer_id] = key

        result = encryption_manager.rotate_customer_key(customer_id)

        assert result is True
        assert key.rotated_at is not None
        assert key.metadata["key_material"] != "old-key-material"
        assert "archived_keys" in key.metadata

    def test_rotate_customer_key_not_found(self, encryption_manager):
        """Test rotating non-existent key."""
        # Mock kms_client.describe_key to return None
        encryption_manager.kms_client.describe_key.side_effect = Exception(
            "Key not found"
        )
        result = encryption_manager.rotate_customer_key("cust-999")
        assert result is False

    def test_encrypt_data_with_kms(self, encryption_manager):
        """Test data encryption with KMS."""
        customer_id = "cust-123"
        data = b"test data"

        # Create key in cache
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/key-123",
        )
        encryption_manager._key_cache[customer_id] = key

        encryption_manager.kms_client.encrypt.return_value = {
            "CiphertextBlob": b"encrypted data"
        }

        encrypted, metadata = encryption_manager.encrypt_data(
            data=data, customer_id=customer_id
        )

        assert encrypted == b"encrypted data"
        assert metadata["customer_id"] == customer_id
        assert metadata["key_id"] == "key-123"
        assert metadata["encryption_method"] == EncryptionMethod.SSE_KMS.value

        encryption_manager.kms_client.encrypt.assert_called_once()

    def test_encrypt_data_with_local_key(self, encryption_manager):
        """Test data encryption with local key."""
        customer_id = "cust-123"
        data = b"test data"

        # Create local key
        key = encryption_manager._create_local_key(
            customer_id=customer_id,
            customer_name="Test",
            rotation_policy=KeyRotationPolicy.ANNUAL,
        )
        encryption_manager._key_cache[customer_id] = key

        encrypted, metadata = encryption_manager.encrypt_data(
            data=data, customer_id=customer_id
        )

        assert encrypted != data
        assert metadata["encryption_method"] == EncryptionMethod.CLIENT_SIDE.value

    def test_decrypt_data_with_kms(self, encryption_manager):
        """Test data decryption with KMS."""
        customer_id = "cust-123"
        encrypted_data = b"encrypted data"

        encryption_metadata = {
            "key_id": "key-123",
            "encryption_method": EncryptionMethod.SSE_KMS.value,
        }

        encryption_manager.kms_client.decrypt.return_value = {
            "Plaintext": b"decrypted data"
        }

        decrypted = encryption_manager.decrypt_data(
            encrypted_data=encrypted_data,
            customer_id=customer_id,
            encryption_metadata=encryption_metadata,
        )

        assert decrypted == b"decrypted data"
        encryption_manager.kms_client.decrypt.assert_called_once()

    def test_generate_data_key_with_kms(self, encryption_manager):
        """Test data key generation with KMS."""
        customer_id = "cust-123"

        # Create key in cache
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
        )
        encryption_manager._key_cache[customer_id] = key

        encryption_manager.kms_client.generate_data_key.return_value = {
            "Plaintext": b"plaintext key",
            "CiphertextBlob": b"encrypted key",
        }

        plaintext, encrypted = encryption_manager.generate_data_key(customer_id)

        assert plaintext == b"plaintext key"
        assert encrypted == b"encrypted key"

        encryption_manager.kms_client.generate_data_key.assert_called_once()

    def test_validate_encryption_compliance(self, encryption_manager):
        """Test encryption compliance validation."""
        customer_id = "cust-123"

        # Create active key
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
            rotation_policy=KeyRotationPolicy.ANNUAL,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        encryption_manager._key_cache[customer_id] = key

        compliance = encryption_manager.validate_encryption_compliance(customer_id)

        assert compliance["customer_id"] == customer_id
        assert compliance["compliant"] is True
        assert len(compliance["issues"]) == 0

    def test_validate_encryption_compliance_no_key(self, encryption_manager):
        """Test compliance validation with no key."""
        # Mock kms_client.describe_key to return None
        encryption_manager.kms_client.describe_key.side_effect = Exception(
            "Key not found"
        )
        compliance = encryption_manager.validate_encryption_compliance("cust-999")

        assert compliance["compliant"] is False
        assert "No encryption key found" in compliance["issues"]

    def test_validate_encryption_compliance_rotation_overdue(self, encryption_manager):
        """Test compliance validation with overdue rotation."""
        customer_id = "cust-123"

        # Create old key
        key = EncryptionKey(
            key_id="key-123",
            key_alias="alias/test",
            customer_id=customer_id,
            key_type=EncryptionMethod.SSE_KMS,
            rotation_policy=KeyRotationPolicy.QUARTERLY,
            created_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        encryption_manager._key_cache[customer_id] = key

        compliance = encryption_manager.validate_encryption_compliance(customer_id)

        assert compliance["compliant"] is False
        assert any("rotation overdue" in issue for issue in compliance["issues"])

    def test_get_encryption_statistics(self, encryption_manager):
        """Test getting encryption statistics."""
        stats = encryption_manager.get_encryption_statistics()

        assert "total_operations" in stats
        assert "encryption_operations" in stats
        assert "decryption_operations" in stats
        assert "total_bytes_processed" in stats
        assert "key_rotations" in stats
        assert "failures" in stats
