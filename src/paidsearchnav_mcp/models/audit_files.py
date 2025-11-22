"""Models for audit file tracking and S3 integration."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field

from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.core.models.base import BasePSNModel


class FileCategory(str, Enum):
    """Categories for file classification."""

    INPUT_CSV = "input_csv"
    INPUT_KEYWORDS = "input_keywords"
    INPUT_SEARCH_TERMS = "input_search_terms"
    OUTPUT_REPORT = "output_report"
    OUTPUT_ACTIONABLE = "output_actionable"
    OUTPUT_SUMMARY = "output_summary"
    OUTPUT_SCRIPTS = "output_scripts"
    AUDIT_LOG = "audit_log"
    OTHER = "other"


class S3FileReference(BasePSNModel):
    """Reference to an S3 file with metadata."""

    file_path: str = Field(..., description="Full S3 path to the file")
    file_name: str = Field(..., description="Name of the file")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    checksum: str = Field(..., description="File checksum (MD5 or SHA256)")
    upload_timestamp: datetime = Field(..., description="When the file was uploaded")
    file_category: FileCategory = Field(..., description="Category of the file")

    # Optional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional file metadata"
    )


class AnalysisWithFiles(BasePSNModel):
    """Analysis result with associated input and output files."""

    analysis: AnalysisResult = Field(..., description="The analysis result")
    input_files: list[S3FileReference] = Field(
        default_factory=list, description="Input files used for analysis"
    )
    output_files: list[S3FileReference] = Field(
        default_factory=list, description="Output files generated from analysis"
    )
    s3_folder_path: str = Field(..., description="S3 folder path for this analysis")

    @property
    def total_input_size(self) -> int:
        """Get total size of input files in bytes."""
        return sum(f.file_size for f in self.input_files)

    @property
    def total_output_size(self) -> int:
        """Get total size of output files in bytes."""
        return sum(f.file_size for f in self.output_files)

    def get_files_by_category(self, category: FileCategory) -> list[S3FileReference]:
        """Get files filtered by category."""
        all_files = self.input_files + self.output_files
        return [f for f in all_files if f.file_category == category]


class AuditSummary(BasePSNModel):
    """Summary information for a customer audit."""

    analysis_id: str = Field(..., description="Analysis ID")
    customer_name: str = Field(..., description="Customer name")
    google_ads_account_id: str = Field(..., description="Google Ads account ID")
    audit_date: datetime = Field(..., description="Date when audit was performed")
    status: str = Field(..., description="Audit status")
    total_recommendations: int = Field(default=0, description="Total recommendations")
    cost_savings: float = Field(default=0.0, description="Potential cost savings")
    input_file_count: int = Field(default=0, description="Number of input files")
    output_file_count: int = Field(default=0, description="Number of output files")
    s3_folder_path: str = Field(..., description="S3 folder path for the audit")

    # Additional summary fields
    analysis_type: str = Field(..., description="Type of analysis performed")
    processing_time: float | None = Field(
        None, description="Analysis processing time in seconds"
    )
    total_file_size: int = Field(default=0, description="Total size of all files")


class AuditFileSet(BasePSNModel):
    """Complete set of files for an audit."""

    analysis_id: str = Field(..., description="Analysis ID")
    input_files: list[S3FileReference] = Field(
        default_factory=list, description="Input files"
    )
    output_reports: list[S3FileReference] = Field(
        default_factory=list, description="Generated report files"
    )
    output_actionable: list[S3FileReference] = Field(
        default_factory=list, description="Actionable output files (scripts, etc.)"
    )
    audit_logs: list[S3FileReference] = Field(
        default_factory=list, description="Audit execution logs"
    )
    s3_folder_path: str = Field(..., description="Base S3 folder path")

    @property
    def all_files(self) -> list[S3FileReference]:
        """Get all files as a single list."""
        return (
            self.input_files
            + self.output_reports
            + self.output_actionable
            + self.audit_logs
        )

    @property
    def total_files(self) -> int:
        """Get total number of files."""
        return len(self.all_files)

    @property
    def total_size(self) -> int:
        """Get total size of all files."""
        return sum(f.file_size for f in self.all_files)


class ArchiveReport(BasePSNModel):
    """Report from archiving old analyses."""

    archived_count: int = Field(default=0, description="Number of analyses archived")
    files_archived: int = Field(default=0, description="Number of files archived")
    space_freed: int = Field(default=0, description="Space freed in bytes")
    archive_location: str | None = Field(None, description="Archive location path")
    archive_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When archiving was performed",
    )
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )

    @property
    def space_freed_mb(self) -> float:
        """Get space freed in megabytes."""
        return self.space_freed / (1024 * 1024)

    @property
    def space_freed_gb(self) -> float:
        """Get space freed in gigabytes."""
        return self.space_freed / (1024 * 1024 * 1024)
