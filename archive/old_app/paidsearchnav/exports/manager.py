"""Export manager for orchestrating data exports."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import (
    ExportConfig,
    ExportDestination,
    ExportError,
    ExportFormat,
    ExportProgress,
    ExportRequest,
    ExportResult,
    ExportStatus,
    PaginationConfig,
)
from .bigquery import BigQueryExporter
from .config import ExportConfigManager
from .retry import RetryPolicy, exponential_backoff_with_jitter

logger = logging.getLogger(__name__)


class ExportManager:
    """Manages data exports to various destinations."""

    def __init__(self, config_manager: Optional[ExportConfigManager] = None):
        """Initialize export manager."""
        self.config_manager = config_manager or ExportConfigManager()
        self.exporters: Dict[str, ExportDestination] = {}
        self.active_exports: Dict[str, ExportRequest] = {}
        self.export_progress: Dict[str, ExportProgress] = {}
        self.retry_policy = RetryPolicy(
            max_attempts=3,
            backoff_func=exponential_backoff_with_jitter,
            retriable_exceptions=(ExportError,),
        )

    def _get_exporter(self, config: ExportConfig) -> ExportDestination:
        """Get or create an exporter for the given configuration."""
        # Create a unique key for the exporter
        key = f"{config.destination_type}:{config.project_id}:{config.dataset}"

        if key not in self.exporters:
            if config.destination_type == ExportFormat.BIGQUERY:
                self.exporters[key] = BigQueryExporter(config)
            else:
                raise ValueError(
                    f"Unsupported export destination: {config.destination_type}"
                )

        return self.exporters[key]

    async def validate_all_connections(self, customer_id: str) -> Dict[str, bool]:
        """Validate connections for all configured exporters."""
        configs = self.config_manager.get_enabled_configs(customer_id)
        results = {}

        for config in configs:
            try:
                exporter = self._get_exporter(config)
                is_valid = await exporter.validate_connection()
                results[config.destination_type.value] = is_valid
            except Exception as e:
                logger.error(f"Failed to validate {config.destination_type}: {e}")
                results[config.destination_type.value] = False

        return results

    async def export_data(
        self, request: ExportRequest, data: Dict[str, List[Dict[str, Any]]]
    ) -> List[ExportResult]:
        """Export data to all configured destinations for a customer."""
        # Track active export
        self.active_exports[request.export_id] = request

        try:
            # Get enabled configurations
            configs = self.config_manager.get_enabled_configs(request.customer_id)

            # Filter by requested destination if specified
            if request.destination:
                configs = [
                    c for c in configs if c.destination_type == request.destination
                ]

            if not configs:
                logger.warning(
                    f"No export configurations found for customer {request.customer_id}"
                )
                return []

            # Export to all configured destinations
            results = []
            tasks = []

            for config in configs:
                exporter = self._get_exporter(config)

                # Create export task with retry
                task = self.retry_policy.execute(
                    exporter.export_batch,
                    request.customer_id,
                    data,
                    {"export_id": request.export_id},
                )
                tasks.append(task)

            # Execute all exports concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            export_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Export failed for {configs[i].destination_type}: {result}"
                    )
                    export_results.append(
                        ExportResult(
                            export_id=request.export_id,
                            status=ExportStatus.FAILED,
                            destination=configs[i].destination_type,
                            error_message=str(result),
                        )
                    )
                else:
                    export_results.append(result)

            return export_results

        finally:
            # Remove from active exports
            self.active_exports.pop(request.export_id, None)

    async def trigger_export(
        self,
        customer_id: str,
        destination: Optional[ExportFormat] = None,
        date_range: Optional[Dict[str, str]] = None,
        include_historical: bool = False,
    ) -> ExportRequest:
        """Trigger a manual export for a customer."""
        request = ExportRequest(
            customer_id=customer_id,
            destination=destination,
            date_range=date_range,
            include_historical=include_historical,
        )

        # In a real implementation, this would fetch data from storage
        # and then call export_data. For now, we'll just return the request.
        logger.info(f"Export triggered: {request.export_id}")

        return request

    def get_active_exports(self) -> List[ExportRequest]:
        """Get list of currently active exports."""
        return list(self.active_exports.values())

    def cancel_export(self, export_id: str) -> bool:
        """Cancel an active export."""
        if export_id in self.active_exports:
            # In a real implementation, this would signal cancellation
            # to the running export tasks
            self.active_exports.pop(export_id)
            logger.info(f"Export cancelled: {export_id}")
            return True
        return False

    async def schedule_exports(self) -> None:
        """Run scheduled exports based on cron expressions."""
        # This would be called by a scheduler service
        # For each customer and configuration with a schedule,
        # check if it's time to run and trigger export
        pass

    def get_export_progress(self, export_id: str) -> Optional[ExportProgress]:
        """Get progress information for an active export.

        Args:
            export_id: Export identifier

        Returns:
            Export progress or None if not found
        """
        return self.export_progress.get(export_id)

    def update_export_progress(self, progress: ExportProgress) -> None:
        """Update progress information for an active export.

        Args:
            progress: Updated progress information
        """
        self.export_progress[progress.export_id] = progress

    def cleanup_export_progress(self, export_id: str) -> None:
        """Clean up progress information for completed export.

        Args:
            export_id: Export identifier
        """
        self.export_progress.pop(export_id, None)

    async def export_data_paginated(
        self,
        request: ExportRequest,
        data: Dict[str, List[Dict[str, Any]]],
        pagination_config: Optional[PaginationConfig] = None,
    ) -> List[ExportResult]:
        """Export data with pagination support for large datasets.

        Args:
            request: Export request
            data: Data to export
            pagination_config: Optional pagination configuration

        Returns:
            List of export results
        """
        # Use provided pagination config or default
        if pagination_config:
            request.pagination_config = pagination_config

        # Track active export with progress
        self.active_exports[request.export_id] = request

        # Initialize progress tracking
        total_records = sum(len(records) for records in data.values())
        progress = ExportProgress(
            export_id=request.export_id,
            current_records=0,
            total_records=total_records,
            current_batch=0,
            total_batches=len(data),
            memory_usage_mb=0.0,
            started_at=datetime.now(timezone.utc),
        )
        self.export_progress[request.export_id] = progress

        try:
            # Use the existing export_data method with progress tracking
            return await self.export_data(request, data)
        finally:
            # Clean up tracking
            self.active_exports.pop(request.export_id, None)
            self.export_progress.pop(request.export_id, None)
