"""Data models for file management operations."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class FileCategory(Enum):
    """File category enumeration."""

    INPUT = "input"
    REPORT = "report"
    ACTIONABLE = "actionable"


class FileType(Enum):
    """Supported file types for audit operations."""

    KEYWORDS_CSV = "keywords.csv"
    SEARCH_TERMS_CSV = "search_terms.csv"
    CAMPAIGNS_CSV = "campaigns.csv"
    AD_GROUPS_CSV = "ad_groups.csv"
    ANALYSIS_SUMMARY_MD = "analysis_summary.md"
    RECOMMENDATIONS_MD = "recommendations.md"
    PERFORMANCE_INSIGHTS_MD = "performance_insights.md"
    CHANGES_CSV = "changes.csv"
    NEGATIVE_KEYWORDS_CSV = "negative_keywords.csv"
    BID_ADJUSTMENTS_CSV = "bid_adjustments.csv"
    PAUSE_KEYWORDS_CSV = "pause_keywords.csv"


class FileMetadata(BaseModel):
    """Metadata for a file stored in S3."""

    file_path: str = Field(..., description="S3 path to the file")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    upload_timestamp: datetime = Field(..., description="Upload timestamp")
    checksum: str = Field(..., description="File checksum (MD5 or SHA256)")
    audit_run_id: str = Field(..., description="Associated audit run ID")
    file_category: FileCategory = Field(..., description="Category of the file")
    file_type: Optional[str] = Field(None, description="Specific file type")
    customer_id: str = Field(..., description="Customer ID")
    google_ads_account_id: str = Field(..., description="Google Ads account ID")
    audit_date: str = Field(..., description="Audit date in YYYY-MM-DD format")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate S3 file path format."""
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        if not v.startswith("s3://") and not v.startswith("/"):
            raise ValueError("File path must be an absolute path or S3 URI")
        return v.strip()

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size."""
        if v < 0:
            raise ValueError("File size cannot be negative")
        return v

    @field_validator("audit_date")
    @classmethod
    def validate_audit_date(cls, v: str) -> str:
        """Validate audit date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Audit date must be in YYYY-MM-DD format")
        return v


class InputFileRecord(BaseModel):
    """Record of an uploaded input CSV file."""

    file_metadata: FileMetadata = Field(..., description="File metadata")
    validation_status: str = Field(..., description="Validation status")
    validation_errors: List[str] = Field(
        default_factory=list, description="Validation errors if any"
    )
    row_count: Optional[int] = Field(None, description="Number of rows in CSV")
    column_names: Optional[List[str]] = Field(None, description="Column names in CSV")


class OutputFileRecord(BaseModel):
    """Record of generated output files."""

    report_files: Dict[str, FileMetadata] = Field(
        default_factory=dict, description="Report file metadata by filename"
    )
    actionable_files: Dict[str, FileMetadata] = Field(
        default_factory=dict, description="Actionable file metadata by filename"
    )
    generation_timestamp: datetime = Field(
        ..., description="Timestamp when files were generated"
    )
    total_size_bytes: int = Field(
        0, description="Total size of all output files in bytes"
    )


class AuditFileSet(BaseModel):
    """Complete set of files for an audit."""

    customer_id: str = Field(..., description="Customer ID")
    google_ads_account_id: str = Field(..., description="Google Ads account ID")
    audit_date: str = Field(..., description="Audit date in YYYY-MM-DD format")
    audit_run_id: str = Field(..., description="Audit run ID")
    input_files: List[InputFileRecord] = Field(
        default_factory=list, description="Input file records"
    )
    output_files: Optional[OutputFileRecord] = Field(
        None, description="Output file records"
    )
    total_file_count: int = Field(0, description="Total number of files")
    total_size_bytes: int = Field(0, description="Total size in bytes")

    @field_validator("audit_date")
    @classmethod
    def validate_audit_date(cls, v: str) -> str:
        """Validate audit date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Audit date must be in YYYY-MM-DD format")
        return v


class CleanupReport(BaseModel):
    """Report of cleanup operations."""

    files_deleted: int = Field(0, description="Number of files deleted")
    bytes_freed: int = Field(0, description="Number of bytes freed")
    customers_affected: int = Field(0, description="Number of customers affected")
    oldest_file_date: Optional[datetime] = Field(
        None, description="Date of oldest file deleted"
    )
    newest_file_date: Optional[datetime] = Field(
        None, description="Date of newest file deleted"
    )
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    cleanup_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Cleanup operation timestamp"
    )


class FileUploadRequest(BaseModel):
    """Request model for file upload operations."""

    customer_id: str = Field(..., description="Customer ID")
    google_ads_account_id: str = Field(..., description="Google Ads account ID")
    audit_date: str = Field(..., description="Audit date in YYYY-MM-DD format")
    filename: str = Field(..., description="Name of the file")
    content_type: Optional[str] = Field(None, description="MIME content type")
    metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata")

    @field_validator("audit_date")
    @classmethod
    def validate_audit_date(cls, v: str) -> str:
        """Validate audit date format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Audit date must be in YYYY-MM-DD format")
        return v


class FileValidationResult(BaseModel):
    """Result of file validation."""

    is_valid: bool = Field(..., description="Whether file is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    file_info: Dict[str, Any] = Field(
        default_factory=dict, description="File information"
    )
