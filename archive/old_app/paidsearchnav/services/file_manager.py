"""S3 File Management Service for Audit Input/Output Operations."""

import asyncio
import asyncio as aio
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from paidsearchnav.core.config import S3Config
from paidsearchnav.core.models.file_management import (
    AuditFileSet,
    CleanupReport,
    FileCategory,
    FileMetadata,
    InputFileRecord,
    OutputFileRecord,
)
from paidsearchnav.integrations.s3 import S3Client, S3ClientError, S3Object
from paidsearchnav.services.file_validation import FileValidator
from paidsearchnav.services.metadata_tracker import MetadataTracker

logger = logging.getLogger(__name__)


class AuditFileManagerService:
    """
    Comprehensive S3 file management service for audit operations.

    Handles upload, storage, retrieval, and cleanup of audit-related files
    with proper organization, metadata tracking, and validation.
    """

    def __init__(
        self, s3_client: S3Client, s3_config: S3Config, max_concurrent_uploads: int = 10
    ):
        """Initialize the audit file manager service.

        Args:
            s3_client: S3 client instance
            s3_config: S3 configuration
            max_concurrent_uploads: Maximum concurrent S3 uploads
        """
        self.s3_client = s3_client
        self.s3_config = s3_config
        self.file_validator = FileValidator()
        self.metadata_tracker = MetadataTracker()
        self._upload_semaphore = aio.Semaphore(max_concurrent_uploads)
        self._allow_invalid = s3_config.__dict__.get("allow_invalid_uploads", False)

    async def upload_input_csv(
        self,
        customer_id: str,
        google_ads_account_id: str,
        audit_date: date,
        file_content: bytes,
        filename: str,
        audit_run_id: Optional[str] = None,
    ) -> InputFileRecord:
        """Upload an input CSV file for audit analysis.

        Args:
            customer_id: Customer ID
            google_ads_account_id: Google Ads account ID
            audit_date: Date of the audit
            file_content: CSV file content as bytes
            filename: Name of the file
            audit_run_id: Optional audit run ID

        Returns:
            InputFileRecord with upload details and validation results

        Raises:
            S3ClientError: If upload fails
            ValueError: If validation fails critically
        """
        start_time = time.time()
        audit_date_str = audit_date.strftime("%Y-%m-%d")
        audit_run_id = audit_run_id or datetime.now(timezone.utc).strftime(
            "%Y%m%d%H%M%S"
        )

        file_type = self._determine_file_type(filename)
        validation_result = self.file_validator.validate_input_file(
            file_content, filename, file_type
        )

        if not validation_result.is_valid and not self._allow_invalid_upload():
            raise ValueError(
                f"File validation failed: {'; '.join(validation_result.errors)}"
            )

        # Sanitize customer inputs to prevent path traversal
        customer_id = self._sanitize_path_input(customer_id)
        customer_name = f"customer_{customer_id}"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_filename = f"{timestamp}_{filename}"

        # Calculate checksum before upload for integrity verification
        checksum = self.file_validator.calculate_checksum(file_content)

        # Detect content type once and reuse
        content_type = self.file_validator.detect_content_type(filename)

        try:
            async with self._upload_semaphore:
                upload_result = await asyncio.to_thread(
                    self.s3_client.upload_content,
                    content=file_content,
                    customer_name=customer_name,
                    customer_number=customer_id,
                    date=audit_date_str,
                    folder="inputs",
                    filename=s3_filename,
                    content_type=content_type,
                    metadata={
                        "audit-run-id": audit_run_id,
                        "google-ads-account-id": google_ads_account_id,
                        "file-type": file_type,
                        "validation-status": "valid"
                        if validation_result.is_valid
                        else "invalid",
                        "original-filename": filename,
                        "checksum": checksum,
                    },
                )

            # Verify checksum matches S3 ETag (if not multipart)
            if "-" not in upload_result.etag:
                # ETag is MD5 for non-multipart uploads
                md5_checksum = self.file_validator.calculate_checksum(
                    file_content, "md5"
                )
                if md5_checksum != upload_result.etag:
                    logger.warning(
                        f"Checksum mismatch for {filename}: local={md5_checksum}, s3={upload_result.etag}"
                    )

            file_metadata = self.metadata_tracker.create_file_metadata(
                file_path=upload_result.key,
                file_size=upload_result.size,
                content_type=content_type,
                checksum=checksum,
                audit_run_id=audit_run_id,
                file_category=FileCategory.INPUT,
                customer_id=customer_id,
                google_ads_account_id=google_ads_account_id,
                audit_date=audit_date_str,
                file_type=file_type,
            )

            audit_metadata = self.metadata_tracker.create_audit_file_metadata(
                file_name=filename,
                file_path=upload_result.key,
                file_size=upload_result.size,
                content_type=content_type,
                checksum=checksum,
                audit_run_id=audit_run_id,
                file_category=FileCategory.INPUT.value,
                file_type=file_type,
                customer_id=customer_id,
                google_ads_account_id=google_ads_account_id,
                audit_date=audit_date_str,
                s3_result=upload_result.model_dump(),
                custom_metadata={"validation_result": validation_result.model_dump()},
            )

            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="upload",
                success=True,
                duration_ms=duration_ms,
                client_info={"filename": filename, "size": upload_result.size},
            )

            logger.info(
                f"Successfully uploaded input CSV: {filename} to {upload_result.key} "
                f"(size: {upload_result.size} bytes, duration: {duration_ms}ms)"
            )

            return InputFileRecord(
                file_metadata=file_metadata,
                validation_status="valid" if validation_result.is_valid else "invalid",
                validation_errors=validation_result.errors,
                row_count=validation_result.file_info.get("row_count"),
                column_names=validation_result.file_info.get("columns"),
            )

        except S3ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="upload",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
                client_info={"filename": filename},
            )
            logger.error(f"Failed to upload input CSV {filename}: {e}")
            raise

    async def store_analysis_outputs(
        self,
        customer_id: str,
        google_ads_account_id: str,
        audit_date: date,
        reports: Dict[str, str],
        actionable_files: Dict[str, bytes],
        audit_run_id: Optional[str] = None,
    ) -> OutputFileRecord:
        """Store analysis output files (reports and actionable CSVs).

        Args:
            customer_id: Customer ID
            google_ads_account_id: Google Ads account ID
            audit_date: Date of the audit
            reports: Dictionary of report filename -> content (markdown)
            actionable_files: Dictionary of filename -> CSV data (bytes)
            audit_run_id: Optional audit run ID

        Returns:
            OutputFileRecord with upload details

        Raises:
            S3ClientError: If any upload fails
        """
        start_time = time.time()
        audit_date_str = audit_date.strftime("%Y-%m-%d")
        audit_run_id = audit_run_id or datetime.now(timezone.utc).strftime(
            "%Y%m%d%H%M%S"
        )
        # Sanitize customer inputs
        customer_id = self._sanitize_path_input(customer_id)
        customer_name = f"customer_{customer_id}"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        report_metadata = {}
        actionable_metadata = {}
        total_size = 0

        async def upload_report(filename: str, content: str) -> FileMetadata:
            """Upload a single report file."""
            s3_filename = f"{timestamp}_{filename}"
            async with self._upload_semaphore:
                upload_result = await asyncio.to_thread(
                    self.s3_client.upload_content,
                    content=content,
                    customer_name=customer_name,
                    customer_number=customer_id,
                    date=audit_date_str,
                    folder="outputs/reports",
                    filename=s3_filename,
                    content_type="text/markdown",
                    metadata={
                        "audit-run-id": audit_run_id,
                        "google-ads-account-id": google_ads_account_id,
                        "file-type": "report",
                        "original-filename": filename,
                    },
                )

            checksum = self.file_validator.calculate_checksum(content)
            return self.metadata_tracker.create_file_metadata(
                file_path=upload_result.key,
                file_size=upload_result.size,
                content_type="text/markdown",
                checksum=checksum,
                audit_run_id=audit_run_id,
                file_category=FileCategory.REPORT,
                customer_id=customer_id,
                google_ads_account_id=google_ads_account_id,
                audit_date=audit_date_str,
                file_type="report",
            )

        async def upload_actionable(filename: str, content: bytes) -> FileMetadata:
            """Upload a single actionable CSV file."""
            s3_filename = f"{timestamp}_{filename}"
            async with self._upload_semaphore:
                upload_result = await asyncio.to_thread(
                    self.s3_client.upload_content,
                    content=content,
                    customer_name=customer_name,
                    customer_number=customer_id,
                    date=audit_date_str,
                    folder="outputs/actionable_files",
                    filename=s3_filename,
                    content_type="text/csv",
                    metadata={
                        "audit-run-id": audit_run_id,
                        "google-ads-account-id": google_ads_account_id,
                        "file-type": "actionable",
                        "original-filename": filename,
                    },
                )

            checksum = self.file_validator.calculate_checksum(content)
            return self.metadata_tracker.create_file_metadata(
                file_path=upload_result.key,
                file_size=upload_result.size,
                content_type="text/csv",
                checksum=checksum,
                audit_run_id=audit_run_id,
                file_category=FileCategory.ACTIONABLE,
                customer_id=customer_id,
                google_ads_account_id=google_ads_account_id,
                audit_date=audit_date_str,
                file_type="actionable",
            )

        try:
            report_tasks = [
                upload_report(filename, content)
                for filename, content in reports.items()
            ]
            report_results = await asyncio.gather(*report_tasks, return_exceptions=True)

            for filename, result in zip(reports.keys(), report_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to upload report {filename}: {result}")
                    raise S3ClientError(f"Failed to upload report {filename}: {result}")
                report_metadata[filename] = result
                total_size += result.file_size

            actionable_tasks = [
                upload_actionable(filename, content)
                for filename, content in actionable_files.items()
            ]
            actionable_results = await asyncio.gather(
                *actionable_tasks, return_exceptions=True
            )

            for filename, result in zip(actionable_files.keys(), actionable_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to upload actionable file {filename}: {result}"
                    )
                    raise S3ClientError(
                        f"Failed to upload actionable file {filename}: {result}"
                    )
                actionable_metadata[filename] = result
                total_size += result.file_size

            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="batch_upload",
                success=True,
                duration_ms=duration_ms,
                client_info={
                    "report_count": len(reports),
                    "actionable_count": len(actionable_files),
                    "total_size": total_size,
                },
            )

            logger.info(
                f"Successfully stored {len(reports)} reports and {len(actionable_files)} "
                f"actionable files (total size: {total_size} bytes, duration: {duration_ms}ms)"
            )

            return OutputFileRecord(
                report_files=report_metadata,
                actionable_files=actionable_metadata,
                generation_timestamp=datetime.now(timezone.utc),
                total_size_bytes=total_size,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="batch_upload",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            raise

    async def get_audit_files(
        self, customer_id: str, google_ads_account_id: str, audit_date: date
    ) -> AuditFileSet:
        """Retrieve all files for a specific audit.

        Args:
            customer_id: Customer ID
            google_ads_account_id: Google Ads account ID
            audit_date: Date of the audit

        Returns:
            AuditFileSet with all files for the audit

        Raises:
            S3ClientError: If listing or retrieval fails
        """
        start_time = time.time()
        audit_date_str = audit_date.strftime("%Y-%m-%d")
        # Sanitize customer inputs
        customer_id = self._sanitize_path_input(customer_id)
        customer_name = f"customer_{customer_id}"

        try:
            all_objects = await asyncio.to_thread(
                self.s3_client.list_objects,
                customer_name=customer_name,
                customer_number=customer_id,
                date=audit_date_str,
            )

            input_files = []
            report_files = {}
            actionable_files = {}
            total_size = 0
            total_count = 0

            for obj in all_objects:
                total_size += obj.size
                total_count += 1

                if "/inputs/" in obj.key:
                    metadata = await self._get_file_metadata(obj)
                    # Extract audit_run_id from S3 metadata if available
                    s3_metadata = await self._get_s3_object_metadata(obj.key)
                    if s3_metadata and "audit-run-id" in s3_metadata:
                        metadata.audit_run_id = s3_metadata["audit-run-id"]
                    input_files.append(
                        InputFileRecord(
                            file_metadata=metadata,
                            validation_status="unknown",
                            validation_errors=[],
                        )
                    )
                elif "/outputs/reports/" in obj.key:
                    metadata = await self._get_file_metadata(obj)
                    filename = Path(obj.key).name
                    report_files[filename] = metadata
                elif "/outputs/actionable_files/" in obj.key:
                    metadata = await self._get_file_metadata(obj)
                    filename = Path(obj.key).name
                    actionable_files[filename] = metadata

            output_files = None
            if report_files or actionable_files:
                output_files = OutputFileRecord(
                    report_files=report_files,
                    actionable_files=actionable_files,
                    generation_timestamp=datetime.now(timezone.utc),
                    total_size_bytes=sum(
                        m.file_size
                        for m in list(report_files.values())
                        + list(actionable_files.values())
                    ),
                )

            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="list",
                success=True,
                duration_ms=duration_ms,
                client_info={
                    "customer_id": customer_id,
                    "audit_date": audit_date_str,
                    "files_found": total_count,
                },
            )

            logger.info(
                f"Retrieved {total_count} files for audit on {audit_date_str} "
                f"(total size: {total_size} bytes, duration: {duration_ms}ms)"
            )

            # Try to get audit_run_id from first file's metadata
            audit_run_id = ""
            if input_files and input_files[0].file_metadata.audit_run_id:
                audit_run_id = input_files[0].file_metadata.audit_run_id

            return AuditFileSet(
                customer_id=customer_id,
                google_ads_account_id=google_ads_account_id,
                audit_date=audit_date_str,
                audit_run_id=audit_run_id,
                input_files=input_files,
                output_files=output_files,
                total_file_count=total_count,
                total_size_bytes=total_size,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="list",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            raise

    async def cleanup_old_audits(self, retention_days: int = 90) -> CleanupReport:
        """Clean up old audit files based on retention policy.

        Args:
            retention_days: Number of days to retain files

        Returns:
            CleanupReport with cleanup details

        Raises:
            S3ClientError: If cleanup operations fail
        """
        start_time = time.time()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        files_deleted = 0
        bytes_freed = 0
        customers_affected = set()
        errors = []
        oldest_file_date = None
        newest_file_date = None

        try:
            all_objects = await asyncio.to_thread(
                self.s3_client.list_objects, prefix=self.s3_config.prefix
            )

            objects_to_delete = []
            for obj in all_objects:
                if obj.last_modified < cutoff_date:
                    objects_to_delete.append(obj)

                    if not oldest_file_date or obj.last_modified < oldest_file_date:
                        oldest_file_date = obj.last_modified
                    if not newest_file_date or obj.last_modified > newest_file_date:
                        newest_file_date = obj.last_modified

                    path_parts = obj.key.split("/")
                    if len(path_parts) >= 3:
                        customers_affected.add(path_parts[2])

            async def delete_object(obj: S3Object) -> bool:
                """Delete a single object."""
                try:
                    await asyncio.to_thread(self.s3_client.delete_object, obj.key)
                    return True
                except Exception as e:
                    errors.append(f"Failed to delete {obj.key}: {str(e)}")
                    return False

            delete_tasks = [delete_object(obj) for obj in objects_to_delete]
            delete_results = await asyncio.gather(
                *delete_tasks, return_exceptions=False
            )

            for obj, success in zip(objects_to_delete, delete_results):
                if success:
                    files_deleted += 1
                    bytes_freed += obj.size

            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="cleanup",
                success=len(errors) == 0,
                duration_ms=duration_ms,
                client_info={
                    "retention_days": retention_days,
                    "files_deleted": files_deleted,
                    "bytes_freed": bytes_freed,
                },
            )

            logger.info(
                f"Cleanup completed: deleted {files_deleted} files, "
                f"freed {bytes_freed} bytes, affected {len(customers_affected)} customers "
                f"(duration: {duration_ms}ms)"
            )

            return CleanupReport(
                files_deleted=files_deleted,
                bytes_freed=bytes_freed,
                customers_affected=len(customers_affected),
                oldest_file_date=oldest_file_date,
                newest_file_date=newest_file_date,
                errors=errors,
                cleanup_timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.metadata_tracker.track_operation(
                operation_type="cleanup",
                success=False,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            raise

    async def _get_file_metadata(self, s3_object: S3Object) -> FileMetadata:
        """Convert S3Object to FileMetadata.

        Args:
            s3_object: S3Object instance

        Returns:
            FileMetadata instance
        """
        path_parts = s3_object.key.split("/")
        customer_id = path_parts[2] if len(path_parts) > 2 else ""
        audit_date = path_parts[3] if len(path_parts) > 3 else ""

        file_category = FileCategory.INPUT
        if "/outputs/reports/" in s3_object.key:
            file_category = FileCategory.REPORT
        elif "/outputs/actionable_files/" in s3_object.key:
            file_category = FileCategory.ACTIONABLE

        return FileMetadata(
            file_path=s3_object.key,
            file_size=s3_object.size,
            content_type=s3_object.content_type or "application/octet-stream",
            upload_timestamp=s3_object.last_modified,
            checksum=s3_object.etag,
            audit_run_id="",
            file_category=file_category,
            customer_id=customer_id,
            google_ads_account_id="",
            audit_date=audit_date,
        )

    def _determine_file_type(self, filename: str) -> str:
        """Determine file type from filename.

        Args:
            filename: Name of the file

        Returns:
            File type string
        """
        filename_lower = filename.lower()
        if "keyword" in filename_lower:
            return "keywords"
        elif "search" in filename_lower and "term" in filename_lower:
            return "search_terms"
        elif "campaign" in filename_lower:
            return "campaigns"
        elif "ad" in filename_lower and "group" in filename_lower:
            return "ad_groups"
        else:
            return "unknown"

    def _allow_invalid_upload(self) -> bool:
        """Check if invalid files should be allowed for upload.

        Returns:
            True if invalid uploads are allowed
        """
        return self._allow_invalid

    def _sanitize_path_input(self, input_str: str) -> str:
        """Sanitize input string to prevent path traversal attacks.

        Args:
            input_str: Input string to sanitize

        Returns:
            Sanitized string safe for use in paths
        """
        # Remove any path traversal patterns
        sanitized = re.sub(r"\.\.[\\/]", "", input_str)
        sanitized = re.sub(r'[<>:"|?*]', "", sanitized)
        sanitized = sanitized.replace("..", "")
        sanitized = sanitized.replace("//", "/")
        sanitized = sanitized.replace("\\", "\\")

        # Remove leading/trailing slashes and spaces
        sanitized = sanitized.strip(" /")

        # If empty after sanitization, use a default
        if not sanitized:
            sanitized = "unknown"

        return sanitized

    async def _get_s3_object_metadata(self, key: str) -> Optional[Dict[str, str]]:
        """Get S3 object metadata.

        Args:
            key: S3 object key

        Returns:
            Metadata dictionary or None if not available
        """
        try:
            result = await asyncio.to_thread(self.s3_client.get_object_metadata, key)
            return result.metadata if hasattr(result, "metadata") else None
        except Exception:
            return None
