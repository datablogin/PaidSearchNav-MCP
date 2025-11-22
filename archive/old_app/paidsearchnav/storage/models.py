"""SQLAlchemy models for storage."""

import uuid
from enum import Enum

import pytz
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship, validates

from paidsearchnav.storage.s3_utils import validate_s3_path


# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class UserType(Enum):
    """User type enumeration."""

    INDIVIDUAL = "individual"
    AGENCY = "agency"

    @classmethod
    def from_string(cls, value: str) -> "UserType":
        """Convert string value to UserType enum instance.

        Args:
            value: String value from database or API

        Returns:
            UserType enum instance

        Raises:
            TypeError: If value is not a string
            ValueError: If value is not a valid UserType
        """
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value).__name__}: {value!r}")

        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid user type: {value}")

    def is_individual(self) -> bool:
        """Check if this is an individual user type.

        Returns:
            True if this is UserType.INDIVIDUAL
        """
        return self == UserType.INDIVIDUAL

    def is_agency(self) -> bool:
        """Check if this is an agency user type.

        Returns:
            True if this is UserType.AGENCY
        """
        return self == UserType.AGENCY


class User(Base):
    """Database model for users."""

    __tablename__ = "users"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # User information
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    user_type = Column(String(20), nullable=False, default=UserType.INDIVIDUAL.value)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    customers = relationship(
        "Customer", back_populates="user", cascade="all, delete-orphan"
    )
    customer_access = relationship(
        "CustomerAccess", back_populates="user", cascade="all, delete-orphan"
    )
    audits = relationship("Audit", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship(
        "Schedule", back_populates="user", cascade="all, delete-orphan"
    )
    reports = relationship(
        "Report", back_populates="user", cascade="all, delete-orphan"
    )

    @validates("user_type")
    def validate_user_type(self, key, value):
        """Validate user type."""
        # Validate that the string value can be converted to UserType enum
        try:
            UserType.from_string(value)
            return value
        except (ValueError, TypeError) as e:
            raise ValueError(str(e))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "user_type": self.user_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GoogleAdsAccount(Base):
    """Database model for Google Ads accounts."""

    __tablename__ = "google_ads_accounts"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Google Ads account information
    customer_id = Column(
        String(20), nullable=False, unique=True
    )  # Google Ads customer ID
    account_name = Column(String(255), nullable=False)
    manager_customer_id = Column(String(20), nullable=True)  # MCC parent
    currency_code = Column(String(3), nullable=False)
    timezone = Column(String(50), nullable=False)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer_accounts = relationship(
        "CustomerGoogleAdsAccount",
        back_populates="google_ads_account",
        cascade="all, delete-orphan",
    )
    analysis_records = relationship(
        "AnalysisRecord",
        back_populates="google_ads_account",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_google_ads_customer_id", "customer_id"),
        Index("idx_google_ads_manager", "manager_customer_id"),
    )

    @validates("customer_id")
    def validate_customer_id(self, key, value):
        """Validate Google Ads customer ID format."""
        if not value:
            raise ValueError("Google Ads customer ID cannot be empty")
        # Google Ads customer IDs are 7-10 digits
        cleaned_id = value.strip().replace("-", "")
        if not cleaned_id.isdigit():
            raise ValueError(
                "Google Ads customer ID must contain only digits and hyphens"
            )
        if len(cleaned_id) < 7 or len(cleaned_id) > 10:
            raise ValueError("Google Ads customer ID must be 7-10 digits")
        return cleaned_id  # Store without hyphens

    @validates("manager_customer_id")
    def validate_manager_customer_id(self, key, value):
        """Validate manager customer ID format."""
        if not value:
            return value
        # Same validation as customer_id
        cleaned_id = value.strip().replace("-", "")
        if not cleaned_id.isdigit():
            raise ValueError("Manager customer ID must contain only digits and hyphens")
        if len(cleaned_id) < 7 or len(cleaned_id) > 10:
            raise ValueError("Manager customer ID must be 7-10 digits")
        return cleaned_id

    @validates("currency_code")
    def validate_currency_code(self, key, value):
        """Validate currency code format."""
        if not value or len(value) != 3:
            raise ValueError("Currency code must be exactly 3 characters")
        return value.upper()

    @validates("timezone")
    def validate_timezone(self, key, value):
        """Validate timezone against pytz timezone list."""
        if not value:
            raise ValueError("Timezone cannot be empty")
        if value not in pytz.all_timezones:
            raise ValueError(
                f"Invalid timezone: {value}. Must be a valid IANA timezone"
            )
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "account_name": self.account_name,
            "manager_customer_id": self.manager_customer_id,
            "currency_code": self.currency_code,
            "timezone": self.timezone,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Customer(Base):
    """Database model for customers."""

    __tablename__ = "customers"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Customer information
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    google_ads_customer_id = Column(String(20), nullable=True, unique=True)

    # Owner (for individual customers)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # S3 folder path for this customer
    s3_folder_path = Column(String(500), nullable=True)

    # Settings and status
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    # Audit information
    last_audit_date = Column(DateTime, nullable=True)
    next_scheduled_audit = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="customers")
    customer_access = relationship(
        "CustomerAccess", back_populates="customer", cascade="all, delete-orphan"
    )
    audits = relationship(
        "Audit", back_populates="customer", cascade="all, delete-orphan"
    )
    schedules = relationship(
        "Schedule", back_populates="customer", cascade="all, delete-orphan"
    )
    google_ads_accounts = relationship(
        "CustomerGoogleAdsAccount",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_customer_user", "user_id", "created_at"),
        Index("idx_customer_google_ads", "google_ads_customer_id"),
    )

    @validates("google_ads_customer_id")
    def validate_google_ads_customer_id(self, key, value):
        """Validate Google Ads customer ID format."""
        if not value:
            return value
        # Google Ads customer IDs are 7-10 digits (aligned with API validation)
        cleaned_id = value.strip().replace("-", "")
        if not cleaned_id.isdigit():
            raise ValueError(
                "Google Ads customer ID must contain only digits and hyphens"
            )
        if len(cleaned_id) < 7 or len(cleaned_id) > 10:
            raise ValueError("Google Ads customer ID must be 7-10 digits")
        return cleaned_id  # Store without hyphens

    @validates("s3_folder_path")
    def validate_s3_folder_path(self, key, value):
        """Validate S3 folder path format."""
        if not value:
            return value
        # Use centralized validation
        validate_s3_path(value)
        return value.rstrip("/")  # Remove trailing slash for consistency

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "google_ads_customer_id": self.google_ads_customer_id,
            "user_id": self.user_id,
            "s3_folder_path": self.s3_folder_path,
            "settings": self.settings,
            "is_active": self.is_active,
            "last_audit_date": self.last_audit_date.isoformat()
            if self.last_audit_date
            else None,
            "next_scheduled_audit": self.next_scheduled_audit.isoformat()
            if self.next_scheduled_audit
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CustomerGoogleAdsAccount(Base):
    """Junction table for Customer and GoogleAdsAccount many-to-many relationship."""

    __tablename__ = "customer_google_ads_accounts"

    # Composite primary key
    customer_id = Column(String(36), ForeignKey("customers.id"), primary_key=True)
    google_ads_account_id = Column(
        String(36), ForeignKey("google_ads_accounts.id"), primary_key=True
    )

    # Additional fields
    account_role = Column(String(50), nullable=False)  # "owner", "manager", "viewer"
    s3_folder_path = Column(
        String(500), nullable=False
    )  # S3 path for this customer-account combo

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    customer = relationship("Customer", back_populates="google_ads_accounts")
    google_ads_account = relationship(
        "GoogleAdsAccount", back_populates="customer_accounts"
    )

    # Indexes
    __table_args__ = (
        Index("idx_cga_customer_google_ads", "customer_id", "google_ads_account_id"),
        Index("idx_cga_google_ads_customer", "google_ads_account_id", "customer_id"),
    )

    @validates("account_role")
    def validate_account_role(self, key, value):
        """Validate account role."""
        valid_roles = {"owner", "manager", "viewer"}
        if value not in valid_roles:
            raise ValueError(
                f"Invalid account role: {value}. Must be one of {valid_roles}"
            )
        return value

    @validates("s3_folder_path")
    def validate_s3_folder_path(self, key, value):
        """Validate S3 folder path format."""
        if not value:
            raise ValueError("S3 folder path cannot be empty")
        # Use centralized validation
        validate_s3_path(value)
        return value.rstrip("/")  # Remove trailing slash for consistency

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "customer_id": self.customer_id,
            "google_ads_account_id": self.google_ads_account_id,
            "account_role": self.account_role,
            "s3_folder_path": self.s3_folder_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CustomerAccess(Base):
    """Database model for customer access control (agency access to client customers)."""

    __tablename__ = "customer_access"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Access relationship
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )

    # Access permissions
    access_level = Column(
        String(20), nullable=False, default="read"
    )  # read, write, admin

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="customer_access")
    customer = relationship("Customer", back_populates="customer_access")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_access_user_customer", "user_id", "customer_id", unique=True),
        Index("idx_access_customer", "customer_id", "is_active"),
    )

    @validates("access_level")
    def validate_access_level(self, key, value):
        """Validate access level."""
        if value not in ["read", "write", "admin"]:
            raise ValueError(f"Invalid access level: {value}")
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "access_level": self.access_level,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AnalysisRecord(Base):
    """Database model for storing analysis results."""

    __tablename__ = "analysis_results"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Customer and analysis info
    customer_id = Column(String(20), nullable=False, index=True)
    google_ads_account_id = Column(
        String(36), ForeignKey("google_ads_accounts.id"), nullable=True
    )
    analysis_type = Column(String(50), nullable=False, index=True)
    analyzer_name = Column(String(100), nullable=False)

    # Time range
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Status
    status = Column(String(20), nullable=False, default="completed")

    # S3 file references
    s3_input_path = Column(String(500), nullable=True)  # S3 path for input data
    s3_output_path = Column(String(500), nullable=True)  # S3 path for output/results

    # Audit run metadata
    audit_id = Column(String(36), ForeignKey("audits.id"), nullable=True)
    run_metadata = Column(JSON, default=dict)  # Additional metadata about the run

    # Metrics summary (for quick queries)
    total_recommendations = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    potential_cost_savings = Column(Float, default=0.0)
    potential_conversion_increase = Column(Float, default=0.0)

    # Full result data
    result_data = Column(JSON, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    google_ads_account = relationship(
        "GoogleAdsAccount", back_populates="analysis_records"
    )
    audit = relationship("Audit")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_customer_date", "customer_id", "created_at"),
        Index("idx_type_date", "analysis_type", "created_at"),
        Index("idx_customer_type", "customer_id", "analysis_type"),
        Index("idx_google_ads_account", "google_ads_account_id"),
        Index("idx_audit_id", "audit_id"),
    )

    @validates("customer_id")
    def validate_customer_id(self, key, value):
        """Validate customer ID format (Google Ads customer ID)."""
        if not value or not value.strip():
            raise ValueError("Customer ID cannot be empty")
        # Google Ads customer IDs are 7-10 digits (aligned with API validation)
        cleaned_id = value.strip().replace("-", "")
        if not cleaned_id.isdigit():
            raise ValueError("Customer ID must contain only digits and hyphens")
        if len(cleaned_id) < 7 or len(cleaned_id) > 10:
            raise ValueError("Customer ID must be 7-10 digits")
        return cleaned_id  # Store without hyphens

    @validates("s3_input_path", "s3_output_path")
    def validate_s3_paths(self, key, value):
        """Validate S3 path format."""
        if not value:
            return value
        # Use centralized validation
        try:
            validate_s3_path(value)
        except ValueError as e:
            # Re-raise with field name for clarity
            raise ValueError(f"{key}: {str(e)}")
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "google_ads_account_id": self.google_ads_account_id,
            "analysis_type": self.analysis_type,
            "analyzer_name": self.analyzer_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "s3_input_path": self.s3_input_path,
            "s3_output_path": self.s3_output_path,
            "audit_id": self.audit_id,
            "run_metadata": self.run_metadata,
            "total_recommendations": self.total_recommendations,
            "critical_issues": self.critical_issues,
            "potential_cost_savings": self.potential_cost_savings,
            "potential_conversion_increase": self.potential_conversion_increase,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ComparisonRecord(Base):
    """Database model for storing comparisons between analyses."""

    __tablename__ = "analysis_comparisons"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Analysis IDs being compared
    analysis_id_1 = Column(String(36), nullable=False, index=True)
    analysis_id_2 = Column(String(36), nullable=False, index=True)

    # Comparison metadata
    customer_id = Column(String(50), nullable=False, index=True)
    comparison_type = Column(String(50), nullable=False)  # e.g., "period_over_period"

    # Comparison results
    comparison_data = Column(JSON, nullable=False)

    # Summary metrics
    recommendations_added = Column(Integer, default=0)
    recommendations_resolved = Column(Integer, default=0)
    cost_savings_change = Column(Float, default=0.0)
    conversion_change = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Indexes
    __table_args__ = (Index("idx_comparison_customer", "customer_id", "created_at"),)


class JobExecutionRecord(Base):
    """Database model for storing job execution history."""

    __tablename__ = "job_executions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Job identification
    job_id = Column(String(100), nullable=False, index=True)
    job_type = Column(String(50), nullable=False, index=True)

    # Execution status
    status = Column(String(20), nullable=False, index=True)

    # Execution timestamps
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)

    # Execution details
    result = Column(JSON, nullable=True)
    error = Column(String(1000), nullable=True)
    context = Column(JSON, nullable=False, default=dict)

    # Retry information
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_job_id_status", "job_id", "status"),
        Index("idx_job_type_status", "job_type", "status"),
        Index("idx_started_at", "started_at"),
    )


class Audit(Base):
    """Database model for audit tracking."""

    __tablename__ = "audits"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Customer and user info
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Audit details
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Float, default=0.0)

    # Configuration
    analyzers = Column(JSON, nullable=False)  # List of analyzer names
    config = Column(JSON, default=dict)  # Audit configuration

    # Results summary (for quick queries)
    total_recommendations = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    potential_savings = Column(Float, default=0.0)

    # Error handling
    error_message = Column(String(1000), nullable=True)
    retry_count = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer = relationship("Customer", back_populates="audits")
    user = relationship("User", back_populates="audits")
    reports = relationship(
        "Report", back_populates="audit", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_audit_customer_status", "customer_id", "status"),
        Index("idx_audit_customer_created", "customer_id", "created_at"),
        Index("idx_audit_user_created", "user_id", "created_at"),
    )

    @validates("status")
    def validate_status(self, key, status):
        """Validate audit status values."""
        valid_statuses = {"pending", "running", "completed", "failed", "cancelled"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid audit status: {status}")
        return status

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "analyzers": self.analyzers,
            "config": self.config,
            "total_recommendations": self.total_recommendations,
            "critical_issues": self.critical_issues,
            "potential_savings": self.potential_savings,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Schedule(Base):
    """Database model for audit schedules."""

    __tablename__ = "schedules"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Customer and user info
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Schedule details
    name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)

    # Configuration
    analyzers = Column(JSON, nullable=False)  # List of analyzer names
    config = Column(JSON, default=dict)  # Schedule configuration

    # Timing
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer = relationship("Customer", back_populates="schedules")
    user = relationship("User", back_populates="schedules")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_customer_enabled", "customer_id", "enabled"),
        Index("idx_next_run", "next_run_at"),
        Index("idx_enabled_next_run", "enabled", "next_run_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "user_id": self.user_id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "enabled": self.enabled,
            "analyzers": self.analyzers,
            "config": self.config,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Report(Base):
    """Database model for generated reports."""

    __tablename__ = "reports"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Audit and user info
    audit_id = Column(String(36), ForeignKey("audits.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Report details
    format = Column(String(20), nullable=False)  # pdf, html, excel, csv
    template = Column(String(50), nullable=False)  # executive_summary, detailed, etc.
    status = Column(String(20), nullable=False, default="generating", index=True)

    # File information
    file_path = Column(String(500), nullable=True)  # Path to generated file
    file_size = Column(Integer, nullable=True)  # Size in bytes

    # Configuration
    config = Column(JSON, default=dict)  # Report generation configuration

    # Error handling
    error_message = Column(String(1000), nullable=True)

    # Expiration
    expires_at = Column(DateTime, nullable=True)  # When report expires

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    audit = relationship("Audit", back_populates="reports")
    user = relationship("User", back_populates="reports")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_report_audit_status", "audit_id", "status"),
        Index("idx_report_expires_at", "expires_at"),
        Index("idx_report_user_created", "user_id", "created_at"),
    )

    @validates("status")
    def validate_status(self, key, status):
        """Validate report status values."""
        valid_statuses = {"generating", "completed", "failed", "expired"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid report status: {status}")
        return status

    @validates("format")
    def validate_format(self, key, format):
        """Validate report format values."""
        valid_formats = {"pdf", "html", "excel", "csv", "json"}
        if format not in valid_formats:
            raise ValueError(f"Invalid report format: {format}")
        return format

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "user_id": self.user_id,
            "format": self.format,
            "template": self.template,
            "status": self.status,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "config": self.config,
            "error_message": self.error_message,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GoogleAdsScript(Base):
    """Database model for Google Ads Scripts."""

    __tablename__ = "google_ads_scripts"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Customer and user info
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Script details
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    script_type = Column(String(50), nullable=False, index=True)

    # Script code and configuration
    script_code = Column(String, nullable=False)  # JavaScript code
    parameters = Column(JSON, default=dict)  # Script parameters
    schedule = Column(String(100), nullable=True)  # Cron expression for scheduling

    # Status and settings
    enabled = Column(Boolean, default=True)
    version = Column(String(20), default="1.0.0")
    tags = Column(JSON, default=list)  # Tags for categorization

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer = relationship("Customer")
    user = relationship("User")
    executions = relationship(
        "ScriptExecution", back_populates="script", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_script_customer_type", "customer_id", "script_type"),
        Index("idx_script_user_created", "user_id", "created_at"),
        Index("idx_script_enabled", "enabled"),
    )

    @validates("script_type")
    def validate_script_type(self, key, script_type):
        """Validate script type values."""
        valid_types = {
            "negative_keyword",
            "conflict_detection",
            "placement_audit",
            "master_negative_list",
            "n_gram_analysis",
            "custom",
        }
        if script_type not in valid_types:
            raise ValueError(f"Invalid script type: {script_type}")
        return script_type

    @validates("script_code")
    def validate_script_code(self, key, script_code):
        """Validate script code size and basic content."""
        if not script_code or not script_code.strip():
            raise ValueError("Script code cannot be empty")

        # Size limit: 100KB for script code
        if len(script_code) > 100000:
            raise ValueError("Script code too large (max 100KB)")

        # Basic security checks - reject obvious malicious patterns
        dangerous_patterns = [
            "eval(",
            "Function(",
            "setTimeout(",
            "setInterval(",
            "XMLHttpRequest",
            "fetch(",
            "import(",
            "require(",
        ]

        script_lower = script_code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in script_lower:
                raise ValueError(
                    f"Script contains potentially dangerous pattern: {pattern}"
                )

        return script_code

    @validates("parameters")
    def validate_parameters(self, key, parameters):
        """Validate script parameters size and content."""
        if parameters is None:
            return {}

        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a dictionary")

        # Convert to JSON string to check size
        import json

        try:
            param_str = json.dumps(parameters)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Parameters must be JSON serializable: {e}")

        # Size limit: 10KB for parameters
        if len(param_str) > 10000:
            raise ValueError("Parameters too large (max 10KB)")

        # Basic validation of parameter values
        for key_name, value in parameters.items():
            if not isinstance(key_name, str):
                raise ValueError("Parameter keys must be strings")

            # Reject excessively long parameter names or values
            if len(key_name) > 100:
                raise ValueError(f"Parameter key too long: {key_name}")

            if isinstance(value, str) and len(value) > 1000:
                raise ValueError(f"Parameter value too long for key: {key_name}")

        return parameters

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "script_type": self.script_type,
            "script_code": self.script_code,
            "parameters": self.parameters,
            "schedule": self.schedule,
            "enabled": self.enabled,
            "version": self.version,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScriptExecution(Base):
    """Database model for Google Ads Script executions."""

    __tablename__ = "script_executions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Script and user info
    script_id = Column(
        String(36), ForeignKey("google_ads_scripts.id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Execution details
    status = Column(String(20), nullable=False, default="pending", index=True)
    execution_type = Column(String(20), default="manual")  # manual, scheduled

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time = Column(Float, nullable=True)  # seconds

    # Results and metrics
    rows_processed = Column(Integer, default=0)
    changes_made = Column(Integer, default=0)
    result_data = Column(JSON, nullable=True)  # Full execution results

    # Error handling
    error_message = Column(String(2000), nullable=True)
    warnings = Column(JSON, default=list)  # List of warning messages

    # External IDs (for Google Ads API integration)
    google_execution_id = Column(String(100), nullable=True, unique=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    script = relationship("GoogleAdsScript", back_populates="executions")
    user = relationship("User")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_execution_script_status", "script_id", "status"),
        Index("idx_execution_user_created", "user_id", "created_at"),
        Index("idx_execution_status_created", "status", "created_at"),
        Index("idx_execution_google_id", "google_execution_id"),
    )

    @validates("status")
    def validate_status(self, key, status):
        """Validate execution status values."""
        valid_statuses = {
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
            "timeout",
        }
        if status not in valid_statuses:
            raise ValueError(f"Invalid execution status: {status}")
        return status

    @validates("execution_type")
    def validate_execution_type(self, key, execution_type):
        """Validate execution type values."""
        valid_types = {"manual", "scheduled", "triggered"}
        if execution_type not in valid_types:
            raise ValueError(f"Invalid execution type: {execution_type}")
        return execution_type

    @validates("result_data")
    def validate_result_data(self, key, result_data):
        """Validate result data size to prevent excessive storage."""
        if result_data is None:
            return None

        import json

        try:
            result_str = json.dumps(result_data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Result data must be JSON serializable: {e}")

        # Size limit: 1MB for result data
        if len(result_str) > 1000000:
            raise ValueError("Result data too large (max 1MB)")

        return result_data

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "script_id": self.script_id,
            "user_id": self.user_id,
            "status": self.status,
            "execution_type": self.execution_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "execution_time": self.execution_time,
            "rows_processed": self.rows_processed,
            "changes_made": self.changes_made,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "google_execution_id": self.google_execution_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowDefinition(Base):
    """Database model for workflow definitions."""

    __tablename__ = "workflow_definitions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Workflow information
    name = Column(String(255), nullable=False, unique=True, index=True)
    version = Column(String(20), nullable=False)
    definition = Column(JSON, nullable=False)  # Workflow definition JSON

    # Status
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    executions = relationship(
        "WorkflowExecution",
        back_populates="workflow_definition",
        cascade="all, delete-orphan",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_workflow_def_name_version", "name", "version"),
        Index("idx_workflow_def_enabled", "enabled"),
    )

    @validates("name")
    def validate_name(self, key, value):
        """Validate workflow name."""
        if not value or not value.strip():
            raise ValueError("Workflow name cannot be empty")
        if len(value) > 255:
            raise ValueError("Workflow name too long (max 255 characters)")
        return value

    @validates("version")
    def validate_version(self, key, value):
        """Validate workflow version."""
        if not value or not value.strip():
            raise ValueError("Workflow version cannot be empty")
        if len(value) > 20:
            raise ValueError("Workflow version too long (max 20 characters)")
        return value

    @validates("definition")
    def validate_definition(self, key, value):
        """Validate workflow definition."""
        if not value:
            raise ValueError("Workflow definition cannot be empty")
        if not isinstance(value, dict):
            raise ValueError("Workflow definition must be a dictionary")

        # Basic validation - ensure it has expected structure
        if "steps" not in value and "name" not in value:
            raise ValueError("Workflow definition must contain 'steps' or 'name'")

        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "definition": self.definition,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowExecution(Base):
    """Database model for workflow executions."""

    __tablename__ = "workflow_executions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign keys
    workflow_definition_id = Column(
        String(36), ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    customer_id = Column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )

    # Execution details
    status = Column(String(20), nullable=False, default="pending", index=True)
    current_step = Column(String(255), nullable=True)
    context = Column(JSON, default=dict)  # Execution context data

    # Error handling
    error_message = Column(String(2000), nullable=True)
    retry_count = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    workflow_definition = relationship(
        "WorkflowDefinition", back_populates="executions"
    )
    customer = relationship("Customer")
    steps = relationship(
        "WorkflowStep", back_populates="execution", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_workflow_exec_status", "status", "created_at"),
        Index("idx_workflow_exec_customer", "customer_id", "status"),
        Index("idx_workflow_exec_definition", "workflow_definition_id", "status"),
        Index("idx_workflow_exec_started", "started_at"),
    )

    @validates("status")
    def validate_status(self, key, value):
        """Validate execution status."""
        valid_statuses = {
            "pending",
            "running",
            "paused",
            "completed",
            "failed",
            "cancelled",
        }
        if value not in valid_statuses:
            raise ValueError(f"Invalid execution status: {value}")
        return value

    @validates("retry_count")
    def validate_retry_count(self, key, value):
        """Validate retry count."""
        if value < 0:
            raise ValueError("Retry count cannot be negative")
        if value > 100:
            raise ValueError("Retry count exceeds maximum (100)")
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workflow_definition_id": self.workflow_definition_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "current_step": self.current_step,
            "context": self.context,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowStep(Base):
    """Database model for workflow step executions."""

    __tablename__ = "workflow_step_executions"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key
    execution_id = Column(
        String(36), ForeignKey("workflow_executions.id"), nullable=False, index=True
    )

    # Step details
    step_name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)

    # Step data
    input_data = Column(JSON, nullable=True)  # Input parameters for the step
    output_data = Column(JSON, nullable=True)  # Output/result from the step

    # Error handling
    error_message = Column(String(2000), nullable=True)
    retry_count = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    execution = relationship("WorkflowExecution", back_populates="steps")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_workflow_step_execution", "execution_id", "created_at"),
        Index("idx_workflow_step_status", "status"),
        Index("idx_workflow_step_name", "step_name"),
    )

    @validates("status")
    def validate_status(self, key, value):
        """Validate step status."""
        valid_statuses = {"pending", "running", "completed", "failed", "skipped"}
        if value not in valid_statuses:
            raise ValueError(f"Invalid step status: {value}")
        return value

    @validates("step_name")
    def validate_step_name(self, key, value):
        """Validate step name."""
        if not value or not value.strip():
            raise ValueError("Step name cannot be empty")
        if len(value) > 255:
            raise ValueError("Step name too long (max 255 characters)")
        return value

    @validates("retry_count")
    def validate_retry_count(self, key, value):
        """Validate retry count."""
        if value < 0:
            raise ValueError("Retry count cannot be negative")
        if value > 10:
            raise ValueError("Retry count exceeds maximum (10)")
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "step_name": self.step_name,
            "status": self.status,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnalysisFile(Base):
    """Database model for tracking files associated with analysis results."""

    __tablename__ = "analysis_files"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Analysis relationship
    analysis_id = Column(
        String(36), ForeignKey("analysis_results.id"), nullable=False, index=True
    )

    # File information
    file_path = Column(String(500), nullable=False)  # Full S3 path
    file_name = Column(String(255), nullable=False)
    file_category = Column(String(20), nullable=False)  # input_csv, output_report, etc.
    file_size = Column(Integer, nullable=False)  # Size in bytes
    content_type = Column(String(100), nullable=True)
    checksum = Column(String(64), nullable=True)  # MD5 or SHA256 checksum

    # File metadata
    file_metadata = Column(JSON, default=dict)  # Additional file metadata

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    analysis = relationship("AnalysisRecord", backref="files")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_analysis_files_analysis", "analysis_id", "file_category"),
        Index("idx_analysis_files_category", "file_category"),
        Index("idx_analysis_files_created", "created_at"),
    )

    @validates("file_category")
    def validate_file_category(self, key, value):
        """Validate file category values."""
        valid_categories = {
            "input_csv",
            "input_keywords",
            "input_search_terms",
            "output_report",
            "output_actionable",
            "output_summary",
            "output_scripts",
            "audit_log",
            "other",
        }
        if value not in valid_categories:
            raise ValueError(f"Invalid file category: {value}")
        return value

    @validates("file_path")
    def validate_file_path(self, key, value):
        """Validate file path format."""
        if not value:
            raise ValueError("File path cannot be empty")
        # Use centralized validation
        try:
            validate_s3_path(value)
        except ValueError as e:
            raise ValueError(f"file_path: {str(e)}")
        return value

    @validates("file_size")
    def validate_file_size(self, key, value):
        """Validate file size is positive."""
        if value < 0:
            raise ValueError("File size must be non-negative")
        return value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_category": self.file_category,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "checksum": self.checksum,
            "file_metadata": self.file_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
