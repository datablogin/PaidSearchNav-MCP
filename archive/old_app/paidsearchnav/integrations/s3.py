"""S3 client service for customer data storage."""

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Union

from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from paidsearchnav.core.circuit_breaker import CircuitBreakerConfig
from paidsearchnav.core.config import S3Config
from paidsearchnav.integrations.aws_config import AWSConfigHelper, AWSCredentialError

logger = logging.getLogger(__name__)

# Constants for S3 operations
DEFAULT_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100MB
DEFAULT_EC2_METADATA_TIMEOUT = 2  # seconds


class S3Object(BaseModel):
    """Represents an S3 object with metadata."""

    key: str = Field(..., description="S3 object key")
    size: int = Field(..., description="Object size in bytes")
    last_modified: datetime = Field(..., description="Last modified timestamp")
    etag: str = Field(..., description="ETag of the object")
    content_type: str | None = Field(None, description="Content type of the object")
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Object metadata"
    )


class S3UploadResult(BaseModel):
    """Result of an S3 upload operation."""

    key: str = Field(..., description="S3 object key")
    bucket: str = Field(..., description="S3 bucket name")
    size: int = Field(..., description="Uploaded file size in bytes")
    etag: str = Field(..., description="ETag of the uploaded object")
    version_id: str | None = Field(
        None, description="Version ID if versioning is enabled"
    )


class S3ClientError(Exception):
    """Base exception for S3 client errors."""

    pass


class S3Client:
    """
    S3 client service with comprehensive file operations and error handling.

    Provides high-level operations for customer data storage with proper
    error handling, retry logic, and circuit breaker pattern.
    """

    def __init__(
        self,
        config: S3Config,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize S3 client.

        Args:
            config: S3 configuration
            circuit_breaker_config: Circuit breaker configuration (optional)

        Raises:
            S3ClientError: If S3 client cannot be initialized
        """
        self.config = config
        self._client = None
        self._circuit_breaker = None

        if not config.enabled:
            logger.warning("S3 integration is disabled in configuration")
            return

        # Setup circuit breaker
        if circuit_breaker_config and circuit_breaker_config.enabled:
            try:
                from circuitbreaker import CircuitBreaker as CBCircuitBreaker

                self._circuit_breaker = CBCircuitBreaker(
                    failure_threshold=circuit_breaker_config.failure_threshold,
                    recovery_timeout=circuit_breaker_config.recovery_timeout,
                    expected_exception=circuit_breaker_config.expected_exception,
                    name="s3_client",
                )
                logger.debug("Circuit breaker enabled for S3Client")
            except ImportError:
                logger.warning(
                    "Circuit breaker requested but circuitbreaker module not available, proceeding without circuit breaker"
                )
                self._circuit_breaker = None

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the S3 client with proper configuration."""
        try:
            self._client = AWSConfigHelper.get_s3_client(self.config)

            # Validate bucket access if bucket is configured
            if self.config.bucket_name:
                AWSConfigHelper.validate_bucket_access(
                    self._client, self.config.bucket_name
                )

            logger.info(f"S3 client initialized for bucket: {self.config.bucket_name}")

        except AWSCredentialError as e:
            raise S3ClientError(f"Failed to initialize S3 client: {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error initializing S3 client: {e}")

    def _execute_with_circuit_breaker(self, operation, *args, **kwargs):
        """Execute operation with circuit breaker if configured."""
        if self._circuit_breaker:
            return self._circuit_breaker.call(operation, *args, **kwargs)
        return operation(*args, **kwargs)

    def _get_content_type(
        self, filename: str, content_type: Optional[str] = None
    ) -> str:
        """
        Determine content type for a file.

        Args:
            filename: Name of the file
            content_type: Explicit content type (optional)

        Returns:
            str: Content type
        """
        if content_type:
            return content_type

        # Guess content type from file extension
        guessed_type, _ = mimetypes.guess_type(filename)
        return guessed_type or "application/octet-stream"

    def upload_file(
        self,
        file_path: Union[str, Path],
        customer_name: str,
        customer_number: str,
        date: str,
        folder: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> S3UploadResult:
        """
        Upload a file to S3 with proper folder structure.

        Args:
            file_path: Path to the local file
            customer_name: Customer name
            customer_number: Customer number
            date: Date in YYYY-MM-DD format
            folder: Folder name (e.g., "inputs", "outputs/reports")
            filename: Custom filename (optional, defaults to original filename)
            content_type: Content type (optional, auto-detected)
            metadata: Additional metadata (optional)

        Returns:
            S3UploadResult: Upload result information

        Raises:
            S3ClientError: If upload fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        file_path = Path(file_path)

        # Use original filename if not provided
        if not filename:
            filename = file_path.name

        # Build S3 key
        s3_object_key = AWSConfigHelper.build_s3_key(
            self.config.prefix, customer_name, customer_number, date, folder, filename
        )

        # Determine content type
        resolved_content_type = self._get_content_type(filename, content_type)

        # Prepare upload arguments
        upload_args = {"ContentType": resolved_content_type, "Metadata": metadata or {}}

        # Add customer context to metadata
        upload_args["Metadata"].update(
            {
                "customer-name": customer_name,
                "customer-number": customer_number,
                "upload-date": datetime.now(timezone.utc).isoformat(),
                "folder": folder,
            }
        )

        try:
            # Handle file access and upload atomically to avoid race conditions
            def _upload():
                try:
                    with open(file_path, "rb") as f:
                        # Get file size after opening to ensure it exists and is accessible
                        file_size = file_path.stat().st_size

                        if file_size >= self.config.multipart_threshold:
                            # Use multipart upload for large files
                            return self._client.upload_fileobj(
                                f,
                                self.config.bucket_name,
                                s3_object_key,
                                ExtraArgs=upload_args,
                            ), file_size
                        else:
                            # Regular upload for smaller files
                            return self._client.put_object(
                                Bucket=self.config.bucket_name,
                                Key=s3_object_key,
                                Body=f,
                                **upload_args,
                            ), file_size
                except FileNotFoundError:
                    raise S3ClientError(
                        f"File does not exist or was removed: {file_path}"
                    )
                except PermissionError:
                    raise S3ClientError(
                        f"Permission denied accessing file: {file_path}"
                    )
                except OSError as e:
                    raise S3ClientError(f"Error accessing file {file_path}: {e}")

            response, file_size = self._execute_with_circuit_breaker(_upload)

            # Get object info for result
            head_response = self._execute_with_circuit_breaker(
                self._client.head_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
            )

            result = S3UploadResult(
                key=s3_object_key,
                bucket=self.config.bucket_name,
                size=file_size,
                etag=head_response["ETag"].strip('"'),
                version_id=head_response.get("VersionId"),
            )

            logger.info(
                f"Successfully uploaded file to S3: s3://{self.config.bucket_name}/{s3_object_key}"
            )
            return result

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            raise S3ClientError(f"S3 upload failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 upload: {e}")

    def upload_content(
        self,
        content: Union[str, bytes, BinaryIO],
        customer_name: str,
        customer_number: str,
        date: str,
        folder: str,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> S3UploadResult:
        """
        Upload content directly to S3.

        Args:
            content: Content to upload (string, bytes, or file-like object)
            customer_name: Customer name
            customer_number: Customer number
            date: Date in YYYY-MM-DD format
            folder: Folder name
            filename: File name
            content_type: Content type (optional)
            metadata: Additional metadata (optional)

        Returns:
            S3UploadResult: Upload result information

        Raises:
            S3ClientError: If upload fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        # Build S3 key
        s3_object_key = AWSConfigHelper.build_s3_key(
            self.config.prefix, customer_name, customer_number, date, folder, filename
        )

        # Handle content conversion and memory efficiently for large file-like objects
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
            if not content_type:
                content_type = "text/plain; charset=utf-8"
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            # For file-like objects, use them directly to avoid loading entire content into memory
            # This handles large files more efficiently
            if hasattr(content, "read"):
                # Use file-like object directly for upload
                content_bytes = content
                # If content type detection is needed, try to read a small sample
                if (
                    not content_type
                    and hasattr(content, "seek")
                    and hasattr(content, "tell")
                ):
                    try:
                        current_pos = content.tell()
                        sample = content.read(1024)  # Read small sample
                        content.seek(current_pos)  # Reset position
                        if isinstance(sample, str):
                            sample = sample.encode("utf-8")
                    except (OSError, IOError):
                        pass  # If seeking fails, continue without sample
            else:
                # Fallback: read content into memory
                content_bytes = content.read() if hasattr(content, "read") else content
                if isinstance(content_bytes, str):
                    content_bytes = content_bytes.encode("utf-8")

        # Determine content type
        resolved_content_type = self._get_content_type(filename, content_type)

        # Prepare upload arguments
        upload_args = {"ContentType": resolved_content_type, "Metadata": metadata or {}}

        # Add customer context to metadata
        upload_args["Metadata"].update(
            {
                "customer-name": customer_name,
                "customer-number": customer_number,
                "upload-date": datetime.now(timezone.utc).isoformat(),
                "folder": folder,
            }
        )

        try:
            # Upload content
            response = self._execute_with_circuit_breaker(
                self._client.put_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
                Body=content_bytes,
                **upload_args,
            )

            # Calculate size based on content type
            if isinstance(content_bytes, (str, bytes)):
                content_size = len(content_bytes)
            else:
                # For file-like objects, try to get size or use response metadata
                if hasattr(content_bytes, "seek") and hasattr(content_bytes, "tell"):
                    try:
                        current_pos = content_bytes.tell()
                        content_bytes.seek(0, 2)  # Seek to end
                        content_size = content_bytes.tell()
                        content_bytes.seek(current_pos)  # Reset position
                    except (OSError, IOError):
                        content_size = 0  # Unknown size
                else:
                    content_size = 0  # Unknown size

            result = S3UploadResult(
                key=s3_object_key,
                bucket=self.config.bucket_name,
                size=content_size,
                etag=response["ETag"].strip('"'),
                version_id=response.get("VersionId"),
            )

            logger.info(
                f"Successfully uploaded content to S3: s3://{self.config.bucket_name}/{s3_object_key}"
            )
            return result

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            raise S3ClientError(f"S3 upload failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 upload: {e}")

    def download_file(
        self, s3_object_key: str, local_path: Union[str, Path], create_dirs: bool = True
    ) -> int:
        """
        Download a file from S3.

        Args:
            s3_object_key: S3 object key
            local_path: Local file path to save to
            create_dirs: Create parent directories if they don't exist

        Returns:
            int: Downloaded file size in bytes

        Raises:
            S3ClientError: If download fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        local_path = Path(local_path)

        # Create parent directories if needed
        if create_dirs:
            local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Download file
            self._execute_with_circuit_breaker(
                self._client.download_file,
                self.config.bucket_name,
                s3_object_key,
                str(local_path),
            )

            file_size = local_path.stat().st_size
            logger.info(
                f"Successfully downloaded file from S3: {s3_object_key} -> {local_path}"
            )
            return file_size

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                raise S3ClientError(f"S3 object not found: {s3_object_key}")
            raise S3ClientError(f"S3 download failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 download: {e}")

    def download_content(
        self, s3_object_key: str, as_text: bool = False
    ) -> Union[bytes, str]:
        """
        Download content from S3 as bytes or text.

        Args:
            s3_object_key: S3 object key
            as_text: Return content as text instead of bytes

        Returns:
            Content as bytes or text

        Raises:
            S3ClientError: If download fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        try:
            # Download object
            response = self._execute_with_circuit_breaker(
                self._client.get_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
            )

            content = response["Body"].read()

            if as_text:
                # Try to decode as UTF-8
                try:
                    content = content.decode("utf-8")
                except UnicodeDecodeError:
                    raise S3ClientError(
                        f"Cannot decode S3 object as text: {s3_object_key}"
                    )

            logger.info(f"Successfully downloaded content from S3: {s3_object_key}")
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                raise S3ClientError(f"S3 object not found: {s3_object_key}")
            raise S3ClientError(f"S3 download failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 download: {e}")

    def list_objects(
        self,
        prefix: str = "",
        customer_name: Optional[str] = None,
        customer_number: Optional[str] = None,
        date: Optional[str] = None,
        max_keys: int = 1000,
    ) -> List[S3Object]:
        """
        List objects in S3 with optional filtering.

        Args:
            prefix: Key prefix to filter by
            customer_name: Filter by customer name
            customer_number: Filter by customer number
            date: Filter by date (YYYY-MM-DD)
            max_keys: Maximum number of objects to return

        Returns:
            List of S3Object instances

        Raises:
            S3ClientError: If listing fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        # Build prefix from customer filters - use the most specific available
        filter_prefix = self.config.prefix.strip("/") + "/"

        if customer_name:
            filter_prefix += customer_name.replace(" ", "_").replace("/", "_") + "/"
            if customer_number:
                filter_prefix += customer_number + "/"
                if date:
                    filter_prefix += date + "/"
        elif date:
            # Special case: filter by date only (across all customers)
            # This requires listing all and filtering in Python
            # For now, use base prefix and filter results
            pass

        # Combine with any additional prefix
        if prefix:
            if not customer_name and not customer_number and not date:
                filter_prefix = prefix
            else:
                filter_prefix = filter_prefix + prefix.lstrip("/")

        try:
            objects = []
            paginator = self._client.get_paginator("list_objects_v2")

            page_iterator = paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=filter_prefix,
                PaginationConfig={"MaxItems": max_keys},
            )

            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        key = obj["Key"]

                        # Apply additional filtering if needed (e.g., date-only filter)
                        if date and not customer_name:
                            # Check if the key contains the date string in the expected position
                            if f"/{date}/" not in key:
                                continue

                        s3_obj = S3Object(
                            key=key,
                            size=obj["Size"],
                            last_modified=obj["LastModified"],
                            etag=obj["ETag"].strip('"'),
                        )
                        objects.append(s3_obj)

            logger.info(f"Listed {len(objects)} objects with prefix: {filter_prefix}")
            return objects

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            raise S3ClientError(f"S3 list operation failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 list operation: {e}")

    def delete_object(self, s3_object_key: str) -> bool:
        """
        Delete an object from S3.

        Args:
            s3_object_key: S3 object key to delete

        Returns:
            bool: True if object was deleted

        Raises:
            S3ClientError: If deletion fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        try:
            self._execute_with_circuit_breaker(
                self._client.delete_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
            )

            logger.info(f"Successfully deleted object from S3: {s3_object_key}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            raise S3ClientError(f"S3 delete operation failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 delete operation: {e}")

    def object_exists(self, s3_object_key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            s3_object_key: S3 object key to check

        Returns:
            bool: True if object exists
        """
        if not self.config.enabled or not self._client:
            return False

        try:
            self._execute_with_circuit_breaker(
                self._client.head_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
            )
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            # Re-raise other errors
            raise S3ClientError(f"Error checking object existence ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error checking object existence: {e}")

    def get_object_metadata(self, s3_object_key: str) -> S3Object:
        """
        Get metadata for an S3 object.

        Args:
            s3_object_key: S3 object key

        Returns:
            S3Object: Object information and metadata

        Raises:
            S3ClientError: If operation fails
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        try:
            response = self._execute_with_circuit_breaker(
                self._client.head_object,
                Bucket=self.config.bucket_name,
                Key=s3_object_key,
            )

            return S3Object(
                key=s3_object_key,
                size=response["ContentLength"],
                last_modified=response["LastModified"],
                etag=response["ETag"].strip('"'),
                content_type=response.get("ContentType"),
                metadata=response.get("Metadata", {}),
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["NoSuchKey", "404"]:
                raise S3ClientError(f"S3 object not found: {s3_object_key}")
            raise S3ClientError(f"S3 head operation failed ({error_code}): {e}")
        except Exception as e:
            raise S3ClientError(f"Unexpected error during S3 head operation: {e}")

    def create_folder_structure(
        self, customer_name: str, customer_number: str, date: str
    ) -> List[str]:
        """
        Create the standardized folder structure for a customer audit.

        Args:
            customer_name: Customer name
            customer_number: Customer number
            date: Date in YYYY-MM-DD format

        Returns:
            List of created folder keys
        """
        if not self.config.enabled or not self._client:
            raise S3ClientError("S3 client is not enabled or initialized")

        # Define folder structure
        folders = [
            "inputs/",
            "outputs/",
            "outputs/reports/",
            "outputs/actionable_files/",
        ]

        created_keys = []

        for folder in folders:
            # Create folder marker object (empty object with trailing slash)
            folder_key = (
                AWSConfigHelper.build_s3_key(
                    self.config.prefix, customer_name, customer_number, date, folder, ""
                ).rstrip("/")
                + "/"
            )

            try:
                self._execute_with_circuit_breaker(
                    self._client.put_object,
                    Bucket=self.config.bucket_name,
                    Key=folder_key,
                    Body=b"",
                    ContentType="application/x-directory",
                    Metadata={
                        "customer-name": customer_name,
                        "customer-number": customer_number,
                        "created-date": datetime.now(timezone.utc).isoformat(),
                        "folder-type": "directory-marker",
                    },
                )
                created_keys.append(folder_key)

            except ClientError as e:
                logger.warning(f"Failed to create folder marker {folder_key}: {e}")
                # Continue with other folders

        logger.info(
            f"Created folder structure for customer {customer_name} ({customer_number}) on {date}"
        )
        return created_keys
