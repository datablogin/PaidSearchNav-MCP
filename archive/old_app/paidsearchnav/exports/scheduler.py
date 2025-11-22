"""Export scheduling functionality."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from croniter import croniter

if TYPE_CHECKING:
    from ..storage.repository import AnalysisRepository
from .base import ExportFormat, ExportRequest
from .manager import ExportManager

logger = logging.getLogger(__name__)


class ExportScheduler:
    """Manages scheduled exports based on cron expressions."""

    def __init__(
        self,
        export_manager: ExportManager,
        repository: Optional["AnalysisRepository"] = None,
        check_interval: int = 60,  # Check every minute
    ):
        """Initialize export scheduler."""
        self.export_manager = export_manager
        self.repository = repository
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Dict[str, datetime] = {}

    async def start(self) -> None:
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Export scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Export scheduler stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self.running:
            try:
                await self._check_schedules()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_schedules(self) -> None:
        """Check all schedules and trigger exports as needed."""
        # Get all customers with export configurations
        customers = await self._get_customers_with_exports()

        for customer_id in customers:
            configs = self.export_manager.config_manager.get_enabled_configs(
                customer_id
            )

            for config in configs:
                if not config.schedule:
                    continue

                # Check if it's time to run this export
                schedule_key = (
                    f"{customer_id}:{config.destination_type}:{config.schedule}"
                )

                if self._should_run_now(config.schedule, schedule_key):
                    await self._trigger_scheduled_export(
                        customer_id, config.destination_type
                    )
                    self._last_run[schedule_key] = datetime.utcnow()

    def _should_run_now(self, cron_expression: str, schedule_key: str) -> bool:
        """Check if a schedule should run now."""
        try:
            cron = croniter(cron_expression, datetime.utcnow())
            next_run = cron.get_prev(datetime)

            # Check if we've already run this schedule
            last_run = self._last_run.get(schedule_key)
            if last_run and last_run >= next_run:
                return False

            # Check if the next run time is within our check interval
            time_diff = (datetime.utcnow() - next_run).total_seconds()
            return 0 <= time_diff <= self.check_interval

        except Exception as e:
            logger.error(f"Error parsing cron expression '{cron_expression}': {e}")
            return False

    async def _trigger_scheduled_export(
        self, customer_id: str, destination: ExportFormat
    ) -> None:
        """Trigger a scheduled export."""
        try:
            logger.info(
                f"Triggering scheduled export for {customer_id} to {destination}"
            )

            # Get data to export
            data = await self._get_export_data(customer_id)

            if not data:
                logger.warning(f"No data to export for {customer_id}")
                return

            # Create export request
            request = ExportRequest(
                customer_id=customer_id,
                destination=destination,
                include_historical=False,  # Scheduled exports are incremental
            )

            # Trigger export
            results = await self.export_manager.export_data(request, data)

            # Log results
            for result in results:
                if result.error_message:
                    logger.error(
                        f"Scheduled export failed for {customer_id} to {destination}: "
                        f"{result.error_message}"
                    )
                else:
                    logger.info(
                        f"Scheduled export completed for {customer_id} to {destination}: "
                        f"{result.records_exported} records exported"
                    )

        except Exception as e:
            logger.error(f"Error in scheduled export for {customer_id}: {e}")

    async def _get_customers_with_exports(self) -> List[str]:
        """Get list of customers with export configurations."""
        # In a real implementation, this would query the database
        # For now, return customers from config
        all_configs = self.export_manager.config_manager.configs
        return list(all_configs.keys())

    async def _get_export_data(
        self, customer_id: str, since: Optional[datetime] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get data to export for a customer."""
        # Default to last 24 hours if not specified
        if not since:
            since = datetime.utcnow() - timedelta(hours=24)

        # Fetch data from repository
        data = {"audit_results": [], "recommendations": [], "metrics": []}

        # Get recent analysis results
        # Note: This is a simplified approach - in production you'd need
        # proper methods to fetch analysis results by date range
        audits = []  # Placeholder for actual implementation

        for audit in audits:
            # Convert audit to export format
            audit_data = {
                "audit_id": audit.id,
                "audit_date": audit.created_at.date().isoformat(),
                "analyzer_name": audit.analyzer_name,
                "keywords_analyzed": audit.keywords_analyzed,
                "issues_found": audit.issues_found,
                "cost_savings": audit.cost_savings,
                "created_at": audit.created_at.isoformat(),
                "updated_at": audit.updated_at.isoformat()
                if audit.updated_at
                else None,
            }
            data["audit_results"].append(audit_data)

            # Get recommendations for this audit
            if audit.recommendations:
                for rec in audit.recommendations:
                    rec_data = {
                        "recommendation_id": rec.id,
                        "audit_id": audit.id,
                        "type": rec.type,
                        "priority": rec.priority,
                        "title": rec.title,
                        "description": rec.description,
                        "estimated_impact": rec.estimated_impact,
                        "metadata": rec.metadata,
                        "created_at": rec.created_at.isoformat(),
                    }
                    data["recommendations"].append(rec_data)

        # Get metrics (simplified for now)
        data["metrics"] = [
            {
                "metric_name": "audits_completed",
                "metric_value": len(audits),
                "metric_type": "count",
                "dimensions": {"customer_id": customer_id},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        return data
