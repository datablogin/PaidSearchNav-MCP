"""GA4 real-time alerts integration for performance monitoring.

This module integrates GA4 real-time metrics with the existing alert
infrastructure to provide immediate notifications for performance issues.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from paidsearchnav_mcp.core.config import GA4Config
from paidsearchnav_mcp.platforms.ga4.client import GA4DataClient
from paidsearchnav_mcp.platforms.ga4.models import GA4Alert, GA4AlertThreshold

try:
    from paidsearchnav_mcp.alerts.manager import AlertManager, get_alert_manager
    from paidsearchnav_mcp.alerts.models import Alert, AlertPriority, AlertType

    ALERTS_AVAILABLE = True
except ImportError:
    AlertManager = None
    get_alert_manager = None
    ALERTS_AVAILABLE = False

    class AlertPriority:
        CRITICAL = "critical"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"

    class AlertType:
        WARNING = "warning"
        SYSTEM = "system"
        INFO = "info"


logger = logging.getLogger(__name__)


class GA4AlertsManager:
    """Manager for GA4 real-time performance alerts."""

    # Default alert thresholds
    DEFAULT_THRESHOLDS = [
        GA4AlertThreshold(
            metric_name="bounceRate",
            threshold_value=0.8,
            comparison_operator="greater_than",
            alert_severity="medium",
            cooldown_minutes=60,
        ),
        GA4AlertThreshold(
            metric_name="sessionConversionRate",
            threshold_value=0.01,
            comparison_operator="less_than",
            alert_severity="high",
            cooldown_minutes=30,
        ),
        GA4AlertThreshold(
            metric_name="activeUsers",
            threshold_value=10,
            comparison_operator="less_than",
            alert_severity="low",
            cooldown_minutes=120,
        ),
        GA4AlertThreshold(
            metric_name="conversions",
            threshold_value=1.0,
            comparison_operator="greater_than",
            alert_severity="low",
            cooldown_minutes=15,
        ),
    ]

    def __init__(
        self,
        ga4_client: GA4DataClient,
        config: GA4Config,
        alert_manager: Optional[AlertManager] = None,
        custom_thresholds: Optional[List[GA4AlertThreshold]] = None,
    ):
        """Initialize GA4 alerts manager.

        Args:
            ga4_client: GA4 Data API client
            config: GA4 configuration
            alert_manager: Optional alert manager for notifications
            custom_thresholds: Optional custom alert thresholds
        """
        self.ga4_client = ga4_client
        self.config = config
        self.alert_manager = alert_manager or (
            get_alert_manager() if ALERTS_AVAILABLE else None
        )
        self.thresholds = custom_thresholds or self.DEFAULT_THRESHOLDS

        # Alert tracking
        self._active_alerts: Dict[str, GA4Alert] = {}
        self._last_check_times: Dict[str, datetime] = {}
        self._alert_history: List[GA4Alert] = []

    async def check_realtime_alerts(self) -> List[GA4Alert]:
        """Check real-time metrics against alert thresholds.

        Returns:
            List of triggered alerts
        """
        if not self.config.enable_realtime_data:
            logger.debug("Real-time data disabled, skipping alert checks")
            return []

        triggered_alerts = []

        try:
            # Get real-time metrics for alert checking
            realtime_data = await self.ga4_client.get_realtime_metrics(
                dimensions=["source", "medium"],
                metrics=["activeUsers", "conversions"],
                limit=100,
            )

            # Get recent session metrics for bounce rate and conversion rate
            session_data = await self.ga4_client.get_historical_metrics(
                start_date="today",
                end_date="today",
                dimensions=["source", "medium"],
                metrics=["sessions", "bounceRate", "sessionConversionRate"],
                limit=100,
            )

            # Check thresholds against real-time data
            for threshold in self.thresholds:
                if not threshold.enabled:
                    continue

                alert = await self._check_threshold(
                    threshold, realtime_data, session_data
                )

                if alert:
                    triggered_alerts.append(alert)

            return triggered_alerts

        except Exception as e:
            logger.error(f"Failed to check GA4 real-time alerts: {e}")
            return []

    async def _check_threshold(
        self,
        threshold: GA4AlertThreshold,
        realtime_data: Dict[str, Any],
        session_data: Dict[str, Any],
    ) -> Optional[GA4Alert]:
        """Check a specific threshold against current metrics.

        Args:
            threshold: Alert threshold to check
            realtime_data: Real-time metrics data
            session_data: Session metrics data

        Returns:
            GA4Alert if threshold is violated, None otherwise
        """
        try:
            # Select appropriate data source based on metric
            if threshold.metric_name in ["activeUsers", "conversions"]:
                data_source = realtime_data
            else:
                data_source = session_data

            # Calculate current metric value
            current_value = self._calculate_metric_value(
                threshold.metric_name, data_source
            )

            if current_value is None:
                logger.debug(f"No data available for metric {threshold.metric_name}")
                return None

            # Check if threshold is violated
            is_violated = self._is_threshold_violated(
                current_value, threshold.threshold_value, threshold.comparison_operator
            )

            if not is_violated:
                # Check if we should resolve an existing alert
                alert_key = f"{threshold.metric_name}_{threshold.comparison_operator}_{threshold.threshold_value}"
                if alert_key in self._active_alerts:
                    self._resolve_alert(alert_key)
                return None

            # Check cooldown period
            alert_key = f"{threshold.metric_name}_{threshold.comparison_operator}_{threshold.threshold_value}"
            last_alert = self._last_check_times.get(alert_key)
            if last_alert:
                cooldown_delta = timedelta(minutes=threshold.cooldown_minutes)
                if datetime.utcnow() - last_alert < cooldown_delta:
                    return None

            # Create and track alert
            alert = GA4Alert(
                property_id=self.config.property_id,
                threshold=threshold,
                current_value=current_value,
                message=self._generate_alert_message(threshold, current_value),
                context={
                    "metric_name": threshold.metric_name,
                    "threshold_value": threshold.threshold_value,
                    "current_value": current_value,
                    "comparison": threshold.comparison_operator,
                    "data_source": "realtime"
                    if threshold.metric_name in ["activeUsers", "conversions"]
                    else "session",
                },
            )

            # Track alert and timing
            self._active_alerts[alert_key] = alert
            self._last_check_times[alert_key] = datetime.utcnow()
            self._alert_history.append(alert)

            # Send alert notification
            await self._send_alert_notification(alert)

            return alert

        except Exception as e:
            logger.error(f"Error checking threshold {threshold.metric_name}: {e}")
            return None

    def _calculate_metric_value(
        self, metric_name: str, data: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate current value for a metric from API response data.

        Args:
            metric_name: Name of the metric to calculate
            data: API response data

        Returns:
            Current metric value or None if not available
        """
        rows = data.get("rows", [])
        if not rows:
            return None

        if metric_name == "activeUsers":
            return sum(float(row.get("activeUsers", 0)) for row in rows)

        elif metric_name == "conversions":
            return sum(float(row.get("conversions", 0)) for row in rows)

        elif metric_name == "bounceRate":
            # Calculate weighted average bounce rate
            total_sessions = sum(float(row.get("sessions", 0)) for row in rows)
            if total_sessions == 0:
                return None

            weighted_bounce_rate = (
                sum(
                    float(row.get("bounceRate", 0)) * float(row.get("sessions", 0))
                    for row in rows
                )
                / total_sessions
            )
            return weighted_bounce_rate

        elif metric_name == "sessionConversionRate":
            # Calculate overall conversion rate
            total_sessions = sum(float(row.get("sessions", 0)) for row in rows)
            total_conversions = sum(float(row.get("conversions", 0)) for row in rows)

            if total_sessions == 0:
                return None

            return total_conversions / total_sessions

        else:
            logger.warning(f"Unknown metric for alert calculation: {metric_name}")
            return None

    def _is_threshold_violated(
        self, current_value: float, threshold_value: float, operator: str
    ) -> bool:
        """Check if threshold is violated.

        Args:
            current_value: Current metric value
            threshold_value: Threshold value to compare against
            operator: Comparison operator

        Returns:
            True if threshold is violated
        """
        if operator == "greater_than":
            return current_value > threshold_value
        elif operator == "less_than":
            return current_value < threshold_value
        elif operator == "equals":
            return abs(current_value - threshold_value) < 0.001  # Float comparison
        elif operator == "not_equals":
            return abs(current_value - threshold_value) >= 0.001
        else:
            logger.warning(f"Unknown comparison operator: {operator}")
            return False

    def _generate_alert_message(
        self, threshold: GA4AlertThreshold, current_value: float
    ) -> str:
        """Generate human-readable alert message.

        Args:
            threshold: Alert threshold that was violated
            current_value: Current metric value

        Returns:
            Alert message string
        """
        if threshold.metric_name == "bounceRate":
            return (
                f"High bounce rate alert: {current_value:.1%} (threshold: {threshold.threshold_value:.1%}) "
                f"for GA4 property {self.config.property_id}"
            )
        elif threshold.metric_name == "sessionConversionRate":
            return (
                f"Low conversion rate alert: {current_value:.2%} (threshold: {threshold.threshold_value:.2%}) "
                f"for GA4 property {self.config.property_id}"
            )
        elif threshold.metric_name == "activeUsers":
            return (
                f"Low active users alert: {current_value:.0f} (threshold: {threshold.threshold_value:.0f}) "
                f"for GA4 property {self.config.property_id}"
            )
        elif threshold.metric_name == "conversions":
            return (
                f"Conversion spike detected: {current_value:.0f} (threshold: {threshold.threshold_value:.0f}) "
                f"for GA4 property {self.config.property_id}"
            )
        else:
            return (
                f"GA4 alert: {threshold.metric_name} is {current_value:.2f} "
                f"({threshold.comparison_operator} {threshold.threshold_value:.2f}) "
                f"for property {self.config.property_id}"
            )

    async def _send_alert_notification(self, ga4_alert: GA4Alert) -> None:
        """Send alert notification through the alert system.

        Args:
            ga4_alert: GA4 alert to send
        """
        if not self.alert_manager:
            logger.warning(
                f"GA4 alert triggered but no alert manager available: {ga4_alert.message}"
            )
            return

        try:
            # Convert GA4Alert to system Alert
            alert = Alert(
                message=ga4_alert.message,
                alert_type=AlertType.WARNING,
                priority=ga4_alert.threshold.alert_severity,
                source="ga4_analytics",
                context={
                    "property_id": ga4_alert.property_id,
                    "metric_name": ga4_alert.threshold.metric_name,
                    "current_value": ga4_alert.current_value,
                    "threshold_value": ga4_alert.threshold.threshold_value,
                    "comparison_operator": ga4_alert.threshold.comparison_operator,
                    "triggered_at": ga4_alert.triggered_at.isoformat(),
                },
            )

            await self.alert_manager.send_alert_async(alert)
            logger.info(f"GA4 alert sent successfully: {ga4_alert.message}")

        except Exception as e:
            logger.error(f"Failed to send GA4 alert notification: {e}")

    def _resolve_alert(self, alert_key: str) -> None:
        """Resolve an active alert.

        Args:
            alert_key: Key of the alert to resolve
        """
        if alert_key in self._active_alerts:
            alert = self._active_alerts[alert_key]
            alert.resolved_at = datetime.utcnow()
            del self._active_alerts[alert_key]

            logger.info(f"Resolved GA4 alert: {alert.message}")

    def get_active_alerts(self) -> List[GA4Alert]:
        """Get list of currently active GA4 alerts.

        Returns:
            List of active GA4 alerts
        """
        return list(self._active_alerts.values())

    def get_alert_history(
        self, hours: int = 24, severity_filter: Optional[str] = None
    ) -> List[GA4Alert]:
        """Get GA4 alert history.

        Args:
            hours: Number of hours to look back
            severity_filter: Optional severity level filter

        Returns:
            List of historical alerts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_alerts = [
            alert for alert in self._alert_history if alert.triggered_at >= cutoff_time
        ]

        if severity_filter:
            filtered_alerts = [
                alert
                for alert in filtered_alerts
                if alert.threshold.alert_severity == severity_filter
            ]

        return sorted(filtered_alerts, key=lambda a: a.triggered_at, reverse=True)

    def add_custom_threshold(self, threshold: GA4AlertThreshold) -> None:
        """Add a custom alert threshold.

        Args:
            threshold: Custom threshold configuration
        """
        self.thresholds.append(threshold)
        logger.info(
            f"Added custom GA4 alert threshold: {threshold.metric_name} "
            f"{threshold.comparison_operator} {threshold.threshold_value}"
        )

    def remove_threshold(self, metric_name: str, threshold_value: float) -> bool:
        """Remove an alert threshold.

        Args:
            metric_name: Name of the metric
            threshold_value: Threshold value to remove

        Returns:
            True if threshold was removed, False if not found
        """
        original_count = len(self.thresholds)
        self.thresholds = [
            threshold
            for threshold in self.thresholds
            if not (
                threshold.metric_name == metric_name
                and threshold.threshold_value == threshold_value
            )
        ]

        removed = len(self.thresholds) < original_count
        if removed:
            logger.info(f"Removed GA4 threshold: {metric_name} {threshold_value}")

        return removed

    def disable_threshold(self, metric_name: str, threshold_value: float) -> bool:
        """Disable an alert threshold.

        Args:
            metric_name: Name of the metric
            threshold_value: Threshold value to disable

        Returns:
            True if threshold was found and disabled
        """
        for threshold in self.thresholds:
            if (
                threshold.metric_name == metric_name
                and threshold.threshold_value == threshold_value
            ):
                threshold.enabled = False
                logger.info(f"Disabled GA4 threshold: {metric_name} {threshold_value}")
                return True

        return False

    async def start_monitoring(self, check_interval_minutes: int = 5) -> None:
        """Start continuous GA4 alerts monitoring.

        Args:
            check_interval_minutes: Interval between alert checks in minutes
        """
        logger.info(
            f"Starting GA4 alerts monitoring with {check_interval_minutes}min intervals"
        )

        while True:
            try:
                alerts = await self.check_realtime_alerts()

                if alerts:
                    logger.info(f"GA4 monitoring check triggered {len(alerts)} alerts")
                else:
                    logger.debug("GA4 monitoring check completed - no alerts")

                # Wait for next check
                await asyncio.sleep(check_interval_minutes * 60)

            except asyncio.CancelledError:
                logger.info("GA4 alerts monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in GA4 alerts monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary of GA4 alerts status.

        Returns:
            Alerts summary
        """
        active_alerts = self.get_active_alerts()
        recent_history = self.get_alert_history(hours=24)

        summary = {
            "property_id": self.config.property_id,
            "monitoring_enabled": self.config.enable_realtime_data,
            "active_alerts_count": len(active_alerts),
            "alerts_last_24h": len(recent_history),
            "threshold_count": len(self.thresholds),
            "enabled_thresholds": len([t for t in self.thresholds if t.enabled]),
            "last_check": max(self._last_check_times.values())
            if self._last_check_times
            else None,
        }

        # Add severity breakdown
        severity_counts = {}
        for alert in active_alerts:
            severity = alert.threshold.alert_severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        summary["active_alerts_by_severity"] = severity_counts

        # Add threshold status
        summary["thresholds"] = [
            {
                "metric": t.metric_name,
                "threshold": t.threshold_value,
                "operator": t.comparison_operator,
                "severity": t.alert_severity,
                "enabled": t.enabled,
            }
            for t in self.thresholds
        ]

        return summary

    async def test_alert_system(self) -> Dict[str, Any]:
        """Test the GA4 alert system functionality.

        Returns:
            Test results
        """
        results = {
            "ga4_api_connection": False,
            "alert_manager_available": self.alert_manager is not None,
            "thresholds_configured": len(self.thresholds) > 0,
            "test_timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Test GA4 API connection
            connection_success, connection_message = self.ga4_client.test_connection()
            results["ga4_api_connection"] = connection_success
            results["ga4_connection_message"] = connection_message

            # Test alert manager if available
            if self.alert_manager and ALERTS_AVAILABLE:
                test_alert = Alert(
                    message="GA4 alert system test",
                    alert_type=AlertType.INFO,
                    priority=AlertPriority.LOW,
                    source="ga4_test",
                    context={"test": True},
                )

                try:
                    await self.alert_manager.send_alert_async(test_alert)
                    results["alert_system_test"] = True
                    results["alert_test_message"] = "Test alert sent successfully"
                except Exception as e:
                    results["alert_system_test"] = False
                    results["alert_test_message"] = f"Test alert failed: {e}"

            # Validate thresholds
            threshold_validation = []
            for threshold in self.thresholds:
                validation = {
                    "metric": threshold.metric_name,
                    "valid": True,
                    "issues": [],
                }

                # Basic threshold validation
                if threshold.threshold_value < 0:
                    validation["valid"] = False
                    validation["issues"].append("Negative threshold value")

                if threshold.cooldown_minutes < 1:
                    validation["valid"] = False
                    validation["issues"].append("Cooldown too short")

                threshold_validation.append(validation)

            results["threshold_validation"] = threshold_validation
            results["overall_status"] = (
                "healthy"
                if all(
                    [
                        results["ga4_api_connection"],
                        results["alert_manager_available"],
                        results["thresholds_configured"],
                    ]
                )
                else "degraded"
            )

        except Exception as e:
            logger.error(f"GA4 alert system test failed: {e}")
            results["overall_status"] = "failed"
            results["error"] = str(e)

        return results

    def cleanup_old_alerts(self, days_to_keep: int = 7) -> int:
        """Clean up old alert history.

        Args:
            days_to_keep: Number of days of history to retain

        Returns:
            Number of alerts cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)

        original_count = len(self._alert_history)
        self._alert_history = [
            alert for alert in self._alert_history if alert.triggered_at >= cutoff_time
        ]

        cleaned_count = original_count - len(self._alert_history)

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old GA4 alerts")

        return cleaned_count

    def get_threshold_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for alert thresholds.

        Returns:
            Threshold performance metrics
        """
        metrics = {}

        for threshold in self.thresholds:
            threshold_key = f"{threshold.metric_name}_{threshold.threshold_value}"

            # Count alerts for this threshold
            threshold_alerts = [
                alert
                for alert in self._alert_history
                if (
                    alert.threshold.metric_name == threshold.metric_name
                    and alert.threshold.threshold_value == threshold.threshold_value
                )
            ]

            # Calculate metrics
            total_alerts = len(threshold_alerts)
            recent_alerts = len(
                [
                    alert
                    for alert in threshold_alerts
                    if (datetime.utcnow() - alert.triggered_at).total_seconds()
                    < 86400  # Last 24h
                ]
            )

            avg_duration = None
            if threshold_alerts:
                resolved_alerts = [
                    alert for alert in threshold_alerts if alert.is_resolved
                ]
                if resolved_alerts:
                    durations = [
                        alert.duration_minutes
                        for alert in resolved_alerts
                        if alert.duration_minutes
                    ]
                    avg_duration = (
                        sum(durations) / len(durations) if durations else None
                    )

            metrics[threshold_key] = {
                "metric_name": threshold.metric_name,
                "threshold_value": threshold.threshold_value,
                "total_alerts_all_time": total_alerts,
                "alerts_last_24h": recent_alerts,
                "average_duration_minutes": avg_duration,
                "enabled": threshold.enabled,
                "severity": threshold.alert_severity,
            }

        return metrics
