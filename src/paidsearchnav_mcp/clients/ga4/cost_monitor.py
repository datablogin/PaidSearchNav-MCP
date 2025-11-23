"""GA4 API cost monitoring and quota management.

This module provides cost monitoring for GA4 Data API usage,
integrating with the existing BigQuery cost monitoring system.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from paidsearchnav_mcp.core.config import GA4Config
from paidsearchnav_mcp.platforms.ga4.models import GA4CostEstimate, GA4QuotaUsage

try:
    from paidsearchnav_mcp.alerts.manager import AlertManager, get_alert_manager
    from paidsearchnav_mcp.alerts.models import AlertPriority, AlertType

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


class GA4CostThreshold(BaseModel):
    """GA4 API cost threshold configuration."""

    percentage: float = Field(
        ..., ge=0, le=100, description="Percentage of daily budget"
    )
    priority: str = Field(..., description="Alert priority")
    action: str = Field(..., description="Recommended action")


class GA4CostMonitor:
    """Monitor GA4 API costs and quota usage."""

    # Default cost per request estimate (GA4 Data API pricing)
    COST_PER_REQUEST = 0.0001  # $0.0001 per request

    # Default quota thresholds
    DEFAULT_THRESHOLDS = [
        GA4CostThreshold(
            percentage=50.0,
            priority=AlertPriority.LOW,
            action="Monitor usage - approaching half of daily budget",
        ),
        GA4CostThreshold(
            percentage=80.0,
            priority=AlertPriority.MEDIUM,
            action="Review API usage - 80% of daily budget consumed",
        ),
        GA4CostThreshold(
            percentage=95.0,
            priority=AlertPriority.HIGH,
            action="Immediate action required - near daily budget limit",
        ),
        GA4CostThreshold(
            percentage=100.0,
            priority=AlertPriority.CRITICAL,
            action="Daily budget exceeded - API usage should be paused",
        ),
    ]

    def __init__(self, config: GA4Config, alert_manager: Optional[AlertManager] = None):
        """Initialize GA4 cost monitor.

        Args:
            config: GA4 configuration
            alert_manager: Optional alert manager for notifications
        """
        self.config = config
        self.alert_manager = alert_manager or (
            get_alert_manager() if ALERTS_AVAILABLE else None
        )

        # Quota tracking
        self._quota_usage: Dict[str, GA4QuotaUsage] = {}
        self._cost_estimates: Dict[str, GA4CostEstimate] = {}
        self._last_alert_times: Dict[str, datetime] = {}

        # Cost estimation settings
        self.cost_per_request = self.COST_PER_REQUEST

    def track_request(self, property_id: str, request_type: str = "standard") -> None:
        """Track a GA4 API request for cost and quota monitoring.

        Args:
            property_id: GA4 property ID
            request_type: Type of request (standard, realtime, batch)
        """
        current_time = datetime.utcnow()

        # Update quota usage
        if property_id not in self._quota_usage:
            self._quota_usage[property_id] = GA4QuotaUsage(
                property_id=property_id, last_reset_time=current_time
            )

        quota = self._quota_usage[property_id]

        # Reset counters if we've passed midnight
        if current_time.date() > quota.last_reset_time.date():
            quota.requests_today = 0
            quota.last_reset_time = current_time

        # Reset hourly counter
        if (current_time - quota.last_reset_time).total_seconds() >= 3600:
            quota.requests_this_hour = 0

        # Reset minute counter
        if (current_time - quota.last_reset_time).total_seconds() >= 60:
            quota.requests_this_minute = 0

        # Increment counters
        quota.requests_today += 1
        quota.requests_this_hour += 1
        quota.requests_this_minute += 1

        # Update cost estimate
        quota.estimated_cost_usd = quota.requests_today * self.cost_per_request

        # Store updated cost estimate
        if property_id not in self._cost_estimates:
            self._cost_estimates[property_id] = GA4CostEstimate(
                property_id=property_id,
                period_start=current_time.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )

        cost_estimate = self._cost_estimates[property_id]
        cost_estimate.requests_count = quota.requests_today
        cost_estimate.estimated_cost_usd = quota.estimated_cost_usd
        cost_estimate.period_end = current_time

        # Check for threshold violations
        self._check_cost_thresholds(property_id, quota)

        logger.debug(
            f"GA4 request tracked for property {property_id}: "
            f"Daily: {quota.requests_today}, Cost: ${quota.estimated_cost_usd:.4f}"
        )

    def get_quota_status(self, property_id: str) -> Optional[GA4QuotaUsage]:
        """Get current quota usage for a property.

        Args:
            property_id: GA4 property ID

        Returns:
            Current quota usage or None if not tracked
        """
        return self._quota_usage.get(property_id)

    def get_cost_estimate(self, property_id: str) -> Optional[GA4CostEstimate]:
        """Get current cost estimate for a property.

        Args:
            property_id: GA4 property ID

        Returns:
            Current cost estimate or None if not tracked
        """
        return self._cost_estimates.get(property_id)

    def is_within_budget(self, property_id: str) -> bool:
        """Check if current usage is within budget.

        Args:
            property_id: GA4 property ID

        Returns:
            True if within budget, False otherwise
        """
        quota = self._quota_usage.get(property_id)
        if not quota:
            return True

        return quota.estimated_cost_usd < self.config.daily_cost_limit_usd

    def get_remaining_budget(self, property_id: str) -> float:
        """Get remaining budget for today.

        Args:
            property_id: GA4 property ID

        Returns:
            Remaining budget in USD
        """
        quota = self._quota_usage.get(property_id)
        if not quota:
            return self.config.daily_cost_limit_usd

        return max(0.0, self.config.daily_cost_limit_usd - quota.estimated_cost_usd)

    def get_projected_daily_cost(self, property_id: str) -> float:
        """Get projected daily cost based on current usage.

        Args:
            property_id: GA4 property ID

        Returns:
            Projected daily cost in USD
        """
        cost_estimate = self._cost_estimates.get(property_id)
        if not cost_estimate:
            return 0.0

        return cost_estimate.daily_projected_cost

    def should_throttle_requests(self, property_id: str) -> bool:
        """Check if requests should be throttled due to budget constraints.

        Args:
            property_id: GA4 property ID

        Returns:
            True if requests should be throttled
        """
        if not self.config.enable_cost_monitoring:
            return False

        quota = self._quota_usage.get(property_id)
        if not quota:
            return False

        # Throttle if approaching daily limits
        return (
            quota.is_approaching_daily_limit
            or quota.estimated_cost_usd >= self.config.cost_alert_threshold_usd
        )

    def get_monitoring_summary(self, property_id: str) -> Dict[str, Any]:
        """Get comprehensive monitoring summary.

        Args:
            property_id: GA4 property ID

        Returns:
            Monitoring summary
        """
        quota = self._quota_usage.get(property_id)
        cost_estimate = self._cost_estimates.get(property_id)

        if not quota or not cost_estimate:
            return {
                "property_id": property_id,
                "status": "no_data",
                "message": "No usage data available",
            }

        return {
            "property_id": property_id,
            "status": "within_budget"
            if self.is_within_budget(property_id)
            else "over_budget",
            "quota_usage": {
                "requests_today": quota.requests_today,
                "requests_this_hour": quota.requests_this_hour,
                "approaching_daily_limit": quota.is_approaching_daily_limit,
                "approaching_hourly_limit": quota.is_approaching_hourly_limit,
            },
            "cost_analysis": {
                "estimated_cost_today": quota.estimated_cost_usd,
                "daily_budget": self.config.daily_cost_limit_usd,
                "remaining_budget": self.get_remaining_budget(property_id),
                "projected_daily_cost": cost_estimate.daily_projected_cost,
                "budget_utilization_percentage": (
                    (quota.estimated_cost_usd / self.config.daily_cost_limit_usd) * 100
                    if self.config.daily_cost_limit_usd > 0
                    else 0
                ),
            },
            "recommendations": self._generate_cost_recommendations(property_id),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _check_cost_thresholds(self, property_id: str, quota: GA4QuotaUsage) -> None:
        """Check cost thresholds and trigger alerts if needed.

        Args:
            property_id: GA4 property ID
            quota: Current quota usage
        """
        if not self.config.enable_cost_monitoring:
            return

        current_percentage = (
            (quota.estimated_cost_usd / self.config.daily_cost_limit_usd) * 100
            if self.config.daily_cost_limit_usd > 0
            else 0
        )

        # Check each threshold
        for threshold in self.DEFAULT_THRESHOLDS:
            if current_percentage >= threshold.percentage:
                alert_key = f"ga4_cost_{property_id}_{threshold.percentage}"

                # Check if we've already alerted recently (cooldown)
                last_alert = self._last_alert_times.get(alert_key)
                if (
                    last_alert
                    and (datetime.utcnow() - last_alert).total_seconds() < 3600
                ):  # 1 hour cooldown
                    continue

                # Send alert
                self._send_cost_alert(property_id, threshold, current_percentage, quota)
                self._last_alert_times[alert_key] = datetime.utcnow()

    def _send_cost_alert(
        self,
        property_id: str,
        threshold: GA4CostThreshold,
        current_percentage: float,
        quota: GA4QuotaUsage,
    ) -> None:
        """Send cost threshold alert.

        Args:
            property_id: GA4 property ID
            threshold: Triggered threshold
            current_percentage: Current cost percentage
            quota: Current quota usage
        """
        if not self.alert_manager:
            logger.warning(
                f"GA4 cost alert triggered for property {property_id} "
                f"({current_percentage:.1f}% of budget) but no alert manager available"
            )
            return

        message = (
            f"GA4 API cost alert for property {property_id}: "
            f"{current_percentage:.1f}% of daily budget consumed "
            f"(${quota.estimated_cost_usd:.2f} of ${self.config.daily_cost_limit_usd:.2f}). "
            f"Action required: {threshold.action}"
        )

        try:
            self.alert_manager.send_alert(
                message=message,
                alert_type=AlertType.WARNING,
                priority=threshold.priority,
                context={
                    "property_id": property_id,
                    "cost_percentage": current_percentage,
                    "estimated_cost": quota.estimated_cost_usd,
                    "daily_limit": self.config.daily_cost_limit_usd,
                    "requests_today": quota.requests_today,
                    "threshold_percentage": threshold.percentage,
                },
            )

            logger.warning(f"GA4 cost alert sent: {message}")

        except Exception as e:
            logger.error(f"Failed to send GA4 cost alert: {e}")

    def _generate_cost_recommendations(self, property_id: str) -> List[Dict[str, str]]:
        """Generate cost optimization recommendations.

        Args:
            property_id: GA4 property ID

        Returns:
            List of cost recommendations
        """
        recommendations = []
        quota = self._quota_usage.get(property_id)
        cost_estimate = self._cost_estimates.get(property_id)

        if not quota or not cost_estimate:
            return recommendations

        # High usage recommendations
        if quota.is_approaching_daily_limit:
            recommendations.append(
                {
                    "type": "quota_optimization",
                    "priority": "high",
                    "title": "Optimize GA4 API Usage",
                    "description": (
                        f"Approaching daily quota limit with {quota.requests_today} requests. "
                        "Consider caching and batch operations."
                    ),
                    "action": "Enable response caching and reduce API call frequency",
                }
            )

        # Cost efficiency recommendations
        if cost_estimate.daily_projected_cost > self.config.daily_cost_limit_usd * 1.2:
            recommendations.append(
                {
                    "type": "cost_optimization",
                    "priority": "medium",
                    "title": "Reduce API Costs",
                    "description": (
                        f"Projected daily cost (${cost_estimate.daily_projected_cost:.2f}) "
                        f"exceeds budget (${self.config.daily_cost_limit_usd:.2f})"
                    ),
                    "action": "Optimize query frequency and implement intelligent caching",
                }
            )

        # Real-time usage recommendations
        if quota.requests_this_hour > 2000:  # Conservative hourly limit
            recommendations.append(
                {
                    "type": "rate_limiting",
                    "priority": "medium",
                    "title": "High Hourly Usage Detected",
                    "description": f"High API usage this hour: {quota.requests_this_hour} requests",
                    "action": "Consider implementing request batching and rate limiting",
                }
            )

        return recommendations

    def reset_daily_usage(self, property_id: str) -> None:
        """Reset daily usage counters for a property.

        Args:
            property_id: GA4 property ID
        """
        if property_id in self._quota_usage:
            quota = self._quota_usage[property_id]
            quota.requests_today = 0
            quota.estimated_cost_usd = 0.0
            quota.last_reset_time = datetime.utcnow()

        if property_id in self._cost_estimates:
            current_time = datetime.utcnow()
            self._cost_estimates[property_id] = GA4CostEstimate(
                property_id=property_id,
                period_start=current_time.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
                period_end=current_time,
                cost_per_request=self.cost_per_request,
            )

        logger.info(f"Reset daily usage for GA4 property {property_id}")

    def get_all_properties_status(self) -> Dict[str, Dict[str, Any]]:
        """Get cost monitoring status for all tracked properties.

        Returns:
            Dictionary mapping property IDs to their monitoring status
        """
        return {
            property_id: self.get_monitoring_summary(property_id)
            for property_id in self._quota_usage.keys()
        }

    def export_usage_report(self, property_id: str, days: int = 7) -> Dict[str, Any]:
        """Export usage report for the specified period.

        Args:
            property_id: GA4 property ID
            days: Number of days to include in report

        Returns:
            Usage report data
        """
        quota = self._quota_usage.get(property_id)
        cost_estimate = self._cost_estimates.get(property_id)

        if not quota or not cost_estimate:
            return {"property_id": property_id, "error": "No usage data available"}

        report = {
            "property_id": property_id,
            "report_period_days": days,
            "current_usage": {
                "requests_today": quota.requests_today,
                "estimated_cost_today": quota.estimated_cost_usd,
                "quota_utilization": {
                    "daily_percentage": (
                        (quota.requests_today / 100000)
                        * 100  # 100k default daily quota
                    ),
                    "approaching_limits": {
                        "daily": quota.is_approaching_daily_limit,
                        "hourly": quota.is_approaching_hourly_limit,
                    },
                },
            },
            "cost_analysis": {
                "cost_per_request": self.cost_per_request,
                "daily_budget": self.config.daily_cost_limit_usd,
                "budget_remaining": self.get_remaining_budget(property_id),
                "projected_monthly_cost": cost_estimate.daily_projected_cost * 30,
            },
            "recommendations": self._generate_cost_recommendations(property_id),
            "generated_at": datetime.utcnow().isoformat(),
        }

        return report

    def set_custom_cost_per_request(self, cost_per_request: float) -> None:
        """Set custom cost per request for more accurate monitoring.

        Args:
            cost_per_request: Cost per API request in USD
        """
        if cost_per_request < 0:
            raise ValueError("Cost per request must be non-negative")

        self.cost_per_request = cost_per_request
        logger.info(f"Updated GA4 cost per request to ${cost_per_request:.6f}")

    def validate_budget_configuration(self) -> Dict[str, Any]:
        """Validate budget and cost monitoring configuration.

        Returns:
            Validation results
        """
        validation = {
            "status": "valid",
            "warnings": [],
            "errors": [],
            "configuration": {
                "cost_monitoring_enabled": self.config.enable_cost_monitoring,
                "daily_budget": self.config.daily_cost_limit_usd,
                "alert_threshold": self.config.cost_alert_threshold_usd,
                "rate_limiting_enabled": self.config.enable_rate_limiting,
            },
        }

        # Validate budget settings
        if self.config.daily_cost_limit_usd <= 0:
            validation["errors"].append("Daily cost limit must be greater than 0")

        if self.config.cost_alert_threshold_usd >= self.config.daily_cost_limit_usd:
            validation["warnings"].append(
                "Cost alert threshold should be lower than daily limit"
            )

        # Validate monitoring capability
        if self.config.enable_cost_monitoring and not self.alert_manager:
            validation["warnings"].append(
                "Cost monitoring enabled but no alert manager available"
            )

        # Set overall status
        if validation["errors"]:
            validation["status"] = "invalid"
        elif validation["warnings"]:
            validation["status"] = "warning"

        return validation

    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """Clean up old monitoring data.

        Args:
            days_to_keep: Number of days of data to retain
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # Clean up old alert times
        old_alert_keys = [
            key
            for key, timestamp in self._last_alert_times.items()
            if timestamp < cutoff_date
        ]

        for key in old_alert_keys:
            del self._last_alert_times[key]

        logger.info(f"Cleaned up {len(old_alert_keys)} old GA4 cost monitoring entries")
