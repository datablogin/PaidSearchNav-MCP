"""Export models for Google Ads import files."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from paidsearchnav.core.models.base import BasePSNModel
from pydantic import Field, field_validator


class ExportFileType(str, Enum):
    """Types of export files."""

    KEYWORD_CHANGES = "keyword_changes"
    NEGATIVE_KEYWORDS = "negative_keywords"
    BID_ADJUSTMENTS = "bid_adjustments"
    CAMPAIGN_CHANGES = "campaign_changes"
    IMPORT_PACKAGE = "import_package"


class ExportStatus(str, Enum):
    """Status of export operation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"


class KeywordChange(BasePSNModel):
    """Represents a keyword change for Google Ads import."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign: str = Field(..., description="Campaign name")
    ad_group: str = Field(..., description="Ad group name")
    keyword: str = Field(..., description="Keyword text")
    match_type: str = Field(..., description="Match type (Exact, Phrase, Broad)")
    status: str = Field(default="Enabled", description="Keyword status")
    max_cpc: Optional[float] = Field(None, description="Maximum CPC bid")
    final_url: Optional[str] = Field(None, description="Final URL for the keyword")

    @field_validator("match_type")
    def validate_match_type(cls, v):
        """Validate match type."""
        valid_types = ["Exact", "Phrase", "Broad"]
        if v not in valid_types:
            raise ValueError(f"Match type must be one of {valid_types}")
        return v

    @field_validator("status")
    def validate_status(cls, v):
        """Validate keyword status."""
        valid_statuses = ["Enabled", "Paused", "Removed"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class NegativeKeyword(BasePSNModel):
    """Represents a negative keyword for Google Ads import."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign: str = Field(..., description="Campaign name")
    ad_group: Optional[str] = Field(
        None, description="Ad group name or [Campaign] for campaign-level"
    )
    keyword: str = Field(..., description="Negative keyword text")
    match_type: str = Field(..., description="Match type (Exact, Phrase, Broad)")

    @field_validator("match_type")
    def validate_match_type(cls, v):
        """Validate match type."""
        valid_types = ["Exact", "Phrase", "Broad"]
        if v not in valid_types:
            raise ValueError(f"Match type must be one of {valid_types}")
        return v

    @property
    def level(self) -> str:
        """Get the level of the negative keyword (campaign or ad group)."""
        return "campaign" if self.ad_group in (None, "[Campaign]") else "ad_group"


class BidAdjustment(BasePSNModel):
    """Represents a bid adjustment for Google Ads import."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign: str = Field(..., description="Campaign name")
    location: Optional[str] = Field(None, description="Location for adjustment")
    device: Optional[str] = Field(None, description="Device for adjustment")
    bid_adjustment: str = Field(
        ..., description="Bid adjustment percentage (e.g., +20%)"
    )

    @field_validator("bid_adjustment")
    def validate_bid_adjustment(cls, v):
        """Validate bid adjustment format."""
        if not v:
            raise ValueError("Bid adjustment cannot be empty")
        # Must be in format like +20%, -15%, or 0%
        if not (v.startswith("+") or v.startswith("-") or v[0].isdigit()):
            raise ValueError("Bid adjustment must start with +, -, or a digit")
        if not v.endswith("%"):
            raise ValueError("Bid adjustment must end with %")
        # Validate the numeric part
        numeric_part = v[:-1].lstrip("+-")
        try:
            float(numeric_part)
        except ValueError:
            raise ValueError("Invalid bid adjustment percentage")
        return v


class CampaignChange(BasePSNModel):
    """Represents a campaign setting change for Google Ads import."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign: str = Field(..., description="Campaign name")
    status: Optional[str] = Field(None, description="Campaign status")
    budget: Optional[float] = Field(None, description="Daily budget")
    bid_strategy: Optional[str] = Field(None, description="Bidding strategy")
    target_cpa: Optional[float] = Field(None, description="Target CPA for CPA bidding")
    target_roas: Optional[float] = Field(
        None, description="Target ROAS for ROAS bidding"
    )

    @field_validator("status")
    def validate_status(cls, v):
        """Validate campaign status."""
        if v is None:
            return v
        valid_statuses = ["Enabled", "Paused", "Removed"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class ExportFile(BasePSNModel):
    """Represents an exported file."""

    file_type: ExportFileType = Field(..., description="Type of export file")
    file_name: str = Field(..., description="Name of the file")
    file_path: Optional[Path] = Field(None, description="Local path to the file")
    s3_key: Optional[str] = Field(None, description="S3 key for the file")
    s3_url: Optional[str] = Field(None, description="S3 download URL")
    row_count: int = Field(default=0, description="Number of rows in the file")
    file_size: int = Field(default=0, description="File size in bytes")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)


class KeywordChangesFile(ExportFile):
    """Export file containing keyword changes."""

    file_type: ExportFileType = Field(default=ExportFileType.KEYWORD_CHANGES)
    changes: List[KeywordChange] = Field(default_factory=list)


class NegativeKeywordsFile(ExportFile):
    """Export file containing negative keywords."""

    file_type: ExportFileType = Field(default=ExportFileType.NEGATIVE_KEYWORDS)
    negatives: List[NegativeKeyword] = Field(default_factory=list)


class BidAdjustmentsFile(ExportFile):
    """Export file containing bid adjustments."""

    file_type: ExportFileType = Field(default=ExportFileType.BID_ADJUSTMENTS)
    adjustments: List[BidAdjustment] = Field(default_factory=list)


class CampaignChangesFile(ExportFile):
    """Export file containing campaign changes."""

    file_type: ExportFileType = Field(default=ExportFileType.CAMPAIGN_CHANGES)
    changes: List[CampaignChange] = Field(default_factory=list)


class ImportPackage(BasePSNModel):
    """Package containing all import files."""

    package_id: str = Field(..., description="Unique package identifier")
    analysis_id: str = Field(..., description="Associated analysis ID")
    customer_id: str = Field(..., description="Google Ads customer ID")
    files: List[ExportFile] = Field(
        default_factory=list, description="List of export files"
    )
    package_path: Optional[Path] = Field(None, description="Local path to package ZIP")
    s3_key: Optional[str] = Field(None, description="S3 key for package ZIP")
    s3_url: Optional[str] = Field(None, description="S3 download URL for package")
    total_changes: int = Field(
        default=0, description="Total number of changes across all files"
    )
    status: ExportStatus = Field(default=ExportStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if package is valid (no validation errors)."""
        if self.errors:
            return False
        return all(not f.validation_errors for f in self.files)

    @property
    def total_file_size(self) -> int:
        """Get total size of all files."""
        return sum(f.file_size for f in self.files)


class ExportRequest(BasePSNModel):
    """Request to export Google Ads import files."""

    analysis_id: str = Field(..., description="Analysis to export from")
    customer_id: str = Field(..., description="Google Ads customer ID")
    include_keyword_changes: bool = Field(default=True)
    include_negative_keywords: bool = Field(default=True)
    include_bid_adjustments: bool = Field(default=True)
    include_campaign_changes: bool = Field(default=True)
    create_package: bool = Field(default=True, description="Create ZIP package")
    validate_before_export: bool = Field(
        default=True, description="Validate data before export"
    )


class ExportResult(BasePSNModel):
    """Result of export operation."""

    request: ExportRequest = Field(..., description="Original export request")
    package: Optional[ImportPackage] = Field(
        None, description="Generated import package"
    )
    status: ExportStatus = Field(..., description="Export status")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)
    duration_seconds: Optional[float] = Field(None)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def mark_completed(self):
        """Mark export as completed."""
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.status = ExportStatus.COMPLETED if not self.errors else ExportStatus.FAILED
