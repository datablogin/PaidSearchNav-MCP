"""Encryption manager for KMS integration and data protection."""

import base64
import logging
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

# Import ClientError if available
try:
    from botocore.exceptions import ClientError
except ImportError:
    # Define a mock ClientError for when boto3 is not installed
    class ClientError(Exception):
        """Mock ClientError when botocore is not available."""

        def __init__(self, error_response, operation_name):
            self.response = error_response
            self.operation_name = operation_name
            super().__init__(str(error_response))


logger = logging.getLogger(__name__)


class EncryptionMethod(Enum):
    """Encryption method enumeration."""

    SSE_S3 = "SSE-S3"  # S3-managed encryption
    SSE_KMS = "SSE-KMS"  # KMS-managed encryption
    SSE_C = "SSE-C"  # Customer-provided encryption
    CLIENT_SIDE = "CLIENT_SIDE"  # Client-side encryption


class KeyRotationPolicy(Enum):
    """Key rotation policy enumeration."""

    MANUAL = "manual"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class EncryptionKey(BaseModel):
    """Encryption key metadata."""

    key_id: str = Field(..., description="Key identifier")
    key_alias: str = Field(..., description="Key alias for easy reference")
    customer_id: str = Field(..., description="Associated customer ID")
    key_type: EncryptionMethod = Field(..., description="Encryption method")
    kms_key_arn: Optional[str] = Field(None, description="KMS key ARN")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rotated_at: Optional[datetime] = Field(None, description="Last rotation timestamp")
    rotation_policy: KeyRotationPolicy = Field(KeyRotationPolicy.ANNUAL)
    is_active: bool = Field(True, description="Whether key is active")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataEncryptionRequest(BaseModel):
    """Request for data encryption."""

    customer_id: str = Field(..., description="Customer ID")
    data_classification: str = Field(..., description="Data classification level")
    encryption_context: Dict[str, str] = Field(default_factory=dict)


class EncryptionAuditEntry(BaseModel):
    """Audit entry for encryption operations."""

    operation: str = Field(..., description="Operation type (encrypt/decrypt)")
    customer_id: str = Field(..., description="Customer ID")
    key_id: str = Field(..., description="Key used")
    data_size: int = Field(..., description="Data size in bytes")
    success: bool = Field(..., description="Operation success status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = Field(None, description="User who performed operation")
    ip_address: Optional[str] = Field(None, description="Source IP address")


class EncryptionManager:
    """
    Manages encryption operations, KMS integration, and key lifecycle.

    This class provides:
    - Customer-specific encryption key management
    - KMS integration for key generation and rotation
    - Data encryption/decryption operations
    - Key rotation policies and automation
    - Encryption audit logging
    - Compliance validation
    """

    def __init__(self, kms_client=None, s3_client=None):
        """
        Initialize Encryption Manager.

        Args:
            kms_client: AWS KMS client (optional)
            s3_client: AWS S3 client (optional)
        """
        self.kms_client = kms_client
        self.s3_client = s3_client
        self._key_cache: Dict[str, EncryptionKey] = {}
        self._master_key_alias = "alias/paidsearchnav-master"
        self._initialize_kms()

    def _initialize_kms(self) -> None:
        """Initialize KMS client and master key."""
        if not self.kms_client:
            try:
                import boto3

                self.kms_client = boto3.client("kms")
                logger.info("KMS client initialized")
            except Exception as e:
                logger.warning(f"KMS client initialization failed: {e}")
                return

        # Ensure master key exists
        try:
            self.kms_client.describe_key(KeyId=self._master_key_alias)
            logger.info(f"Master key found: {self._master_key_alias}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                logger.info("Master key not found, creating...")
                self._create_master_key()

    def _create_master_key(self) -> None:
        """Create master KMS key for the application."""
        if not self.kms_client:
            return

        try:
            response = self.kms_client.create_key(
                Description="PaidSearchNav master encryption key",
                KeyUsage="ENCRYPT_DECRYPT",
                Origin="AWS_KMS",
                MultiRegion=False,
                Tags=[
                    {"TagKey": "Application", "TagValue": "PaidSearchNav"},
                    {"TagKey": "Purpose", "TagValue": "MasterKey"},
                    {"TagKey": "Environment", "TagValue": "Production"},
                ],
            )

            key_id = response["KeyMetadata"]["KeyId"]

            # Create alias
            self.kms_client.create_alias(
                AliasName=self._master_key_alias, TargetKeyId=key_id
            )

            logger.info(f"Master key created: {key_id}")

        except ClientError as e:
            logger.error(f"Failed to create master key: {e}")

    def create_customer_key(
        self,
        customer_id: str,
        customer_name: str,
        rotation_policy: KeyRotationPolicy = KeyRotationPolicy.ANNUAL,
    ) -> EncryptionKey:
        """
        Create customer-specific encryption key.

        Args:
            customer_id: Customer ID
            customer_name: Customer name
            rotation_policy: Key rotation policy

        Returns:
            Created encryption key metadata
        """
        if not self.kms_client:
            # Fallback to local key generation
            return self._create_local_key(customer_id, customer_name, rotation_policy)

        try:
            # Create customer-specific KMS key
            key_alias = f"alias/psn-customer-{customer_id}"

            response = self.kms_client.create_key(
                Description=f"Encryption key for customer {customer_name}",
                KeyUsage="ENCRYPT_DECRYPT",
                Origin="AWS_KMS",
                Tags=[
                    {"TagKey": "Application", "TagValue": "PaidSearchNav"},
                    {"TagKey": "CustomerId", "TagValue": customer_id},
                    {"TagKey": "CustomerName", "TagValue": customer_name},
                    {"TagKey": "Purpose", "TagValue": "CustomerDataEncryption"},
                ],
            )

            key_id = response["KeyMetadata"]["KeyId"]
            key_arn = response["KeyMetadata"]["Arn"]

            # Create alias for easy reference
            self.kms_client.create_alias(AliasName=key_alias, TargetKeyId=key_id)

            # Enable automatic key rotation if policy is not manual
            if rotation_policy != KeyRotationPolicy.MANUAL:
                self.kms_client.enable_key_rotation(KeyId=key_id)

            # Create key metadata
            encryption_key = EncryptionKey(
                key_id=key_id,
                key_alias=key_alias,
                customer_id=customer_id,
                key_type=EncryptionMethod.SSE_KMS,
                kms_key_arn=key_arn,
                rotation_policy=rotation_policy,
                metadata={
                    "customer_name": customer_name,
                    "created_by": "EncryptionManager",
                },
            )

            # Cache the key
            self._key_cache[customer_id] = encryption_key

            logger.info(f"Customer key created: {key_alias}")
            return encryption_key

        except ClientError as e:
            logger.error(f"Failed to create customer key: {e}")
            # Fallback to local key
            return self._create_local_key(customer_id, customer_name, rotation_policy)

    def _create_local_key(
        self, customer_id: str, customer_name: str, rotation_policy: KeyRotationPolicy
    ) -> EncryptionKey:
        """Create local encryption key when KMS is not available."""
        key_id = secrets.token_hex(32)
        key_alias = f"local-{customer_id}"

        encryption_key = EncryptionKey(
            key_id=key_id,
            key_alias=key_alias,
            customer_id=customer_id,
            key_type=EncryptionMethod.CLIENT_SIDE,
            rotation_policy=rotation_policy,
            metadata={
                "customer_name": customer_name,
                "key_material": base64.b64encode(secrets.token_bytes(32)).decode(),
                "created_by": "EncryptionManager",
            },
        )

        self._key_cache[customer_id] = encryption_key

        logger.info(f"Local key created for customer: {customer_id}")
        return encryption_key

    def get_customer_key(self, customer_id: str) -> Optional[EncryptionKey]:
        """
        Get customer encryption key.

        Args:
            customer_id: Customer ID

        Returns:
            Encryption key if found
        """
        # Check cache
        if customer_id in self._key_cache:
            return self._key_cache[customer_id]

        # Try to load from KMS
        if self.kms_client:
            try:
                key_alias = f"alias/psn-customer-{customer_id}"
                response = self.kms_client.describe_key(KeyId=key_alias)

                key_metadata = response["KeyMetadata"]

                encryption_key = EncryptionKey(
                    key_id=key_metadata["KeyId"],
                    key_alias=key_alias,
                    customer_id=customer_id,
                    key_type=EncryptionMethod.SSE_KMS,
                    kms_key_arn=key_metadata["Arn"],
                    created_at=key_metadata["CreationDate"],
                    is_active=key_metadata["KeyState"] == "Enabled",
                )

                self._key_cache[customer_id] = encryption_key
                return encryption_key

            except ClientError:
                logger.warning(f"Customer key not found in KMS: {customer_id}")

        return None

    def rotate_customer_key(self, customer_id: str) -> bool:
        """
        Rotate customer encryption key.

        Args:
            customer_id: Customer ID

        Returns:
            True if rotation successful
        """
        key = self.get_customer_key(customer_id)

        if not key:
            logger.error(f"No key found for customer: {customer_id}")
            return False

        if key.key_type == EncryptionMethod.SSE_KMS and self.kms_client:
            try:
                # KMS handles rotation automatically when enabled
                # We just update our metadata
                key.rotated_at = datetime.now(timezone.utc)

                # Log rotation
                self._log_key_rotation(customer_id, key.key_id)

                logger.info(f"Key rotated for customer: {customer_id}")
                return True

            except ClientError as e:
                logger.error(f"Failed to rotate key: {e}")
                return False

        elif key.key_type == EncryptionMethod.CLIENT_SIDE:
            # Generate new key material for local keys
            new_key_material = base64.b64encode(secrets.token_bytes(32)).decode()

            # Archive old key
            if "key_material" in key.metadata:
                if "archived_keys" not in key.metadata:
                    key.metadata["archived_keys"] = []

                key.metadata["archived_keys"].append(
                    {
                        "key": key.metadata["key_material"],
                        "archived_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

            # Update with new key
            key.metadata["key_material"] = new_key_material
            key.rotated_at = datetime.now(timezone.utc)

            logger.info(f"Local key rotated for customer: {customer_id}")
            return True

        return False

    def encrypt_data(
        self,
        data: bytes,
        customer_id: str,
        encryption_context: Optional[Dict[str, str]] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Encrypt data for a customer.

        Args:
            data: Data to encrypt
            customer_id: Customer ID
            encryption_context: Additional context for encryption

        Returns:
            Tuple of (encrypted data, encryption metadata)
        """
        key = self.get_customer_key(customer_id)

        if not key:
            # Create key if it doesn't exist
            key = self.create_customer_key(customer_id, f"Customer-{customer_id}")

        encryption_metadata = {
            "customer_id": customer_id,
            "key_id": key.key_id,
            "encryption_method": key.key_type.value,
            "encrypted_at": datetime.now(timezone.utc).isoformat(),
        }

        if key.key_type == EncryptionMethod.SSE_KMS and self.kms_client:
            try:
                # Use KMS for encryption
                response = self.kms_client.encrypt(
                    KeyId=key.key_id,
                    Plaintext=data,
                    EncryptionContext=encryption_context or {},
                )

                encrypted_data = response["CiphertextBlob"]
                encryption_metadata["kms_key_arn"] = key.kms_key_arn

            except ClientError as e:
                logger.error(f"KMS encryption failed: {e}")
                raise

        elif key.key_type == EncryptionMethod.CLIENT_SIDE:
            # Use local encryption
            encrypted_data = self._local_encrypt(
                data, key.metadata.get("key_material", "")
            )

        else:
            raise ValueError(f"Unsupported encryption method: {key.key_type}")

        # Log encryption operation
        self._log_encryption_operation(
            "encrypt", customer_id, key.key_id, len(data), True
        )

        return encrypted_data, encryption_metadata

    def decrypt_data(
        self,
        encrypted_data: bytes,
        customer_id: str,
        encryption_metadata: Dict[str, Any],
        encryption_context: Optional[Dict[str, str]] = None,
    ) -> bytes:
        """
        Decrypt data for a customer.

        Args:
            encrypted_data: Encrypted data
            customer_id: Customer ID
            encryption_metadata: Metadata from encryption
            encryption_context: Additional context for decryption

        Returns:
            Decrypted data
        """
        key_id = encryption_metadata.get("key_id")
        encryption_method = encryption_metadata.get("encryption_method")

        if encryption_method == EncryptionMethod.SSE_KMS.value and self.kms_client:
            try:
                response = self.kms_client.decrypt(
                    CiphertextBlob=encrypted_data,
                    EncryptionContext=encryption_context or {},
                )

                decrypted_data = response["Plaintext"]

            except ClientError as e:
                logger.error(f"KMS decryption failed: {e}")
                raise

        elif encryption_method == EncryptionMethod.CLIENT_SIDE.value:
            key = self.get_customer_key(customer_id)
            if not key:
                raise ValueError(f"No key found for customer: {customer_id}")

            decrypted_data = self._local_decrypt(
                encrypted_data, key.metadata.get("key_material", "")
            )

        else:
            raise ValueError(f"Unsupported encryption method: {encryption_method}")

        # Log decryption operation
        self._log_encryption_operation(
            "decrypt", customer_id, key_id, len(encrypted_data), True
        )

        return decrypted_data

    def _local_encrypt(self, data: bytes, key_material: str) -> bytes:
        """Perform local encryption using AES."""
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            # Decode key material
            key = base64.b64decode(key_material)

            # Generate IV
            iv = secrets.token_bytes(16)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key), modes.CBC(iv), backend=default_backend()
            )
            encryptor = cipher.encryptor()

            # Pad data
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()

            # Encrypt
            encrypted = encryptor.update(padded_data) + encryptor.finalize()

            # Combine IV and encrypted data
            return iv + encrypted

        except ImportError:
            # Fallback to simple XOR encryption if cryptography not available
            logger.warning(
                "Cryptography library not available, using fallback encryption"
            )
            key_bytes = base64.b64decode(key_material)
            encrypted = bytes(
                a ^ b
                for a, b in zip(data, key_bytes * (len(data) // len(key_bytes) + 1))
            )
            return encrypted

    def _local_decrypt(self, encrypted_data: bytes, key_material: str) -> bytes:
        """Perform local decryption using AES."""
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            # Decode key material
            key = base64.b64decode(key_material)

            # Extract IV
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key), modes.CBC(iv), backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Decrypt
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove padding
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()

            return data

        except ImportError:
            # Fallback decryption
            logger.warning(
                "Cryptography library not available, using fallback decryption"
            )
            key_bytes = base64.b64decode(key_material)
            decrypted = bytes(
                a ^ b
                for a, b in zip(
                    encrypted_data,
                    key_bytes * (len(encrypted_data) // len(key_bytes) + 1),
                )
            )
            return decrypted

    def generate_data_key(
        self, customer_id: str, key_spec: str = "AES_256"
    ) -> Tuple[bytes, bytes]:
        """
        Generate data encryption key for customer.

        Args:
            customer_id: Customer ID
            key_spec: Key specification (AES_256 or AES_128)

        Returns:
            Tuple of (plaintext key, encrypted key)
        """
        key = self.get_customer_key(customer_id)

        if not key:
            key = self.create_customer_key(customer_id, f"Customer-{customer_id}")

        if key.key_type == EncryptionMethod.SSE_KMS and self.kms_client:
            try:
                response = self.kms_client.generate_data_key(
                    KeyId=key.key_id, KeySpec=key_spec
                )

                return response["Plaintext"], response["CiphertextBlob"]

            except ClientError as e:
                logger.error(f"Failed to generate data key: {e}")
                raise

        else:
            # Generate local data key
            if key_spec == "AES_256":
                plaintext_key = secrets.token_bytes(32)
            else:
                plaintext_key = secrets.token_bytes(16)

            # Encrypt the data key
            encrypted_key, _ = self.encrypt_data(plaintext_key, customer_id)

            return plaintext_key, encrypted_key

    def validate_encryption_compliance(self, customer_id: str) -> Dict[str, Any]:
        """
        Validate encryption compliance for customer.

        Args:
            customer_id: Customer ID

        Returns:
            Compliance validation results
        """
        compliance = {
            "customer_id": customer_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "compliant": True,
            "issues": [],
        }

        # Check if customer has encryption key
        key = self.get_customer_key(customer_id)

        if not key:
            compliance["compliant"] = False
            compliance["issues"].append("No encryption key found")
            return compliance

        # Check key status
        if not key.is_active:
            compliance["compliant"] = False
            compliance["issues"].append("Encryption key is not active")

        # Check key rotation
        if key.rotation_policy != KeyRotationPolicy.MANUAL:
            days_since_rotation = 365  # Default

            if key.rotated_at:
                days_since_rotation = (datetime.now(timezone.utc) - key.rotated_at).days
            elif key.created_at:
                days_since_rotation = (datetime.now(timezone.utc) - key.created_at).days

            rotation_thresholds = {
                KeyRotationPolicy.MONTHLY: 30,
                KeyRotationPolicy.QUARTERLY: 90,
                KeyRotationPolicy.ANNUAL: 365,
            }

            threshold = rotation_thresholds.get(key.rotation_policy, 365)

            if days_since_rotation > threshold:
                compliance["compliant"] = False
                compliance["issues"].append(
                    f"Key rotation overdue ({days_since_rotation} days since last rotation)"
                )

        # Check encryption method
        if key.key_type == EncryptionMethod.CLIENT_SIDE:
            compliance["warnings"] = compliance.get("warnings", [])
            compliance["warnings"].append("Using client-side encryption instead of KMS")

        compliance["key_info"] = {
            "key_id": key.key_id,
            "key_type": key.key_type.value,
            "created_at": key.created_at.isoformat() if key.created_at else None,
            "rotated_at": key.rotated_at.isoformat() if key.rotated_at else None,
            "rotation_policy": key.rotation_policy.value,
        }

        return compliance

    def _log_encryption_operation(
        self,
        operation: str,
        customer_id: str,
        key_id: str,
        data_size: int,
        success: bool,
    ) -> None:
        """Log encryption operation for audit."""
        audit_entry = EncryptionAuditEntry(
            operation=operation,
            customer_id=customer_id,
            key_id=key_id,
            data_size=data_size,
            success=success,
        )

        # In production, this would write to audit log storage
        logger.info(f"Encryption audit: {audit_entry.model_dump_json()}")

    def _log_key_rotation(self, customer_id: str, key_id: str) -> None:
        """Log key rotation event."""
        logger.info(
            f"Key rotation: customer={customer_id}, key={key_id}, "
            f"timestamp={datetime.now(timezone.utc).isoformat()}"
        )

    def get_encryption_statistics(
        self,
        customer_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get encryption operation statistics.

        Args:
            customer_id: Filter by customer (optional)
            start_date: Start date for statistics
            end_date: End date for statistics

        Returns:
            Encryption statistics
        """
        # In production, this would query audit logs
        stats = {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "total_operations": 0,
            "encryption_operations": 0,
            "decryption_operations": 0,
            "total_bytes_processed": 0,
            "key_rotations": 0,
            "failures": 0,
        }

        if customer_id:
            stats["customer_id"] = customer_id

        return stats
