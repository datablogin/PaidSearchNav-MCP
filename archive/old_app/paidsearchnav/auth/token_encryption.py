"""Token encryption utilities for OAuth2 tokens."""

import base64
import json
import logging
from typing import Any, Dict

from paidsearchnav.security.encryption_manager import EncryptionManager

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Handles encryption/decryption of OAuth2 tokens."""

    def __init__(self, encryption_manager: EncryptionManager):
        """Initialize token encryption.

        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager

    def encrypt_token(
        self, token: str, customer_id: str, token_type: str = "oauth_token"
    ) -> Dict[str, str]:
        """Encrypt an OAuth2 token.

        Args:
            token: Token to encrypt
            customer_id: Customer ID for key selection
            token_type: Type of token for context

        Returns:
            Dictionary with encrypted token and metadata
        """
        if not token or not token.strip():
            return {"encrypted_token": "", "encryption_metadata": "{}"}

        try:
            # Create encryption context for audit trail
            encryption_context = {
                "token_type": token_type,
                "customer_id": customer_id,
                "purpose": "oauth_token_storage",
            }

            # Encrypt the token
            encrypted_data, metadata = self.encryption_manager.encrypt_data(
                customer_id=customer_id,
                data=token.encode("utf-8"),
                encryption_context=encryption_context,
            )

            # Convert to base64 for storage
            encrypted_b64 = base64.b64encode(encrypted_data).decode("utf-8")

            return {
                "encrypted_token": encrypted_b64,
                "encryption_metadata": json.dumps(metadata),
            }

        except Exception as e:
            logger.error(f"Token encryption failed for customer {customer_id}: {e}")
            # Security: Do not fall back to weak protection, fail securely
            raise RuntimeError(
                f"Token encryption failed for customer {customer_id}. "
                "Cannot store tokens without proper encryption."
            ) from e

    def decrypt_token(
        self, encrypted_token: str, encryption_metadata: str, customer_id: str
    ) -> str:
        """Decrypt an OAuth2 token.

        Args:
            encrypted_token: Base64 encoded encrypted token
            encryption_metadata: Encryption metadata as string
            customer_id: Customer ID for key selection

        Returns:
            Decrypted token string
        """
        if not encrypted_token or not encrypted_token.strip():
            return ""

        try:
            # Parse metadata safely
            try:
                metadata = (
                    json.loads(encryption_metadata) if encryption_metadata else {}
                )
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON metadata for customer {customer_id}, using fallback"
                )
                metadata = {"fallback": True, "method": "base64"}

            # Handle legacy base64 tokens (backward compatibility only)
            if metadata.get("fallback") or metadata.get("method") == "base64":
                logger.warning(
                    f"Found legacy base64 token for customer {customer_id}. "
                    "Consider re-authenticating for better security."
                )
                return base64.b64decode(encrypted_token.encode("utf-8")).decode("utf-8")

            # Decrypt using encryption manager
            encrypted_data = base64.b64decode(encrypted_token.encode("utf-8"))

            decrypted_data = self.encryption_manager.decrypt_data(
                customer_id=customer_id,
                encrypted_data=encrypted_data,
                encryption_metadata=metadata,
            )

            return decrypted_data.decode("utf-8")

        except Exception as e:
            logger.error(f"Token decryption failed for customer {customer_id}: {e}")
            # No fallback decoding - fail securely
            raise RuntimeError(
                f"Token decryption failed for customer {customer_id}. "
                "Token may be corrupted or encryption key may be invalid."
            ) from e

    def encrypt_token_data(
        self, token_data: Dict[str, Any], customer_id: str
    ) -> Dict[str, Any]:
        """Encrypt all sensitive fields in token data.

        Args:
            token_data: Token data dictionary
            customer_id: Customer ID

        Returns:
            Dictionary with encrypted sensitive fields
        """
        encrypted_data = token_data.copy()

        # Fields to encrypt
        sensitive_fields = [
            "access_token",
            "refresh_token",
            "client_secret",
        ]

        for field in sensitive_fields:
            if field in token_data and token_data[field]:
                encryption_result = self.encrypt_token(
                    token_data[field], customer_id, f"{field}_oauth"
                )
                encrypted_data[f"{field}_encrypted"] = encryption_result[
                    "encrypted_token"
                ]
                encrypted_data[f"{field}_metadata"] = encryption_result[
                    "encryption_metadata"
                ]

                # Remove plaintext field
                if not field.endswith("_encrypted"):
                    encrypted_data.pop(field, None)

        return encrypted_data

    def decrypt_token_data(
        self, encrypted_data: Dict[str, Any], customer_id: str
    ) -> Dict[str, Any]:
        """Decrypt all encrypted fields in token data.

        Args:
            encrypted_data: Encrypted token data
            customer_id: Customer ID

        Returns:
            Dictionary with decrypted sensitive fields
        """
        decrypted_data = encrypted_data.copy()

        # Fields to decrypt
        encrypted_fields = [
            "access_token_encrypted",
            "refresh_token_encrypted",
            "client_secret_encrypted",
        ]

        for encrypted_field in encrypted_fields:
            if encrypted_field in encrypted_data:
                # Get corresponding metadata field
                metadata_field = encrypted_field.replace("_encrypted", "_metadata")
                metadata = encrypted_data.get(metadata_field, "{}")

                # Decrypt token
                decrypted_token = self.decrypt_token(
                    encrypted_data[encrypted_field], metadata, customer_id
                )

                # Set decrypted field name
                plain_field = encrypted_field.replace("_encrypted", "")
                decrypted_data[plain_field] = decrypted_token

                # Remove encrypted fields from output
                decrypted_data.pop(encrypted_field, None)
                decrypted_data.pop(metadata_field, None)

        return decrypted_data
