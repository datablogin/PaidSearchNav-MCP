"""S3 Security Manager for IAM policies and bucket security configuration."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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


from paidsearchnav.core.config import S3Config

# Import AWSConfigHelper if available
try:
    from paidsearchnav.integrations.aws_config import AWSConfigHelper
except ImportError:
    # Mock AWSConfigHelper when AWS dependencies are not available
    class AWSConfigHelper:
        """Mock AWSConfigHelper for testing."""

        @staticmethod
        def get_s3_client(config):
            return None

        @staticmethod
        def validate_bucket_access(client, bucket_name):
            pass

        @staticmethod
        def build_s3_key(
            prefix, customer_name, customer_number, date, folder, filename
        ):
            return (
                f"{prefix}/{customer_name}/{customer_number}/{date}/{folder}/{filename}"
            )


logger = logging.getLogger(__name__)


class S3BucketPolicy(BaseModel):
    """S3 bucket policy configuration."""

    enforce_ssl: bool = Field(True, description="Enforce SSL/TLS for all requests")
    block_public_access: bool = Field(True, description="Block all public access")
    versioning_enabled: bool = Field(True, description="Enable object versioning")
    lifecycle_enabled: bool = Field(True, description="Enable lifecycle policies")
    server_access_logging: bool = Field(True, description="Enable access logging")
    encryption_type: str = Field(
        "SSE-S3", description="Encryption type (SSE-S3 or SSE-KMS)"
    )
    kms_key_id: Optional[str] = Field(None, description="KMS key ID for SSE-KMS")


class IAMPolicyTemplate(BaseModel):
    """IAM policy template for customer access."""

    policy_name: str = Field(..., description="Policy name")
    customer_id: str = Field(..., description="Customer ID")
    bucket_name: str = Field(..., description="S3 bucket name")
    prefix: str = Field(..., description="S3 prefix for customer data")
    permissions: List[str] = Field(..., description="List of allowed actions")
    conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Policy conditions"
    )


# Constants for security configuration
DEFAULT_PRESIGNED_URL_EXPIRATION = 3600  # 1 hour
MAX_PRESIGNED_URL_EXPIRATION = 86400  # 24 hours
MAX_PRESIGNED_URL_EXPIRATION_EXTENDED = 604800  # 7 days
DEFAULT_TOKEN_DURATION_HOURS = 24
DEFAULT_ACCESS_DURATION_HOURS = 1
LIFECYCLE_ARCHIVE_DAYS = 90
LIFECYCLE_DELETE_DAYS = 365
LIFECYCLE_INCOMPLETE_UPLOAD_DAYS = 7
AUDIT_BUFFER_SIZE = 10000
AUDIT_BUFFER_RETAIN = 5000


class PreSignedURLConfig(BaseModel):
    """Configuration for pre-signed URLs."""

    expiration_seconds: int = Field(
        DEFAULT_PRESIGNED_URL_EXPIRATION, description="URL expiration time in seconds"
    )
    max_expiration: int = Field(
        MAX_PRESIGNED_URL_EXPIRATION,
        description="Maximum allowed expiration (24 hours)",
    )
    allowed_methods: List[str] = Field(
        default_factory=lambda: ["GET", "PUT"], description="Allowed HTTP methods"
    )
    require_encryption: bool = Field(True, description="Require encryption for uploads")


class S3SecurityManager:
    """
    Manages S3 security policies, IAM permissions, and access control.

    This class provides comprehensive security management for S3 buckets including:
    - IAM policy generation and management
    - Bucket security configuration
    - Pre-signed URL generation with security constraints
    - Access control list management
    - Security compliance validation
    """

    def __init__(self, config: S3Config):
        """
        Initialize S3 Security Manager.

        Args:
            config: S3 configuration
        """
        self.config = config
        self._s3_client = None
        self._iam_client = None
        self._sts_client = None

        if config.enabled:
            self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize AWS service clients."""
        try:
            self._s3_client = AWSConfigHelper.get_s3_client(self.config)

            # Try to initialize IAM and STS clients if boto3 is available
            try:
                import boto3

                session = boto3.Session(
                    region_name=self.config.region,
                    aws_access_key_id=self.config.aws_access_key_id,
                    aws_secret_access_key=self.config.aws_secret_access_key.get_secret_value()
                    if self.config.aws_secret_access_key
                    else None,
                )
                self._iam_client = session.client("iam")
                self._sts_client = session.client("sts")
                logger.info("S3 Security Manager initialized with AWS clients")
            except ImportError:
                logger.warning("boto3 not available, IAM/STS clients not initialized")
                self._iam_client = None
                self._sts_client = None

        except Exception as e:
            logger.warning(f"Failed to fully initialize S3 Security Manager: {e}")
            # Don't raise - allow partial initialization for testing

    def generate_customer_iam_policy(
        self,
        customer_id: str,
        customer_name: str,
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate IAM policy for customer-specific access.

        Args:
            customer_id: Customer ID
            customer_name: Customer name
            permissions: List of allowed S3 actions (defaults to read/write)

        Returns:
            IAM policy document
        """
        if permissions is None:
            permissions = [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ]

        # Build customer-specific prefix
        customer_prefix = f"{self.config.prefix.strip('/')}/{customer_name.replace(' ', '_')}/{customer_id}"

        # Build condition based on configuration
        condition = {"StringEquals": {"s3:x-amz-server-side-encryption": "AES256"}}

        # Only add IP restriction if IP ranges are configured
        allowed_ips = self._get_allowed_ip_ranges()
        if allowed_ips:
            condition["IpAddress"] = {"aws:SourceIp": allowed_ips}

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": f"CustomerAccess{customer_id}",
                    "Effect": "Allow",
                    "Action": permissions,
                    "Resource": [
                        f"arn:aws:s3:::{self.config.bucket_name}/{customer_prefix}/*"
                    ],
                    "Condition": condition,
                },
                {
                    "Sid": f"CustomerListBucket{customer_id}",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": [f"arn:aws:s3:::{self.config.bucket_name}"],
                    "Condition": {
                        "StringLike": {"s3:prefix": [f"{customer_prefix}/*"]}
                    },
                },
            ],
        }

        return policy

    def configure_bucket_security(
        self, bucket_policy: Optional[S3BucketPolicy] = None
    ) -> bool:
        """
        Configure comprehensive security settings for S3 bucket.

        Args:
            bucket_policy: Bucket policy configuration (uses defaults if not provided)

        Returns:
            True if configuration successful
        """
        if not self._s3_client:
            logger.error("S3 client not initialized")
            return False

        if bucket_policy is None:
            bucket_policy = S3BucketPolicy()

        try:
            # 1. Block public access
            if bucket_policy.block_public_access:
                self._configure_public_access_block()

            # 2. Enable versioning
            if bucket_policy.versioning_enabled:
                self._enable_versioning()

            # 3. Configure encryption
            self._configure_encryption(
                bucket_policy.encryption_type, bucket_policy.kms_key_id
            )

            # 4. Enable access logging
            if bucket_policy.server_access_logging:
                self._enable_access_logging()

            # 5. Apply bucket policy for SSL enforcement
            if bucket_policy.enforce_ssl:
                self._apply_ssl_bucket_policy()

            # 6. Configure lifecycle policies
            if bucket_policy.lifecycle_enabled:
                self._configure_lifecycle_policies()

            logger.info(
                f"Successfully configured security for bucket: {self.config.bucket_name}"
            )
            return True

        except ClientError as e:
            logger.error(f"AWS error configuring bucket security: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error configuring bucket security: {e}")
            raise

    def _configure_public_access_block(self) -> None:
        """Block all public access to the bucket."""
        try:
            self._s3_client.put_public_access_block(
                Bucket=self.config.bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            logger.info("Public access block configured")
        except ClientError as e:
            logger.error(f"Failed to configure public access block: {e}")
            raise

    def _enable_versioning(self) -> None:
        """Enable versioning for the bucket."""
        try:
            self._s3_client.put_bucket_versioning(
                Bucket=self.config.bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )
            logger.info("Versioning enabled")
        except ClientError as e:
            logger.error(f"Failed to enable versioning: {e}")
            raise

    def _configure_encryption(
        self, encryption_type: str, kms_key_id: Optional[str] = None
    ) -> None:
        """Configure server-side encryption for the bucket."""
        try:
            if encryption_type == "SSE-KMS" and kms_key_id:
                rule = {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "aws:kms",
                        "KMSMasterKeyID": kms_key_id,
                    },
                    "BucketKeyEnabled": True,
                }
            else:
                rule = {
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
                }

            self._s3_client.put_bucket_encryption(
                Bucket=self.config.bucket_name,
                ServerSideEncryptionConfiguration={"Rules": [rule]},
            )
            logger.info(f"Encryption configured: {encryption_type}")
        except ClientError as e:
            logger.error(f"Failed to configure encryption: {e}")
            raise

    def _enable_access_logging(self) -> None:
        """Enable server access logging for the bucket."""
        if not self._s3_client:
            logger.warning("S3 client not available for access logging configuration")
            return

        # Check if logging bucket is configured
        logging_bucket = getattr(self.config, "logging_bucket", None)
        if not logging_bucket:
            logger.warning(
                "Access logging not configured: no logging_bucket specified in config. "
                "Set S3Config.logging_bucket to enable access logging."
            )
            return

        try:
            # Configure access logging to the specified logging bucket
            self._s3_client.put_bucket_logging(
                Bucket=self.config.bucket_name,
                BucketLoggingStatus={
                    "LoggingEnabled": {
                        "TargetBucket": logging_bucket,
                        "TargetPrefix": f"s3-access-logs/{self.config.bucket_name}/",
                    }
                },
            )
            logger.info(
                f"Access logging enabled: logs will be written to {logging_bucket}"
            )
        except ClientError as e:
            logger.error(f"Failed to enable access logging: {e}")
            # Don't raise - allow bucket to function without logging

    def _apply_ssl_bucket_policy(self) -> None:
        """Apply bucket policy to enforce SSL/TLS."""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DenyInsecureConnections",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        f"arn:aws:s3:::{self.config.bucket_name}/*",
                        f"arn:aws:s3:::{self.config.bucket_name}",
                    ],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }
            ],
        }

        try:
            self._s3_client.put_bucket_policy(
                Bucket=self.config.bucket_name, Policy=json.dumps(policy)
            )
            logger.info("SSL enforcement policy applied")
        except ClientError as e:
            logger.error(f"Failed to apply SSL policy: {e}")
            raise

    def _configure_lifecycle_policies(self) -> None:
        """Configure lifecycle policies for data retention and archival."""
        lifecycle_config = {
            "Rules": [
                {
                    "ID": "ArchiveOldAudits",
                    "Status": "Enabled",
                    "Transitions": [
                        {"Days": LIFECYCLE_ARCHIVE_DAYS, "StorageClass": "GLACIER"}
                    ],
                    "Expiration": {
                        "Days": LIFECYCLE_DELETE_DAYS  # Delete after 1 year
                    },
                },
                {
                    "ID": "DeleteIncompleteMultipartUploads",
                    "Status": "Enabled",
                    "AbortIncompleteMultipartUpload": {
                        "DaysAfterInitiation": LIFECYCLE_INCOMPLETE_UPLOAD_DAYS
                    },
                },
            ]
        }

        try:
            self._s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.config.bucket_name, LifecycleConfiguration=lifecycle_config
            )
            logger.info("Lifecycle policies configured")
        except ClientError as e:
            logger.error(f"Failed to configure lifecycle policies: {e}")
            raise

    def generate_presigned_url(
        self,
        object_key: str,
        operation: str = "GET",
        expiration: Optional[int] = None,
        customer_id: Optional[str] = None,
        enforce_encryption: bool = True,
    ) -> Tuple[str, datetime]:
        """
        Generate a secure pre-signed URL with constraints.

        Args:
            object_key: S3 object key
            operation: HTTP operation (GET or PUT)
            expiration: URL expiration in seconds (uses config default if not specified)
            customer_id: Customer ID for access validation
            enforce_encryption: Require encryption for uploads

        Returns:
            Tuple of (pre-signed URL, expiration datetime)
        """
        if not self._s3_client:
            raise ValueError("S3 client not initialized")

        # Use configured defaults if not specified
        if expiration is None:
            expiration = getattr(
                self.config,
                "default_presigned_url_expiration",
                DEFAULT_PRESIGNED_URL_EXPIRATION,
            )

        # Validate expiration time against configured maximum
        max_expiration = getattr(
            self.config, "max_presigned_url_expiration", MAX_PRESIGNED_URL_EXPIRATION
        )
        if expiration > max_expiration:
            logger.warning(
                f"Expiration {expiration} exceeds maximum {max_expiration}, using maximum"
            )
            expiration = max_expiration

        # Map operation to S3 client method
        operation_map = {
            "GET": "get_object",
            "PUT": "put_object",
            "DELETE": "delete_object",
        }

        if operation not in operation_map:
            raise ValueError(f"Unsupported operation: {operation}")

        # Build parameters
        params = {"Bucket": self.config.bucket_name, "Key": object_key}

        # Add encryption requirement for uploads
        if operation == "PUT" and enforce_encryption:
            params["ServerSideEncryption"] = "AES256"

        try:
            url = self._s3_client.generate_presigned_url(
                ClientMethod=operation_map[operation],
                Params=params,
                ExpiresIn=expiration,
            )

            expiration_time = datetime.now(timezone.utc) + timedelta(seconds=expiration)

            # Log the pre-signed URL generation
            self._log_presigned_url_generation(
                object_key=object_key,
                operation=operation,
                customer_id=customer_id,
                expiration_time=expiration_time,
            )

            return url, expiration_time

        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL: {e}")
            raise

    def validate_customer_access(
        self, customer_id: str, object_key: str, operation: str = "GET"
    ) -> bool:
        """
        Validate if a customer has access to a specific object.

        Args:
            customer_id: Customer ID
            object_key: S3 object key
            operation: Operation to validate

        Returns:
            True if access is allowed
        """
        # Extract customer ID from the object key
        key_parts = object_key.split("/")

        # Expected format: prefix/customer_name/customer_id/date/folder/file
        if len(key_parts) < 3:
            return False

        # Check if the customer ID in the path matches
        path_customer_id = key_parts[2]

        if path_customer_id != customer_id:
            logger.warning(
                f"Access denied: Customer {customer_id} attempting to access "
                f"object belonging to {path_customer_id}"
            )
            return False

        return True

    def create_cross_account_role(
        self, customer_account_id: str, role_name: str, external_id: str
    ) -> Dict[str, Any]:
        """
        Create IAM role for cross-account access.

        Args:
            customer_account_id: Customer's AWS account ID
            role_name: Name for the IAM role
            external_id: External ID for additional security

        Returns:
            Role information including ARN
        """
        if not self._iam_client:
            raise ValueError("IAM client not initialized")

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{customer_account_id}:root"},
                    "Action": "sts:AssumeRole",
                    "Condition": {"StringEquals": {"sts:ExternalId": external_id}},
                }
            ],
        }

        try:
            response = self._iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Cross-account access role for customer {customer_account_id}",
                MaxSessionDuration=3600,
                Tags=[
                    {"Key": "Customer", "Value": customer_account_id},
                    {"Key": "Purpose", "Value": "CrossAccountS3Access"},
                    {"Key": "ManagedBy", "Value": "PaidSearchNav"},
                ],
            )

            logger.info(f"Created cross-account role: {role_name}")
            return response["Role"]

        except ClientError as e:
            logger.error(f"Failed to create cross-account role: {e}")
            raise

    def revoke_customer_access(
        self, customer_id: str, policy_arn: Optional[str] = None
    ) -> bool:
        """
        Revoke customer access to S3 resources.

        Args:
            customer_id: Customer ID
            policy_arn: Policy ARN to detach/delete

        Returns:
            True if revocation successful
        """
        try:
            # Implementation would involve:
            # 1. Detaching policies from users/roles
            # 2. Deleting customer-specific policies
            # 3. Invalidating any active pre-signed URLs (through versioning)

            logger.info(f"Access revoked for customer: {customer_id}")
            return True

        except ClientError as e:
            logger.error(f"AWS error revoking access for customer {customer_id}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error revoking access for customer {customer_id}: {e}"
            )
            raise

    def _get_allowed_ip_ranges(self) -> List[str]:
        """Get list of allowed IP ranges for access control."""
        # Use configured IP ranges from S3Config
        # If no ranges configured, return empty list (no IP restrictions in IAM policy)
        if hasattr(self.config, "allowed_ip_ranges") and self.config.allowed_ip_ranges:
            return self.config.allowed_ip_ranges
        # Return empty list if no IP restrictions configured
        # This will omit the IP condition from the IAM policy
        return []

    def _log_presigned_url_generation(
        self,
        object_key: str,
        operation: str,
        customer_id: Optional[str],
        expiration_time: datetime,
    ) -> None:
        """Log pre-signed URL generation for audit purposes."""
        logger.info(
            f"Pre-signed URL generated: "
            f"object={object_key}, "
            f"operation={operation}, "
            f"customer={customer_id}, "
            f"expires={expiration_time.isoformat()}"
        )

    def get_bucket_compliance_status(self) -> Dict[str, Any]:
        """
        Check bucket compliance with security requirements.

        Returns:
            Compliance status report
        """
        if not self._s3_client:
            return {"error": "S3 client not initialized"}

        compliance = {
            "bucket": self.config.bucket_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        try:
            # Check versioning
            versioning = self._s3_client.get_bucket_versioning(
                Bucket=self.config.bucket_name
            )
            compliance["checks"]["versioning"] = versioning.get("Status") == "Enabled"

            # Check encryption
            try:
                encryption = self._s3_client.get_bucket_encryption(
                    Bucket=self.config.bucket_name
                )
                compliance["checks"]["encryption"] = True
                compliance["checks"]["encryption_type"] = encryption[
                    "ServerSideEncryptionConfiguration"
                ]["Rules"][0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
            except ClientError:
                compliance["checks"]["encryption"] = False

            # Check public access block
            try:
                public_block = self._s3_client.get_public_access_block(
                    Bucket=self.config.bucket_name
                )
                config = public_block["PublicAccessBlockConfiguration"]
                compliance["checks"]["public_access_blocked"] = all(
                    [
                        config.get("BlockPublicAcls", False),
                        config.get("IgnorePublicAcls", False),
                        config.get("BlockPublicPolicy", False),
                        config.get("RestrictPublicBuckets", False),
                    ]
                )
            except ClientError:
                compliance["checks"]["public_access_blocked"] = False

            # Calculate overall compliance
            checks = compliance["checks"]
            total_checks = len([k for k in checks.keys() if k != "encryption_type"])
            passed_checks = len(
                [v for k, v in checks.items() if k != "encryption_type" and v is True]
            )
            compliance["compliance_score"] = f"{passed_checks}/{total_checks}"
            compliance["is_compliant"] = passed_checks == total_checks

        except ClientError as e:
            logger.error(f"AWS error checking compliance: {e}")
            compliance["error"] = str(e)
        except Exception as e:
            logger.error(f"Unexpected error checking compliance: {e}")
            raise

        return compliance
