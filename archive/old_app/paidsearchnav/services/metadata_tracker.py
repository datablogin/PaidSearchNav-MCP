"""Metadata tracking for file operations."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from paidsearchnav.core.models.file_management import FileCategory, FileMetadata
from paidsearchnav.core.models.file_metadata import (
    AuditFileMetadata,
    FileAccessMetadata,
    FileOperationMetadata,
    FileProcessingMetadata,
    FileVersionMetadata,
    S3FileMetadata,
)

logger = logging.getLogger(__name__)


class MetadataTracker:
    """Tracks metadata for file operations."""

    def __init__(self):
        """Initialize metadata tracker."""
        self._metadata_cache: Dict[str, AuditFileMetadata] = {}
        self._operation_history: List[FileOperationMetadata] = []

    def create_file_metadata(
        self,
        file_path: str,
        file_size: int,
        content_type: str,
        checksum: str,
        audit_run_id: str,
        file_category: FileCategory,
        customer_id: str,
        google_ads_account_id: str,
        audit_date: str,
        file_type: Optional[str] = None,
        s3_metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Create file metadata record.

        Args:
            file_path: S3 path to the file
            file_size: File size in bytes
            content_type: MIME content type
            checksum: File checksum
            audit_run_id: Associated audit run ID
            file_category: Category of the file
            customer_id: Customer ID
            google_ads_account_id: Google Ads account ID
            audit_date: Audit date in YYYY-MM-DD format
            file_type: Specific file type (optional)
            s3_metadata: S3-specific metadata (optional)

        Returns:
            FileMetadata instance
        """
        return FileMetadata(
            file_path=file_path,
            file_size=file_size,
            content_type=content_type,
            upload_timestamp=datetime.now(timezone.utc),
            checksum=checksum,
            audit_run_id=audit_run_id,
            file_category=file_category,
            file_type=file_type,
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
        )

    def create_audit_file_metadata(
        self,
        file_name: str,
        file_path: str,
        file_size: int,
        content_type: str,
        checksum: str,
        audit_run_id: str,
        file_category: str,
        file_type: str,
        customer_id: str,
        google_ads_account_id: str,
        audit_date: str,
        s3_result: Optional[Dict[str, Any]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditFileMetadata:
        """Create comprehensive audit file metadata.

        Args:
            file_name: Original file name
            file_path: S3 path to the file
            file_size: File size in bytes
            content_type: MIME content type
            checksum: File checksum
            audit_run_id: Associated audit run ID
            file_category: Category of the file
            file_type: Specific file type
            customer_id: Customer ID
            google_ads_account_id: Google Ads account ID
            audit_date: Audit date in YYYY-MM-DD format
            s3_result: S3 upload result (optional)
            custom_metadata: Custom metadata fields (optional)

        Returns:
            AuditFileMetadata instance
        """
        file_id = str(uuid.uuid4())

        s3_metadata = None
        if s3_result:
            s3_metadata = S3FileMetadata(
                bucket=s3_result.get("bucket", ""),
                key=s3_result.get("key", file_path),
                etag=s3_result.get("etag", ""),
                version_id=s3_result.get("version_id"),
                metadata_tags=s3_result.get("metadata", {}),
            )

        access_metadata = FileAccessMetadata(
            last_modified=datetime.now(timezone.utc),
            last_modified_by=None,
            access_count=0,
        )

        metadata = AuditFileMetadata(
            file_id=file_id,
            audit_run_id=audit_run_id,
            customer_id=customer_id,
            google_ads_account_id=google_ads_account_id,
            audit_date=audit_date,
            file_category=file_category,
            file_type=file_type,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            checksum=checksum,
            s3_metadata=s3_metadata,
            access_metadata=access_metadata,
            custom_metadata=custom_metadata or {},
        )

        self._metadata_cache[file_id] = metadata
        return metadata

    def track_operation(
        self,
        operation_type: str,
        success: bool,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> FileOperationMetadata:
        """Track a file operation.

        Args:
            operation_type: Type of operation (upload/download/delete)
            success: Whether operation succeeded
            duration_ms: Operation duration in milliseconds
            error_message: Error message if failed
            user_id: User who performed the operation
            client_info: Client information

        Returns:
            FileOperationMetadata instance
        """
        operation = FileOperationMetadata(
            operation_id=str(uuid.uuid4()),
            operation_type=operation_type,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            user_id=user_id,
            client_info=client_info,
        )

        self._operation_history.append(operation)

        if len(self._operation_history) > 1000:
            self._operation_history = self._operation_history[-500:]

        return operation

    def track_processing(
        self,
        processor_name: str,
        processor_version: str,
        input_checksum: str,
        processing_time_ms: int,
        output_checksum: Optional[str] = None,
        records_processed: Optional[int] = None,
        records_skipped: Optional[int] = None,
        processing_errors: Optional[Dict[str, Any]] = None,
    ) -> FileProcessingMetadata:
        """Track file processing metadata.

        Args:
            processor_name: Name of the processor
            processor_version: Version of the processor
            input_checksum: Checksum of input file
            processing_time_ms: Processing time in milliseconds
            output_checksum: Checksum of output file
            records_processed: Number of records processed
            records_skipped: Number of records skipped
            processing_errors: Processing errors

        Returns:
            FileProcessingMetadata instance
        """
        return FileProcessingMetadata(
            processing_id=str(uuid.uuid4()),
            processor_name=processor_name,
            processor_version=processor_version,
            input_checksum=input_checksum,
            output_checksum=output_checksum,
            processing_time_ms=processing_time_ms,
            records_processed=records_processed,
            records_skipped=records_skipped,
            processing_errors=processing_errors,
        )

    def create_version_metadata(
        self,
        version_number: int,
        created_by: Optional[str] = None,
        change_summary: Optional[str] = None,
        previous_version_id: Optional[str] = None,
    ) -> FileVersionMetadata:
        """Create file version metadata.

        Args:
            version_number: Version number
            created_by: User who created this version
            change_summary: Summary of changes
            previous_version_id: Previous version ID

        Returns:
            FileVersionMetadata instance
        """
        return FileVersionMetadata(
            version_number=version_number,
            version_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            change_summary=change_summary,
            previous_version_id=previous_version_id,
            is_current=True,
        )

    def update_access_metadata(
        self, file_id: str, accessed_by: Optional[str] = None
    ) -> Optional[FileAccessMetadata]:
        """Update access metadata for a file.

        Args:
            file_id: File identifier
            accessed_by: User who accessed the file

        Returns:
            Updated FileAccessMetadata or None if file not found
        """
        if file_id in self._metadata_cache:
            metadata = self._metadata_cache[file_id]
            if metadata.access_metadata:
                metadata.access_metadata.last_accessed = datetime.now(timezone.utc)
                metadata.access_metadata.access_count += 1
                return metadata.access_metadata
        return None

    def get_file_metadata(self, file_id: str) -> Optional[AuditFileMetadata]:
        """Get metadata for a file.

        Args:
            file_id: File identifier

        Returns:
            AuditFileMetadata or None if not found
        """
        return self._metadata_cache.get(file_id)

    def get_operation_history(
        self, limit: int = 100, operation_type: Optional[str] = None
    ) -> List[FileOperationMetadata]:
        """Get operation history.

        Args:
            limit: Maximum number of operations to return
            operation_type: Filter by operation type

        Returns:
            List of FileOperationMetadata
        """
        history = self._operation_history
        if operation_type:
            history = [op for op in history if op.operation_type == operation_type]
        return history[-limit:]

    def export_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Export metadata as dictionary.

        Args:
            file_id: File identifier

        Returns:
            Dictionary representation or None if not found
        """
        metadata = self.get_file_metadata(file_id)
        if metadata:
            return metadata.model_dump(mode="json", exclude_none=True)
        return None

    def import_metadata(self, metadata_dict: Dict[str, Any]) -> AuditFileMetadata:
        """Import metadata from dictionary.

        Args:
            metadata_dict: Dictionary representation

        Returns:
            AuditFileMetadata instance
        """
        metadata = AuditFileMetadata(**metadata_dict)
        self._metadata_cache[metadata.file_id] = metadata
        return metadata

    def clear_cache(self) -> int:
        """Clear metadata cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._metadata_cache)
        self._metadata_cache.clear()
        logger.info(f"Cleared {count} metadata entries from cache")
        return count

    def get_cache_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of entries in cache
        """
        return len(self._metadata_cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics.

        Returns:
            Dictionary with statistics
        """
        total_operations = len(self._operation_history)
        successful_operations = sum(1 for op in self._operation_history if op.success)
        failed_operations = total_operations - successful_operations

        operation_types = {}
        for op in self._operation_history:
            operation_types[op.operation_type] = (
                operation_types.get(op.operation_type, 0) + 1
            )

        return {
            "cache_size": self.get_cache_size(),
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "operation_types": operation_types,
        }
