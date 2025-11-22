"""Google BigQuery export implementation."""

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import psutil

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import GoogleCloudError
    from google.oauth2 import service_account

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False

    # Create a mock module to avoid AttributeError on type annotations
    class MockBigQuery:
        Client = None
        DatasetReference = None
        SchemaField = None
        Table = None
        TimePartitioning = None
        TimePartitioningType = None

    bigquery = MockBigQuery()
    GoogleCloudError = Exception
    service_account = None

from ..core.circuit_breaker import (
    create_bigquery_circuit_breaker,
    create_bigquery_retry_handler,
)
from ..core.config import CircuitBreakerConfig
from ..platforms.ga4.bigquery_client import GA4BigQueryClient
from ..platforms.ga4.validation import GA4DataValidator

try:
    from circuitbreaker import CircuitBreakerError
except ImportError:
    CircuitBreakerError = Exception
from .base import (
    ExportConfig,
    ExportConnectionError,
    ExportDestination,
    ExportFormat,
    ExportProgress,
    ExportResult,
    ExportStatus,
    ExportValidationError,
    PaginationConfig,
)

logger = logging.getLogger(__name__)

# BigQuery limits
DEFAULT_BATCH_SIZE = (
    10000  # BigQuery streaming insert limit - configurable via pagination config
)
MAX_ROW_SIZE_BYTES = 5 * 1024 * 1024  # 5MB per row
MAX_MEMORY_USAGE_MB = 500  # Default memory limit for BigQuery exports


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format with timezone."""
    return datetime.now(timezone.utc).isoformat()


class BigQueryExporter(ExportDestination):
    """Export data to Google BigQuery."""

    def __init__(
        self,
        config: ExportConfig,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize BigQuery exporter."""
        super().__init__(config)
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "Google Cloud BigQuery is not installed. "
                "Install with: pip install google-cloud-bigquery"
            )
        self.client: Optional[bigquery.Client] = None
        self.dataset_ref: Optional[bigquery.DatasetReference] = None
        self._validated_credentials = False
        self._process = psutil.Process(os.getpid())

        # Use pagination config for batch size
        self.batch_size = (
            config.pagination.batch_size if config.pagination else DEFAULT_BATCH_SIZE
        )

        # Initialize circuit breaker and retry handler
        self._circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.circuit_breaker = create_bigquery_circuit_breaker(
            self._circuit_breaker_config
        )
        self.retry_handler = create_bigquery_retry_handler()

        # CSV fallback exporter for graceful degradation
        self._csv_fallback_exporter: Optional[Any] = None
        self._csv_fallback_dir: Optional[Path] = None

        # GA4 integration support
        self._ga4_client: Optional[GA4BigQueryClient] = None
        self._ga4_validator: Optional[GA4DataValidator] = None

    def _get_csv_fallback_exporter(self):
        """Get or create CSV fallback exporter."""
        if self._csv_fallback_exporter is None:
            from pathlib import Path

            from .csv import CSVExporter

            # Create CSV exporter with same config
            output_dir = Path.cwd() / "bigquery_fallback_exports"
            self._csv_fallback_dir = output_dir
            self._csv_fallback_exporter = CSVExporter(
                output_dir=output_dir,
                pagination_config=self.config.pagination,
            )
            logger.info(f"Initialized CSV fallback exporter at {output_dir}")
        return self._csv_fallback_exporter

    def configure_ga4_integration(
        self,
        ga4_project_id: str,
        ga4_dataset_id: str,
        location: str = "US",
    ) -> None:
        """Configure GA4 BigQuery integration for enhanced exports.

        Args:
            ga4_project_id: Google Cloud project ID with GA4 exports
            ga4_dataset_id: GA4 BigQuery dataset ID
            location: BigQuery location
        """
        try:
            self._ga4_client = GA4BigQueryClient(
                project_id=ga4_project_id,
                ga4_dataset_id=ga4_dataset_id,
                location=location,
            )
            self._ga4_validator = GA4DataValidator(self._ga4_client)
            logger.info(f"GA4 integration configured for dataset {ga4_dataset_id}")
        except Exception as e:
            logger.error(f"Failed to configure GA4 integration: {e}")
            self._ga4_client = None
            self._ga4_validator = None

    def validate_ga4_integration(
        self,
        export_data: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Validate GA4 integration before export.

        Args:
            export_data: Data to be exported
            start_date: Export start date
            end_date: Export end date

        Returns:
            Validation report or None if GA4 not configured
        """
        if not self._ga4_validator:
            logger.info("GA4 validation not configured, skipping")
            return None

        try:
            validation_report = self._ga4_validator.run_comprehensive_validation(
                export_data, start_date, end_date
            )

            quality_score = validation_report.get("validation_summary", {}).get(
                "overall_quality_score", 0
            )
            logger.info(
                f"GA4 validation completed with quality score: {quality_score:.1f}/100"
            )

            return validation_report

        except Exception as e:
            logger.error(f"GA4 validation failed: {e}")
            return {"error": str(e), "quality_score": 0.0}

    @property
    def is_circuit_breaker_open(self) -> bool:
        """Check if the circuit breaker is open (BigQuery unavailable)."""
        return self.circuit_breaker.is_open

    @property
    def should_use_csv_fallback(self) -> bool:
        """Determine if we should use CSV fallback instead of BigQuery."""
        return self.is_circuit_breaker_open or not BIGQUERY_AVAILABLE

    async def _export_audit_results_to_csv(
        self,
        customer_id: str,
        audit_data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        export_id: str,
        started_at: datetime,
    ) -> ExportResult:
        """Fallback to CSV export when BigQuery is unavailable."""
        try:
            csv_exporter = self._get_csv_fallback_exporter()

            # Convert audit data format for CSV
            csv_data = {"audit_results": audit_data}

            result = await csv_exporter.export_batch(customer_id, csv_data, metadata)

            # Update result to indicate this was a fallback
            return ExportResult(
                export_id=export_id,
                status=result.status,
                destination=ExportFormat.CSV,  # Changed from BIGQUERY to CSV
                records_exported=result.records_exported,
                started_at=started_at,
                completed_at=result.completed_at,
                metadata={
                    **result.metadata,
                    "fallback_reason": "BigQuery circuit breaker open",
                    "original_destination": "BigQuery",
                    "circuit_breaker_metrics": self.circuit_breaker.metrics,
                },
            )
        except Exception as e:
            logger.error(f"CSV fallback export failed: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.CSV,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"CSV fallback failed: {str(e)}",
            )

    def _validate_credentials(self) -> None:
        """Validate credentials format without logging sensitive data."""
        if self._validated_credentials:
            return

        if "service_account_json" in self.config.credentials:
            try:
                creds_data = json.loads(self.config.credentials["service_account_json"])
                required_fields = [
                    "type",
                    "project_id",
                    "private_key_id",
                    "private_key",
                    "client_email",
                ]
                missing_fields = [f for f in required_fields if f not in creds_data]
                if missing_fields:
                    raise ExportValidationError(
                        f"Service account JSON missing required fields: {', '.join(missing_fields)}"
                    )
                if creds_data.get("type") != "service_account":
                    raise ExportValidationError(
                        "Invalid credential type. Expected 'service_account'"
                    )
            except json.JSONDecodeError as e:
                raise ExportValidationError(
                    f"Invalid service account JSON format: {str(e)}"
                )

        self._validated_credentials = True

    @contextmanager
    def _get_client_context(self):
        """Context manager for BigQuery client lifecycle."""
        client = None
        try:
            client = self._get_client()
            yield client
        finally:
            # Clean up client resources if needed
            if client and hasattr(client, "close"):
                client.close()

    def _get_client(self) -> bigquery.Client:
        """Get or create BigQuery client."""
        if self.client is None:
            self._validate_credentials()

            if "service_account_json" in self.config.credentials:
                # Use service account credentials
                creds = service_account.Credentials.from_service_account_info(
                    json.loads(self.config.credentials["service_account_json"])
                )
                self.client = bigquery.Client(
                    credentials=creds, project=self.config.project_id
                )
                logger.info(
                    f"BigQuery client created for project: {self.config.project_id}"
                )
            else:
                # Use default credentials
                self.client = bigquery.Client(project=self.config.project_id)
                logger.info(
                    f"BigQuery client created with default credentials for project: {self.config.project_id}"
                )

        return self.client

    def _get_dataset_ref(self) -> bigquery.DatasetReference:
        """Get dataset reference."""
        if self.dataset_ref is None:
            client = self._get_client()
            self.dataset_ref = client.dataset(self.config.dataset)
        return self.dataset_ref

    async def validate_connection(self) -> bool:
        """Validate BigQuery connection and permissions."""
        # Check if we should use CSV fallback mode
        if self.should_use_csv_fallback:
            logger.warning(
                "BigQuery circuit breaker is open - validation skipped, using CSV fallback"
            )
            return True

        @self.circuit_breaker
        def _validate_connection_internal():
            client = self._get_client()

            # Check if dataset exists
            dataset_ref = self._get_dataset_ref()
            client.get_dataset(dataset_ref)

            # Test write permissions by checking table creation
            test_table_id = (
                f"{self.config.dataset}._connection_test_{uuid.uuid4().hex[:8]}"
            )
            table_ref = dataset_ref.table(test_table_id)
            schema = [
                bigquery.SchemaField("test_field", "STRING"),
            ]
            table = bigquery.Table(table_ref, schema=schema)

            # Create and immediately delete test table
            created_table = client.create_table(table)
            client.delete_table(created_table)

            logger.info(
                f"Successfully validated BigQuery connection to {self.config.project_id}.{self.config.dataset}"
            )
            return True

        try:
            # Use retry handler for connection validation
            return await self.retry_handler.execute_with_retry(
                _validate_connection_internal
            )
        except GoogleCloudError as e:
            logger.error(f"BigQuery connection validation failed: {e}")
            raise ExportConnectionError(f"Failed to connect to BigQuery: {str(e)}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid credentials format: {e}")
            raise ExportValidationError(f"Invalid credentials: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during connection validation: {e}")
            raise ExportConnectionError(f"Connection validation failed: {str(e)}")

    def _validate_audit_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize audit result row."""
        if not row.get("audit_id"):
            raise ExportValidationError("audit_id is required")
        if not row.get("audit_date"):
            raise ExportValidationError("audit_date is required")

        # Ensure numeric fields are valid
        metrics = row.get("metrics", {})
        metrics["keywords_analyzed"] = max(0, int(metrics.get("keywords_analyzed", 0)))
        metrics["issues_found"] = max(0, int(metrics.get("issues_found", 0)))
        metrics["cost_savings"] = max(0.0, float(metrics.get("cost_savings", 0.0)))

        # Validate date format
        try:
            if isinstance(row["audit_date"], str) and "T" in row["audit_date"]:
                # Convert datetime to date string
                row["audit_date"] = row["audit_date"].split("T")[0]
        except (KeyError, ValueError, TypeError) as e:
            raise ExportValidationError(f"Invalid audit_date format: {e}")

        return row

    def _validate_recommendation_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize recommendation row."""
        if not row.get("recommendation_id"):
            raise ExportValidationError("recommendation_id is required")
        if not row.get("audit_id"):
            raise ExportValidationError("audit_id is required")

        # Validate priority
        valid_priorities = ["high", "medium", "low"]
        if row.get("priority") not in valid_priorities:
            row["priority"] = "medium"  # Default to medium

        # Ensure numeric fields
        row["estimated_impact"] = max(0.0, float(row.get("estimated_impact", 0.0)))

        # Ensure metadata is JSON serializable
        metadata = row.get("metadata", {})
        if isinstance(metadata, dict):
            row["metadata"] = json.dumps(metadata)
        elif not isinstance(metadata, str):
            row["metadata"] = "{}"

        return row

    def _validate_metric_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize metric row."""
        if not row.get("metric_name"):
            raise ExportValidationError("metric_name is required")

        # Validate metric type
        valid_types = ["currency", "count", "percentage", "ratio"]
        if row.get("metric_type") not in valid_types:
            row["metric_type"] = "count"  # Default type

        # Ensure numeric value
        row["metric_value"] = float(row.get("metric_value", 0.0))

        # Ensure dimensions is JSON serializable
        dimensions = row.get("dimensions", {})
        if isinstance(dimensions, dict):
            row["dimensions"] = json.dumps(dimensions)
        elif not isinstance(dimensions, str):
            row["dimensions"] = "{}"

        return row

    def _ensure_table_exists(
        self, table_name: str, schema: List[bigquery.SchemaField]
    ) -> bigquery.Table:
        """Ensure table exists with proper schema."""
        client = self._get_client()
        dataset_ref = self._get_dataset_ref()
        table_ref = dataset_ref.table(table_name)

        try:
            # Check if table exists
            table = client.get_table(table_ref)
            logger.info(f"Table {table_name} already exists")
            return table
        except GoogleCloudError as e:
            # Create table if it doesn't exist
            logger.info(f"Table {table_name} not found, creating it: {e}")
            table = bigquery.Table(table_ref, schema=schema)

            # Set up partitioning
            if table_name in ["audit_results", "recommendations"]:
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="created_at"
                    if table_name == "recommendations"
                    else "audit_date",
                )

            created_table = client.create_table(table)
            logger.info(f"Created table {table_name}")
            return created_table

    def _get_audit_results_schema(self) -> List[bigquery.SchemaField]:
        """Get schema for audit results table."""
        return [
            bigquery.SchemaField("audit_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("audit_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("analyzer_name", "STRING"),
            bigquery.SchemaField(
                "metrics",
                "RECORD",
                mode="REPEATED",
                fields=[
                    bigquery.SchemaField("keywords_analyzed", "INTEGER"),
                    bigquery.SchemaField("issues_found", "INTEGER"),
                    bigquery.SchemaField("cost_savings", "FLOAT"),
                ],
            ),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ]

    def _get_recommendations_schema(self) -> List[bigquery.SchemaField]:
        """Get schema for recommendations table."""
        return [
            bigquery.SchemaField("recommendation_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("audit_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("type", "STRING"),
            bigquery.SchemaField("priority", "STRING"),
            bigquery.SchemaField("title", "STRING"),
            bigquery.SchemaField("description", "STRING"),
            bigquery.SchemaField("estimated_impact", "FLOAT"),
            bigquery.SchemaField("metadata", "JSON"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]

    def _get_metrics_schema(self) -> List[bigquery.SchemaField]:
        """Get schema for metrics table."""
        return [
            bigquery.SchemaField("metric_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("metric_value", "FLOAT"),
            bigquery.SchemaField("metric_type", "STRING"),
            bigquery.SchemaField("dimensions", "JSON"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        ]

    async def export_audit_results(
        self,
        customer_id: str,
        audit_data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export audit results to BigQuery with circuit breaker and CSV fallback."""
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        # Use circuit breaker protection for the entire operation
        @self.circuit_breaker
        def _execute_bigquery_export():
            # Ensure table exists
            table = self._ensure_table_exists(
                "audit_results", self._get_audit_results_schema()
            )

            # Prepare data for insertion with validation
            rows = []
            validation_errors = []
            for idx, item in enumerate(audit_data):
                try:
                    row = {
                        "audit_id": item.get("audit_id"),
                        "customer_id": customer_id,
                        "audit_date": item.get("audit_date"),
                        "analyzer_name": item.get("analyzer_name"),
                        "metrics": {
                            "keywords_analyzed": item.get("keywords_analyzed", 0),
                            "issues_found": item.get("issues_found", 0),
                            "cost_savings": item.get("cost_savings", 0.0),
                        },
                        "created_at": item.get("created_at", _get_utc_timestamp()),
                        "updated_at": item.get("updated_at", _get_utc_timestamp()),
                    }
                    validated_row = self._validate_audit_row(row)
                    rows.append(validated_row)
                except ExportValidationError as e:
                    validation_errors.append(f"Row {idx}: {e}")
                    logger.warning(f"Skipping invalid audit row {idx}: {e}")
                    continue

            if not rows:
                raise ExportValidationError(
                    f"No valid rows to export. Errors: {validation_errors[:5]}"
                )

            # Insert data in batches
            client = self._get_client()
            total_errors = []
            rows_inserted = 0

            for i in range(0, len(rows), self.batch_size):
                batch = rows[i : i + self.batch_size]
                errors = client.insert_rows_json(table, batch)
                if errors:
                    total_errors.extend(errors)
                    logger.error(
                        f"Batch {i // self.batch_size + 1} had {len(errors)} errors"
                    )
                else:
                    rows_inserted += len(batch)

                # Log progress for large exports
                if i % (self.batch_size * 10) == 0:  # Every 10 batches
                    progress = (i + len(batch)) / len(rows) * 100
                    memory_mb = self._process.memory_info().rss / 1024 / 1024
                    logger.info(
                        f"BigQuery export progress: {progress:.1f}% "
                        f"({i + len(batch)}/{len(rows)} rows, {memory_mb:.1f}MB)"
                    )

            return total_errors, rows_inserted, len(rows)

        try:
            # Execute BigQuery export with retry and circuit breaker protection
            (
                total_errors,
                rows_inserted,
                total_rows,
            ) = await self.retry_handler.execute_with_retry(_execute_bigquery_export)

            if total_errors:
                error_msg = f"Failed to insert {len(total_errors)} rows. Sample errors: {total_errors[:3]}"
                logger.error(error_msg)
                return ExportResult(
                    export_id=export_id,
                    status=ExportStatus.FAILED,
                    destination=ExportFormat.BIGQUERY,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    error_message=error_msg,
                    metadata={
                        "rows_attempted": total_rows,
                        "rows_inserted": rows_inserted,
                    },
                )

            logger.info(
                f"Successfully exported {rows_inserted} audit results to BigQuery"
            )

            return ExportResult(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=rows_inserted,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "table": f"{self.config.project_id}.{self.config.dataset}.audit_results",
                    "customer_id": customer_id,
                    "total_rows_processed": total_rows,
                },
            )

        except ExportValidationError as e:
            logger.error(f"Validation error during audit results export: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"Validation error: {str(e)}",
            )
        except CircuitBreakerError as e:
            # Circuit breaker is open - use CSV fallback immediately
            logger.warning(f"BigQuery circuit breaker is open, using CSV fallback: {e}")
            return await self._export_audit_results_to_csv(
                customer_id, audit_data, metadata, export_id, started_at
            )
        except Exception as e:
            # Check if this is a circuit breaker exception or BigQuery error
            logger.error(f"BigQuery export failed, attempting CSV fallback: {e}")

            # Circuit breaker may have opened during the operation, try CSV fallback
            try:
                logger.warning(
                    f"Falling back to CSV export due to BigQuery failure: {e}"
                )
                return await self._export_audit_results_to_csv(
                    customer_id, audit_data, metadata, export_id, started_at
                )
            except Exception as fallback_error:
                logger.error(f"Both BigQuery and CSV fallback failed: {fallback_error}")
                return ExportResult(
                    export_id=export_id,
                    status=ExportStatus.FAILED,
                    destination=ExportFormat.BIGQUERY,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    error_message=f"BigQuery failed: {str(e)}. CSV fallback also failed: {str(fallback_error)}",
                    metadata={
                        "original_error": str(e),
                        "fallback_error": str(fallback_error),
                        "circuit_breaker_state": self.circuit_breaker.state,
                    },
                )

    async def export_recommendations(
        self,
        customer_id: str,
        recommendations: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export recommendations to BigQuery."""
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        try:
            # Ensure table exists
            table = self._ensure_table_exists(
                "recommendations", self._get_recommendations_schema()
            )

            # Prepare data for insertion with validation
            rows = []
            validation_errors = []
            for idx, item in enumerate(recommendations):
                try:
                    row = {
                        "recommendation_id": item.get("recommendation_id"),
                        "audit_id": item.get("audit_id"),
                        "type": item.get("type"),
                        "priority": item.get("priority"),
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "estimated_impact": item.get("estimated_impact", 0.0),
                        "metadata": item.get("metadata", {}),
                        "created_at": item.get("created_at", _get_utc_timestamp()),
                    }
                    validated_row = self._validate_recommendation_row(row)
                    rows.append(validated_row)
                except ExportValidationError as e:
                    validation_errors.append(f"Row {idx}: {e}")
                    logger.warning(f"Skipping invalid recommendation row {idx}: {e}")
                    continue

            if not rows:
                raise ExportValidationError(
                    f"No valid rows to export. Errors: {validation_errors[:5]}"
                )

            # Insert data in batches
            client = self._get_client()
            total_errors = []
            rows_inserted = 0

            for i in range(0, len(rows), self.batch_size):
                batch = rows[i : i + self.batch_size]
                errors = client.insert_rows_json(table, batch)
                if errors:
                    total_errors.extend(errors)
                    logger.error(
                        f"Batch {i // self.batch_size + 1} had {len(errors)} errors"
                    )
                else:
                    rows_inserted += len(batch)

                # Log progress for large exports
                if i % (self.batch_size * 10) == 0:  # Every 10 batches
                    progress = (i + len(batch)) / len(rows) * 100
                    memory_mb = self._process.memory_info().rss / 1024 / 1024
                    logger.info(
                        f"BigQuery export progress: {progress:.1f}% "
                        f"({i + len(batch)}/{len(rows)} rows, {memory_mb:.1f}MB)"
                    )

            if total_errors:
                error_msg = f"Failed to insert {len(total_errors)} rows. Sample errors: {total_errors[:3]}"
                logger.error(error_msg)
                return ExportResult(
                    export_id=export_id,
                    status=ExportStatus.FAILED,
                    destination=ExportFormat.BIGQUERY,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    error_message=error_msg,
                    metadata={
                        "rows_attempted": len(rows),
                        "rows_inserted": rows_inserted,
                    },
                )

            logger.info(
                f"Successfully exported {rows_inserted} recommendations to BigQuery"
            )

            return ExportResult(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=rows_inserted,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "table": f"{self.config.project_id}.{self.config.dataset}.recommendations",
                    "customer_id": customer_id,
                    "validation_errors": len(validation_errors),
                },
            )

        except ExportValidationError as e:
            logger.error(f"Validation error during recommendations export: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"Validation error: {str(e)}",
            )
        except GoogleCloudError as e:
            logger.error(f"BigQuery error during recommendations export: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"BigQuery error: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error exporting recommendations: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"Unexpected error: {str(e)}",
            )

    async def export_metrics(
        self,
        customer_id: str,
        metrics: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """Export metrics to BigQuery."""
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        try:
            # Ensure table exists
            table = self._ensure_table_exists("metrics", self._get_metrics_schema())

            # Prepare data for insertion with validation
            rows = []
            validation_errors = []
            for idx, item in enumerate(metrics):
                try:
                    row = {
                        "metric_id": item.get("metric_id", f"{export_id}_{idx}"),
                        "customer_id": customer_id,
                        "metric_name": item.get("metric_name"),
                        "metric_value": item.get("metric_value", 0.0),
                        "metric_type": item.get("metric_type", "count"),
                        "dimensions": item.get("dimensions", {}),
                        "timestamp": item.get("timestamp", _get_utc_timestamp()),
                    }
                    validated_row = self._validate_metric_row(row)
                    rows.append(validated_row)
                except ExportValidationError as e:
                    validation_errors.append(f"Row {idx}: {e}")
                    logger.warning(f"Skipping invalid metric row {idx}: {e}")
                    continue

            if not rows:
                raise ExportValidationError(
                    f"No valid rows to export. Errors: {validation_errors[:5]}"
                )

            # Insert data in batches
            client = self._get_client()
            total_errors = []
            rows_inserted = 0

            for i in range(0, len(rows), self.batch_size):
                batch = rows[i : i + self.batch_size]
                errors = client.insert_rows_json(table, batch)
                if errors:
                    total_errors.extend(errors)
                    logger.error(
                        f"Batch {i // self.batch_size + 1} had {len(errors)} errors"
                    )
                else:
                    rows_inserted += len(batch)

                # Log progress for large exports
                if i % (self.batch_size * 10) == 0:  # Every 10 batches
                    progress = (i + len(batch)) / len(rows) * 100
                    memory_mb = self._process.memory_info().rss / 1024 / 1024
                    logger.info(
                        f"BigQuery export progress: {progress:.1f}% "
                        f"({i + len(batch)}/{len(rows)} rows, {memory_mb:.1f}MB)"
                    )

            if total_errors:
                error_msg = f"Failed to insert {len(total_errors)} rows. Sample errors: {total_errors[:3]}"
                logger.error(error_msg)
                return ExportResult(
                    export_id=export_id,
                    status=ExportStatus.FAILED,
                    destination=ExportFormat.BIGQUERY,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    error_message=error_msg,
                    metadata={
                        "rows_attempted": len(rows),
                        "rows_inserted": rows_inserted,
                    },
                )

            logger.info(f"Successfully exported {rows_inserted} metrics to BigQuery")

            return ExportResult(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=rows_inserted,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "table": f"{self.config.project_id}.{self.config.dataset}.metrics",
                    "customer_id": customer_id,
                    "validation_errors": len(validation_errors),
                },
            )

        except ExportValidationError as e:
            logger.error(f"Validation error during metrics export: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"Validation error: {str(e)}",
            )
        except GoogleCloudError as e:
            logger.error(f"BigQuery error during metrics export: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"BigQuery error: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error exporting metrics: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=f"Unexpected error: {str(e)}",
            )

    async def check_export_status(self, export_id: str) -> ExportResult:
        """Check the status of an export job."""
        # For BigQuery streaming inserts, exports are synchronous
        # This method is mainly for compatibility with async export destinations
        return ExportResult(
            export_id=export_id,
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            metadata={"message": "BigQuery exports are synchronous"},
        )

    async def export_batch_paginated(
        self,
        customer_id: str,
        data: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> ExportResult:
        """Export batch data with enhanced pagination support and progress tracking.

        Args:
            customer_id: Customer identifier
            data: Data to export
            metadata: Optional metadata
            progress_callback: Optional callback for progress updates

        Returns:
            Export result
        """
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        # Create progress tracker
        total_records = sum(len(records) for records in data.values())
        progress = ExportProgress(
            export_id=export_id,
            current_records=0,
            total_records=total_records,
            current_batch=0,
            total_batches=len(data),
            memory_usage_mb=0.0,
            started_at=started_at,
        )

        try:
            results = []
            current_records_processed = 0

            # Process each data type
            for batch_idx, (table_type, records) in enumerate(data.items()):
                progress.current_batch = batch_idx + 1

                if not records:
                    continue

                logger.info(
                    f"Processing BigQuery export for {table_type}: {len(records)} records "
                    f"(batch {progress.current_batch}/{progress.total_batches})"
                )

                # Export based on table type
                if table_type == "audit_results":
                    result = await self.export_audit_results(
                        customer_id, records, metadata
                    )
                elif table_type == "recommendations":
                    result = await self.export_recommendations(
                        customer_id, records, metadata
                    )
                elif table_type == "metrics":
                    result = await self.export_metrics(customer_id, records, metadata)
                else:
                    logger.warning(f"Unknown table type: {table_type}")
                    continue

                results.append(result)
                current_records_processed += len(records)

                # Update progress
                progress.current_records = current_records_processed
                progress.memory_usage_mb = self._process.memory_info().rss / 1024 / 1024

                if progress_callback:
                    progress_callback(progress.current_records, progress.total_records)

            # Combine results
            total_exported = sum(r.records_exported for r in results)
            all_failed = all(r.status == ExportStatus.FAILED for r in results)

            completed_at = datetime.now(timezone.utc)
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED if all_failed else ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=total_exported,
                started_at=started_at,
                completed_at=completed_at,
                progress=progress,
                metadata={
                    "customer_id": customer_id,
                    "batches_processed": len(data),
                    "batch_size": self.batch_size,
                    "peak_memory_mb": progress.memory_usage_mb,
                    "individual_results": [
                        {
                            "table_type": table_type,
                            "status": result.status.value,
                            "records": result.records_exported,
                            "error": result.error_message,
                        }
                        for (table_type, _), result in zip(data.items(), results)
                    ],
                },
            )

        except Exception as e:
            logger.error(
                f"BigQuery paginated export failed for customer {customer_id}: {e}"
            )
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                progress=progress,
            )

    def update_pagination_config(self, pagination_config: PaginationConfig) -> None:
        """Update pagination configuration.

        Args:
            pagination_config: New pagination configuration
        """
        self.config.pagination = pagination_config
        self.batch_size = pagination_config.batch_size
        logger.info(
            f"BigQuery pagination config updated: batch_size={pagination_config.batch_size}, "
            f"max_memory_mb={pagination_config.max_memory_mb}"
        )

    def cleanup_csv_fallback(self, remove_files: bool = False) -> bool:
        """Clean up CSV fallback resources.

        Args:
            remove_files: Whether to remove the fallback directory and files

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            if self._csv_fallback_exporter:
                # Clear the exporter reference
                self._csv_fallback_exporter = None
                logger.info("Cleaned up CSV fallback exporter reference")

            if (
                remove_files
                and self._csv_fallback_dir
                and self._csv_fallback_dir.exists()
            ):
                import shutil

                shutil.rmtree(self._csv_fallback_dir)
                logger.info(f"Removed CSV fallback directory: {self._csv_fallback_dir}")
                self._csv_fallback_dir = None

            return True
        except Exception as e:
            logger.error(f"Error during CSV fallback cleanup: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        try:
            # Always cleanup references, but don't remove files unless explicitly requested
            self.cleanup_csv_fallback(remove_files=False)
        except Exception as e:
            logger.error(f"Error during BigQuery exporter cleanup: {e}")
        return False  # Don't suppress exceptions

    def get_circuit_breaker_health(self) -> dict[str, Any]:
        """Get circuit breaker health information for monitoring."""
        return self.circuit_breaker.get_health_check_info()

    def get_retry_metrics(self) -> dict[str, Any]:
        """Get retry handler metrics."""
        return self.retry_handler.metrics

    def get_service_health(self) -> dict[str, Any]:
        """Get comprehensive service health information."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bigquery": {
                "available": BIGQUERY_AVAILABLE,
                "circuit_breaker": self.get_circuit_breaker_health(),
                "retry_handler": self.get_retry_metrics(),
            },
            "csv_fallback": {
                "enabled": True,
                "exporter_initialized": self._csv_fallback_exporter is not None,
            },
            "configuration": {
                "batch_size": self.batch_size,
                "circuit_breaker_enabled": self._circuit_breaker_config.enabled,
                "failure_threshold": self._circuit_breaker_config.failure_threshold,
                "recovery_timeout": self._circuit_breaker_config.recovery_timeout,
            },
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on BigQuery service."""
        health_info = {
            "service": "BigQuery Export",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unknown",
        }

        try:
            # If circuit breaker is open, service is degraded but operational via CSV
            if self.circuit_breaker.is_open:
                health_info.update(
                    {
                        "status": "degraded",
                        "message": "BigQuery circuit breaker open, using CSV fallback",
                        "circuit_breaker": self.get_circuit_breaker_health(),
                        "fallback_available": True,
                    }
                )
                return health_info

            # Try to validate connection to BigQuery
            connection_valid = await self.validate_connection()

            if connection_valid:
                health_info.update(
                    {
                        "status": "healthy",
                        "message": "BigQuery connection validated successfully",
                        "circuit_breaker": self.get_circuit_breaker_health(),
                        "retry_metrics": self.get_retry_metrics(),
                    }
                )
            else:
                health_info.update(
                    {
                        "status": "unhealthy",
                        "message": "BigQuery connection validation failed",
                        "circuit_breaker": self.get_circuit_breaker_health(),
                    }
                )

        except Exception as e:
            health_info.update(
                {
                    "status": "unhealthy",
                    "message": f"Health check failed: {str(e)}",
                    "error": str(e),
                    "circuit_breaker": self.get_circuit_breaker_health(),
                }
            )

        return health_info
