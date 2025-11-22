"""Customer initialization models and data structures."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from paidsearchnav_mcp.models.base import BasePSNModel


class BusinessType(str, Enum):
    """Type of business for categorization."""

    RETAIL = "retail"
    ECOMMERCE = "ecommerce"
    SERVICE = "service"
    LEGAL = "legal"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    AUTOMOTIVE = "automotive"
    REAL_ESTATE = "real_estate"
    EDUCATION = "education"
    NONPROFIT = "nonprofit"
    OTHER = "other"


class InitializationStatus(str, Enum):
    """Status of customer initialization process."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class CustomerInitRequest(BaseModel):
    """Request model for customer initialization."""

    name: str = Field(..., min_length=1, max_length=100, description="Customer name")
    email: str = Field(..., description="Primary contact email")
    business_type: BusinessType = Field(
        ..., description="Type of business for categorization"
    )
    google_ads_customer_ids: List[str] = Field(
        ..., min_length=1, description="List of Google Ads customer IDs to link"
    )
    contact_person: Optional[str] = Field(
        None, max_length=100, description="Primary contact person name"
    )
    phone: Optional[str] = Field(
        None, max_length=20, description="Contact phone number"
    )
    company_website: Optional[str] = Field(
        None, max_length=255, description="Company website URL"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Additional notes about the customer"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise PydanticCustomError("value_error", "Invalid email format")
        return v

    @field_validator("google_ads_customer_ids")
    @classmethod
    def validate_google_ads_ids(cls, v: List[str]) -> List[str]:
        """Validate Google Ads customer IDs format."""
        for customer_id in v:
            # Remove hyphens if present and validate
            clean_id = customer_id.replace("-", "")
            if not clean_id.isdigit() or len(clean_id) != 10:
                raise PydanticCustomError(
                    "value_error",
                    f"Invalid Google Ads customer ID format: {customer_id}. "
                    "Must be 10 digits (with or without hyphens)",
                )
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v:
            # Basic phone number validation - remove common separators
            cleaned = "".join(c for c in v if c.isdigit())
            if len(cleaned) < 10 or len(cleaned) > 15:
                raise PydanticCustomError(
                    "value_error", "Phone number must be between 10 and 15 digits"
                )
        return v


class S3FolderStructure(BaseModel):
    """S3 folder structure information."""

    base_path: str = Field(..., description="Base S3 path for customer")
    customer_name_sanitized: str = Field(
        ..., description="Sanitized customer name used in paths"
    )
    customer_number: str = Field(..., description="Unique customer number")
    inputs_path: str = Field(..., description="Path for input files")
    outputs_path: str = Field(..., description="Path for output files")
    reports_path: str = Field(..., description="Path for report files")
    actionable_files_path: str = Field(
        ..., description="Path for actionable export files"
    )
    created_folders: List[str] = Field(
        default_factory=list, description="List of successfully created folder markers"
    )


class GoogleAdsAccountLink(BaseModel):
    """Google Ads account linking information."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    account_name: str = Field(..., description="Account display name")
    currency_code: Optional[str] = Field(None, description="Account currency")
    time_zone: Optional[str] = Field(None, description="Account time zone")
    account_type: Optional[str] = Field(None, description="Account type")
    accessible: bool = Field(True, description="Whether account is accessible")
    link_status: str = Field(default="active", description="Status of the account link")
    validation_errors: List[str] = Field(
        default_factory=list, description="Any validation errors encountered"
    )


class CustomerRecord(BasePSNModel):
    """Database customer record."""

    customer_id: str = Field(..., description="Unique customer identifier")
    name: str = Field(..., description="Customer name")
    name_sanitized: str = Field(..., description="Sanitized name for paths")
    email: str = Field(..., description="Primary contact email")
    business_type: BusinessType = Field(..., description="Business type")
    contact_person: Optional[str] = Field(None, description="Contact person")
    phone: Optional[str] = Field(None, description="Phone number")
    company_website: Optional[str] = Field(None, description="Website URL")
    notes: Optional[str] = Field(None, description="Customer notes")

    # S3 configuration
    s3_base_path: str = Field(..., description="Base S3 path")
    s3_bucket_name: Optional[str] = Field(None, description="S3 bucket name")

    # Status tracking
    initialization_status: InitializationStatus = Field(
        default=InitializationStatus.PENDING,
        description="Current initialization status",
    )

    # Linked Google Ads accounts
    google_ads_accounts: List[GoogleAdsAccountLink] = Field(
        default_factory=list, description="Linked Google Ads accounts"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When customer was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )


class CustomerInitResponse(BaseModel):
    """Response model for customer initialization."""

    success: bool = Field(..., description="Whether initialization succeeded")
    customer_record: Optional[CustomerRecord] = Field(
        None, description="Created customer record"
    )
    s3_structure: Optional[S3FolderStructure] = Field(
        None, description="Created S3 folder structure"
    )
    google_ads_links: List[GoogleAdsAccountLink] = Field(
        default_factory=list, description="Linked Google Ads accounts"
    )
    initialization_status: InitializationStatus = Field(
        ..., description="Final initialization status"
    )
    errors: List[str] = Field(
        default_factory=list, description="Any errors encountered during initialization"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings generated during initialization"
    )
    duration_seconds: float = Field(
        ..., description="Time taken to complete initialization"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When initialization completed"
    )


class InitializationProgress(BaseModel):
    """Progress tracking for customer initialization."""

    customer_id: str = Field(..., description="Customer identifier")
    current_step: str = Field(..., description="Current initialization step")
    total_steps: int = Field(..., description="Total number of steps")
    completed_steps: int = Field(..., description="Number of completed steps")
    status: InitializationStatus = Field(..., description="Current status")
    last_update: datetime = Field(
        default_factory=datetime.utcnow, description="Last progress update"
    )
    details: Dict[str, str] = Field(
        default_factory=dict, description="Additional progress details"
    )


class ValidationResult(BaseModel):
    """Result of customer initialization validation."""

    valid: bool = Field(..., description="Whether validation passed")
    customer_exists: bool = Field(..., description="Customer record exists")
    s3_structure_valid: bool = Field(..., description="S3 structure is valid")
    google_ads_links_valid: bool = Field(..., description="Google Ads links are valid")
    database_consistent: bool = Field(
        ..., description="Database relationships are consistent"
    )
    errors: List[str] = Field(
        default_factory=list, description="Validation errors found"
    )
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When validation was performed"
    )


# Utility functions for generating identifiers
def generate_customer_number() -> str:
    """Generate a unique customer number."""
    return str(uuid.uuid4()).replace("-", "").upper()[:12]


def generate_customer_id() -> str:
    """Generate a unique customer ID."""
    return f"cust_{uuid.uuid4()}"
