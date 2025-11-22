"""AWS configuration helpers for S3 integration."""

import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from paidsearchnav.core.config import S3Config

logger = logging.getLogger(__name__)

# Constants for AWS operations
DEFAULT_EC2_METADATA_TIMEOUT = 2  # seconds - configurable timeout
MAX_EC2_METADATA_TIMEOUT = 10  # seconds - maximum allowed timeout


class AWSCredentialError(Exception):
    """Raised when AWS credentials are invalid or missing."""

    pass


class AWSConfigHelper:
    """Helper class for AWS configuration and credential management."""

    @staticmethod
    def get_boto3_session(config: S3Config) -> boto3.Session:
        """
        Create a boto3 session with appropriate credentials.

        Args:
            config: S3 configuration containing credentials and region

        Returns:
            boto3.Session: Configured session

        Raises:
            AWSCredentialError: If credentials are invalid or missing
        """
        session_kwargs: Dict[str, Any] = {"region_name": config.region}

        # Use explicit credentials if provided
        if config.access_key_id and config.secret_access_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": config.access_key_id,
                    "aws_secret_access_key": config.secret_access_key.get_secret_value(),
                }
            )

            # Include session token for temporary credentials
            if config.session_token:
                session_kwargs["aws_session_token"] = (
                    config.session_token.get_secret_value()
                )

        try:
            session = boto3.Session(**session_kwargs)

            # Test credentials by attempting to get caller identity
            sts_client = session.client("sts")
            identity = sts_client.get_caller_identity()

            logger.info(
                f"Successfully authenticated as AWS account: {identity.get('Account')}"
            )
            return session

        except (NoCredentialsError, PartialCredentialsError) as e:
            raise AWSCredentialError(f"Invalid or missing AWS credentials: {e}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["InvalidUserID.NotFound", "AccessDenied"]:
                raise AWSCredentialError(f"AWS credentials are invalid: {e}")
            raise AWSCredentialError(f"AWS credential validation failed: {e}")
        except Exception as e:
            raise AWSCredentialError(
                f"Unexpected error validating AWS credentials: {e}"
            )

    @staticmethod
    def get_s3_client(config: S3Config) -> Any:
        """
        Create an S3 client with proper configuration.

        Args:
            config: S3 configuration

        Returns:
            boto3 S3 client

        Raises:
            AWSCredentialError: If credentials are invalid
        """
        session = AWSConfigHelper.get_boto3_session(config)

        client_config = {
            "region_name": config.region,
            "config": boto3.session.Config(
                retries={"max_attempts": config.max_attempts, "mode": "adaptive"},
                connect_timeout=config.connect_timeout,
                read_timeout=config.read_timeout,
                max_pool_connections=config.max_concurrency,
            ),
        }

        return session.client("s3", **client_config)

    @staticmethod
    def validate_bucket_access(s3_client: Any, bucket_name: str) -> bool:
        """
        Validate that the bucket exists and is accessible.

        Args:
            s3_client: boto3 S3 client
            bucket_name: Name of the S3 bucket

        Returns:
            bool: True if bucket is accessible

        Raises:
            AWSCredentialError: If access validation fails
        """
        try:
            # Check if bucket exists and we have access
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Successfully validated access to S3 bucket: {bucket_name}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code == "404":
                raise AWSCredentialError(f"S3 bucket '{bucket_name}' does not exist")
            elif error_code in ["403", "AccessDenied"]:
                raise AWSCredentialError(
                    f"Access denied to S3 bucket '{bucket_name}'. Check permissions."
                )
            else:
                raise AWSCredentialError(
                    f"Failed to access S3 bucket '{bucket_name}': {e}"
                )
        except Exception as e:
            raise AWSCredentialError(
                f"Unexpected error accessing S3 bucket '{bucket_name}': {e}"
            )

    @staticmethod
    def build_s3_key(
        prefix: str,
        customer_name: str,
        customer_number: str,
        date: str,
        folder: str,
        filename: str,
    ) -> str:
        """
        Build a standardized S3 key following the folder structure.

        Format: {prefix}/{customer-name}/{customer-number}/{YYYY-MM-DD}/{folder}/{filename}

        Args:
            prefix: S3 prefix (e.g., "PaidSearchNav")
            customer_name: Customer name
            customer_number: Customer number
            date: Date in YYYY-MM-DD format
            folder: Folder name (e.g., "inputs", "outputs/reports")
            filename: File name

        Returns:
            str: Complete S3 key
        """
        # Sanitize customer name for S3 key (replace spaces and special chars)
        safe_customer_name = customer_name.replace(" ", "_").replace("/", "_")

        # Build key components
        key_parts = [
            prefix.strip("/"),
            safe_customer_name,
            customer_number,
            date,
            folder.strip("/"),
            filename,
        ]

        # Join with forward slashes and ensure no double slashes
        key = "/".join(part for part in key_parts if part)
        return key

    @staticmethod
    def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
        """
        Parse an S3 URI into bucket and key components.

        Args:
            s3_uri: S3 URI in format s3://bucket-name/key/path

        Returns:
            tuple: (bucket_name, key)

        Raises:
            ValueError: If URI format is invalid
        """
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")

        # Remove s3:// prefix
        path = s3_uri[5:]

        # Split into bucket and key
        parts = path.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid S3 URI format - missing key: {s3_uri}")

        bucket_name, key = parts
        if not bucket_name:
            raise ValueError(f"Invalid S3 URI format - empty bucket name: {s3_uri}")

        return bucket_name, key

    @staticmethod
    def get_environment_credentials() -> Optional[Dict[str, str]]:
        """
        Get AWS credentials from environment variables.

        Returns:
            dict: Environment credentials or None if not found
        """
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

        if access_key and secret_key:
            creds = {"access_key_id": access_key, "secret_access_key": secret_key}
            if session_token:
                creds["session_token"] = session_token
            return creds

        return None

    @staticmethod
    def is_running_on_ec2() -> bool:
        """
        Check if the application is running on EC2 (for IAM role detection).

        Returns:
            bool: True if running on EC2
        """
        try:
            # Check for EC2 metadata service
            import urllib.error
            import urllib.request

            req = urllib.request.Request(
                "http://169.254.169.254/latest/meta-data/instance-id",
                headers={"User-Agent": "paidsearchnav/1.0"},
            )

            # Use configurable timeout for high-latency environments
            timeout = min(
                int(
                    os.getenv("PSN_EC2_METADATA_TIMEOUT", DEFAULT_EC2_METADATA_TIMEOUT)
                ),
                MAX_EC2_METADATA_TIMEOUT,
            )

            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status == 200

        except (urllib.error.URLError, TimeoutError, OSError):
            return False
