"""Async alert processors for handling and sending alerts."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional

from paidsearchnav.logging.handlers import EmailAlertHandler, SlackAlertHandler

from .models import Alert, AlertBatch, AlertConfig, AlertPriority, AlertStatus
from .rate_limiter import AlertRateLimiter


class AsyncAlertProcessor:
    """Async processor for handling alerts with batching and rate limiting."""

    def __init__(
        self, config: AlertConfig, rate_limiter: Optional[AlertRateLimiter] = None
    ):
        """Initialize async alert processor.

        Args:
            config: Alert configuration
            rate_limiter: Optional rate limiter instance
        """
        self.config = config
        self.rate_limiter = rate_limiter or AlertRateLimiter()

        # Processing queues with size limits to prevent memory issues
        max_queue_size = config.max_queue_size
        self._pending_alerts: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._batch_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)

        # Batching state
        self._current_batches: Dict[str, List[Alert]] = defaultdict(list)
        self._batch_timers: Dict[str, asyncio.Task] = {}

        # Duplicate detection - use bounded deque to prevent memory leaks
        self._recent_alerts: Deque[Alert] = deque(maxlen=1000)
        self._duplicate_window = timedelta(minutes=config.duplicate_window_minutes)

        # Processing tasks
        self._processor_task: Optional[asyncio.Task] = None
        self._batch_processor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Alert handlers
        self._handlers: Dict[str, Any] = {}

        # Logger
        self._logger = logging.getLogger(__name__)

        # Statistics
        self.stats: Dict[str, Any] = {
            "alerts_processed": 0,
            "alerts_sent": 0,
            "alerts_failed": 0,
            "alerts_batched": 0,
            "duplicates_detected": 0,
            "processing_times": [],
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()
        self._running = False

    def register_handler(self, channel: str, handler: Any) -> None:
        """Register an alert handler for a channel.

        Args:
            channel: Channel name (e.g., 'slack', 'email')
            handler: Alert handler instance
        """
        self._handlers[channel] = handler

    async def start(self) -> None:
        """Start the async alert processor."""
        if self._running:
            return

        self._running = True

        # Start processing tasks
        self._processor_task = asyncio.create_task(self._process_alerts())
        self._batch_processor_task = asyncio.create_task(self._process_batches())
        self._cleanup_task = asyncio.create_task(self._cleanup_task_routine())

    async def stop(self) -> None:
        """Stop the async alert processor."""
        self._running = False

        # Cancel batch timers
        for task in self._batch_timers.values():
            task.cancel()

        # Cancel processing tasks
        tasks = [
            t
            for t in [
                self._processor_task,
                self._batch_processor_task,
                self._cleanup_task,
            ]
            if t is not None
        ]
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def submit_alert(self, alert: Alert) -> bool:
        """Submit an alert for processing.

        Args:
            alert: Alert to process

        Returns:
            True if alert was accepted
        """
        if not self._running:
            return False

        # Check rate limits
        allowed, retry_after = await self.rate_limiter.is_allowed(alert)
        if not allowed:
            alert.update_status(AlertStatus.RATE_LIMITED)
            return False

        # Check for duplicates
        if self.config.enable_duplicate_detection and self._is_duplicate(alert):
            self.stats["duplicates_detected"] += 1
            return False

        # Add to processing queue with timeout to prevent blocking
        try:
            await asyncio.wait_for(self._pending_alerts.put(alert), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            self._logger.warning(
                "Alert queue is full, dropping alert",
                extra={
                    "alert_title": alert.title,
                    "queue_size": self._pending_alerts.qsize(),
                    "queue_maxsize": self._pending_alerts.maxsize,
                    "component": "alert_processor",
                },
            )
            alert.update_status(AlertStatus.FAILED, "Queue full")
            return False

    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is a duplicate of recent alerts.

        Args:
            alert: Alert to check

        Returns:
            True if duplicate detected
        """
        cutoff_time = datetime.utcnow() - self._duplicate_window

        # Clean old alerts
        filtered_alerts = [a for a in self._recent_alerts if a.created_at > cutoff_time]
        self._recent_alerts.clear()
        self._recent_alerts.extend(filtered_alerts)

        # Check for duplicates
        for recent_alert in self._recent_alerts:
            if alert.is_duplicate_of(recent_alert):
                return True

        # Add to recent alerts
        self._recent_alerts.append(alert)
        return False

    async def _process_alerts(self) -> None:
        """Main alert processing loop."""
        while self._running:
            try:
                # Get next alert with timeout
                alert = await asyncio.wait_for(self._pending_alerts.get(), timeout=1.0)

                start_time = time.time()

                # Update status
                alert.update_status(AlertStatus.PROCESSING)

                # Determine processing strategy
                if self._should_send_immediately(alert):
                    # Send immediately
                    await self._send_alert_immediately(alert)
                else:
                    # Add to batch
                    await self._add_to_batch(alert)

                # Update statistics
                processing_time = (time.time() - start_time) * 1000  # ms
                self.stats["processing_times"].append(processing_time)
                self.stats["alerts_processed"] += 1

            except asyncio.TimeoutError:
                # No alerts to process, continue
                continue
            except Exception as e:
                # Log error but continue processing
                self._logger.exception(
                    "Error processing alert",
                    extra={"error": str(e), "component": "alert_processor"},
                )

    def _should_send_immediately(self, alert: Alert) -> bool:
        """Determine if alert should be sent immediately.

        Args:
            alert: Alert to check

        Returns:
            True if should send immediately
        """
        # Critical alerts are always sent immediately
        if alert.priority == AlertPriority.CRITICAL:
            return self.config.critical_alert_immediate_send

        # Check if batching is disabled
        if not self.config.enable_batching:
            return True

        return False

    async def _send_alert_immediately(self, alert: Alert) -> None:
        """Send alert immediately without batching.

        Args:
            alert: Alert to send
        """
        success = await self._send_single_alert(alert)
        if success:
            alert.update_status(AlertStatus.SENT)
            self.stats["alerts_sent"] += 1
        else:
            alert.update_status(AlertStatus.FAILED)
            self.stats["alerts_failed"] += 1

    async def _add_to_batch(self, alert: Alert) -> None:
        """Add alert to appropriate batch.

        Args:
            alert: Alert to batch
        """
        # Determine batch key (group similar alerts)
        batch_key = self._get_batch_key(alert)

        async with self._lock:
            self._current_batches[batch_key].append(alert)
            alert.update_status(AlertStatus.BATCHED)

            # Check if batch is full
            if len(self._current_batches[batch_key]) >= self.config.batch_size:
                await self._flush_batch(batch_key)
            else:
                # Set/reset batch timer
                await self._set_batch_timer(batch_key, alert.priority)

    def _get_batch_key(self, alert: Alert) -> str:
        """Get batch key for grouping similar alerts.

        Args:
            alert: Alert to get key for

        Returns:
            Batch key string
        """
        # Group by type, priority, and source for better batching
        return f"{alert.type.value}_{alert.priority.value}_{alert.source}"

    async def _set_batch_timer(self, batch_key: str, priority: AlertPriority) -> None:
        """Set or reset batch timer.

        Args:
            batch_key: Batch key
            priority: Alert priority for timeout determination
        """
        # Cancel existing timer
        if batch_key in self._batch_timers:
            self._batch_timers[batch_key].cancel()

        # Determine timeout based on priority
        if priority == AlertPriority.HIGH:
            timeout = self.config.high_priority_batch_timeout
        else:
            timeout = self.config.batch_timeout_seconds

        # Create new timer
        self._batch_timers[batch_key] = asyncio.create_task(
            self._batch_timer(batch_key, timeout)
        )

    async def _batch_timer(self, batch_key: str, timeout: int) -> None:
        """Timer for flushing batches.

        Args:
            batch_key: Batch key
            timeout: Timeout in seconds
        """
        try:
            await asyncio.sleep(timeout)
            await self._flush_batch(batch_key)
        except asyncio.CancelledError:
            # Timer was cancelled, do nothing
            pass

    async def _flush_batch(self, batch_key: str) -> None:
        """Flush a batch of alerts.

        Args:
            batch_key: Batch to flush
        """
        async with self._lock:
            if (
                batch_key not in self._current_batches
                or not self._current_batches[batch_key]
            ):
                return

            # Create batch
            alerts = self._current_batches[batch_key].copy()
            batch = AlertBatch(alerts=alerts)

            # Clear batch
            self._current_batches[batch_key].clear()

            # Cancel timer
            if batch_key in self._batch_timers:
                self._batch_timers[batch_key].cancel()
                del self._batch_timers[batch_key]

        # Send batch to processing queue
        await self._batch_queue.put(batch)
        self.stats["alerts_batched"] += len(alerts)

    async def _process_batches(self) -> None:
        """Process batched alerts."""
        while self._running:
            try:
                # Get next batch with timeout
                batch = await asyncio.wait_for(self._batch_queue.get(), timeout=1.0)

                # Process batch
                await self._send_batch(batch)
                batch.mark_processed()

            except asyncio.TimeoutError:
                # No batches to process, continue
                continue
            except Exception as e:
                # Log error but continue processing
                self._logger.exception(
                    "Error processing batch",
                    extra={"error": str(e), "component": "batch_processor"},
                )

    async def _send_batch(self, batch: AlertBatch) -> None:
        """Send a batch of alerts.

        Args:
            batch: Batch to send
        """
        # Group alerts by channel requirements
        channel_alerts = self._group_alerts_by_channel(batch.alerts)

        # Send to each channel
        for channel, alerts in channel_alerts.items():
            if channel in self._handlers:
                try:
                    await self._send_alerts_to_channel(alerts, channel)
                except Exception as e:
                    # Mark alerts as failed
                    for alert in alerts:
                        alert.update_status(AlertStatus.FAILED, str(e))
                    self.stats["alerts_failed"] += len(alerts)

    def _group_alerts_by_channel(self, alerts: List[Alert]) -> Dict[str, List[Alert]]:
        """Group alerts by their target channels.

        Args:
            alerts: Alerts to group

        Returns:
            Dictionary of channel -> alerts
        """
        channel_alerts = defaultdict(list)

        for alert in alerts:
            # Determine target channels based on priority
            channels = self._get_alert_channels(alert)
            for channel in channels:
                channel_alerts[channel].append(alert)

        return dict(channel_alerts)

    def _get_alert_channels(self, alert: Alert) -> List[str]:
        """Get target channels for an alert.

        Args:
            alert: Alert to get channels for

        Returns:
            List of channel names
        """
        channels = []

        # Check configured channel priorities
        for channel, priorities in self.config.channel_priorities.items():
            if alert.priority in priorities and channel in self._handlers:
                channels.append(channel)

        # Fallback to default channels
        if not channels:
            channels = [
                ch for ch in self.config.default_channels if ch in self._handlers
            ]

        return channels

    async def _send_alerts_to_channel(self, alerts: List[Alert], channel: str) -> None:
        """Send alerts to a specific channel.

        Args:
            alerts: Alerts to send
            channel: Channel name
        """
        handler = self._handlers[channel]

        if channel == "slack" and isinstance(handler, SlackAlertHandler):
            await self._send_to_slack(alerts, handler)
        elif channel == "email" and isinstance(handler, EmailAlertHandler):
            await self._send_to_email(alerts, handler)
        else:
            # Generic handler
            for alert in alerts:
                await self._send_single_alert_to_handler(alert, handler)

    async def _send_to_slack(
        self, alerts: List[Alert], handler: SlackAlertHandler
    ) -> None:
        """Send alerts to Slack with batching.

        Args:
            alerts: Alerts to send
            handler: Slack handler
        """
        # Create combined message for batch
        if len(alerts) == 1:
            # Single alert
            alert = alerts[0]
            # Convert alert to log record format
            import logging

            record = logging.LogRecord(
                name=alert.source,
                level=logging.ERROR
                if alert.priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]
                else logging.WARNING,
                pathname="",
                lineno=0,
                msg=alert.message,
                args=(),
                exc_info=None,
            )
            record.customer_id = alert.customer_id
            record.job_id = alert.job_id

            try:
                handler.emit(record)
                alert.update_status(AlertStatus.SENT)
                alert.channels_sent.append("slack")
                self.stats["alerts_sent"] += 1
            except Exception as e:
                alert.update_status(AlertStatus.FAILED, str(e))
                self.stats["alerts_failed"] += 1
        else:
            # Batch of alerts - create summary
            await self._send_batch_to_slack(alerts, handler)

    async def _send_batch_to_slack(
        self, alerts: List[Alert], handler: SlackAlertHandler
    ) -> None:
        """Send batch of alerts to Slack as summary.

        Args:
            alerts: Alerts in batch
            handler: Slack handler
        """
        # Create summary message
        priority_counts: Dict[str, int] = defaultdict(int)
        type_counts: Dict[str, int] = defaultdict(int)

        for alert in alerts:
            priority_counts[alert.priority.value] += 1
            type_counts[alert.type.value] += 1

        summary_msg = f"Alert Batch Summary ({len(alerts)} alerts):\n"
        summary_msg += f"Priorities: {dict(priority_counts)}\n"
        summary_msg += f"Types: {dict(type_counts)}\n"

        # Add individual alert titles
        summary_msg += "\nAlerts:\n"
        for alert in alerts[:5]:  # Limit to first 5
            summary_msg += f"• {alert.title}\n"

        if len(alerts) > 5:
            summary_msg += f"• ... and {len(alerts) - 5} more alerts"

        # Send summary
        import logging

        record = logging.LogRecord(
            name="AlertSystem",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg=summary_msg,
            args=(),
            exc_info=None,
        )

        try:
            handler.emit(record)
            # Mark all alerts as sent
            for alert in alerts:
                alert.update_status(AlertStatus.SENT)
                alert.channels_sent.append("slack")
            self.stats["alerts_sent"] += len(alerts)
        except Exception as e:
            # Mark all alerts as failed
            for alert in alerts:
                alert.update_status(AlertStatus.FAILED, str(e))
            self.stats["alerts_failed"] += len(alerts)

    async def _send_to_email(
        self, alerts: List[Alert], handler: EmailAlertHandler
    ) -> None:
        """Send alerts to email.

        Args:
            alerts: Alerts to send
            handler: Email handler
        """
        # For email, send individual alerts or create digest
        if len(alerts) <= 3:
            # Send individual alerts
            for alert in alerts:
                await self._send_single_alert_to_email(alert, handler)
        else:
            # Send as digest
            await self._send_digest_to_email(alerts, handler)

    async def _send_single_alert_to_email(
        self, alert: Alert, handler: EmailAlertHandler
    ) -> None:
        """Send single alert to email.

        Args:
            alert: Alert to send
            handler: Email handler
        """
        import logging

        record = logging.LogRecord(
            name=alert.source,
            level=logging.ERROR
            if alert.priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]
            else logging.WARNING,
            pathname="",
            lineno=0,
            msg=alert.message,
            args=(),
            exc_info=None,
        )
        record.customer_id = alert.customer_id
        record.job_id = alert.job_id

        try:
            handler.emit(record)
            alert.update_status(AlertStatus.SENT)
            alert.channels_sent.append("email")
            self.stats["alerts_sent"] += 1
        except Exception as e:
            alert.update_status(AlertStatus.FAILED, str(e))
            self.stats["alerts_failed"] += 1

    async def _send_digest_to_email(
        self, alerts: List[Alert], handler: EmailAlertHandler
    ) -> None:
        """Send digest of alerts to email.

        Args:
            alerts: Alerts to include in digest
            handler: Email handler
        """
        # Create digest message
        digest_msg = f"PaidSearchNav Alert Digest - {len(alerts)} alerts\n\n"

        for i, alert in enumerate(alerts, 1):
            digest_msg += f"{i}. [{alert.priority.value.upper()}] {alert.title}\n"
            digest_msg += f"   Source: {alert.source}\n"
            digest_msg += f"   Time: {alert.created_at}\n"
            digest_msg += f"   Message: {alert.message[:200]}...\n\n"

        import logging

        record = logging.LogRecord(
            name="AlertDigest",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg=digest_msg,
            args=(),
            exc_info=None,
        )

        try:
            handler.emit(record)
            # Mark all alerts as sent
            for alert in alerts:
                alert.update_status(AlertStatus.SENT)
                alert.channels_sent.append("email")
            self.stats["alerts_sent"] += len(alerts)
        except Exception as e:
            # Mark all alerts as failed
            for alert in alerts:
                alert.update_status(AlertStatus.FAILED, str(e))
            self.stats["alerts_failed"] += len(alerts)

    async def _send_single_alert(self, alert: Alert) -> bool:
        """Send single alert to all appropriate channels.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully to at least one channel
        """
        channels = self._get_alert_channels(alert)
        success_count = 0

        for channel in channels:
            if channel in self._handlers:
                try:
                    await self._send_alerts_to_channel([alert], channel)
                    success_count += 1
                except Exception as e:
                    self._logger.exception(
                        "Failed to send alert to channel",
                        extra={
                            "channel": channel,
                            "error": str(e),
                            "alert_id": alert.id if hasattr(alert, "id") else None,
                            "component": "alert_sender",
                        },
                    )

        return success_count > 0

    async def _send_single_alert_to_handler(self, alert: Alert, handler: Any) -> None:
        """Send single alert to a handler.

        Args:
            alert: Alert to send
            handler: Handler to use
        """
        # Generic handler interface
        if hasattr(handler, "send_alert"):
            await handler.send_alert(alert)
        else:
            # Fallback to logging handler interface
            import logging

            record = logging.LogRecord(
                name=alert.source,
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg=alert.message,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

    async def _cleanup_task_routine(self) -> None:
        """Periodic cleanup task."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up rate limiter
                await self.rate_limiter.cleanup_old_buckets()

                # Clean up processing times (keep only recent ones)
                if len(self.stats["processing_times"]) > 1000:
                    self.stats["processing_times"] = self.stats["processing_times"][
                        -500:
                    ]

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(
                    "Error in cleanup task",
                    extra={"error": str(e), "component": "cleanup_task"},
                )

    async def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()

        # Add rate limiter stats
        rate_limiter_stats = await self.rate_limiter.get_stats()
        stats["rate_limiter"] = rate_limiter_stats

        # Add processing time statistics
        if self.stats["processing_times"]:
            stats["avg_processing_time_ms"] = sum(self.stats["processing_times"]) / len(
                self.stats["processing_times"]
            )
            stats["max_processing_time_ms"] = max(self.stats["processing_times"])
            stats["min_processing_time_ms"] = min(self.stats["processing_times"])
        else:
            stats["avg_processing_time_ms"] = 0
            stats["max_processing_time_ms"] = 0
            stats["min_processing_time_ms"] = 0

        # Add queue sizes and limits
        stats["pending_queue_size"] = self._pending_alerts.qsize()
        stats["pending_queue_maxsize"] = self._pending_alerts.maxsize
        stats["processing_queue_size"] = self._processing_queue.qsize()
        stats["processing_queue_maxsize"] = self._processing_queue.maxsize
        stats["batch_queue_size"] = self._batch_queue.qsize()
        stats["batch_queue_maxsize"] = self._batch_queue.maxsize

        # Add memory usage indicators
        stats["recent_alerts_count"] = len(self._recent_alerts)
        stats["recent_alerts_maxlen"] = getattr(self._recent_alerts, "maxlen", None)
        stats["active_batches"] = len(self._current_batches)
        stats["batch_timers"] = len(self._batch_timers)

        return stats

    async def flush_all_batches(self) -> None:
        """Flush all pending batches immediately."""
        batches_to_process = []

        # Collect all batches while holding the lock
        async with self._lock:
            batch_keys = list(self._current_batches.keys())
            for batch_key in batch_keys:
                if self._current_batches[batch_key]:
                    # Create batch
                    alerts = self._current_batches[batch_key].copy()
                    batch = AlertBatch(alerts=alerts)
                    batches_to_process.append(batch)

                    # Clear batch
                    self._current_batches[batch_key].clear()

                    # Cancel timer
                    if batch_key in self._batch_timers:
                        self._batch_timers[batch_key].cancel()
                        del self._batch_timers[batch_key]

        # Process batches outside the lock
        for batch in batches_to_process:
            await self._batch_queue.put(batch)
            self.stats["alerts_batched"] += len(batch.alerts)
