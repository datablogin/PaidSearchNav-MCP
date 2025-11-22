"""Configuration management for PaidSearchNav."""

import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class SecretProvider(str, Enum):
    """Secret provider backends."""

    ENVIRONMENT = "environment"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    HASHICORP_VAULT = "hashicorp_vault"


class TokenStorageBackend(str, Enum):
    """Token storage backend options.

    - FILE_ENCRYPTED: Default encrypted file storage in user's home directory
    - KEYRING: OS-level keyring storage (macOS Keychain, Windows Credential Manager, Linux Secret Service)
    - SECRET_MANAGER: Cloud secret manager integration (AWS, GCP, HashiCorp Vault)
    """

    FILE_ENCRYPTED = "file_encrypted"
    KEYRING = "keyring"
    SECRET_MANAGER = "secret_manager"


class StorageBackend(str, Enum):
    """Storage backend options."""

    POSTGRESQL = "postgresql"
    BIGQUERY = "bigquery"
    FIRESTORE = "firestore"


class BigQueryTier(str, Enum):
    """BigQuery integration tiers for premium analytics.

    - DISABLED: BigQuery integration disabled
    - STANDARD: CSV-only exports (no BigQuery)
    - PREMIUM: BigQuery analytics and real-time insights
    - ENTERPRISE: Premium + ML models and predictive analytics
    """

    DISABLED = "disabled"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class LogFormat(str, Enum):
    """Log format options."""

    JSON = "json"
    TEXT = "text"


class GoogleAdsConfig(BaseModel):
    """Google Ads API configuration."""

    developer_token: SecretStr = Field(..., min_length=1)
    client_id: str = Field(..., min_length=1)
    client_secret: SecretStr = Field(..., min_length=1)
    refresh_token: SecretStr | None = None
    login_customer_id: str | None = None
    api_version: str = Field(default="v18")
    oauth_redirect_uris: list[str] = Field(
        default=["http://localhost:8080/callback"],
        description="OAuth2 redirect URIs for consent flows",
    )
    # Pagination settings
    default_page_size: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Default page size for Google Ads API requests (1-10000)",
    )
    max_page_size: int = Field(
        default=10000,
        ge=1,
        le=10000,
        description="Maximum page size for Google Ads API requests (Google Ads limit is 10000)",
    )

    # Rate limiting settings for Google Ads API operations
    enable_rate_limiting: bool = Field(
        default=True, description="Enable proactive rate limiting for Google Ads API"
    )

    # Search operation rate limits
    search_requests_per_minute: int = Field(
        default=300, ge=1, description="Search requests per minute per customer"
    )
    search_requests_per_hour: int = Field(
        default=18000, ge=1, description="Search requests per hour per customer"
    )
    search_requests_per_day: int = Field(
        default=432000, ge=1, description="Search requests per day per customer"
    )

    # Mutate operation rate limits
    mutate_requests_per_minute: int = Field(
        default=100, ge=1, description="Mutate requests per minute per customer"
    )
    mutate_requests_per_hour: int = Field(
        default=6000, ge=1, description="Mutate requests per hour per customer"
    )
    mutate_requests_per_day: int = Field(
        default=144000, ge=1, description="Mutate requests per day per customer"
    )

    # Report operation rate limits
    report_requests_per_minute: int = Field(
        default=133, ge=1, description="Report requests per minute per customer"
    )
    report_requests_per_hour: int = Field(
        default=7980, ge=1, description="Report requests per hour per customer"
    )
    report_requests_per_day: int = Field(
        default=191520, ge=1, description="Report requests per day per customer"
    )

    # Bulk operation rate limits (more conservative)
    bulk_requests_per_minute: int = Field(
        default=15, ge=1, description="Bulk mutate requests per minute per customer"
    )
    bulk_requests_per_hour: int = Field(
        default=900, ge=1, description="Bulk mutate requests per hour per customer"
    )
    bulk_requests_per_day: int = Field(
        default=21600, ge=1, description="Bulk mutate requests per day per customer"
    )

    # Account info operation rate limits
    account_requests_per_minute: int = Field(
        default=80, ge=1, description="Account info requests per minute per customer"
    )
    account_requests_per_hour: int = Field(
        default=4800, ge=1, description="Account info requests per hour per customer"
    )
    account_requests_per_day: int = Field(
        default=115200, ge=1, description="Account info requests per day per customer"
    )

    # Backoff configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for rate-limited operations",
    )
    backoff_multiplier: float = Field(
        default=2.0, ge=1.0, le=10.0, description="Exponential backoff multiplier"
    )
    max_backoff_seconds: float = Field(
        default=60.0, ge=1.0, le=300.0, description="Maximum backoff time in seconds"
    )

    @field_validator("login_customer_id")
    @classmethod
    def validate_customer_id(cls, v: str | None) -> str | None:
        """Validate and clean customer ID."""
        if v:
            # Remove dashes from customer ID
            cleaned = v.replace("-", "")
            if not cleaned.isdigit() or len(cleaned) != 10:
                raise ValueError("Customer ID must be 10 digits")
            return cleaned
        return v

    @model_validator(mode="after")
    def validate_rate_limit_consistency(self) -> "GoogleAdsConfig":
        """Validate that rate limits are logically consistent across time windows."""
        operation_types = [
            (
                "search",
                self.search_requests_per_minute,
                self.search_requests_per_hour,
                self.search_requests_per_day,
            ),
            (
                "mutate",
                self.mutate_requests_per_minute,
                self.mutate_requests_per_hour,
                self.mutate_requests_per_day,
            ),
            (
                "report",
                self.report_requests_per_minute,
                self.report_requests_per_hour,
                self.report_requests_per_day,
            ),
            (
                "bulk",
                self.bulk_requests_per_minute,
                self.bulk_requests_per_hour,
                self.bulk_requests_per_day,
            ),
            (
                "account",
                self.account_requests_per_minute,
                self.account_requests_per_hour,
                self.account_requests_per_day,
            ),
        ]

        for op_name, per_minute, per_hour, per_day in operation_types:
            # Check minute * 60 doesn't exceed hour limit
            if per_minute * 60 > per_hour:
                raise ValueError(
                    f"{op_name} rate limit inconsistency: "
                    f"{per_minute}/min * 60 = {per_minute * 60} exceeds {per_hour}/hour limit"
                )

            # Check hour * 24 doesn't exceed day limit
            if per_hour * 24 > per_day:
                raise ValueError(
                    f"{op_name} rate limit inconsistency: "
                    f"{per_hour}/hour * 24 = {per_hour * 24} exceeds {per_day}/day limit"
                )

            # Check minute * 1440 doesn't exceed day limit
            if per_minute * 1440 > per_day:
                raise ValueError(
                    f"{op_name} rate limit inconsistency: "
                    f"{per_minute}/min * 1440 = {per_minute * 1440} exceeds {per_day}/day limit"
                )

        # Validate backoff configuration
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        if self.backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0")

        if self.max_backoff_seconds < 1.0:
            raise ValueError("max_backoff_seconds must be >= 1.0")

        return self


class GA4Config(BaseModel):
    """Google Analytics 4 API configuration for real-time analytics."""

    enabled: bool = Field(default=False, description="Enable GA4 API integration")
    property_id: str = Field(
        default="", description="GA4 Property ID (e.g., 123456789)"
    )

    # Authentication
    service_account_key_path: str | None = Field(
        default=None, description="Path to service account JSON key file"
    )
    use_application_default_credentials: bool = Field(
        default=True, description="Use Application Default Credentials"
    )

    # API settings
    api_version: str = Field(default="v1beta", description="GA4 Data API version")

    # Rate limiting settings for GA4 Data API
    enable_rate_limiting: bool = Field(
        default=True, description="Enable proactive rate limiting for GA4 Data API"
    )
    requests_per_minute: int = Field(
        default=120, ge=1, description="GA4 API requests per minute per property"
    )
    requests_per_hour: int = Field(
        default=7200, ge=1, description="GA4 API requests per hour per property"
    )
    requests_per_day: int = Field(
        default=172800, ge=1, description="GA4 API requests per day per property"
    )

    # Data freshness settings
    max_data_lag_hours: int = Field(
        default=2, ge=1, le=48, description="Maximum acceptable data lag in hours"
    )
    enable_realtime_data: bool = Field(
        default=True, description="Enable real-time data API (runRealtimeReport)"
    )

    # Retry and timeout settings
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts"
    )
    backoff_multiplier: float = Field(
        default=2.0, ge=1.0, le=10.0, description="Exponential backoff multiplier"
    )
    max_backoff_seconds: float = Field(
        default=60.0, ge=1.0, le=300.0, description="Maximum backoff time in seconds"
    )
    request_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0, description="Request timeout in seconds"
    )

    # Caching configuration
    enable_response_cache: bool = Field(
        default=True, description="Enable caching of API responses"
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache TTL for API responses in seconds",
    )

    # Cost monitoring
    enable_cost_monitoring: bool = Field(
        default=True, description="Enable cost monitoring for GA4 API usage"
    )
    daily_cost_limit_usd: float = Field(
        default=50.0, ge=0, description="Daily GA4 API cost limit in USD"
    )
    cost_alert_threshold_usd: float = Field(
        default=40.0, ge=0, description="Cost threshold for alerts in USD"
    )

    # Business analysis settings
    average_cpa_usd: float = Field(
        default=50.0,
        ge=0,
        description="Average cost per acquisition for ROAS calculations",
    )

    # Batch processing settings
    max_concurrent_requests: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent API requests"
    )
    batch_size: int = Field(
        default=100, ge=1, le=1000, description="Batch size for bulk operations"
    )

    @field_validator("property_id")
    @classmethod
    def validate_property_id(cls, v: str) -> str:
        """Validate GA4 property ID format."""
        if v and not v.isdigit():
            raise ValueError("GA4 property ID must be numeric")
        return v

    @model_validator(mode="after")
    def validate_ga4_config(self) -> "GA4Config":
        """Validate GA4 configuration."""
        if self.enabled and not self.property_id:
            raise ValueError("property_id is required when GA4 is enabled")

        # Validate authentication configuration
        if self.enabled:
            auth_methods = [
                self.service_account_key_path,
                self.use_application_default_credentials,
            ]
            if not any(auth_methods):
                raise ValueError(
                    "At least one authentication method must be configured: "
                    "service_account_key_path or use_application_default_credentials"
                )

        # Validate cost controls
        if self.daily_cost_limit_usd < self.cost_alert_threshold_usd:
            raise ValueError(
                "daily_cost_limit_usd must be greater than cost_alert_threshold_usd"
            )

        # Validate rate limit consistency
        if self.requests_per_minute * 60 > self.requests_per_hour:
            raise ValueError(
                "Rate limit inconsistency: requests_per_minute * 60 exceeds requests_per_hour"
            )

        if self.requests_per_hour * 24 > self.requests_per_day:
            raise ValueError(
                "Rate limit inconsistency: requests_per_hour * 24 exceeds requests_per_day"
            )

        # Validate timeout settings
        if self.max_backoff_seconds < self.request_timeout_seconds:
            raise ValueError(
                "max_backoff_seconds should be greater than request_timeout_seconds"
            )

        return self

    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> bool:
        """Validate GA4 date range format and logic."""
        import re
        from datetime import datetime

        # GA4 accepts relative dates or YYYY-MM-DD format
        ga4_relative_dates = {
            "today",
            "yesterday",
            "7daysAgo",
            "14daysAgo",
            "30daysAgo",
            "60daysAgo",
            "90daysAgo",
        }

        date_pattern = r"^\d{4}-\d{2}-\d{2}$"

        for date_val in [start_date, end_date]:
            if date_val not in ga4_relative_dates and not re.match(
                date_pattern, date_val
            ):
                raise ValueError(
                    f"Invalid date format: {date_val}. Must be YYYY-MM-DD or GA4 relative date"
                )

        # If both are YYYY-MM-DD, validate start <= end
        if re.match(date_pattern, start_date) and re.match(date_pattern, end_date):
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if start > end:
                raise ValueError("start_date must be before or equal to end_date")

        return True

    @staticmethod
    def validate_dimensions_and_metrics(
        dimensions: list[str], metrics: list[str]
    ) -> bool:
        """Validate GA4 dimension and metric names."""
        # Common GA4 dimensions
        valid_dimensions = {
            "source",
            "medium",
            "campaign",
            "campaignName",
            "country",
            "city",
            "deviceCategory",
            "landingPage",
            "sessionSource",
            "sessionMedium",
            "date",
            "dateHour",
            "dayOfWeek",
            "hour",
            "month",
            "year",
        }

        # Common GA4 metrics
        valid_metrics = {
            "sessions",
            "bounceRate",
            "averageSessionDuration",
            "conversions",
            "totalRevenue",
            "sessionConversionRate",
            "activeUsers",
            "newUsers",
            "screenPageViews",
            "eventCount",
            "purchaseRevenue",
        }

        for dim in dimensions:
            if dim not in valid_dimensions:
                raise ValueError(f"Unknown GA4 dimension: {dim}")

        for metric in metrics:
            if metric not in valid_metrics:
                raise ValueError(f"Unknown GA4 metric: {metric}")

        return True


class BigQueryConfig(BaseModel):
    """BigQuery configuration for premium analytics tier."""

    enabled: bool = Field(default=False, description="Enable BigQuery integration")
    tier: BigQueryTier = Field(
        default=BigQueryTier.DISABLED, description="BigQuery tier level"
    )
    project_id: str = Field(default="", description="Google Cloud project ID")
    dataset_id: str = Field(default="paidsearchnav", description="BigQuery dataset ID")
    location: str = Field(default="US", description="BigQuery dataset location")

    # Authentication
    service_account_key_path: str | None = Field(
        default=None, description="Path to service account JSON key file"
    )
    use_application_default_credentials: bool = Field(
        default=True, description="Use Application Default Credentials"
    )

    # Performance and cost optimization
    enable_query_cache: bool = Field(
        default=True, description="Enable BigQuery query cache"
    )
    enable_real_time_streaming: bool = Field(
        default=False, description="Enable real-time streaming inserts"
    )
    enable_ml_models: bool = Field(
        default=False, description="Enable BigQuery ML models (Enterprise tier)"
    )

    # Cost controls
    daily_cost_limit_usd: float = Field(
        default=100.0, ge=0, description="Daily BigQuery cost limit in USD"
    )
    max_query_bytes: int = Field(
        default=1024**4,
        ge=1024**3,
        description="Maximum bytes per query (default: 1TB)",
    )
    query_timeout_seconds: int = Field(
        default=300, ge=30, le=3600, description="Query timeout in seconds"
    )

    # Table configuration
    default_partition_expiration_days: int | None = Field(
        default=None, description="Default partition expiration in days"
    )
    enable_row_level_security: bool = Field(
        default=True, description="Enable row-level security for multi-tenant data"
    )

    @model_validator(mode="after")
    def validate_bigquery_config(self) -> "BigQueryConfig":
        """Validate BigQuery configuration."""
        if self.enabled and self.tier == BigQueryTier.DISABLED:
            raise ValueError("Cannot enable BigQuery with DISABLED tier")

        if self.tier != BigQueryTier.DISABLED and not self.project_id:
            raise ValueError("project_id is required for BigQuery integration")

        if self.enable_ml_models and self.tier != BigQueryTier.ENTERPRISE:
            raise ValueError("ML models require ENTERPRISE tier")

        # Validate authentication configuration
        if self.tier != BigQueryTier.DISABLED:
            auth_methods = [
                self.service_account_key_path,
                self.use_application_default_credentials,
            ]
            if not any(auth_methods):
                raise ValueError(
                    "At least one authentication method must be configured: "
                    "service_account_key_path or use_application_default_credentials"
                )

        # Validate cost controls
        if self.daily_cost_limit_usd < 0:
            raise ValueError("daily_cost_limit_usd must be non-negative")

        if self.max_query_bytes < 1024**3:  # Minimum 1GB
            raise ValueError("max_query_bytes must be at least 1GB (1073741824 bytes)")

        if self.query_timeout_seconds < 30 or self.query_timeout_seconds > 3600:
            raise ValueError(
                "query_timeout_seconds must be between 30 and 3600 seconds"
            )

        # Validate BigQuery-specific settings
        if self.location not in ["US", "EU", "asia-northeast1", "asia-southeast1"]:
            # Allow other regions but warn about potential issues
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"BigQuery location '{self.location}' may not be optimal. "
                "Consider using 'US', 'EU', or a regional location for better performance."
            )

        # Validate tier-specific features
        if self.enable_real_time_streaming and self.tier == BigQueryTier.STANDARD:
            raise ValueError("Real-time streaming requires PREMIUM or ENTERPRISE tier")

        # Validate partition expiration
        if self.default_partition_expiration_days is not None:
            if self.default_partition_expiration_days < 1:
                raise ValueError(
                    "default_partition_expiration_days must be at least 1 day"
                )
            if self.default_partition_expiration_days > 7300:  # ~20 years
                raise ValueError(
                    "default_partition_expiration_days cannot exceed 7300 days"
                )

        return self


class S3Config(BaseModel):
    """S3 configuration for customer data storage."""

    enabled: bool = Field(default=False, description="Enable S3 integration")
    bucket_name: str | None = Field(default=None, description="S3 bucket name")
    region: str = Field(default="us-east-1", description="AWS region")
    prefix: str = Field(
        default="PaidSearchNav", description="S3 prefix for multi-tenant scenarios"
    )
    access_key_id: str | None = Field(
        default=None, description="AWS access key ID (optional with IAM)"
    )
    secret_access_key: SecretStr | None = Field(
        default=None, description="AWS secret access key (optional with IAM)"
    )
    session_token: SecretStr | None = Field(
        default=None, description="AWS session token for temporary credentials"
    )

    # Upload/download settings
    multipart_threshold: int = Field(
        default=100 * 1024 * 1024,  # DEFAULT_MULTIPART_THRESHOLD constant
        description="Multipart upload threshold in bytes (100MB)",
    )
    max_concurrency: int = Field(
        default=10, ge=1, le=50, description="Max concurrent operations"
    )

    # Retry and timeout settings
    max_attempts: int = Field(
        default=3, ge=1, le=10, description="Maximum retry attempts"
    )
    connect_timeout: float = Field(
        default=60.0, ge=1.0, description="Connection timeout in seconds"
    )
    read_timeout: float = Field(
        default=60.0, ge=1.0, description="Read timeout in seconds"
    )

    # Security settings
    allowed_ip_ranges: list[str] = Field(
        default_factory=lambda: [],
        description="Allowed IP ranges for access control (empty = all allowed)",
    )
    aws_access_key_id: str | None = Field(
        default=None, description="AWS access key ID for security operations"
    )
    aws_secret_access_key: SecretStr | None = Field(
        default=None, description="AWS secret access key for security operations"
    )
    logging_bucket: str | None = Field(
        default=None, description="S3 bucket for access logs"
    )
    max_presigned_url_expiration: int = Field(
        default=86400,
        ge=60,
        le=604800,
        description="Max expiration for pre-signed URLs in seconds (default 24h, max 7d)",
    )
    default_presigned_url_expiration: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default expiration for pre-signed URLs in seconds (default 1h)",
    )
    enable_encryption: bool = Field(
        default=True, description="Enable server-side encryption"
    )
    kms_key_id: str | None = Field(
        default=None, description="KMS key ID for SSE-KMS encryption"
    )

    # S3 path patterns for customer data organization
    customer_input_path_pattern: str = Field(
        default="ret/{customer_id}/inputs",
        description="S3 path pattern for customer input files (supports {customer_id} placeholder)",
    )
    customer_output_path_pattern: str = Field(
        default="ret/{customer_id}/outputs",
        description="S3 path pattern for customer output files (supports {customer_id} placeholder)",
    )
    analysis_output_filename_pattern: str = Field(
        default="{analysis_id}_{data_type}_analysis.json",
        description="Filename pattern for analysis outputs (supports {analysis_id}, {data_type} placeholders)",
    )

    # Path validation settings
    input_path_base_prefix: str = Field(
        default="ret",
        description="Required base prefix for input paths (security constraint)",
    )
    max_customer_folder_length: int = Field(
        default=100,
        ge=1,
        le=255,
        description="Maximum length for customer folder names",
    )

    def get_customer_input_path(self, customer_id: str) -> str:
        """
        Generate customer input path from pattern.

        Args:
            customer_id: Customer identifier

        Returns:
            Formatted input path
        """
        return self.customer_input_path_pattern.format(customer_id=customer_id)

    def get_customer_output_path(self, customer_id: str) -> str:
        """
        Generate customer output path from pattern.

        Args:
            customer_id: Customer identifier

        Returns:
            Formatted output path
        """
        return self.customer_output_path_pattern.format(customer_id=customer_id)

    def get_analysis_output_filename(self, analysis_id: str, data_type: str) -> str:
        """
        Generate analysis output filename from pattern.

        Args:
            analysis_id: Analysis identifier
            data_type: Type of analysis data

        Returns:
            Formatted filename
        """
        return self.analysis_output_filename_pattern.format(
            analysis_id=analysis_id, data_type=data_type
        )

    @field_validator("bucket_name")
    @classmethod
    def validate_bucket_name(cls, v: str | None) -> str | None:
        """Validate S3 bucket name format."""
        if v:
            if not (3 <= len(v) <= 63):
                raise ValueError("S3 bucket name must be between 3 and 63 characters")
            import re

            if not re.match(r"^[a-z0-9.-]+$", v):
                raise ValueError(
                    "S3 bucket name can only contain lowercase letters, numbers, periods, and hyphens"
                )
            if (
                v.startswith(".")
                or v.endswith(".")
                or v.startswith("-")
                or v.endswith("-")
            ):
                raise ValueError(
                    "S3 bucket name cannot start or end with periods or hyphens"
                )
            if ".." in v or ".-" in v or "-." in v:
                raise ValueError(
                    "S3 bucket name cannot contain consecutive periods or period-hyphen combinations"
                )
        return v

    @model_validator(mode="after")
    def validate_s3_config(self) -> "S3Config":
        """Validate S3 configuration consistency."""
        if self.enabled and not self.bucket_name:
            raise ValueError("bucket_name is required when S3 is enabled")
        return self


class StorageConfig(BaseModel):
    """Storage configuration."""

    backend: StorageBackend = StorageBackend.POSTGRESQL
    connection_string: SecretStr | None = None
    project_id: str | None = None
    dataset_name: str | None = None
    retention_days: int = Field(default=90, ge=1)
    s3: S3Config = Field(default_factory=S3Config)

    @field_validator("connection_string")
    @classmethod
    def validate_postgresql_config(
        cls, v: SecretStr | None, info: Any
    ) -> SecretStr | None:
        """Validate PostgreSQL configuration."""
        if info.data.get("backend") == StorageBackend.POSTGRESQL and not v:
            raise ValueError("connection_string required for PostgreSQL backend")
        return v


class RedisConfig(BaseModel):
    """Redis configuration for caching and distributed rate limiting."""

    enabled: bool = Field(default=False, description="Enable Redis backend")
    url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    auth_token: SecretStr | None = Field(
        default=None, description="Redis authentication token"
    )
    db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    max_connections: int = Field(
        default=20, ge=1, le=100, description="Maximum Redis connections in pool"
    )
    connection_timeout: float = Field(
        default=5.0, ge=0.1, le=30.0, description="Connection timeout in seconds"
    )
    socket_timeout: float = Field(
        default=5.0, ge=0.1, le=30.0, description="Socket timeout in seconds"
    )
    retry_on_timeout: bool = Field(
        default=True, description="Retry operations on timeout"
    )
    health_check_interval: int = Field(
        default=30, ge=1, le=300, description="Health check interval in seconds"
    )

    # Rate limiting specific settings
    rate_limit_key_prefix: str = Field(
        default="psn:rate_limit:", description="Key prefix for rate limiting data"
    )
    rate_limit_key_ttl: int = Field(
        default=86400, ge=3600, description="TTL for rate limiting keys in seconds"
    )
    distributed_lock_timeout: float = Field(
        default=10.0, ge=0.1, le=60.0, description="Distributed lock timeout in seconds"
    )
    distributed_lock_retry_delay: float = Field(
        default=0.1, ge=0.01, le=1.0, description="Lock retry delay in seconds"
    )

    # Rate limiting behavior settings
    max_wait_time: int = Field(
        default=300,
        ge=30,
        le=600,
        description="Maximum wait time for rate limiting in seconds",
    )
    cleanup_history_retention: int = Field(
        default=86400,
        ge=3600,
        le=172800,
        description="How long to keep rate limit history in seconds",
    )
    redis_health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="How often to check Redis health in seconds",
    )

    @field_validator("url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError(
                "Redis URL must start with 'redis://', 'rediss://', or 'unix://'"
            )

        # Additional validation for redis:// URLs
        if v.startswith("redis://") or v.startswith("rediss://"):
            import urllib.parse

            try:
                parsed = urllib.parse.urlparse(v)
                if not parsed.hostname:
                    raise ValueError("Redis URL must include a hostname")
                if parsed.port and (parsed.port < 1 or parsed.port > 65535):
                    raise ValueError("Redis URL port must be between 1 and 65535")
                if parsed.path and not parsed.path.startswith("/"):
                    raise ValueError("Redis URL path must start with '/'")
            except Exception as e:
                raise ValueError(f"Invalid Redis URL format: {e}")

        return v

    @model_validator(mode="after")
    def validate_configuration(self) -> "RedisConfig":
        """Validate overall Redis configuration."""
        if self.enabled:
            # Ensure reasonable defaults when Redis is enabled
            if self.connection_timeout > self.socket_timeout * 2:
                raise ValueError(
                    "Connection timeout should not be more than 2x socket timeout"
                )

            if self.distributed_lock_timeout < self.distributed_lock_retry_delay * 10:
                raise ValueError(
                    "Lock timeout should be at least 10x the retry delay for reasonable retry attempts"
                )

        return self


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration for external API calls."""

    enabled: bool = True
    failure_threshold: int = Field(
        default=5,
        ge=1,
        description="Number of consecutive failures before opening circuit",
    )
    recovery_timeout: int = Field(
        default=60, ge=1, description="Seconds to wait before trying to close circuit"
    )
    expected_exception: tuple[type[Exception], ...] = Field(
        default=(Exception,), description="Exception types that trigger circuit breaker"
    )
    # Half-open state configuration
    success_threshold: int = Field(
        default=3,
        ge=1,
        description="Number of successful calls needed to close circuit",
    )
    # Metrics and monitoring
    collect_metrics: bool = Field(
        default=True, description="Whether to collect circuit breaker metrics"
    )


class SchedulerConfig(BaseModel):
    """Scheduler configuration."""

    enabled: bool = True
    default_schedule: str = "0 0 1 */3 *"  # Quarterly
    timezone: str = "UTC"
    max_concurrent_audits: int = Field(default=5, ge=1)
    max_parallel_analyzers: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of analyzers to run in parallel within a single audit",
    )
    retry_attempts: int = Field(default=3, ge=0)
    job_store_url: SecretStr | None = (
        None  # SQLAlchemy URL for APScheduler job persistence
    )


class SessionLoggingConfig(BaseModel):
    """Session logging configuration for high-throughput scenarios."""

    enabled: bool = Field(default=True, description="Enable session metrics collection")
    detailed_logging: bool = Field(
        default=False, description="Enable detailed per-session logging (for debugging)"
    )
    metrics_interval: float = Field(
        default=60.0,
        ge=1.0,
        description="Interval in seconds to log aggregated metrics",
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: LogFormat = LogFormat.JSON
    sentry_dsn: SecretStr | None = None
    slack_webhook_url: SecretStr | None = None
    email_alerts_to: str | None = None
    session_logging: SessionLoggingConfig = Field(default_factory=SessionLoggingConfig)

    # Generic webhook handler configuration
    webhook_url: SecretStr | None = None
    webhook_method: str = Field(default="POST", description="HTTP method for webhook")
    webhook_timeout: int = Field(
        default=30, ge=1, le=300, description="Webhook timeout in seconds"
    )
    webhook_auth_type: str | None = Field(
        default=None, description="Auth type: bearer, basic, api_key, custom"
    )
    webhook_auth_token: SecretStr | None = None
    webhook_retry_attempts: int = Field(
        default=3, ge=0, le=10, description="Number of retry attempts"
    )
    webhook_retry_backoff: str = Field(
        default="exponential", description="Retry backoff strategy"
    )
    webhook_ssl_verify: bool = Field(
        default=True, description="Verify SSL certificates"
    )
    webhook_headers: str | None = Field(
        default=None, description="JSON string of additional headers"
    )
    webhook_payload_template: str | None = Field(
        default=None, description="JSON string of payload template"
    )

    @property
    def email_recipients(self) -> list[str]:
        """Parse email recipients from comma-separated string."""
        if self.email_alerts_to:
            return [
                email.strip()
                for email in self.email_alerts_to.split(",")
                if email.strip()
            ]
        return []


class AnalyzerThresholds(BaseModel):
    """Configurable thresholds for analyzers."""

    # Search Terms Analyzer thresholds
    min_impressions: int = Field(default=10, ge=1)
    min_clicks_for_negative: int = Field(default=10, ge=1)
    max_cpa_multiplier: float = Field(default=2.0, gt=0.0)
    min_conversions_for_add: float = Field(default=1.0, ge=0.0)
    min_roas_for_add: float = Field(default=2.0, ge=0.0)
    max_ctr_for_negative: float = Field(default=1.0, ge=0.0, le=100.0)  # Percentage
    min_impressions_for_ctr_check: int = Field(default=100, ge=1)
    default_cpa_fallback: float = Field(
        default=100.0, gt=0.0
    )  # Used when no conversions exist

    # Geo Performance Analyzer thresholds
    geo_expansion_roas_threshold: float = Field(default=3.0, gt=0.0)

    # Performance Max Analyzer thresholds
    pmax_good_roas_threshold: float = Field(default=3.0, gt=0.0)
    pmax_excellent_roas_threshold: float = Field(default=5.0, gt=0.0)

    # Shared Negative Validator thresholds
    shared_negative_min_percentage: float = Field(default=80.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_threshold_combinations(self) -> "AnalyzerThresholds":
        """Validate threshold combinations make business sense."""
        # ROAS thresholds should be consistent
        if self.min_roas_for_add < 1.0:
            raise ValueError("min_roas_for_add should be >= 1.0 for profitability")

        # Performance Max thresholds should be ordered
        if self.pmax_excellent_roas_threshold <= self.pmax_good_roas_threshold:
            raise ValueError(
                "pmax_excellent_roas_threshold must be greater than pmax_good_roas_threshold"
            )

        # CPA multiplier should be reasonable
        if self.max_cpa_multiplier > 10.0:
            raise ValueError(
                "max_cpa_multiplier should not exceed 10.0 (1000% of average)"
            )

        # CTR threshold should be reasonable
        if self.max_ctr_for_negative > 5.0:
            raise ValueError(
                "max_ctr_for_negative should not exceed 5.0% (very low CTR)"
            )

        # Conversion threshold should be meaningful
        if self.min_conversions_for_add > 100.0:
            raise ValueError(
                "min_conversions_for_add should not exceed 100 (too restrictive)"
            )

        return self


class WorkflowConfig(BaseModel):
    """Workflow orchestration configuration."""

    persistence_mode: str = Field(
        default="database",
        description="Persistence mode: 'memory' or 'database'",
        pattern="^(memory|database)$",
    )
    enable_database_persistence: bool = Field(
        default=True,
        description="Enable database persistence for workflows (if False, uses in-memory storage)",
    )
    context_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Context TTL in hours for in-memory storage (1-168 hours)",
    )
    cleanup_interval_minutes: int = Field(
        default=30,
        ge=5,
        le=60,
        description="Cleanup interval for expired contexts in minutes (5-60 minutes)",
    )
    max_concurrent_executions: int = Field(
        default=100, ge=1, le=1000, description="Maximum concurrent workflow executions"
    )
    enable_monitoring: bool = Field(
        default=True, description="Enable workflow monitoring and metrics"
    )


class MLConfig(BaseModel):
    """Machine Learning configuration for enterprise tier."""

    # CausalInferenceTools configuration
    causal_tools_path: str | None = Field(
        default=None,
        description="Path to CausalInferenceTools library (auto-detected if None)",
    )
    max_concurrent_models: int = Field(
        default=10, ge=1, le=50, description="Maximum concurrent ML models"
    )
    cache_ttl_hours: int = Field(
        default=24, ge=1, le=168, description="Model prediction cache TTL in hours"
    )

    # Data processing limits
    max_dataset_size: int = Field(
        default=50000, ge=100, description="Maximum dataset size for ML processing"
    )
    min_sample_size: int = Field(
        default=100, ge=10, description="Minimum sample size for causal analysis"
    )
    bootstrap_samples: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="Bootstrap samples for confidence intervals",
    )

    # Performance settings
    enable_async_training: bool = Field(
        default=True, description="Enable asynchronous model training"
    )
    training_timeout_minutes: int = Field(
        default=30, ge=5, le=120, description="Training timeout in minutes"
    )
    prediction_timeout_seconds: int = Field(
        default=60, ge=10, le=300, description="Prediction timeout in seconds"
    )

    @field_validator("causal_tools_path")
    @classmethod
    def validate_causal_tools_path(cls, v: str | None) -> str | None:
        """Validate CausalInferenceTools path if provided."""
        if v:
            from pathlib import Path

            path = Path(v)
            if not path.exists():
                raise ValueError(f"CausalInferenceTools path does not exist: {v}")
        return v


class FeatureFlags(BaseModel):
    """Feature flags configuration."""

    enable_pmax_analysis: bool = True
    enable_geo_dashboard: bool = True
    enable_auto_negatives: bool = False


class Settings(BaseSettings):
    """Application settings.

    Environment Variables:
        Token Storage Backend:
            PSN_TOKEN_STORAGE_BACKEND=file_encrypted  (default - encrypted file storage)
            PSN_TOKEN_STORAGE_BACKEND=keyring         (OS-level keyring storage)
            PSN_TOKEN_STORAGE_BACKEND=secret_manager  (cloud secret manager)
            PSN_TOKEN_STORAGE_SERVICE_NAME=paidsearchnav  (keyring service name)

        Secret Provider (for secret_manager backend):
            PSN_SECRET_PROVIDER=environment           (default - environment variables)
            PSN_SECRET_PROVIDER=aws_secrets_manager   (AWS Secrets Manager)
            PSN_SECRET_PROVIDER=gcp_secret_manager    (GCP Secret Manager)
            PSN_SECRET_PROVIDER=hashicorp_vault       (HashiCorp Vault)

        Google Ads API:
            PSN_GOOGLE_ADS_DEVELOPER_TOKEN=your_dev_token
            PSN_GOOGLE_ADS_CLIENT_ID=your_client_id
            PSN_GOOGLE_ADS_CLIENT_SECRET=your_client_secret
            PSN_GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token
            PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
    """

    model_config = SettingsConfigDict(
        env_prefix="PSN_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Core settings
    environment: Environment = Environment.DEVELOPMENT
    secret_provider: SecretProvider = SecretProvider.ENVIRONMENT
    token_storage_backend: TokenStorageBackend = TokenStorageBackend.FILE_ENCRYPTED
    token_storage_service_name: str = Field(
        default="paidsearchnav",
        description="Service name for keyring token storage (advanced use cases)",
    )
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".paidsearchnav")
    debug: bool = False
    database_url: SecretStr | None = None

    # Monitoring and Observability settings
    tracing_enabled: bool = Field(
        default=True, description="Enable OpenTelemetry tracing"
    )
    otlp_endpoint: str | None = Field(
        default=None,
        description="OpenTelemetry OTLP endpoint (e.g., http://localhost:4317)",
    )
    otlp_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Headers for OTLP exporter (e.g., API keys)",
    )
    tracing_console_export: bool = Field(
        default=False,
        description="Export traces to console (for debugging)",
    )
    tracing_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (0.0 to 1.0)",
    )
    metrics_export_interval: int = Field(
        default=60,
        ge=1,
        description="Metrics export interval in seconds",
    )
    log_directory: str = Field(
        default="logs",
        description="Directory for structured log files",
    )

    # API settings
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_cors_origins: list[str] = Field(default=["http://localhost:3000"])
    api_enable_rate_limiting: bool = Field(default=True)

    # Rate limiting configuration for customer access control
    rate_limit_customer_access_per_user_minute: int = Field(
        default=100, description="Max customer access checks per user per minute"
    )
    rate_limit_customer_access_per_user_hour: int = Field(
        default=1000, description="Max customer access checks per user per hour"
    )
    rate_limit_customer_access_per_ip_minute: int = Field(
        default=200, description="Max customer access checks per IP per minute"
    )
    rate_limit_customer_access_per_ip_hour: int = Field(
        default=2000, description="Max customer access checks per IP per hour"
    )
    rate_limit_agency_multiplier: float = Field(
        default=5.0,
        description="Multiplier for agency rate limits (agencies get higher limits)",
    )
    rate_limit_cleanup_interval: int = Field(
        default=300,
        description="Cleanup interval in seconds for rate limit entries (default 5 minutes)",
    )

    jwt_secret_key: SecretStr = Field(default=SecretStr("change-me-in-production"))
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)
    jwt_blacklist_cleanup_seconds: int = Field(
        default=3600,
        description="Interval between JWT blacklist cleanups in seconds (default: 1 hour)",
    )
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    api_key_required: bool = Field(default=False)
    api_key: SecretStr = Field(default=SecretStr("test-api-key"))

    # Component configurations
    google_ads: GoogleAdsConfig | None = None
    ga4: GA4Config = Field(default_factory=GA4Config)
    bigquery: BigQueryConfig = Field(default_factory=BigQueryConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    thresholds: AnalyzerThresholds = Field(default_factory=AnalyzerThresholds)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    cache: Any = (
        None  # Cache configuration - imported at runtime to avoid circular imports
    )

    # Cloud provider settings (optional)
    aws_default_region: str | None = None
    gcp_project_id: str | None = None
    vault_url: str | None = None
    vault_token: SecretStr | None = None

    def get_env(self, key: str, default: str | None = None) -> str | None:
        """Get environment variable with PSN_ prefix."""
        return os.environ.get(f"PSN_{key}", default)

    @classmethod
    def from_env(
        cls, env_file: Path | None = None, client_config_file: Path | None = None
    ) -> "Settings":
        """Load settings from environment and optionally override with client config."""
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to load .env from project root
            root_dir = Path(__file__).parent.parent.parent
            env_path = root_dir / ".env"
            if env_path.exists():
                load_dotenv(env_path)

        # Build nested configs from environment
        env_vars = {k: v for k, v in os.environ.items() if k.startswith("PSN_")}

        # Parse nested configurations
        config_data: dict[str, Any] = {
            "environment": env_vars.get("PSN_ENVIRONMENT", "development"),
            "secret_provider": env_vars.get("PSN_SECRET_PROVIDER", "environment"),
            "token_storage_backend": env_vars.get(
                "PSN_TOKEN_STORAGE_BACKEND", "file_encrypted"
            ),
            "debug": env_vars.get("PSN_DEBUG", "false").lower() == "true",
            "database_url": SecretStr(env_vars.get("PSN_DATABASE_URL"))
            if env_vars.get("PSN_DATABASE_URL")
            else None,
            "api_host": env_vars.get("PSN_API_HOST", "127.0.0.1"),
            "api_port": int(env_vars.get("PSN_API_PORT", "8000")),
            "jwt_secret_key": SecretStr(
                env_vars.get("PSN_JWT_SECRET_KEY", "change-me-in-production")
            ),
            "jwt_algorithm": env_vars.get("PSN_JWT_ALGORITHM", "HS256"),
            "jwt_expire_minutes": int(env_vars.get("PSN_JWT_EXPIRE_MINUTES", "60")),
            "google_oauth_client_id": env_vars.get("PSN_GOOGLE_OAUTH_CLIENT_ID"),
            "google_oauth_client_secret": SecretStr(
                env_vars.get("PSN_GOOGLE_OAUTH_CLIENT_SECRET")
            )
            if env_vars.get("PSN_GOOGLE_OAUTH_CLIENT_SECRET")
            else None,
        }

        # Parse CORS origins
        cors_origins = env_vars.get(
            "PSN_API_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        )
        config_data["api_cors_origins"] = [
            origin.strip() for origin in cors_origins.split(",") if origin.strip()
        ]

        # Handle data_dir
        if "PSN_DATA_DIR" in env_vars:
            config_data["data_dir"] = Path(env_vars["PSN_DATA_DIR"])
        # Google Ads config
        google_ads_token = env_vars.get("PSN_GOOGLE_ADS_DEVELOPER_TOKEN")
        google_ads_client_id = env_vars.get("PSN_GOOGLE_ADS_CLIENT_ID")
        google_ads_client_secret = env_vars.get("PSN_GOOGLE_ADS_CLIENT_SECRET")

        if google_ads_token and google_ads_client_id and google_ads_client_secret:
            config_data["google_ads"] = GoogleAdsConfig(
                developer_token=SecretStr(google_ads_token),
                client_id=google_ads_client_id,
                client_secret=SecretStr(google_ads_client_secret),
                refresh_token=SecretStr(env_vars.get("PSN_GOOGLE_ADS_REFRESH_TOKEN"))
                if env_vars.get("PSN_GOOGLE_ADS_REFRESH_TOKEN")
                else None,
                login_customer_id=env_vars.get("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
                api_version=env_vars.get("PSN_GOOGLE_ADS_API_VERSION", "v18"),
                default_page_size=int(
                    env_vars.get("PSN_GOOGLE_ADS_DEFAULT_PAGE_SIZE", "1000")
                ),
                max_page_size=int(
                    env_vars.get("PSN_GOOGLE_ADS_MAX_PAGE_SIZE", "10000")
                ),
            )

        # GA4 config
        if any(k.startswith("PSN_GA4_") for k in env_vars):
            ga4_config_data = {}
            if env_vars.get("PSN_GA4_ENABLED", "false").lower() == "true":
                ga4_config_data["enabled"] = True
            if env_vars.get("PSN_GA4_PROPERTY_ID"):
                ga4_config_data["property_id"] = env_vars.get("PSN_GA4_PROPERTY_ID")
            if env_vars.get("PSN_GA4_SERVICE_ACCOUNT_KEY_PATH"):
                ga4_config_data["service_account_key_path"] = env_vars.get(
                    "PSN_GA4_SERVICE_ACCOUNT_KEY_PATH"
                )
            if env_vars.get("PSN_GA4_USE_APPLICATION_DEFAULT_CREDENTIALS"):
                ga4_config_data["use_application_default_credentials"] = (
                    env_vars.get(
                        "PSN_GA4_USE_APPLICATION_DEFAULT_CREDENTIALS", "true"
                    ).lower()
                    == "true"
                )
            if env_vars.get("PSN_GA4_API_VERSION"):
                ga4_config_data["api_version"] = env_vars.get("PSN_GA4_API_VERSION")
            if env_vars.get("PSN_GA4_ENABLE_RATE_LIMITING"):
                ga4_config_data["enable_rate_limiting"] = (
                    env_vars.get("PSN_GA4_ENABLE_RATE_LIMITING", "true").lower()
                    == "true"
                )
            if env_vars.get("PSN_GA4_REQUESTS_PER_MINUTE"):
                ga4_config_data["requests_per_minute"] = int(
                    env_vars.get("PSN_GA4_REQUESTS_PER_MINUTE")
                )
            if env_vars.get("PSN_GA4_REQUESTS_PER_HOUR"):
                ga4_config_data["requests_per_hour"] = int(
                    env_vars.get("PSN_GA4_REQUESTS_PER_HOUR")
                )
            if env_vars.get("PSN_GA4_REQUESTS_PER_DAY"):
                ga4_config_data["requests_per_day"] = int(
                    env_vars.get("PSN_GA4_REQUESTS_PER_DAY")
                )
            if env_vars.get("PSN_GA4_MAX_DATA_LAG_HOURS"):
                ga4_config_data["max_data_lag_hours"] = int(
                    env_vars.get("PSN_GA4_MAX_DATA_LAG_HOURS")
                )
            if env_vars.get("PSN_GA4_ENABLE_REALTIME_DATA"):
                ga4_config_data["enable_realtime_data"] = (
                    env_vars.get("PSN_GA4_ENABLE_REALTIME_DATA", "true").lower()
                    == "true"
                )
            if env_vars.get("PSN_GA4_DAILY_COST_LIMIT_USD"):
                ga4_config_data["daily_cost_limit_usd"] = float(
                    env_vars.get("PSN_GA4_DAILY_COST_LIMIT_USD")
                )
            if env_vars.get("PSN_GA4_COST_ALERT_THRESHOLD_USD"):
                ga4_config_data["cost_alert_threshold_usd"] = float(
                    env_vars.get("PSN_GA4_COST_ALERT_THRESHOLD_USD")
                )

            config_data["ga4"] = GA4Config(**ga4_config_data)

        # Storage config
        if any(k.startswith("PSN_STORAGE_") for k in env_vars) or any(
            k.startswith("PSN_S3_") for k in env_vars
        ):
            # S3 config
            s3_config_data = {}
            if env_vars.get("PSN_S3_ENABLED", "false").lower() == "true":
                s3_config_data["enabled"] = True
            if env_vars.get("PSN_S3_BUCKET_NAME"):
                s3_config_data["bucket_name"] = env_vars.get("PSN_S3_BUCKET_NAME")
            if env_vars.get("PSN_S3_REGION"):
                s3_config_data["region"] = env_vars.get("PSN_S3_REGION")
            if env_vars.get("PSN_S3_PREFIX"):
                s3_config_data["prefix"] = env_vars.get("PSN_S3_PREFIX")
            if env_vars.get("PSN_AWS_ACCESS_KEY_ID"):
                s3_config_data["access_key_id"] = env_vars.get("PSN_AWS_ACCESS_KEY_ID")
            if env_vars.get("PSN_AWS_SECRET_ACCESS_KEY"):
                s3_config_data["secret_access_key"] = SecretStr(
                    env_vars.get("PSN_AWS_SECRET_ACCESS_KEY")
                )
            if env_vars.get("PSN_AWS_SESSION_TOKEN"):
                s3_config_data["session_token"] = SecretStr(
                    env_vars.get("PSN_AWS_SESSION_TOKEN")
                )
            if env_vars.get("PSN_S3_MULTIPART_THRESHOLD"):
                s3_config_data["multipart_threshold"] = int(
                    env_vars.get("PSN_S3_MULTIPART_THRESHOLD")
                )
            if env_vars.get("PSN_S3_MAX_CONCURRENCY"):
                s3_config_data["max_concurrency"] = int(
                    env_vars.get("PSN_S3_MAX_CONCURRENCY")
                )
            if env_vars.get("PSN_S3_MAX_ATTEMPTS"):
                s3_config_data["max_attempts"] = int(
                    env_vars.get("PSN_S3_MAX_ATTEMPTS")
                )
            if env_vars.get("PSN_S3_CONNECT_TIMEOUT"):
                s3_config_data["connect_timeout"] = float(
                    env_vars.get("PSN_S3_CONNECT_TIMEOUT")
                )
            if env_vars.get("PSN_S3_READ_TIMEOUT"):
                s3_config_data["read_timeout"] = float(
                    env_vars.get("PSN_S3_READ_TIMEOUT")
                )

            config_data["storage"] = StorageConfig(
                backend=StorageBackend(
                    env_vars.get("PSN_STORAGE_BACKEND", "postgresql")
                ),
                connection_string=SecretStr(
                    env_vars.get("PSN_STORAGE_CONNECTION_STRING")
                )
                if env_vars.get("PSN_STORAGE_CONNECTION_STRING")
                else None,
                project_id=env_vars.get("PSN_STORAGE_PROJECT_ID"),
                dataset_name=env_vars.get("PSN_STORAGE_DATASET_NAME"),
                retention_days=int(env_vars.get("PSN_STORAGE_RETENTION_DAYS", "90")),
                s3=S3Config(**s3_config_data) if s3_config_data else S3Config(),
            )

        # Scheduler config
        if any(k.startswith("PSN_SCHEDULER_") for k in env_vars):
            config_data["scheduler"] = SchedulerConfig(
                enabled=env_vars.get("PSN_SCHEDULER_ENABLED", "true").lower() == "true",
                default_schedule=env_vars.get(
                    "PSN_SCHEDULER_DEFAULT_SCHEDULE", "0 0 1 */3 *"
                ),
                timezone=env_vars.get("PSN_SCHEDULER_TIMEZONE", "UTC"),
                max_concurrent_audits=int(
                    env_vars.get("PSN_SCHEDULER_MAX_CONCURRENT_AUDITS", "5")
                ),
                max_parallel_analyzers=int(
                    env_vars.get("PSN_SCHEDULER_MAX_PARALLEL_ANALYZERS", "3")
                ),
                retry_attempts=int(env_vars.get("PSN_SCHEDULER_RETRY_ATTEMPTS", "3")),
                job_store_url=SecretStr(env_vars.get("PSN_SCHEDULER_JOB_STORE_URL"))
                if env_vars.get("PSN_SCHEDULER_JOB_STORE_URL")
                else None,
            )

        # Circuit breaker config
        if any(k.startswith("PSN_CIRCUIT_BREAKER_") for k in env_vars):
            config_data["circuit_breaker"] = CircuitBreakerConfig(
                enabled=env_vars.get("PSN_CIRCUIT_BREAKER_ENABLED", "true").lower()
                == "true",
                failure_threshold=int(
                    env_vars.get("PSN_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
                ),
                recovery_timeout=int(
                    env_vars.get("PSN_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
                ),
                success_threshold=int(
                    env_vars.get("PSN_CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "3")
                ),
                collect_metrics=env_vars.get(
                    "PSN_CIRCUIT_BREAKER_COLLECT_METRICS", "true"
                ).lower()
                == "true",
            )

        # Logging config
        if any(k.startswith("PSN_LOGGING_") for k in env_vars):
            config_data["logging"] = LoggingConfig(
                level=env_vars.get("PSN_LOGGING_LEVEL", "INFO"),
                format=LogFormat(env_vars.get("PSN_LOGGING_FORMAT", "json")),
                sentry_dsn=SecretStr(env_vars.get("PSN_LOGGING_SENTRY_DSN"))
                if env_vars.get("PSN_LOGGING_SENTRY_DSN")
                else None,
                slack_webhook_url=SecretStr(
                    env_vars.get("PSN_LOGGING_SLACK_WEBHOOK_URL")
                )
                if env_vars.get("PSN_LOGGING_SLACK_WEBHOOK_URL")
                else None,
                email_alerts_to=env_vars.get("PSN_LOGGING_EMAIL_ALERTS_TO"),
            )

        # Feature flags
        config_data["features"] = FeatureFlags(
            enable_pmax_analysis=env_vars.get(
                "PSN_ENABLE_PMAX_ANALYSIS", "true"
            ).lower()
            == "true",
            enable_geo_dashboard=env_vars.get(
                "PSN_ENABLE_GEO_DASHBOARD", "true"
            ).lower()
            == "true",
            enable_auto_negatives=env_vars.get(
                "PSN_ENABLE_AUTO_NEGATIVES", "false"
            ).lower()
            == "true",
        )

        # Cloud provider settings
        aws_region = os.environ.get("AWS_DEFAULT_REGION")
        gcp_project = os.environ.get("GCP_PROJECT_ID")
        vault_url = os.environ.get("VAULT_URL")
        vault_token = os.environ.get("VAULT_TOKEN")

        if aws_region:
            config_data["aws_default_region"] = aws_region
        if gcp_project:
            config_data["gcp_project_id"] = gcp_project
        if vault_url:
            config_data["vault_url"] = vault_url
        if vault_token:
            config_data["vault_token"] = SecretStr(vault_token)

        # Parse environment string to Environment enum
        if "environment" in config_data:
            config_data["environment"] = Environment(config_data["environment"])

        # Parse secret_provider string to SecretProvider enum
        if "secret_provider" in config_data:
            config_data["secret_provider"] = SecretProvider(
                config_data["secret_provider"]
            )

        # Parse token_storage_backend string to TokenStorageBackend enum
        if "token_storage_backend" in config_data:
            config_data["token_storage_backend"] = TokenStorageBackend(
                config_data["token_storage_backend"]
            )

        # ML config
        if any(k.startswith("PSN_ML_") for k in env_vars):
            ml_config_data = {}
            if env_vars.get("PSN_ML_CAUSAL_TOOLS_PATH"):
                ml_config_data["causal_tools_path"] = env_vars.get(
                    "PSN_ML_CAUSAL_TOOLS_PATH"
                )
            if env_vars.get("PSN_ML_MAX_CONCURRENT_MODELS"):
                ml_config_data["max_concurrent_models"] = int(
                    env_vars.get("PSN_ML_MAX_CONCURRENT_MODELS")
                )
            if env_vars.get("PSN_ML_CACHE_TTL_HOURS"):
                ml_config_data["cache_ttl_hours"] = int(
                    env_vars.get("PSN_ML_CACHE_TTL_HOURS")
                )
            if env_vars.get("PSN_ML_MAX_DATASET_SIZE"):
                ml_config_data["max_dataset_size"] = int(
                    env_vars.get("PSN_ML_MAX_DATASET_SIZE")
                )
            if env_vars.get("PSN_ML_MIN_SAMPLE_SIZE"):
                ml_config_data["min_sample_size"] = int(
                    env_vars.get("PSN_ML_MIN_SAMPLE_SIZE")
                )
            if env_vars.get("PSN_ML_BOOTSTRAP_SAMPLES"):
                ml_config_data["bootstrap_samples"] = int(
                    env_vars.get("PSN_ML_BOOTSTRAP_SAMPLES")
                )
            if env_vars.get("PSN_ML_ENABLE_ASYNC_TRAINING"):
                ml_config_data["enable_async_training"] = (
                    env_vars.get("PSN_ML_ENABLE_ASYNC_TRAINING", "true").lower()
                    == "true"
                )
            if env_vars.get("PSN_ML_TRAINING_TIMEOUT_MINUTES"):
                ml_config_data["training_timeout_minutes"] = int(
                    env_vars.get("PSN_ML_TRAINING_TIMEOUT_MINUTES")
                )
            if env_vars.get("PSN_ML_PREDICTION_TIMEOUT_SECONDS"):
                ml_config_data["prediction_timeout_seconds"] = int(
                    env_vars.get("PSN_ML_PREDICTION_TIMEOUT_SECONDS")
                )

            config_data["ml"] = MLConfig(**ml_config_data)

        # Cache config
        if any(k.startswith("PSN_CACHE_") for k in env_vars):
            cache_config_data = {
                "enabled": env_vars.get("PSN_CACHE_ENABLED", "false").lower() == "true",
                "backend": env_vars.get("PSN_CACHE_BACKEND", "redis"),
            }

            # Redis config
            redis_config_data = {
                "url": env_vars.get("PSN_CACHE_REDIS_URL", "redis://localhost:6379"),
                "cluster": env_vars.get("PSN_CACHE_REDIS_CLUSTER", "false").lower()
                == "true",
            }
            if env_vars.get("PSN_CACHE_REDIS_PASSWORD"):
                redis_config_data["password"] = env_vars.get("PSN_CACHE_REDIS_PASSWORD")

            # TTL config
            ttl_config_data = {}
            if env_vars.get("PSN_CACHE_TTL_DEFAULT"):
                ttl_config_data["default"] = int(env_vars.get("PSN_CACHE_TTL_DEFAULT"))
            if env_vars.get("PSN_CACHE_TTL_CUSTOMER_LIST"):
                ttl_config_data["customer_list"] = int(
                    env_vars.get("PSN_CACHE_TTL_CUSTOMER_LIST")
                )
            if env_vars.get("PSN_CACHE_TTL_AUDIT_REPORT"):
                ttl_config_data["audit_report"] = int(
                    env_vars.get("PSN_CACHE_TTL_AUDIT_REPORT")
                )
            if env_vars.get("PSN_CACHE_TTL_RECOMMENDATIONS"):
                ttl_config_data["recommendations"] = int(
                    env_vars.get("PSN_CACHE_TTL_RECOMMENDATIONS")
                )
            if env_vars.get("PSN_CACHE_TTL_ANALYZER_RESULTS"):
                ttl_config_data["analyzer_results"] = int(
                    env_vars.get("PSN_CACHE_TTL_ANALYZER_RESULTS")
                )
            if env_vars.get("PSN_CACHE_TTL_API_RESPONSES"):
                ttl_config_data["api_responses"] = int(
                    env_vars.get("PSN_CACHE_TTL_API_RESPONSES")
                )

            from paidsearchnav_mcp.cache.config import (
                CacheConfig,
                CacheTTLConfig,
                RedisCacheConfig,
            )

            config_data["cache"] = CacheConfig(
                **cache_config_data,
                redis=RedisCacheConfig(**redis_config_data),
                ttl=CacheTTLConfig(**ttl_config_data)
                if ttl_config_data
                else CacheTTLConfig(),
            )

        # Override with client config if provided
        if client_config_file and client_config_file.exists():
            import json

            try:
                with open(client_config_file, "r") as f:
                    client_config = json.load(f)
                config_data = cls._merge_client_config(config_data, client_config)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Failed to load client config {client_config_file}: {e}"
                )

        return cls(**config_data)

    @classmethod
    def _merge_client_config(
        cls, base_config: dict[str, Any], client_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge client configuration into base configuration."""
        # Override BigQuery settings if present
        if "bigquery" in client_config:
            bigquery_overrides = client_config["bigquery"]
            if "bigquery" not in base_config:
                base_config["bigquery"] = {}

            # Map client config to expected format
            bigquery_mapping = {
                "enabled": "enabled",
                "tier": "tier",
                "project_id": "project_id",
                "dataset_id": "dataset_id",
                "location": "location",
                "service_account_path": "service_account_path",
                "service_account_json": "service_account_json",
                "use_default_credentials": "use_default_credentials",
                "daily_cost_limit_usd": "daily_cost_limit_usd",
                "cost_alert_threshold_usd": "cost_alert_threshold_usd",
                "max_query_bytes": "max_query_bytes",
                "query_timeout_seconds": "query_timeout_seconds",
                "enable_query_cache": "enable_query_cache",
                "cache_ttl_seconds": "cache_ttl_seconds",
                "streaming_insert_batch_size": "streaming_insert_batch_size",
                "enable_ml_models": "enable_ml_models",
                "enable_real_time_streaming": "enable_real_time_streaming",
            }

            for client_key, config_key in bigquery_mapping.items():
                if client_key in bigquery_overrides:
                    base_config["bigquery"][config_key] = bigquery_overrides[client_key]

        # Override Google Ads settings if present
        if "google_ads" in client_config:
            google_ads_overrides = client_config["google_ads"]
            if "google_ads" not in base_config:
                base_config["google_ads"] = {}

            google_ads_mapping = {
                "customer_id": "customer_id",
                "login_customer_id": "login_customer_id",
                "api_version": "api_version",
                "default_page_size": "default_page_size",
                "max_page_size": "max_page_size",
            }

            for client_key, config_key in google_ads_mapping.items():
                if client_key in google_ads_overrides:
                    if config_key in ["customer_id", "login_customer_id"]:
                        # These might need to be set in the config differently
                        continue  # Skip for now, handle in client-specific logic
                    base_config["google_ads"][config_key] = google_ads_overrides[
                        client_key
                    ]

        # Override GA4 settings if present
        if "ga4" in client_config:
            ga4_overrides = client_config["ga4"]
            if "ga4" not in base_config:
                base_config["ga4"] = {}

            ga4_mapping = {
                "enabled": "enabled",
                "property_id": "property_id",
                "service_account_key_path": "service_account_key_path",
                "use_application_default_credentials": "use_application_default_credentials",
                "enable_rate_limiting": "enable_rate_limiting",
                "requests_per_minute": "requests_per_minute",
                "requests_per_hour": "requests_per_hour",
                "requests_per_day": "requests_per_day",
                "enable_cost_monitoring": "enable_cost_monitoring",
                "daily_cost_limit_usd": "daily_cost_limit_usd",
                "cost_alert_threshold_usd": "cost_alert_threshold_usd",
                "average_cpa_usd": "average_cpa_usd",
                "cache_ttl_seconds": "cache_ttl_seconds",
                "enable_realtime_data": "enable_realtime_data",
                "max_data_lag_hours": "max_data_lag_hours",
            }

            for client_key, config_key in ga4_mapping.items():
                if client_key in ga4_overrides:
                    base_config["ga4"][config_key] = ga4_overrides[client_key]

        return base_config

    def validate_required_settings(self) -> None:
        """Validate that all required settings are present."""
        errors = []

        # Check Google Ads credentials
        if not self.google_ads:
            errors.append("Google Ads configuration is required")
        else:
            if not self.google_ads.developer_token:
                errors.append("PSN_GOOGLE_ADS_DEVELOPER_TOKEN is required")
            if not self.google_ads.client_id:
                errors.append("PSN_GOOGLE_ADS_CLIENT_ID is required")
            if not self.google_ads.client_secret:
                errors.append("PSN_GOOGLE_ADS_CLIENT_SECRET is required")

        # Check storage backend requirements
        if (
            self.storage.backend == StorageBackend.POSTGRESQL
            and not self.storage.connection_string
        ):
            errors.append(
                "PSN_STORAGE_CONNECTION_STRING is required for PostgreSQL backend"
            )
        elif self.storage.backend == StorageBackend.BIGQUERY:
            if not self.storage.project_id:
                errors.append("PSN_STORAGE_PROJECT_ID is required for BigQuery backend")
            if not self.storage.dataset_name:
                errors.append(
                    "PSN_STORAGE_DATASET_NAME is required for BigQuery backend"
                )
        elif self.storage.backend == StorageBackend.FIRESTORE:
            if not self.storage.project_id:
                errors.append(
                    "PSN_STORAGE_PROJECT_ID is required for Firestore backend"
                )

        # Check secret provider requirements
        if (
            self.secret_provider == SecretProvider.AWS_SECRETS_MANAGER
            and not self.aws_default_region
        ):
            errors.append("AWS_DEFAULT_REGION is required for AWS Secrets Manager")
        elif (
            self.secret_provider == SecretProvider.GCP_SECRET_MANAGER
            and not self.gcp_project_id
        ):
            errors.append("GCP_PROJECT_ID is required for GCP Secret Manager")
        elif self.secret_provider == SecretProvider.HASHICORP_VAULT:
            if not self.vault_url:
                errors.append("VAULT_URL is required for HashiCorp Vault")
            if not self.vault_token:
                errors.append("VAULT_TOKEN is required for HashiCorp Vault")

        # Check token storage backend requirements
        if self.token_storage_backend == TokenStorageBackend.SECRET_MANAGER:
            # Ensure secret provider is configured when using secret manager for tokens
            if self.secret_provider == SecretProvider.ENVIRONMENT:
                errors.append(
                    "SECRET_MANAGER token storage requires a cloud secret provider "
                    "(AWS_SECRETS_MANAGER, GCP_SECRET_MANAGER, or HASHICORP_VAULT)"
                )
        elif self.token_storage_backend == TokenStorageBackend.KEYRING:
            # Warn about keyring availability (not an error since fallback exists)
            import logging

            logger = logging.getLogger(__name__)
            try:
                import keyring

                # Test basic keyring availability
                if keyring.get_keyring() is None:
                    logger.warning(
                        "KEYRING token storage configured but no keyring backend available. "
                        "Will fall back to encrypted file storage."
                    )
            except ImportError:
                logger.warning(
                    "KEYRING token storage configured but keyring module not available. "
                    "Will fall back to encrypted file storage."
                )

        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        settings = Settings.from_env()
        settings.validate_required_settings()
        return settings
    except (ValidationError, ValueError) as e:
        logging.error(f"Configuration error: {e}")
        raise


def setup_logging(settings: Settings) -> None:
    """Configure logging based on settings."""
    log_level = getattr(logging, settings.logging.level.upper())

    if settings.logging.format == LogFormat.JSON:
        import json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "paidsearchnav.log")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
