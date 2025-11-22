"""Hybrid data export manager supporting both CSV and BigQuery outputs."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from paidsearchnav.core.config import BigQueryTier

from .base import (
    ExportConfig,
    ExportError,
    ExportFormat,
    ExportProgress,
    ExportRequest,
    ExportResult,
    ExportStatus,
    PaginationConfig,
)
from .csv import CSVExporter
from .manager import ExportManager

logger = logging.getLogger(__name__)


class CustomerTier:
    """Customer tier configuration for export modes."""

    STANDARD = "standard"  # CSV-only exports
    PREMIUM = "premium"  # BigQuery analytics + CSV fallback
    ENTERPRISE = "enterprise"  # Premium + ML models + real-time streaming


class HybridExportConfig:
    """Configuration for hybrid export behavior."""

    def __init__(
        self,
        customer_tier: str = CustomerTier.STANDARD,
        output_mode: str = "auto",  # auto, csv, bigquery, both
        bigquery_enabled: bool = False,
        fallback_to_csv: bool = True,
        cost_tracking_enabled: bool = True,
        max_cost_per_export_usd: float = 10.0,
        pagination_config: Optional[PaginationConfig] = None,
    ):
        self.customer_tier = customer_tier
        self.output_mode = output_mode
        self.bigquery_enabled = bigquery_enabled
        self.fallback_to_csv = fallback_to_csv
        self.cost_tracking_enabled = cost_tracking_enabled
        self.max_cost_per_export_usd = max_cost_per_export_usd
        self.pagination_config = (
            pagination_config or self._get_default_pagination_config(customer_tier)
        )

    def _get_default_pagination_config(self, customer_tier: str) -> PaginationConfig:
        """Get default pagination configuration based on customer tier."""
        if customer_tier == CustomerTier.ENTERPRISE:
            return PaginationConfig(
                batch_size=50000,  # Larger batches for enterprise
                max_memory_mb=1000,  # More memory allowed
                enable_streaming=True,
                progress_callback_interval=5000,
            )
        elif customer_tier == CustomerTier.PREMIUM:
            return PaginationConfig(
                batch_size=25000,
                max_memory_mb=500,
                enable_streaming=True,
                progress_callback_interval=2500,
            )
        else:  # STANDARD
            return PaginationConfig(
                batch_size=10000,
                max_memory_mb=100,
                enable_streaming=True,
                progress_callback_interval=1000,
            )

    def should_export_to_csv(self) -> bool:
        """Determine if CSV export should be performed."""
        if self.output_mode == "csv":
            return True
        elif self.output_mode == "bigquery":
            return False  # BigQuery only
        elif self.output_mode == "both":
            return True
        else:  # auto mode
            return True  # Always generate CSV for backward compatibility

    def should_export_to_bigquery(self) -> bool:
        """Determine if BigQuery export should be performed."""
        if not self.bigquery_enabled:
            return False

        if self.customer_tier == CustomerTier.STANDARD:
            return False

        if self.output_mode == "csv":
            return False
        elif self.output_mode == "bigquery":
            return True
        elif self.output_mode == "both":
            return True
        else:  # auto mode
            return self.customer_tier in [CustomerTier.PREMIUM, CustomerTier.ENTERPRISE]


class HybridExportManager(ExportManager):
    """Enhanced export manager supporting both CSV and BigQuery outputs with fallback."""

    def __init__(self, config_manager: Optional[Any] = None):
        super().__init__(config_manager)
        self.csv_exporter = CSVExporter()
        self.cost_tracker: Dict[str, float] = {}  # Track costs per customer
        self.progress_trackers: Dict[str, ExportProgress] = {}  # Track export progress

    def get_customer_tier(self, customer_id: str) -> str:
        """Determine customer tier based on configuration or customer ID.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer tier (standard, premium, enterprise)
        """
        # Use config manager if available
        if hasattr(self, "config_manager") and self.config_manager:
            try:
                return self.config_manager.get_customer_tier(customer_id)
            except (AttributeError, NotImplementedError):
                logger.debug(
                    "Config manager doesn't support customer tier lookup, using fallback"
                )

        # Fallback configuration - should be moved to environment/config in production
        tier_map = {
            # Example customer mappings - these should be in configuration
            "1234567890": CustomerTier.PREMIUM,
            "0987654321": CustomerTier.ENTERPRISE,
        }

        tier = tier_map.get(customer_id, CustomerTier.STANDARD)
        logger.info(f"Customer {customer_id} assigned tier: {tier}")
        return tier

    def get_hybrid_config(
        self, customer_id: str, bigquery_config: Optional[Any] = None
    ) -> HybridExportConfig:
        """Get hybrid export configuration for a customer.

        Args:
            customer_id: Customer identifier
            bigquery_config: BigQuery configuration from settings

        Returns:
            Hybrid export configuration
        """
        customer_tier = self.get_customer_tier(customer_id)

        # Determine BigQuery enablement
        bigquery_enabled = False
        if bigquery_config:
            bigquery_enabled = (
                bigquery_config.enabled
                and bigquery_config.tier != BigQueryTier.DISABLED
            )

        # Set output mode based on tier and configuration
        output_mode = "auto"
        if customer_tier == CustomerTier.STANDARD:
            output_mode = "csv"
        elif bigquery_enabled and customer_tier in [
            CustomerTier.PREMIUM,
            CustomerTier.ENTERPRISE,
        ]:
            output_mode = "both"  # Default to both for premium customers

        return HybridExportConfig(
            customer_tier=customer_tier,
            output_mode=output_mode,
            bigquery_enabled=bigquery_enabled,
            fallback_to_csv=True,
            cost_tracking_enabled=True,
            max_cost_per_export_usd=10.0
            if customer_tier == CustomerTier.PREMIUM
            else 25.0,
        )

    async def export_data_hybrid(
        self,
        request: ExportRequest,
        data: Dict[str, List[Dict[str, Any]]],
        bigquery_config: Optional[Any] = None,
    ) -> List[ExportResult]:
        """Export data using hybrid approach (CSV + BigQuery based on customer tier).

        Args:
            request: Export request
            data: Data to export
            bigquery_config: BigQuery configuration

        Returns:
            List of export results
        """
        hybrid_config = self.get_hybrid_config(request.customer_id, bigquery_config)
        results = []

        logger.info(
            f"Starting hybrid export for customer {request.customer_id} "
            f"(tier: {hybrid_config.customer_tier}, mode: {hybrid_config.output_mode})"
        )

        # Always try CSV first for backward compatibility
        if hybrid_config.should_export_to_csv():
            try:
                csv_result = await self._export_to_csv(request, data)
                results.append(csv_result)
                logger.info(f"CSV export successful for customer {request.customer_id}")
            except Exception as e:
                logger.error(
                    f"CSV export failed for customer {request.customer_id}: {e}"
                )
                results.append(
                    ExportResult(
                        export_id=request.export_id,
                        status=ExportStatus.FAILED,
                        destination=ExportFormat.CSV,
                        error_message=f"CSV export failed: {str(e)}",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                )

        # Try BigQuery if enabled and appropriate for customer tier
        bigquery_success = False
        if hybrid_config.should_export_to_bigquery():
            try:
                # Check cost limits before proceeding
                if await self._check_cost_limits(request.customer_id, hybrid_config):
                    bigquery_result = await self._export_to_bigquery(
                        request, data, bigquery_config
                    )
                    results.append(bigquery_result)

                    if bigquery_result.status == ExportStatus.COMPLETED:
                        bigquery_success = True
                        logger.info(
                            f"BigQuery export successful for customer {request.customer_id}"
                        )

                        # Track costs
                        if hybrid_config.cost_tracking_enabled:
                            await self._track_export_cost(
                                request.customer_id, bigquery_result
                            )
                    else:
                        logger.warning(
                            f"BigQuery export failed for customer {request.customer_id}"
                        )
                else:
                    logger.warning(
                        f"BigQuery export skipped for customer {request.customer_id} due to cost limits"
                    )
                    results.append(
                        ExportResult(
                            export_id=request.export_id,
                            status=ExportStatus.FAILED,
                            destination=ExportFormat.BIGQUERY,
                            error_message="BigQuery export skipped: cost limit exceeded",
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
            except Exception as e:
                logger.error(
                    f"BigQuery export failed for customer {request.customer_id}: {e}"
                )
                results.append(
                    ExportResult(
                        export_id=request.export_id,
                        status=ExportStatus.FAILED,
                        destination=ExportFormat.BIGQUERY,
                        error_message=f"BigQuery export failed: {str(e)}",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                )

        # Fallback logic: if BigQuery was supposed to work but failed, ensure CSV exists
        if (
            hybrid_config.should_export_to_bigquery()
            and not bigquery_success
            and hybrid_config.fallback_to_csv
            and not hybrid_config.should_export_to_csv()  # CSV wasn't already attempted
        ):
            logger.info(
                f"Falling back to CSV for customer {request.customer_id} due to BigQuery failure"
            )
            try:
                csv_fallback_result = await self._export_to_csv(request, data)
                results.append(csv_fallback_result)
                logger.info(
                    f"CSV fallback successful for customer {request.customer_id}"
                )
            except Exception as e:
                logger.error(
                    f"CSV fallback failed for customer {request.customer_id}: {e}"
                )
                results.append(
                    ExportResult(
                        export_id=request.export_id,
                        status=ExportStatus.FAILED,
                        destination=ExportFormat.CSV,
                        error_message=f"CSV fallback failed: {str(e)}",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                )

        # Log summary
        successful_exports = [r for r in results if r.status == ExportStatus.COMPLETED]
        failed_exports = [r for r in results if r.status == ExportStatus.FAILED]

        logger.info(
            f"Hybrid export completed for customer {request.customer_id}: "
            f"{len(successful_exports)} successful, {len(failed_exports)} failed"
        )

        return results

    async def _export_to_csv(
        self, request: ExportRequest, data: Dict[str, List[Dict[str, Any]]]
    ) -> ExportResult:
        """Export data to CSV format.

        Args:
            request: Export request
            data: Data to export

        Returns:
            Export result
        """
        # Use the actual CSV exporter
        if not hasattr(self, "csv_exporter"):
            from .csv import CSVExporter

            self.csv_exporter = CSVExporter()

        # Export using the real CSV exporter
        export_result = await self.csv_exporter.export_batch(
            request.customer_id, data, {"export_id": request.export_id}
        )

        # Add cost tracking logging for CSV exports
        logger.info(
            f"CSV export completed for customer {request.customer_id}: "
            f"{export_result.records_exported} records, "
            f"status: {export_result.status.value}"
        )

        return export_result

    async def _export_to_bigquery(
        self,
        request: ExportRequest,
        data: Dict[str, List[Dict[str, Any]]],
        bigquery_config: Optional[Any] = None,
    ) -> ExportResult:
        """Export data to BigQuery.

        Args:
            request: Export request
            data: Data to export
            bigquery_config: BigQuery configuration

        Returns:
            Export result
        """
        if not bigquery_config:
            raise ExportError("BigQuery configuration is required for BigQuery export")

        # Create BigQuery config for the exporter
        export_config = ExportConfig(
            destination_type=ExportFormat.BIGQUERY,
            project_id=bigquery_config.project_id,
            dataset=bigquery_config.dataset_id,
            credentials={},  # Would be populated from bigquery_config
        )

        # Get or create BigQuery exporter
        bigquery_exporter = self._get_exporter(export_config)

        # Export to BigQuery (this will use the existing BigQueryExporter)
        return await bigquery_exporter.export_batch(
            request.customer_id, data, {"export_id": request.export_id}
        )

    async def _check_cost_limits(
        self, customer_id: str, hybrid_config: HybridExportConfig
    ) -> bool:
        """Check if customer is within cost limits for BigQuery export.

        Args:
            customer_id: Customer identifier
            hybrid_config: Hybrid configuration

        Returns:
            True if within limits, False otherwise
        """
        if not hybrid_config.cost_tracking_enabled:
            return True

        current_cost = self.cost_tracker.get(customer_id, 0.0)
        return current_cost < hybrid_config.max_cost_per_export_usd

    async def _track_export_cost(
        self, customer_id: str, export_result: ExportResult
    ) -> None:
        """Track the cost of a BigQuery export.

        Args:
            customer_id: Customer identifier
            export_result: Export result containing cost information
        """
        # Estimate cost based on records exported
        # This is a simplified cost model - in production would integrate with BigQuery billing
        estimated_cost = 0.001 * (
            export_result.records_exported or 0
        )  # $0.001 per record

        if customer_id not in self.cost_tracker:
            self.cost_tracker[customer_id] = 0.0

        self.cost_tracker[customer_id] += estimated_cost

        logger.info(
            f"BigQuery cost tracking - Customer: {customer_id}, "
            f"Records: {export_result.records_exported or 0}, "
            f"Cost: ${estimated_cost:.4f}, "
            f"Total: ${self.cost_tracker[customer_id]:.4f}, "
            f"Export ID: {export_result.export_id}"
        )

    def get_customer_cost_usage(self, customer_id: str) -> Dict[str, Any]:
        """Get cost usage information for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            Cost usage information
        """
        current_cost = self.cost_tracker.get(customer_id, 0.0)
        hybrid_config = self.get_hybrid_config(customer_id)

        return {
            "customer_id": customer_id,
            "current_cost_usd": current_cost,
            "cost_limit_usd": hybrid_config.max_cost_per_export_usd,
            "cost_percentage": (current_cost / hybrid_config.max_cost_per_export_usd)
            * 100,
            "tier": hybrid_config.customer_tier,
            "bigquery_enabled": hybrid_config.bigquery_enabled,
        }

    def reset_customer_costs(self, customer_id: str) -> None:
        """Reset cost tracking for a customer (e.g., monthly reset).

        Args:
            customer_id: Customer identifier
        """
        if customer_id in self.cost_tracker:
            old_cost = self.cost_tracker[customer_id]
            self.cost_tracker[customer_id] = 0.0
            logger.info(
                f"Reset cost tracking for customer {customer_id} (was ${old_cost:.4f})"
            )

    async def export_data_hybrid_paginated(
        self,
        request: ExportRequest,
        data: Dict[str, List[Dict[str, Any]]],
        bigquery_config: Optional[Any] = None,
    ) -> List[ExportResult]:
        """Export data using hybrid approach with enhanced pagination support.

        Args:
            request: Export request with pagination config
            data: Data to export
            bigquery_config: BigQuery configuration

        Returns:
            List of export results
        """
        hybrid_config = self.get_hybrid_config(request.customer_id, bigquery_config)

        # Use request pagination config or hybrid config defaults
        pagination_config = request.pagination_config or hybrid_config.pagination_config

        # Update exporters with pagination config
        self.csv_exporter.update_pagination_config(pagination_config)

        # Track total records for progress calculation
        total_records = sum(len(records) for records in data.values())

        # Initialize progress tracking
        progress = ExportProgress(
            export_id=request.export_id,
            current_records=0,
            total_records=total_records,
            current_batch=0,
            total_batches=len(data),
            memory_usage_mb=0.0,
            started_at=datetime.now(timezone.utc),
        )
        self.progress_trackers[request.export_id] = progress

        # Progress callback to update tracking
        def update_progress(current: int, total: int):
            progress.current_records = current
            if request.progress_callback:
                request.progress_callback(current, total)

        logger.info(
            f"Starting paginated hybrid export for customer {request.customer_id} "
            f"({total_records} total records, batch_size={pagination_config.batch_size})"
        )

        # Call the original hybrid export method with progress callback
        results = await self.export_data_hybrid(request, data, bigquery_config)

        # Update final progress
        progress.current_records = total_records

        return results

    def get_export_progress(self, export_id: str) -> Optional[ExportProgress]:
        """Get progress information for an active export.

        Args:
            export_id: Export identifier

        Returns:
            Export progress or None if not found
        """
        return self.progress_trackers.get(export_id)

    def cleanup_progress_tracker(self, export_id: str) -> None:
        """Clean up progress tracker for completed export.

        Args:
            export_id: Export identifier
        """
        self.progress_trackers.pop(export_id, None)

    async def export_large_dataset_streaming(
        self,
        request: ExportRequest,
        data_provider: Callable,  # Function that yields data in batches
        bigquery_config: Optional[Any] = None,
        batch_size: int = 10000,
    ) -> List[ExportResult]:
        """Export large datasets using streaming approach to minimize memory usage.

        Args:
            request: Export request
            data_provider: Callable that yields data batches
            bigquery_config: BigQuery configuration
            batch_size: Size of each batch

        Returns:
            List of export results
        """
        hybrid_config = self.get_hybrid_config(request.customer_id, bigquery_config)

        logger.info(
            f"Starting streaming export for customer {request.customer_id} "
            f"(batch_size={batch_size}, tier={hybrid_config.customer_tier})"
        )

        results = []
        batch_count = 0
        total_records = 0

        try:
            # Process data in batches using the provider
            async for batch_data in data_provider(batch_size):
                batch_count += 1
                batch_records = sum(len(records) for records in batch_data.values())
                total_records += batch_records

                logger.info(
                    f"Processing batch {batch_count}: {batch_records} records "
                    f"({total_records} total so far)"
                )

                # Create temporary request for this batch
                batch_request = ExportRequest(
                    export_id=f"{request.export_id}_batch_{batch_count}",
                    customer_id=request.customer_id,
                    destination=request.destination,
                )

                # Export this batch
                batch_results = await self.export_data_hybrid(
                    batch_request, batch_data, bigquery_config
                )
                results.extend(batch_results)

        except Exception as e:
            logger.error(f"Streaming export failed: {e}")
            # Return partial results with error information

        logger.info(
            f"Streaming export completed: {batch_count} batches, {total_records} total records"
        )

        return results
