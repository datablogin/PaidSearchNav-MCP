"""Script scheduling and monitoring system."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from croniter import croniter

from .base import ScriptBase, ScriptExecutor, ScriptResult, ScriptStatus
from .logging_utils import get_structured_logger, set_correlation_id

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Base exception for scheduler errors."""

    pass


class ScheduleNotFoundError(SchedulerError):
    """Raised when a schedule is not found."""

    pass


class ScheduleAlreadyExistsError(SchedulerError):
    """Raised when trying to add a duplicate schedule."""

    pass


class SchedulerNotRunningError(SchedulerError):
    """Raised when scheduler operations are attempted while not running."""

    pass


class ScriptExecutionError(SchedulerError):
    """Raised when script execution fails."""

    def __init__(
        self,
        message: str,
        script_id: str,
        schedule_id: str,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.script_id = script_id
        self.schedule_id = schedule_id
        self.original_error = original_error


class ScheduleStatus(Enum):
    """Schedule status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class ScriptExecution:
    """Record of a script execution."""

    execution_id: str
    script_id: str
    schedule_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: ScriptStatus
    result: Optional[ScriptResult]
    error: Optional[str]


@dataclass
class ScriptSchedule:
    """Schedule configuration for a script."""

    schedule_id: str
    script_id: str
    cron_expression: str
    description: str
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    execution_history: List[ScriptExecution] = field(default_factory=list)
    max_history: int = 100

    def __post_init__(self):
        if self.next_run is None and self.enabled:
            self.update_next_run()

    def update_next_run(self):
        """Update the next run time based on cron expression."""
        if not self.enabled:
            self.next_run = None
            return

        base_time = self.last_run or datetime.utcnow()
        cron = croniter(self.cron_expression, base_time)
        self.next_run = cron.get_next(datetime)

    def should_run(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the schedule should run now."""
        if not self.enabled or not self.next_run:
            return False

        current_time = current_time or datetime.utcnow()
        return current_time >= self.next_run

    def add_execution(self, execution: ScriptExecution):
        """Add an execution record to history."""
        self.execution_history.append(execution)

        # Maintain history limit
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history :]

        # Update last run time
        if execution.end_time:
            self.last_run = execution.end_time
            self.update_next_run()


class ScriptScheduler:
    """Manages script scheduling and execution."""

    # Resource limits
    MIN_WORKERS = 1
    MAX_WORKERS = 10
    DEFAULT_WORKERS = 4

    def __init__(self, executor: ScriptExecutor, max_workers: int = None):
        self.executor = executor
        self.schedules: Dict[str, ScriptSchedule] = {}
        self.running_executions: Dict[str, ScriptExecution] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self.logger = get_structured_logger(f"{__name__}.{self.__class__.__name__}")

        # Validate and set max_workers
        if max_workers is None:
            max_workers = self.DEFAULT_WORKERS

        if not isinstance(max_workers, int):
            raise ValueError(f"max_workers must be an integer, got {type(max_workers)}")

        if max_workers < self.MIN_WORKERS:
            self.logger.warning(
                f"max_workers ({max_workers}) is below minimum ({self.MIN_WORKERS}), using minimum"
            )
            max_workers = self.MIN_WORKERS
        elif max_workers > self.MAX_WORKERS:
            self.logger.warning(
                f"max_workers ({max_workers}) exceeds maximum ({self.MAX_WORKERS}), using maximum"
            )
            max_workers = self.MAX_WORKERS

        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.logger.info(f"Initialized scheduler with {max_workers} worker threads")

    def add_schedule(
        self, script: ScriptBase, cron_expression: str, description: str
    ) -> str:
        """Add a script to the scheduler."""
        # Register script with executor
        script_id = self.executor.register_script(script)

        # Create schedule
        schedule_id = f"schedule_{script_id}_{datetime.utcnow().timestamp()}"
        schedule = ScriptSchedule(
            schedule_id=schedule_id,
            script_id=script_id,
            cron_expression=cron_expression,
            description=description,
        )

        self.schedules[schedule_id] = schedule
        self.logger.info(f"Added schedule {schedule_id} for script {script_id}")

        return schedule_id

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule."""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            self.logger.info(f"Removed schedule {schedule_id}")
            return True
        return False

    def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule."""
        if schedule_id in self.schedules:
            self.schedules[schedule_id].enabled = False
            self.schedules[schedule_id].next_run = None
            self.logger.info(f"Paused schedule {schedule_id}")
            return True
        return False

    def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule."""
        if schedule_id in self.schedules:
            self.schedules[schedule_id].enabled = True
            self.schedules[schedule_id].update_next_run()
            self.logger.info(f"Resumed schedule {schedule_id}")
            return True
        return False

    async def start(self):
        """Start the scheduler."""
        if self._running:
            self.logger.warning("Scheduler is already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        self.logger.info("Scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # Wait for running executions to complete
        if self.running_executions:
            self.logger.info(
                f"Waiting for {len(self.running_executions)} executions to complete"
            )
            await asyncio.sleep(5)  # Give executions time to complete

        self.thread_pool.shutdown(wait=True)
        self.logger.info("Scheduler stopped")

    async def _run_scheduler(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Check schedules
                current_time = datetime.utcnow()

                for schedule in list(self.schedules.values()):
                    if schedule.should_run(current_time):
                        # Run in thread pool to avoid blocking
                        asyncio.create_task(self._execute_scheduled_script(schedule))

                # Sleep for a short interval
                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                # Allow cancellation to propagate
                raise
            except SchedulerError as e:
                self.logger.error(f"Scheduler error: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on scheduler errors
            except Exception as e:
                self.logger.critical(
                    f"Unexpected scheduler error: {str(e)}", exc_info=True
                )
                # For critical errors, consider stopping the scheduler
                if not self._running:
                    break
                await asyncio.sleep(120)  # Wait even longer for unexpected errors

    async def _execute_scheduled_script(self, schedule: ScriptSchedule):
        """Execute a scheduled script."""
        execution_id = f"exec_{schedule.schedule_id}_{datetime.utcnow().timestamp()}"

        # Set correlation ID for this execution
        correlation_id = set_correlation_id()

        execution = ScriptExecution(
            execution_id=execution_id,
            script_id=schedule.script_id,
            schedule_id=schedule.schedule_id,
            start_time=datetime.utcnow(),
            end_time=None,
            status=ScriptStatus.RUNNING,
            result=None,
            error=None,
        )

        self.running_executions[execution_id] = execution

        try:
            self.logger.info(
                "Starting scheduled script execution",
                extra={
                    "execution_id": execution_id,
                    "schedule_id": schedule.schedule_id,
                    "script_id": schedule.script_id,
                    "cron_expression": schedule.cron_expression,
                },
            )

            # Execute script in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.thread_pool, self.executor.execute_script, schedule.script_id
            )

            execution.status = ScriptStatus(result["status"])
            execution.result = result

        except asyncio.CancelledError:
            # Handle cancellation gracefully
            self.logger.warning(f"Execution {execution_id} was cancelled")
            execution.status = ScriptStatus.CANCELLED
            execution.error = "Execution cancelled"
            raise
        except ScriptExecutionError as e:
            self.logger.error(
                f"Script execution failed for {execution_id}: {str(e)}",
                extra={"script_id": e.script_id, "schedule_id": e.schedule_id},
            )
            execution.status = ScriptStatus.FAILED
            execution.error = str(e)
        except Exception as e:
            # Wrap unexpected errors
            error = ScriptExecutionError(
                f"Unexpected error during execution: {str(e)}",
                script_id=schedule.script_id,
                schedule_id=schedule.schedule_id,
                original_error=e,
            )
            self.logger.error(
                f"Execution {execution_id} failed with unexpected error", exc_info=True
            )
            execution.status = ScriptStatus.FAILED
            execution.error = str(error)

        finally:
            execution.end_time = datetime.utcnow()
            schedule.add_execution(execution)
            del self.running_executions[execution_id]

            self.logger.info(
                f"Completed execution {execution_id} with status {execution.status.value}"
            )

    def get_schedule_status(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a schedule."""
        if schedule_id not in self.schedules:
            return None

        schedule = self.schedules[schedule_id]

        # Get recent executions
        recent_executions = []
        for exec in schedule.execution_history[-10:]:  # Last 10
            recent_executions.append(
                {
                    "execution_id": exec.execution_id,
                    "start_time": exec.start_time.isoformat(),
                    "end_time": exec.end_time.isoformat() if exec.end_time else None,
                    "status": exec.status.value,
                    "error": exec.error,
                }
            )

        return {
            "schedule_id": schedule.schedule_id,
            "script_id": schedule.script_id,
            "cron_expression": schedule.cron_expression,
            "description": schedule.description,
            "enabled": schedule.enabled,
            "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
            "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
            "total_executions": len(schedule.execution_history),
            "recent_executions": recent_executions,
        }

    def get_all_schedules(self) -> List[Dict[str, Any]]:
        """Get status of all schedules."""
        return [self.get_schedule_status(schedule_id) for schedule_id in self.schedules]

    def get_running_executions(self) -> List[Dict[str, Any]]:
        """Get currently running executions."""
        executions = []

        for exec in self.running_executions.values():
            executions.append(
                {
                    "execution_id": exec.execution_id,
                    "script_id": exec.script_id,
                    "schedule_id": exec.schedule_id,
                    "start_time": exec.start_time.isoformat(),
                    "duration": (datetime.utcnow() - exec.start_time).total_seconds(),
                }
            )

        return executions


class ScriptMonitor:
    """Monitors script performance and health."""

    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.logger = get_structured_logger(f"{__name__}.{self.__class__.__name__}")

    def record_execution(self, script_id: str, execution: ScriptExecution):
        """Record execution metrics."""
        if script_id not in self.metrics:
            self.metrics[script_id] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "total_duration": 0,
                "total_rows_processed": 0,
                "total_changes_made": 0,
                "last_execution": None,
                "error_rate": 0.0,
                "avg_duration": 0.0,
            }

        metrics = self.metrics[script_id]
        metrics["total_executions"] += 1

        if execution.status == ScriptStatus.COMPLETED:
            metrics["successful_executions"] += 1
        else:
            metrics["failed_executions"] += 1

        if execution.end_time and execution.start_time:
            duration = (execution.end_time - execution.start_time).total_seconds()
            metrics["total_duration"] += duration
            metrics["avg_duration"] = (
                metrics["total_duration"] / metrics["total_executions"]
            )

        if execution.result:
            metrics["total_rows_processed"] += execution.result.get("rows_processed", 0)
            metrics["total_changes_made"] += execution.result.get("changes_made", 0)

        metrics["last_execution"] = execution.end_time
        metrics["error_rate"] = (
            metrics["failed_executions"] / metrics["total_executions"]
        )

        # Check for alerts
        self._check_alerts(script_id, execution)

    def _check_alerts(self, script_id: str, execution: ScriptExecution):
        """Check for alert conditions."""
        metrics = self.metrics[script_id]

        # High error rate alert
        if metrics["error_rate"] > 0.5 and metrics["total_executions"] > 5:
            self.alerts.append(
                {
                    "type": "high_error_rate",
                    "script_id": script_id,
                    "message": f"Script {script_id} has error rate of {metrics['error_rate']:.1%}",
                    "timestamp": datetime.utcnow(),
                    "severity": "high",
                }
            )

        # Long execution time alert
        if execution.end_time and execution.start_time:
            duration = (execution.end_time - execution.start_time).total_seconds()
            if duration > 300:  # 5 minutes
                self.alerts.append(
                    {
                        "type": "long_execution",
                        "script_id": script_id,
                        "message": f"Script {script_id} took {duration:.1f} seconds to execute",
                        "timestamp": datetime.utcnow(),
                        "severity": "medium",
                    }
                )

        # No changes made alert (for scripts that should make changes)
        if execution.result and execution.result.get("changes_made", 0) == 0:
            if script_id.startswith("negative_keyword_"):
                self.alerts.append(
                    {
                        "type": "no_changes",
                        "script_id": script_id,
                        "message": f"Script {script_id} made no changes",
                        "timestamp": datetime.utcnow(),
                        "severity": "low",
                    }
                )

    def get_metrics(self, script_id: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for scripts."""
        if script_id:
            return self.metrics.get(script_id, {})
        return self.metrics

    def get_alerts(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get alerts, optionally filtered by severity."""
        if severity:
            return [a for a in self.alerts if a["severity"] == severity]
        return self.alerts

    def clear_alerts(self, older_than: Optional[timedelta] = None):
        """Clear old alerts."""
        if older_than:
            cutoff = datetime.utcnow() - older_than
            self.alerts = [a for a in self.alerts if a["timestamp"] > cutoff]
        else:
            self.alerts = []
