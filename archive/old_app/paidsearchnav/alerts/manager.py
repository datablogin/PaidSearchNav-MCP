"""Alert manager for coordinating the alert system."""

import logging
from typing import Any, Dict, List, Optional

from paidsearchnav.core.config import Settings
from paidsearchnav.logging.handlers import (
    EmailAlertHandler,
    SentryHandler,
    SlackAlertHandler,
)

from .models import Alert, AlertConfig, AlertMetrics, AlertPriority, AlertType
from .processors import AsyncAlertProcessor
from .rate_limiter import AdaptiveRateLimiter


class AlertManager:
    """Central manager for the alert system."""

    def __init__(self, settings: Settings, config: Optional[AlertConfig] = None):
        """Initialize alert manager.

        Args:
            settings: Application settings
            config: Optional alert configuration
        """
        self.settings = settings
        self.config = config or AlertConfig()

        # Initialize components
        rate_limiter_config = {
            "max_alerts_per_minute": self.config.max_alerts_per_minute,
            "max_alerts_per_hour": self.config.max_alerts_per_hour,
            "enable_adaptive_limiting": True,
        }

        self.rate_limiter = AdaptiveRateLimiter(rate_limiter_config)
        self.processor = AsyncAlertProcessor(self.config, self.rate_limiter)
        self.metrics = AlertMetrics()

        # State
        self._started = False
        self._logger = logging.getLogger(__name__)

        # Initialize handlers
        self._initialize_handlers()

    def _initialize_handlers(self) -> None:
        """Initialize alert handlers based on settings."""
        self._initialize_slack_handler()
        self._initialize_email_handler()
        self._initialize_sentry_handler()
        self._initialize_webhook_handler()

    def _initialize_slack_handler(self) -> None:
        """Initialize Slack alert handler."""
        if not (
            hasattr(self.settings, "logging")
            and hasattr(self.settings.logging, "slack_webhook_url")
        ):
            return

        if not self.settings.logging.slack_webhook_url:
            return

        try:
            webhook_url = self.settings.logging.slack_webhook_url.get_secret_value()
            if webhook_url:
                slack_handler = SlackAlertHandler(
                    webhook_url=webhook_url,
                    channel=getattr(self.settings.logging, "slack_channel", None),
                )
                self.processor.register_handler("slack", slack_handler)
                self._logger.info("Slack alert handler initialized")
            else:
                self._logger.warning(
                    "Slack webhook URL is empty, Slack handler disabled"
                )
        except Exception as e:
            self._logger.warning(
                f"Failed to get Slack webhook URL: {e}, Slack handler disabled"
            )

    def _initialize_email_handler(self) -> None:
        """Initialize email alert handler."""
        if not hasattr(self.settings, "logging"):
            return

        logging_config = self.settings.logging
        if not (
            hasattr(logging_config, "smtp_host")
            and logging_config.smtp_host
            and hasattr(logging_config, "email_to")
            and logging_config.email_to
        ):
            return

        try:
            smtp_password = None
            if (
                hasattr(logging_config, "smtp_password")
                and logging_config.smtp_password
            ):
                smtp_password = logging_config.smtp_password.get_secret_value()

            email_handler = EmailAlertHandler(
                smtp_host=logging_config.smtp_host,
                smtp_port=getattr(logging_config, "smtp_port", 587),
                smtp_username=getattr(logging_config, "smtp_username", None),
                smtp_password=smtp_password,
                from_email=getattr(
                    logging_config, "email_from", "alerts@paidsearchnav.com"
                ),
                to_emails=logging_config.email_to,
                use_tls=True,
            )
            self.processor.register_handler("email", email_handler)
            self._logger.info("Email alert handler initialized")
        except Exception as e:
            self._logger.warning(
                f"Failed to configure email handler: {e}, Email handler disabled"
            )

    def _initialize_sentry_handler(self) -> None:
        """Initialize Sentry alert handler."""
        if not (
            hasattr(self.settings, "logging")
            and hasattr(self.settings.logging, "sentry_dsn")
        ):
            return

        if not self.settings.logging.sentry_dsn:
            return

        try:
            sentry_dsn = self.settings.logging.sentry_dsn.get_secret_value()
            if sentry_dsn:
                sentry_handler = SentryHandler(
                    dsn=sentry_dsn,
                    environment=getattr(self.settings, "environment", "development"),
                )
                self.processor.register_handler("sentry", sentry_handler)
                self._logger.info("Sentry alert handler initialized")
            else:
                self._logger.warning("Sentry DSN is empty, Sentry handler disabled")
        except Exception as e:
            self._logger.warning(
                f"Failed to get Sentry DSN: {e}, Sentry handler disabled"
            )

    def _initialize_webhook_handler(self) -> None:
        """Initialize generic webhook alert handler."""
        if not (
            hasattr(self.settings, "logging")
            and hasattr(self.settings.logging, "webhook_url")
        ):
            return

        if not self.settings.logging.webhook_url:
            return

        try:
            import json

            from paidsearchnav.alerts.handlers.webhook import WebhookAlertHandler

            webhook_url = self.settings.logging.webhook_url.get_secret_value()
            if webhook_url:
                # Parse headers if provided
                headers = None
                if self.settings.logging.webhook_headers:
                    try:
                        headers = json.loads(self.settings.logging.webhook_headers)
                    except json.JSONDecodeError:
                        self._logger.warning("Invalid webhook headers format, ignoring")

                # Parse payload template if provided
                payload_template = None
                if self.settings.logging.webhook_payload_template:
                    try:
                        payload_template = json.loads(
                            self.settings.logging.webhook_payload_template
                        )
                    except json.JSONDecodeError:
                        self._logger.warning(
                            "Invalid webhook payload template format, ignoring"
                        )

                # Get auth token if provided
                auth_token = None
                if self.settings.logging.webhook_auth_token:
                    auth_token = (
                        self.settings.logging.webhook_auth_token.get_secret_value()
                    )

                webhook_handler = WebhookAlertHandler(
                    webhook_url=webhook_url,
                    method=self.settings.logging.webhook_method,
                    headers=headers,
                    auth_type=self.settings.logging.webhook_auth_type,
                    auth_token=auth_token,
                    timeout=self.settings.logging.webhook_timeout,
                    retry_attempts=self.settings.logging.webhook_retry_attempts,
                    retry_backoff=self.settings.logging.webhook_retry_backoff,
                    ssl_verify=self.settings.logging.webhook_ssl_verify,
                    payload_template=payload_template,
                )
                self.processor.register_handler("webhook", webhook_handler)
                self._logger.info("Webhook alert handler initialized")
            else:
                self._logger.warning("Webhook URL is empty, webhook handler disabled")
        except Exception as e:
            self._logger.warning(
                f"Failed to configure webhook handler: {e}, webhook handler disabled"
            )

    async def start(self) -> None:
        """Start the alert manager."""
        if self._started:
            return

        await self.processor.start()
        self._started = True
        self._logger.info("Alert manager started")

    async def stop(self) -> None:
        """Stop the alert manager."""
        if not self._started:
            return

        await self.processor.stop()
        self._started = False
        self._logger.info("Alert manager stopped")

    async def send_alert(
        self,
        alert_type: AlertType,
        priority: AlertPriority,
        title: str,
        message: str,
        source: str,
        context: Optional[Dict[str, Any]] = None,
        customer_id: Optional[str] = None,
        job_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Send an alert through the system.

        Args:
            alert_type: Type of alert
            priority: Alert priority
            title: Alert title
            message: Alert message
            source: Source component
            context: Optional context data
            customer_id: Optional customer ID
            job_id: Optional job ID
            tags: Optional tags

        Returns:
            True if alert was accepted for processing
        """
        if not self._started:
            await self.start()

        # Create alert
        alert = Alert(
            type=alert_type,
            priority=priority,
            title=title,
            message=message,
            source=source,
            context=context or {},
            customer_id=customer_id,
            job_id=job_id,
            tags=tags or [],
        )

        # Update metrics
        self.metrics.increment_alert(alert)

        # Submit to processor
        success = await self.processor.submit_alert(alert)

        if success:
            self._logger.debug(f"Alert submitted: {alert.title}")
        else:
            self._logger.warning(f"Alert rejected: {alert.title}")

        return success

    async def send_error_alert(
        self,
        title: str,
        message: str,
        source: str,
        priority: AlertPriority = AlertPriority.HIGH,
        **kwargs,
    ) -> bool:
        """Send an error alert.

        Args:
            title: Alert title
            message: Error message
            source: Source component
            priority: Alert priority
            **kwargs: Additional alert parameters

        Returns:
            True if alert was accepted
        """
        return await self.send_alert(
            alert_type=AlertType.ERROR,
            priority=priority,
            title=title,
            message=message,
            source=source,
            **kwargs,
        )

    async def send_performance_alert(
        self,
        title: str,
        message: str,
        source: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        **kwargs,
    ) -> bool:
        """Send a performance alert.

        Args:
            title: Alert title
            message: Performance message
            source: Source component
            priority: Alert priority
            **kwargs: Additional alert parameters

        Returns:
            True if alert was accepted
        """
        return await self.send_alert(
            alert_type=AlertType.PERFORMANCE,
            priority=priority,
            title=title,
            message=message,
            source=source,
            **kwargs,
        )

    async def send_security_alert(
        self,
        title: str,
        message: str,
        source: str,
        priority: AlertPriority = AlertPriority.CRITICAL,
        **kwargs,
    ) -> bool:
        """Send a security alert.

        Args:
            title: Alert title
            message: Security message
            source: Source component
            priority: Alert priority
            **kwargs: Additional alert parameters

        Returns:
            True if alert was accepted
        """
        return await self.send_alert(
            alert_type=AlertType.SECURITY,
            priority=priority,
            title=title,
            message=message,
            source=source,
            **kwargs,
        )

    async def send_system_alert(
        self,
        title: str,
        message: str,
        source: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        **kwargs,
    ) -> bool:
        """Send a system alert.

        Args:
            title: Alert title
            message: System message
            source: Source component
            priority: Alert priority
            **kwargs: Additional alert parameters

        Returns:
            True if alert was accepted
        """
        return await self.send_alert(
            alert_type=AlertType.SYSTEM,
            priority=priority,
            title=title,
            message=message,
            source=source,
            **kwargs,
        )

    def update_system_load(self, load: float) -> None:
        """Update system load for adaptive rate limiting.

        Args:
            load: System load value (0.0 to 1.0)
        """
        if isinstance(self.rate_limiter, AdaptiveRateLimiter):
            self.rate_limiter.update_system_load(load)

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of alert system.

        Returns:
            Health status dictionary
        """
        stats = await self.processor.get_stats()

        # Determine health
        alerts_sent = stats.get("alerts_sent", 0)
        alerts_failed = stats.get("alerts_failed", 0)
        total_alerts = alerts_sent + alerts_failed

        if total_alerts > 0:
            success_rate = alerts_sent / total_alerts
            healthy = success_rate > 0.9  # 90% success rate threshold
        else:
            healthy = True  # No alerts processed yet

        return {
            "status": "healthy" if healthy else "degraded",
            "started": self._started,
            "success_rate": success_rate if total_alerts > 0 else 1.0,
            "total_alerts_processed": total_alerts,
            "alerts_sent": alerts_sent,
            "alerts_failed": alerts_failed,
            "alerts_rate_limited": stats.get("alerts_rate_limited", 0),
            "pending_queue_size": stats.get("pending_queue_size", 0),
            "batch_queue_size": stats.get("batch_queue_size", 0),
            "active_batches": stats.get("active_batches", 0),
            "avg_processing_time_ms": stats.get("avg_processing_time_ms", 0),
            "handlers_registered": len(self.processor._handlers),
            "rate_limiter": stats.get("rate_limiter", {}),
        }

    async def get_metrics(self) -> AlertMetrics:
        """Get alert system metrics.

        Returns:
            Alert metrics
        """
        # Update metrics from processor stats
        stats = await self.processor.get_stats()

        self.metrics.alerts_sent = stats.get("alerts_sent", 0)
        self.metrics.alerts_failed = stats.get("alerts_failed", 0)
        self.metrics.alerts_rate_limited = stats.get("alerts_rate_limited", 0)
        self.metrics.alerts_batched = stats.get("alerts_batched", 0)

        # Update processing times
        if stats.get("avg_processing_time_ms"):
            self.metrics.update_processing_time(stats["avg_processing_time_ms"])

        return self.metrics

    async def flush_pending_alerts(self) -> None:
        """Flush all pending batched alerts immediately."""
        if self._started:
            await self.processor.flush_all_batches()

    def get_config(self) -> AlertConfig:
        """Get current alert configuration.

        Returns:
            Alert configuration
        """
        return self.config

    def update_config(self, new_config: AlertConfig) -> None:
        """Update alert configuration.

        Args:
            new_config: New configuration
        """
        self.config = new_config
        # Note: For full config updates, may need to restart processor

    async def test_handlers(self) -> Dict[str, bool]:
        """Test all registered alert handlers.

        Returns:
            Dictionary of handler -> success status
        """
        results = {}

        test_alert = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Alert System Test",
            message="This is a test alert to verify handler functionality.",
            source="AlertManager",
        )

        for channel, handler in self.processor._handlers.items():
            try:
                # Try to send test alert
                await self.processor._send_alerts_to_channel([test_alert], channel)
                results[channel] = True
            except Exception as e:
                self._logger.error(f"Handler test failed for {channel}: {e}")
                results[channel] = False

        return results


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(settings: Optional[Settings] = None) -> AlertManager:
    """Get or create global alert manager instance.

    Args:
        settings: Optional settings for initialization

    Returns:
        Alert manager instance
    """
    global _alert_manager

    if _alert_manager is None:
        if settings is None:
            raise ValueError("Settings required for first alert manager initialization")
        _alert_manager = AlertManager(settings)

    return _alert_manager


def reset_alert_manager() -> None:
    """Reset global alert manager instance.

    This is primarily for testing purposes to ensure clean state between tests.
    """
    global _alert_manager
    _alert_manager = None


async def send_alert(
    alert_type: AlertType,
    priority: AlertPriority,
    title: str,
    message: str,
    source: str,
    **kwargs,
) -> bool:
    """Convenience function to send an alert.

    Args:
        alert_type: Type of alert
        priority: Alert priority
        title: Alert title
        message: Alert message
        source: Source component
        **kwargs: Additional alert parameters

    Returns:
        True if alert was accepted
    """
    try:
        manager = get_alert_manager()
        return await manager.send_alert(
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            source=source,
            **kwargs,
        )
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to send alert: {e}")
        return False


# Convenience functions for common alert types
async def send_error_alert(title: str, message: str, source: str, **kwargs) -> bool:
    """Send an error alert."""
    return await send_alert(
        AlertType.ERROR, AlertPriority.HIGH, title, message, source, **kwargs
    )


async def send_warning_alert(title: str, message: str, source: str, **kwargs) -> bool:
    """Send a warning alert."""
    return await send_alert(
        AlertType.WARNING, AlertPriority.MEDIUM, title, message, source, **kwargs
    )


async def send_performance_alert(
    title: str, message: str, source: str, **kwargs
) -> bool:
    """Send a performance alert."""
    return await send_alert(
        AlertType.PERFORMANCE, AlertPriority.MEDIUM, title, message, source, **kwargs
    )


async def send_security_alert(title: str, message: str, source: str, **kwargs) -> bool:
    """Send a security alert."""
    return await send_alert(
        AlertType.SECURITY, AlertPriority.CRITICAL, title, message, source, **kwargs
    )
