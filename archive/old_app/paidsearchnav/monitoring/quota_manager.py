"""Advanced API quota monitoring and management system."""

import asyncio
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class QuotaExhaustionError(Exception):
    """Raised when API quota is exhausted."""

    def __init__(self, message: str, quota_type: str, usage: int, limit: int):
        self.quota_type = quota_type
        self.usage = usage
        self.limit = limit
        super().__init__(message)


class QuotaAlert:
    """Represents a quota alert."""

    def __init__(
        self, alert_type: str, message: str, severity: str, timestamp: datetime
    ):
        self.alert_type = alert_type
        self.message = message
        self.severity = severity  # 'warning', 'critical'
        self.timestamp = timestamp


class AdvancedQuotaManager:
    """Advanced quota manager with monitoring and predictive analysis."""

    def __init__(
        self,
        daily_quota_limit: int = 50000,
        rate_limit_per_minute: int = 500,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95,
        enable_predictive_analysis: bool = True,
    ):
        """Initialize advanced quota manager.

        Args:
            daily_quota_limit: Daily API quota limit
            rate_limit_per_minute: Rate limit per minute
            warning_threshold: Threshold for warning alerts (0.0 to 1.0)
            critical_threshold: Threshold for critical alerts (0.0 to 1.0)
            enable_predictive_analysis: Enable predictive quota usage analysis
        """
        self.daily_quota_limit = daily_quota_limit
        self.rate_limit_per_minute = rate_limit_per_minute
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.enable_predictive_analysis = enable_predictive_analysis

        # Thread-safe quota tracking
        self._lock = threading.Lock()
        self._quota_usage = 0
        self._last_reset = datetime.now().date()

        # Minute-based rate limiting
        self._minute_usage = 0
        self._minute_start = datetime.now().replace(second=0, microsecond=0)

        # Usage history for predictive analysis (last 24 hours)
        self._usage_history = deque(maxlen=1440)  # 24 hours * 60 minutes

        # Alert system
        self._alerts: List[QuotaAlert] = []
        self._last_alert_check = datetime.now()

        # Analyzer-specific usage tracking
        self._analyzer_usage = defaultdict(int)
        self._analyzer_timing = defaultdict(list)  # Track execution times

        # Queue for pending analyzer executions when quota is low
        self._execution_queue = asyncio.Queue()
        self._queue_processor_task: Optional[asyncio.Task] = None

    async def check_quota_availability(
        self, estimated_calls: int, analyzer_name: str, priority: str = "normal"
    ) -> bool:
        """Check if quota is available for estimated calls with analyzer context.

        Args:
            estimated_calls: Estimated number of API calls needed
            analyzer_name: Name of the analyzer requesting quota
            priority: Priority level ('low', 'normal', 'high', 'critical')

        Returns:
            True if quota is available, False otherwise
        """
        with self._lock:
            await self._reset_if_needed()

            # Check daily quota
            projected_usage = self._quota_usage + estimated_calls
            if projected_usage > self.daily_quota_limit:
                await self._create_alert(
                    "quota_exhaustion",
                    f"Daily quota would be exceeded: {projected_usage}/{self.daily_quota_limit} for {analyzer_name}",
                    "critical",
                )

                # Allow critical priority even if over quota
                if (
                    priority == "critical"
                    and projected_usage <= self.daily_quota_limit * 1.05
                ):
                    logger.warning(
                        f"Allowing critical analyzer {analyzer_name} to exceed quota slightly"
                    )
                    return True

                return False

            # Check per-minute rate limit
            minute_projected = self._minute_usage + estimated_calls
            if minute_projected > self.rate_limit_per_minute:
                await self._create_alert(
                    "rate_limit",
                    f"Rate limit would be exceeded: {minute_projected}/{self.rate_limit_per_minute} for {analyzer_name}",
                    "warning",
                )
                return False

            # Check if we're approaching thresholds
            daily_percentage = projected_usage / self.daily_quota_limit

            if daily_percentage >= self.critical_threshold:
                await self._create_alert(
                    "quota_critical",
                    f"Quota usage critical: {daily_percentage:.1%} for {analyzer_name}",
                    "critical",
                )
            elif daily_percentage >= self.warning_threshold:
                await self._create_alert(
                    "quota_warning",
                    f"Quota usage high: {daily_percentage:.1%} for {analyzer_name}",
                    "warning",
                )

            return True

    async def reserve_quota(self, calls_used: int, analyzer_name: str) -> None:
        """Reserve quota for API calls with analyzer tracking.

        Args:
            calls_used: Number of API calls used
            analyzer_name: Name of the analyzer that used the quota
        """
        with self._lock:
            await self._reset_if_needed()

            self._quota_usage += calls_used
            self._minute_usage += calls_used

            # Track per-analyzer usage
            self._analyzer_usage[analyzer_name] += calls_used

            # Record usage in history for predictive analysis
            current_minute = datetime.now().replace(second=0, microsecond=0)
            self._usage_history.append(
                {
                    "timestamp": current_minute,
                    "calls": calls_used,
                    "analyzer": analyzer_name,
                }
            )

            logger.debug(
                f"Quota reserved for {analyzer_name}: {calls_used} calls. "
                f"Daily: {self._quota_usage}/{self.daily_quota_limit}, "
                f"Minute: {self._minute_usage}/{self.rate_limit_per_minute}"
            )

    async def predict_quota_exhaustion(self) -> Optional[datetime]:
        """Predict when quota will be exhausted based on usage patterns.

        Returns:
            Predicted exhaustion time or None if within limits
        """
        if not self.enable_predictive_analysis or len(self._usage_history) < 10:
            return None

        with self._lock:
            # Calculate recent usage rate (calls per minute)
            recent_history = list(self._usage_history)[-60:]  # Last hour
            if len(recent_history) < 5:
                return None

            total_calls = sum(entry["calls"] for entry in recent_history)
            time_span_minutes = len(recent_history)
            calls_per_minute = total_calls / time_span_minutes

            # Calculate remaining quota and estimated time to exhaustion
            remaining_quota = self.daily_quota_limit - self._quota_usage

            if calls_per_minute > 0:
                minutes_to_exhaustion = remaining_quota / calls_per_minute

                # Only predict if exhaustion is within next 4 hours
                if minutes_to_exhaustion <= 240:  # 4 hours
                    return datetime.now() + timedelta(minutes=minutes_to_exhaustion)

            return None

    async def get_analyzer_efficiency_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get efficiency metrics for each analyzer.

        Returns:
            Dictionary with analyzer efficiency data
        """
        with self._lock:
            metrics = {}

            for analyzer, usage in self._analyzer_usage.items():
                timing_data = self._analyzer_timing.get(analyzer, [])

                metrics[analyzer] = {
                    "total_quota_used": usage,
                    "quota_percentage": (usage / self.daily_quota_limit) * 100,
                    "average_execution_time": (
                        sum(timing_data) / len(timing_data) if timing_data else 0
                    ),
                    "execution_count": len(timing_data),
                    "efficiency_score": self._calculate_efficiency_score(
                        analyzer, usage, timing_data
                    ),
                }

            return metrics

    def _calculate_efficiency_score(
        self, analyzer: str, quota_used: int, timing_data: List[float]
    ) -> float:
        """Calculate efficiency score for an analyzer (0-100).

        Args:
            analyzer: Analyzer name
            quota_used: Total quota used by analyzer
            timing_data: List of execution times

        Returns:
            Efficiency score from 0 (poor) to 100 (excellent)
        """
        if not timing_data or quota_used == 0:
            return 0.0

        # Base score
        score = 50.0

        # Factor 1: Quota efficiency (lower usage per execution is better)
        avg_quota_per_execution = quota_used / len(timing_data)
        if avg_quota_per_execution < 20:  # Very efficient
            score += 25
        elif avg_quota_per_execution < 50:  # Good
            score += 15
        elif avg_quota_per_execution > 100:  # Poor efficiency
            score -= 20

        # Factor 2: Execution time consistency (lower variance is better)
        if len(timing_data) > 1:
            avg_time = sum(timing_data) / len(timing_data)
            variance = sum((t - avg_time) ** 2 for t in timing_data) / len(timing_data)
            if variance < 10:  # Very consistent
                score += 15
            elif variance > 50:  # Inconsistent
                score -= 15

        # Factor 3: Speed (faster is better)
        avg_time = sum(timing_data) / len(timing_data)
        if avg_time < 30:  # Very fast
            score += 10
        elif avg_time > 120:  # Slow
            score -= 10

        return max(0.0, min(100.0, score))

    async def _reset_if_needed(self) -> None:
        """Reset quota counters if needed."""
        now = datetime.now()

        # Reset daily quota
        if now.date() > self._last_reset:
            old_usage = self._quota_usage
            self._quota_usage = 0
            self._last_reset = now.date()
            self._analyzer_usage.clear()
            logger.info(
                f"Daily quota reset. Previous day usage: {old_usage}/{self.daily_quota_limit}"
            )

        # Reset minute quota (with race condition protection)
        current_minute = now.replace(second=0, microsecond=0)
        if current_minute > self._minute_start:
            # Only reset if we haven't already reset for this minute
            # This prevents race conditions during minute boundaries
            old_usage = self._minute_usage
            self._minute_usage = 0
            self._minute_start = current_minute

            if old_usage > 0:
                logger.debug(
                    f"Minute quota reset at {current_minute}. Previous minute usage: {old_usage}"
                )

    async def _create_alert(self, alert_type: str, message: str, severity: str) -> None:
        """Create a quota alert.

        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Alert severity level
        """
        alert = QuotaAlert(alert_type, message, severity, datetime.now())
        self._alerts.append(alert)

        # Keep only last 100 alerts
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

        # Log alert
        log_method = logger.critical if severity == "critical" else logger.warning
        log_method(f"Quota Alert [{severity.upper()}]: {message}")

    async def get_quota_status(self) -> Dict[str, Any]:
        """Get comprehensive quota status.

        Returns:
            Dictionary with detailed quota status
        """
        with self._lock:
            await self._reset_if_needed()

            # Get prediction
            predicted_exhaustion = await self.predict_quota_exhaustion()

            # Get recent alerts
            recent_alerts = [
                {
                    "type": alert.alert_type,
                    "message": alert.message,
                    "severity": alert.severity,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self._alerts[-10:]  # Last 10 alerts
            ]

            return {
                "daily_usage": self._quota_usage,
                "daily_limit": self.daily_quota_limit,
                "daily_remaining": self.daily_quota_limit - self._quota_usage,
                "daily_percentage": (self._quota_usage / self.daily_quota_limit) * 100,
                "minute_usage": self._minute_usage,
                "minute_limit": self.rate_limit_per_minute,
                "minute_remaining": self.rate_limit_per_minute - self._minute_usage,
                "minute_percentage": (self._minute_usage / self.rate_limit_per_minute)
                * 100,
                "predicted_exhaustion": predicted_exhaustion.isoformat()
                if predicted_exhaustion
                else None,
                "analyzer_breakdown": dict(self._analyzer_usage),
                "recent_alerts": recent_alerts,
                "status": self._get_status_level(),
                "recommendations": self._get_recommendations(),
            }

    def _get_status_level(self) -> str:
        """Get current status level based on usage."""
        daily_pct = self._quota_usage / self.daily_quota_limit
        minute_pct = self._minute_usage / self.rate_limit_per_minute

        if (
            daily_pct >= self.critical_threshold
            or minute_pct >= self.critical_threshold
        ):
            return "critical"
        elif (
            daily_pct >= self.warning_threshold or minute_pct >= self.warning_threshold
        ):
            return "warning"
        else:
            return "healthy"

    def _get_recommendations(self) -> List[str]:
        """Get recommendations based on current quota usage."""
        recommendations = []

        daily_pct = self._quota_usage / self.daily_quota_limit

        if daily_pct >= self.critical_threshold:
            recommendations.append("Consider pausing non-critical analyzer executions")
            recommendations.append("Implement analyzer prioritization queue")
        elif daily_pct >= self.warning_threshold:
            recommendations.append("Monitor quota usage closely")
            recommendations.append("Consider spacing out analyzer executions")

        # Analyzer-specific recommendations
        if self._analyzer_usage:
            highest_usage = max(self._analyzer_usage.items(), key=lambda x: x[1])
            if highest_usage[1] > self.daily_quota_limit * 0.3:  # 30% of daily quota
                recommendations.append(
                    f"Consider optimizing {highest_usage[0]} - using {highest_usage[1]} daily quota"
                )

        return recommendations


class AnalyzerExecutionQueue:
    """Queue system for managing analyzer executions based on quota availability."""

    def __init__(self, quota_manager: AdvancedQuotaManager, max_concurrent: int = 3):
        """Initialize execution queue.

        Args:
            quota_manager: Quota manager instance
            max_concurrent: Maximum concurrent executions
        """
        self.quota_manager = quota_manager
        self.max_concurrent = max_concurrent
        self._queue = asyncio.PriorityQueue()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_processor_running = False

    async def queue_analyzer_execution(
        self,
        analyzer_name: str,
        execution_func: callable,
        estimated_quota: int,
        priority: int = 1,  # Lower number = higher priority
        max_wait_time: Optional[int] = None,
    ) -> Any:
        """Queue an analyzer execution with priority and quota management.

        Args:
            analyzer_name: Name of the analyzer
            execution_func: Function to execute the analyzer
            estimated_quota: Estimated quota consumption
            priority: Execution priority (lower = higher priority)
            max_wait_time: Maximum wait time in seconds

        Returns:
            Execution result
        """
        # Create execution item
        execution_id = f"{analyzer_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        execution_item = {
            "id": execution_id,
            "analyzer_name": analyzer_name,
            "execution_func": execution_func,
            "estimated_quota": estimated_quota,
            "queued_at": datetime.now(),
            "max_wait_time": max_wait_time,
        }

        # Add to priority queue
        await self._queue.put((priority, execution_item))

        logger.info(
            f"Queued {analyzer_name} execution with priority {priority}, "
            f"estimated quota: {estimated_quota}"
        )

        # Start queue processor if not running
        if not self._queue_processor_running:
            await self._start_queue_processor()

        # Wait for execution to complete or timeout
        if max_wait_time:
            try:
                return await asyncio.wait_for(
                    self._wait_for_execution(execution_id), timeout=max_wait_time
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Analyzer execution {execution_id} timed out after {max_wait_time}s"
                )
                return None
        else:
            return await self._wait_for_execution(execution_id)

    async def _start_queue_processor(self) -> None:
        """Start the queue processor task."""
        if self._queue_processor_running:
            return

        self._queue_processor_running = True
        self._queue_processor_task = asyncio.create_task(self._process_queue())
        logger.info("Started analyzer execution queue processor")

    async def _process_queue(self) -> None:
        """Process the analyzer execution queue."""
        while self._queue_processor_running:
            try:
                # Get next execution from queue (wait up to 1 second)
                try:
                    priority, execution_item = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                execution_id = execution_item["id"]
                analyzer_name = execution_item["analyzer_name"]
                estimated_quota = execution_item["estimated_quota"]

                # Check if execution has been waiting too long
                if execution_item["max_wait_time"]:
                    wait_time = (
                        datetime.now() - execution_item["queued_at"]
                    ).total_seconds()
                    if wait_time > execution_item["max_wait_time"]:
                        logger.warning(f"Dropping expired execution: {execution_id}")
                        continue

                # Wait for semaphore (concurrent execution limit)
                await self._semaphore.acquire()

                try:
                    # Check quota availability again
                    if await self.quota_manager.check_quota_availability(
                        estimated_quota, analyzer_name, "normal"
                    ):
                        # Execute analyzer
                        task = asyncio.create_task(
                            self._execute_with_tracking(execution_item)
                        )
                        self._running_tasks[execution_id] = task

                        logger.info(f"Started execution: {execution_id}")
                    else:
                        # Put back in queue with lower priority
                        await self._queue.put((priority + 1, execution_item))
                        logger.info(
                            f"Re-queued {execution_id} due to quota constraints"
                        )

                        # Wait a bit before processing next item
                        await asyncio.sleep(5)
                finally:
                    self._semaphore.release()

            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)

    async def _execute_with_tracking(self, execution_item: Dict[str, Any]) -> Any:
        """Execute analyzer with performance tracking.

        Args:
            execution_item: Execution item from queue

        Returns:
            Execution result
        """
        execution_id = execution_item["id"]
        analyzer_name = execution_item["analyzer_name"]
        start_time = datetime.now()

        try:
            # Execute the analyzer
            result = await execution_item["execution_func"]()

            # Track execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            with self.quota_manager._lock:
                self.quota_manager._analyzer_timing[analyzer_name].append(
                    execution_time
                )
                # Keep only last 50 executions for each analyzer
                if len(self.quota_manager._analyzer_timing[analyzer_name]) > 50:
                    self.quota_manager._analyzer_timing[analyzer_name] = (
                        self.quota_manager._analyzer_timing[analyzer_name][-50:]
                    )

            logger.info(f"Completed execution: {execution_id} in {execution_time:.2f}s")
            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Failed execution: {execution_id} after {execution_time:.2f}s - {e}"
            )
            raise
        finally:
            # Clean up tracking
            self._running_tasks.pop(execution_id, None)

    async def _wait_for_execution(self, execution_id: str) -> Any:
        """Wait for a specific execution to complete.

        Args:
            execution_id: ID of the execution to wait for

        Returns:
            Execution result
        """
        # Poll for task completion
        while execution_id not in self._running_tasks:
            await asyncio.sleep(0.1)

        task = self._running_tasks[execution_id]
        return await task

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status.

        Returns:
            Dictionary with queue status information
        """
        return {
            "queue_size": self._queue.qsize(),
            "running_tasks": len(self._running_tasks),
            "max_concurrent": self.max_concurrent,
            "processor_running": self._queue_processor_running,
            "current_executions": list(self._running_tasks.keys()),
        }

    async def stop_queue_processor(self) -> None:
        """Stop the queue processor."""
        self._queue_processor_running = False
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped analyzer execution queue processor")


async def monitor_api_health(client: GoogleAdsAPIClient) -> Dict[str, Any]:
    """Monitor Google Ads API health and responsiveness.

    Args:
        client: Google Ads API client

    Returns:
        Dictionary with API health metrics
    """
    health_metrics = {
        "api_reachable": False,
        "response_time": None,
        "authentication_valid": False,
        "quota_status": "unknown",
        "last_check": datetime.now().isoformat(),
    }

    start_time = datetime.now()

    try:
        # Simple health check - get customer info
        customer_id = "577-746-1198"  # TopGolf customer ID

        # This is a lightweight call to test connectivity
        campaigns = await client.get_campaigns(
            customer_id=customer_id,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
        )

        response_time = (datetime.now() - start_time).total_seconds()

        health_metrics.update(
            {
                "api_reachable": True,
                "response_time": response_time,
                "authentication_valid": True,
                "quota_status": "available",
                "campaigns_accessible": len(campaigns) > 0,
            }
        )

        logger.info(f"API health check passed in {response_time:.2f}s")

    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds()
        error_type = type(e).__name__

        health_metrics.update(
            {
                "response_time": response_time,
                "error": str(e),
                "error_type": error_type,
            }
        )

        # Categorize the error
        if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
            health_metrics["authentication_valid"] = False
        elif "quota" in str(e).lower() or "rate limit" in str(e).lower():
            health_metrics["quota_status"] = "exhausted"

        logger.warning(f"API health check failed: {error_type} - {e}")

    return health_metrics
