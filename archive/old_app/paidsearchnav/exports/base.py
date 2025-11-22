"""Base classes and interfaces for the export pipeline."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExportStatus(str, Enum):
    """Status of an export job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportFormat(str, Enum):
    """Supported export formats."""

    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"
    PARQUET = "parquet"
    CSV = "csv"
    JSON_LINES = "json_lines"


@dataclass
class PaginationConfig:
    """Configuration for pagination during exports."""

    batch_size: int = 10000  # Default batch size
    max_memory_mb: int = 100  # Maximum memory usage in MB
    enable_streaming: bool = True  # Enable streaming for large datasets
    progress_callback_interval: int = 1000  # Progress callback every N records


@dataclass
class ExportConfig:
    """Configuration for an export destination."""

    destination_type: ExportFormat
    credentials: Dict[str, Any]
    schedule: Optional[str] = None  # Cron expression
    enabled: bool = True
    options: Dict[str, Any] = field(default_factory=dict)
    pagination: PaginationConfig = field(default_factory=PaginationConfig)

    # BigQuery specific
    project_id: Optional[str] = None
    dataset: Optional[str] = None

    # Snowflake specific
    account: Optional[str] = None
    warehouse: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None

    # File export specific
    output_path: Optional[str] = None
    compression: Optional[str] = None


@dataclass
class ExportRequest:
    """Request to export data."""

    export_id: str = field(default_factory=lambda: str(uuid4()))
    customer_id: str = ""
    destination: ExportFormat = ExportFormat.BIGQUERY
    date_range: Optional[Dict[str, str]] = None
    include_historical: bool = False
    filters: Dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)
    requested_by: Optional[str] = None
    pagination_config: Optional[PaginationConfig] = None
    progress_callback: Optional[Callable[[int, int], None]] = None  # (current, total)


@dataclass
class ExportProgress:
    """Progress information for an export operation."""

    export_id: str
    current_records: int
    total_records: Optional[int]
    current_batch: int
    total_batches: Optional[int]
    memory_usage_mb: float
    started_at: datetime
    estimated_completion: Optional[datetime] = None

    @property
    def progress_percentage(self) -> Optional[float]:
        """Calculate progress percentage if total is known."""
        if self.total_records and self.total_records > 0:
            return min(100.0, (self.current_records / self.total_records) * 100.0)
        return None


@dataclass
class ExportResult:
    """Result of an export operation."""

    export_id: str
    status: ExportStatus
    destination: ExportFormat
    records_exported: int = 0
    files_created: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    progress: Optional[ExportProgress] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate export duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ExportDestination(ABC):
    """Abstract base class for export destinations."""

    def __init__(self, config: ExportConfig):
        """Initialize the export destination."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate that we can connect to the destination."""
        pass

    @abstractmethod
    async def export_audit_results(
        self,
        customer_id: str,
        audit_data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export audit results to the destination."""
        pass

    @abstractmethod
    async def export_recommendations(
        self,
        customer_id: str,
        recommendations: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export recommendations to the destination."""
        pass

    @abstractmethod
    async def export_metrics(
        self,
        customer_id: str,
        metrics: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export metrics to the destination."""
        pass

    @abstractmethod
    async def check_export_status(self, export_id: str) -> ExportResult:
        """Check the status of an ongoing export."""
        pass

    async def export_batch(
        self,
        customer_id: str,
        data: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export multiple data types in a single batch."""
        results = []

        if "audit_results" in data:
            results.append(
                await self.export_audit_results(
                    customer_id, data["audit_results"], metadata
                )
            )

        if "recommendations" in data:
            results.append(
                await self.export_recommendations(
                    customer_id, data["recommendations"], metadata
                )
            )

        if "metrics" in data:
            results.append(
                await self.export_metrics(customer_id, data["metrics"], metadata)
            )

        # Combine results
        total_records = sum(r.records_exported for r in results)
        all_files = []
        for r in results:
            all_files.extend(r.files_created)

        # Return combined result
        return ExportResult(
            export_id=results[0].export_id if results else str(uuid4()),
            status=ExportStatus.COMPLETED
            if all(r.status == ExportStatus.COMPLETED for r in results)
            else ExportStatus.FAILED,
            destination=self.config.destination_type,
            records_exported=total_records,
            files_created=all_files,
            started_at=min(
                (r.started_at for r in results if r.started_at), default=None
            ),
            completed_at=max(
                (r.completed_at for r in results if r.completed_at), default=None
            ),
            metadata={"batch_size": len(results)},
        )


class ExportError(Exception):
    """Base exception for export errors."""

    pass


class ExportConnectionError(ExportError):
    """Error connecting to export destination."""

    pass


class ExportValidationError(ExportError):
    """Error validating export data or configuration."""

    pass


class ExportTimeoutError(ExportError):
    """Export operation timed out."""

    pass
