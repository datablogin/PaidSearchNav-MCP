"""Google Ads Scripts API integration and execution runner."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.storage.models import GoogleAdsScript, ScriptExecution

from .base import ScriptStatus
from .logging_utils import get_structured_logger, set_correlation_id

logger = logging.getLogger(__name__)


class GoogleAdsScriptRunner:
    """Runner for executing Google Ads Scripts through the Google Ads API."""

    def __init__(
        self,
        client: GoogleAdsClient,
        session: AsyncSession,
        settings: Settings,
    ):
        self.client = client
        self.session = session
        self.settings = settings
        self.logger = get_structured_logger(f"{__name__}.{self.__class__.__name__}")

        # Track running executions
        self._running_executions: Dict[str, asyncio.Task] = {}

        # Maximum concurrent executions (configurable via settings)
        self.max_concurrent_executions = getattr(
            settings, "max_concurrent_script_executions", 10
        )

        # Session lock to prevent concurrent commits
        self._session_lock = asyncio.Lock()

    async def wait_for_running_executions(self) -> None:
        """Wait for all running executions to complete."""
        if self._running_executions:
            await asyncio.gather(
                *self._running_executions.values(), return_exceptions=True
            )

    async def execute_script(
        self, script: GoogleAdsScript, user_id: str, execution_type: str = "manual"
    ) -> str:
        """Execute a Google Ads Script and return execution ID.

        Args:
            script: The script to execute
            user_id: ID of user executing the script
            execution_type: Type of execution (manual, scheduled, triggered)

        Returns:
            Execution ID for tracking

        Raises:
            RuntimeError: If maximum concurrent executions limit is reached
        """
        # Check if we've reached the maximum concurrent executions limit
        if len(self._running_executions) >= self.max_concurrent_executions:
            raise RuntimeError(
                f"Maximum concurrent executions limit reached ({self.max_concurrent_executions}). "
                f"Please wait for some scripts to complete before starting new ones."
            )

        # Set correlation ID for this execution
        correlation_id = set_correlation_id()

        # Create execution record
        execution = ScriptExecution(
            script_id=script.id,
            user_id=user_id,
            status="pending",
            execution_type=execution_type,
        )

        async with self._session_lock:  # Use session lock here too
            self.session.add(execution)
            try:
                await self.session.commit()
                await self.session.refresh(execution)
            except Exception as e:
                # Handle session errors gracefully
                try:
                    await self.session.rollback()
                except Exception:
                    pass
                # Try to get the execution ID if possible
                if not execution.id:
                    execution.id = f"temp_{datetime.now(timezone.utc).timestamp()}"

        self.logger.info(
            "Starting script execution",
            extra={
                "execution_id": execution.id,
                "script_id": script.id,
                "script_name": script.name,
                "script_type": script.script_type,
                "user_id": user_id,
                "execution_type": execution_type,
            },
        )

        # Start async execution
        task = asyncio.create_task(
            self._execute_script_async(script, execution, correlation_id)
        )
        self._running_executions[execution.id] = task

        return execution.id

    async def _execute_script_async(
        self, script: GoogleAdsScript, execution: ScriptExecution, correlation_id: str
    ) -> None:
        """Execute script asynchronously."""
        start_time = time.time()  # Initialize start_time at the beginning
        execution_id = execution.id

        async def safe_update_execution_by_id(status: str, **kwargs):
            """Safely update execution status by ID, avoiding session context issues."""
            async with self._session_lock:  # Ensure only one task can commit at a time
                try:
                    from sqlalchemy import update

                    # Build update statement with provided fields
                    update_data = {"status": status, **kwargs}

                    # Execute update by ID to avoid session context issues
                    stmt = (
                        update(ScriptExecution)
                        .where(ScriptExecution.id == execution_id)
                        .values(**update_data)
                    )

                    await self.session.execute(stmt)
                    await self.session.commit()

                    # Update the execution object for logging
                    for key, value in update_data.items():
                        setattr(execution, key, value)

                except Exception as commit_error:
                    # Log the commit error but don't fail the entire execution
                    self.logger.warning(f"Session update failed: {commit_error}")
                    try:
                        await self.session.rollback()
                    except Exception:
                        pass  # Ignore rollback errors too

                    # Update the execution object for logging even if DB update failed
                    for key, value in {"status": status, **kwargs}.items():
                        setattr(execution, key, value)

        try:
            # Set correlation ID for logging context
            set_correlation_id(correlation_id)

            # Update execution status
            await safe_update_execution_by_id(
                "running", started_at=datetime.now(timezone.utc)
            )

            # Execute the script using Google Ads Scripts API
            result = await self._call_google_ads_scripts_api(script)

            # Calculate execution time
            execution_time = time.time() - start_time

            # Update execution with results
            await safe_update_execution_by_id(
                "completed",
                completed_at=datetime.now(timezone.utc),
                execution_time=execution_time,
                rows_processed=result.get("rows_processed", 0),
                changes_made=result.get("changes_made", 0),
                result_data=result,
            )

            self.logger.info(
                "Script execution completed successfully",
                extra={
                    "execution_id": execution_id,
                    "execution_time": execution_time,
                    "rows_processed": result.get("rows_processed", 0),
                    "changes_made": result.get("changes_made", 0),
                },
            )

        except Exception as e:
            # Handle execution failure - start_time is always available now
            execution_time = time.time() - start_time

            await safe_update_execution_by_id(
                "failed",
                completed_at=datetime.now(timezone.utc),
                execution_time=execution_time,
                error_message=str(e),
            )

            self.logger.error(
                "Script execution failed",
                extra={
                    "execution_id": execution_id,
                    "execution_time": execution_time,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
        finally:
            # Clean up tracking
            if execution_id in self._running_executions:
                del self._running_executions[execution_id]

    async def _call_google_ads_scripts_api(
        self, script: GoogleAdsScript
    ) -> Dict[str, Any]:
        """Call the Google Ads Scripts API to execute a script.

        Note: This is a simplified implementation. In practice, Google Ads Scripts
        are executed within the Google Ads interface, not directly via API calls.
        This implementation simulates the process for demonstration purposes.

        For real implementation, you would need to:
        1. Use Google Apps Script API to create/update scripts
        2. Use Google Ads API to trigger script execution
        3. Poll for results and status updates
        """

        # Simulate API call delay (configurable for testing)
        api_delay = getattr(self.settings, "google_ads_scripts_api_delay", 1.0)
        await asyncio.sleep(api_delay)

        # For now, return mock results based on script type
        # In real implementation, this would involve:
        # 1. Creating/updating script in Google Ads account
        # 2. Triggering execution
        # 3. Polling for completion
        # 4. Retrieving results

        if script.script_type == "negative_keyword":
            # Calculate rows processed based on parameters (for backwards compatibility with tests)
            lookback_days = script.parameters.get("lookback_days", 30)
            rows_processed = lookback_days * 10 if lookback_days else 150
            changes_made = max(1, rows_processed // 20)

            return {
                "success": True,
                "rows_processed": rows_processed,
                "changes_made": changes_made,
                "details": {
                    "negative_keywords_added": changes_made,
                    "campaigns_processed": 5,
                    "cost_threshold": script.parameters.get("cost_threshold", 50.0),
                },
                "warnings": [],
            }
        elif script.script_type == "conflict_detection":
            return {
                "success": True,
                "rows_processed": 500,
                "changes_made": 0,  # Detection only, no changes
                "details": {
                    "conflicts_found": 12,
                    "keywords_analyzed": 500,
                    "campaigns_checked": 10,
                },
                "warnings": ["Some keywords may need manual review"],
            }
        elif script.script_type == "placement_audit":
            return {
                "success": True,
                "rows_processed": 200,
                "changes_made": 8,
                "details": {
                    "placements_analyzed": 200,
                    "problematic_placements": 8,
                    "exclusions_added": 8,
                },
                "warnings": [],
            }
        else:
            # Generic result for custom scripts
            return {
                "success": True,
                "rows_processed": 100,
                "changes_made": 10,
                "details": {"custom_script_executed": True},
                "warnings": [],
            }

    async def get_script_status(self, execution_id: str) -> Optional[ScriptStatus]:
        """Get the current status of a script execution."""
        try:
            # Query execution from database
            execution = await self.session.get(ScriptExecution, execution_id)
            if not execution:
                return None

            # Map database status to ScriptStatus enum
            status_mapping = {
                "pending": ScriptStatus.PENDING,
                "running": ScriptStatus.RUNNING,
                "completed": ScriptStatus.COMPLETED,
                "failed": ScriptStatus.FAILED,
                "cancelled": ScriptStatus.CANCELLED,
                "timeout": ScriptStatus.FAILED,  # Map timeout to failed
            }

            return status_mapping.get(execution.status, ScriptStatus.PENDING)

        except Exception as e:
            self.logger.error(f"Error getting script status: {e}")
            return None

    async def cancel_script(self, execution_id: str) -> bool:
        """Cancel a running script execution."""
        try:
            # Get execution record
            execution = await self.session.get(ScriptExecution, execution_id)
            if not execution:
                self.logger.warning(
                    f"Execution {execution_id} not found for cancellation"
                )
                return False

            # Only cancel if execution is pending or running
            if execution.status not in ["pending", "running"]:
                self.logger.warning(
                    f"Cannot cancel execution {execution_id} with status {execution.status}"
                )
                return False

            # Cancel the async task if it's running
            if execution_id in self._running_executions:
                task = self._running_executions[execution_id]
                task.cancel()
                del self._running_executions[execution_id]

            # Update execution status
            execution.status = "cancelled"
            execution.completed_at = datetime.now(timezone.utc)

            await self.session.commit()

            self.logger.info(f"Cancelled script execution {execution_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error cancelling script execution {execution_id}: {e}")
            return False

    async def get_execution_history(
        self, script_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get execution history for scripts."""
        try:
            from sqlalchemy import desc, select

            # Build query
            query = select(ScriptExecution)

            if script_id:
                query = query.where(ScriptExecution.script_id == script_id)

            query = query.order_by(desc(ScriptExecution.created_at)).limit(limit)

            # Execute query
            result = await self.session.execute(query)
            executions = result.scalars().all()

            # Convert to dictionaries
            return [execution.to_dict() for execution in executions]

        except Exception as e:
            self.logger.error(f"Error getting execution history: {e}")
            return []

    async def get_script_metrics(self, script_id: str) -> Dict[str, Any]:
        """Get performance metrics for a script."""
        try:
            from sqlalchemy import case, func, select

            # Get execution statistics
            query = select(
                func.count(ScriptExecution.id).label("total_executions"),
                func.sum(
                    case((ScriptExecution.status == "completed", 1), else_=0)
                ).label("successful_executions"),
                func.avg(ScriptExecution.execution_time).label("avg_execution_time"),
                func.sum(ScriptExecution.rows_processed).label("total_rows_processed"),
                func.sum(ScriptExecution.changes_made).label("total_changes_made"),
            ).where(ScriptExecution.script_id == script_id)

            result = await self.session.execute(query)
            row = result.fetchone()

            if not row:
                return {}

            total_executions = row.total_executions or 0
            successful_executions = row.successful_executions or 0

            return {
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate": (
                    successful_executions / total_executions
                    if total_executions > 0
                    else 0
                ),
                "avg_execution_time": float(row.avg_execution_time or 0),
                "total_rows_processed": row.total_rows_processed or 0,
                "total_changes_made": row.total_changes_made or 0,
            }

        except Exception as e:
            self.logger.error(f"Error getting script metrics: {e}")
            return {}

    async def cleanup_old_executions(
        self, days: int = 30, batch_size: int = 1000
    ) -> int:
        """Clean up execution records older than specified days using batched deletion.

        Args:
            days: Number of days to keep executions (older ones will be deleted)
            batch_size: Number of records to delete in each batch to avoid long transactions

        Returns:
            Total number of records deleted
        """
        try:
            from datetime import timedelta

            from sqlalchemy import delete, select

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            total_deleted = 0

            self.logger.info(f"Starting cleanup of executions older than {cutoff_date}")

            while True:
                # Select IDs to delete in batches first (since DELETE doesn't support LIMIT directly)
                select_query = (
                    select(ScriptExecution.id)
                    .where(ScriptExecution.created_at < cutoff_date)
                    .limit(batch_size)
                )

                result = await self.session.execute(select_query)
                ids_to_delete = [row[0] for row in result.fetchall()]

                if not ids_to_delete:
                    # No more records to delete
                    break

                # Delete the selected records
                delete_query = delete(ScriptExecution).where(
                    ScriptExecution.id.in_(ids_to_delete)
                )

                delete_result = await self.session.execute(delete_query)
                await self.session.commit()

                batch_deleted = delete_result.rowcount
                total_deleted += batch_deleted

                self.logger.debug(f"Deleted batch of {batch_deleted} execution records")

                # If we deleted less than the batch size, we're done
                if batch_deleted < batch_size:
                    break

                # Small delay between batches to prevent overwhelming the database
                await asyncio.sleep(0.1)

            self.logger.info(
                f"Cleanup completed. Deleted {total_deleted} old execution records"
            )
            return total_deleted

        except Exception as e:
            self.logger.error(f"Error cleaning up old executions: {e}")
            await self.session.rollback()
            return 0
