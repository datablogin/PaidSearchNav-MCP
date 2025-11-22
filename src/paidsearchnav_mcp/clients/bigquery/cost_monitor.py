"""BigQuery cost monitoring and management."""

import logging
from typing import Any, Dict, List, Optional

from .cost_monitor_enhanced import EnhancedBigQueryCostMonitor

logger = logging.getLogger(__name__)


class BigQueryCostMonitor:
    """Monitors and manages BigQuery costs (legacy wrapper)."""

    def __init__(self, config, authenticator):
        """Initialize cost monitor."""
        self.config = config
        self.authenticator = authenticator

        # Initialize enhanced monitor for new features
        self._enhanced_monitor = EnhancedBigQueryCostMonitor(config, authenticator)

    async def get_daily_costs(
        self, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get BigQuery costs for the current day."""
        return await self._enhanced_monitor.get_daily_costs(customer_id)

    async def check_cost_alerts(
        self, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if cost alerts should be triggered."""
        return await self._enhanced_monitor.check_cost_alerts(customer_id)

    # === NEW ENHANCED METHODS ===

    async def get_real_time_costs(
        self, customer_id: Optional[str] = None, lookback_hours: int = 1
    ) -> Dict[str, Any]:
        """Get real-time BigQuery costs with <5 minute delay."""
        return await self._enhanced_monitor.get_real_time_costs(
            customer_id, lookback_hours
        )

    async def check_budget_enforcement(
        self, customer_id: str, additional_cost_usd: float = 0.0
    ) -> Dict[str, Any]:
        """Check budget limits and enforce controls."""
        return await self._enhanced_monitor.check_budget_enforcement(
            customer_id, additional_cost_usd
        )

    async def detect_unusual_patterns(
        self, customer_id: Optional[str] = None, lookback_days: int = 7
    ) -> List[Any]:
        """Detect unusual cost usage patterns."""
        return await self._enhanced_monitor.detect_unusual_patterns(
            customer_id, lookback_days
        )

    async def generate_cost_analytics(
        self, customer_id: Optional[str] = None, period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive cost analytics and insights."""
        return await self._enhanced_monitor.generate_cost_analytics(
            customer_id, period_days
        )

    async def get_cost_summary_report(
        self, customer_id: Optional[str] = None, report_type: str = "weekly"
    ) -> Dict[str, Any]:
        """Generate automated cost summary reports."""
        return await self._enhanced_monitor.get_cost_summary_report(
            customer_id, report_type
        )

    async def set_customer_budget(
        self,
        customer_id: str,
        tier: str,
        daily_limit_usd: float,
        monthly_limit_usd: float,
        emergency_limit_usd: Optional[float] = None,
        thresholds: Optional[List[Any]] = None,
    ) -> Any:
        """Set or update customer budget configuration."""
        return await self._enhanced_monitor.set_customer_budget(
            customer_id,
            tier,
            daily_limit_usd,
            monthly_limit_usd,
            emergency_limit_usd,
            thresholds,
        )

    async def get_customer_budgets(self) -> Dict[str, Any]:
        """Get all customer budget configurations."""
        return await self._enhanced_monitor.get_customer_budgets()
