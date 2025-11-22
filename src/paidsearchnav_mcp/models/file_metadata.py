"""Metadata models for file operations."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class S3FileMetadata(BaseModel):
    """S3-specific file metadata."""

    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key")
    etag: str = Field(..., description="ETag of the S3 object")
    version_id: Optional[str] = Field(
        None, description="Version ID if versioning enabled"
    )
    storage_class: Optional[str] = Field("STANDARD", description="S3 storage class")
    server_side_encryption: Optional[str] = Field(None, description="Encryption type")
    metadata_tags: Dict[str, str] = Field(
        default_factory=dict, description="S3 object metadata tags"
    )


class FileOperationMetadata(BaseModel):
    """Metadata for file operations."""

    operation_id: str = Field(..., description="Unique operation ID")
    operation_type: str = Field(
        ..., description="Type of operation (upload/download/delete)"
    )
    timestamp: datetime = Field(..., description="Operation timestamp")
    duration_ms: Optional[int] = Field(
        None, description="Operation duration in milliseconds"
    )
    success: bool = Field(..., description="Whether operation succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    user_id: Optional[str] = Field(None, description="User who performed the operation")
    client_info: Optional[Dict[str, Any]] = Field(
        None, description="Client information"
    )


class FileProcessingMetadata(BaseModel):
    """Metadata for file processing operations."""

    processing_id: str = Field(..., description="Unique processing ID")
    processor_name: str = Field(..., description="Name of the processor")
    processor_version: str = Field(..., description="Version of the processor")
    input_checksum: str = Field(..., description="Checksum of input file")
    output_checksum: Optional[str] = Field(None, description="Checksum of output file")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    records_processed: Optional[int] = Field(
        None, description="Number of records processed"
    )
    records_skipped: Optional[int] = Field(
        None, description="Number of records skipped"
    )
    processing_errors: Optional[Dict[str, Any]] = Field(
        None, description="Processing errors"
    )


class FileVersionMetadata(BaseModel):
    """Metadata for file versioning."""

    version_number: int = Field(..., description="Version number")
    version_id: str = Field(..., description="Unique version ID")
    created_at: datetime = Field(..., description="Version creation timestamp")
    created_by: Optional[str] = Field(None, description="User who created this version")
    change_summary: Optional[str] = Field(None, description="Summary of changes")
    previous_version_id: Optional[str] = Field(None, description="Previous version ID")
    is_current: bool = Field(True, description="Whether this is the current version")


class FileAccessMetadata(BaseModel):
    """Metadata for file access tracking."""

    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    access_count: int = Field(0, description="Number of times accessed")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    last_modified_by: Optional[str] = Field(None, description="User who last modified")
    permissions: Dict[str, str] = Field(
        default_factory=dict, description="File permissions"
    )
    retention_policy: Optional[str] = Field(None, description="Retention policy")
    expiry_date: Optional[datetime] = Field(None, description="File expiry date")


class AuditFileMetadata(BaseModel):
    """Complete metadata for audit files."""

    file_id: str = Field(..., description="Unique file identifier")
    audit_run_id: str = Field(..., description="Associated audit run ID")
    customer_id: str = Field(..., description="Customer ID")
    google_ads_account_id: str = Field(..., description="Google Ads account ID")
    audit_date: str = Field(..., description="Audit date in YYYY-MM-DD format")
    file_category: str = Field(
        ..., description="File category (input/report/actionable)"
    )
    file_type: str = Field(..., description="Specific file type")
    file_name: str = Field(..., description="Original file name")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="File checksum")
    s3_metadata: Optional[S3FileMetadata] = Field(
        None, description="S3-specific metadata"
    )
    operation_metadata: Optional[FileOperationMetadata] = Field(
        None, description="Operation metadata"
    )
    processing_metadata: Optional[FileProcessingMetadata] = Field(
        None, description="Processing metadata"
    )
    version_metadata: Optional[FileVersionMetadata] = Field(
        None, description="Version metadata"
    )
    access_metadata: Optional[FileAccessMetadata] = Field(
        None, description="Access metadata"
    )
    custom_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata fields"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Metadata creation timestamp"
    )

    @field_validator("audit_date")
    @classmethod
    def validate_audit_date(cls, v: str) -> str:
        """Validate audit date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Audit date must be in YYYY-MM-DD format")
        return v

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size."""
        if v < 0:
            raise ValueError("File size cannot be negative")
        return v
