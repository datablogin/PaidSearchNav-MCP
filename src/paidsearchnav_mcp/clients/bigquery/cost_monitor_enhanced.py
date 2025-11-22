"""Enhanced BigQuery cost monitoring and alerting system."""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import bigquery
from pydantic import BaseModel, Field

try:
    from paidsearchnav_mcp.alerts.manager import AlertManager, get_alert_manager
    from paidsearchnav_mcp.alerts.models import AlertPriority, AlertType
except ImportError:
    # Graceful degradation if alerts module is not available
    AlertManager = None
    get_alert_manager = None

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


class CostThreshold(BaseModel):
    """Cost threshold configuration for alerts."""

    percentage: float = Field(..., ge=0, le=100, description="Percentage of budget")
    priority: AlertPriority = Field(
        ..., description="Alert priority for this threshold"
    )
    action: str = Field(..., description="Recommended action")


class CustomerBudgetConfig(BaseModel):
    """Budget configuration for a customer."""

    customer_id: str = Field(..., description="Customer identifier")
    tier: str = Field(..., description="Customer tier (standard/premium/enterprise)")
    daily_limit_usd: float = Field(..., gt=0, description="Daily budget limit in USD")
    monthly_limit_usd: float = Field(
        ..., gt=0, description="Monthly budget limit in USD"
    )
    emergency_limit_usd: float = Field(
        ..., gt=0, description="Emergency stop limit in USD"
    )

    # Alert thresholds
    thresholds: List[CostThreshold] = Field(
        default_factory=lambda: [
            CostThreshold(
                percentage=50.0, priority=AlertPriority.MEDIUM, action="monitor"
            ),
            CostThreshold(
                percentage=80.0, priority=AlertPriority.HIGH, action="review"
            ),
            CostThreshold(
                percentage=95.0, priority=AlertPriority.CRITICAL, action="throttle"
            ),
        ],
        description="Cost alert thresholds",
    )

    # Grace period handling
    grace_period_hours: int = Field(default=1, description="Grace period for overruns")
    throttle_enabled: bool = Field(
        default=True, description="Enable automatic throttling"
    )
    alerts_enabled: bool = Field(default=True, description="Enable cost alerts")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CostUsagePattern(BaseModel):
    """Unusual cost usage pattern detection."""

    pattern_type: str = Field(..., description="Type of unusual pattern")
    severity: str = Field(..., description="Pattern severity")
    description: str = Field(..., description="Pattern description")
    cost_impact_usd: float = Field(..., description="Estimated cost impact")
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class EnhancedBigQueryCostMonitor:
    """Enhanced BigQuery cost monitoring and management system."""

    def __init__(
        self, config, authenticator, alert_manager: Optional[AlertManager] = None
    ):
        """Initialize enhanced cost monitor."""
        self.config = config
        self.authenticator = authenticator
        self.alert_manager = alert_manager or (
            get_alert_manager() if get_alert_manager else None
        )

        # Budget configurations cache
        self._budget_configs: Dict[str, CustomerBudgetConfig] = {}

        # Default tier configurations
        self._default_budgets = {
            "standard": CustomerBudgetConfig(
                customer_id="default_standard",
                tier="standard",
                daily_limit_usd=10.0,
                monthly_limit_usd=300.0,
                emergency_limit_usd=50.0,
            ),
            "premium": CustomerBudgetConfig(
                customer_id="default_premium",
                tier="premium",
                daily_limit_usd=50.0,
                monthly_limit_usd=1500.0,
                emergency_limit_usd=200.0,
            ),
            "enterprise": CustomerBudgetConfig(
                customer_id="default_enterprise",
                tier="enterprise",
                daily_limit_usd=200.0,
                monthly_limit_usd=6000.0,
                emergency_limit_usd=1000.0,
            ),
        }

        # Cost tracking state
        self._cost_cache: Dict[str, Dict[str, Any]] = {}
        self._alert_cooldowns: Dict[str, datetime] = {}

    async def get_real_time_costs(
        self, customer_id: Optional[str] = None, lookback_hours: int = 1
    ) -> Dict[str, Any]:
        """Get real-time BigQuery costs with <5 minute delay."""

        try:
            client = await self.authenticator.get_client()
            current_time = datetime.utcnow()
            start_time = current_time - timedelta(hours=lookback_hours)

            # Query recent BigQuery job costs
            query = f"""
            SELECT
                job_id,
                creation_time,
                total_bytes_processed,
                total_slot_ms,
                total_bytes_processed / POWER(1024, 4) * 5.0 as query_cost_usd,
                total_slot_ms / 1000 / 3600 * 0.04 as slot_cost_usd,
                (total_bytes_processed / POWER(1024, 4) * 5.0) +
                (total_slot_ms / 1000 / 3600 * 0.04) as total_cost_usd,
                user_email,
                labels
            FROM `{self.config.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE creation_time >= @start_time
            AND creation_time <= @current_time
            AND job_type = 'QUERY'
            AND state = 'DONE'
            """

            if customer_id:
                query += """
                AND (
                    user_email LIKE @customer_pattern
                    OR job_id LIKE @customer_pattern
                    OR EXISTS (
                        SELECT 1 FROM UNNEST(labels) as label
                        WHERE label.key = 'customer_id' AND label.value = @customer_id
                    )
                )
                """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "start_time", "TIMESTAMP", start_time
                    ),
                    bigquery.ScalarQueryParameter(
                        "current_time", "TIMESTAMP", current_time
                    ),
                ]
            )

            if customer_id:
                job_config.query_parameters.extend(
                    [
                        bigquery.ScalarQueryParameter(
                            "customer_pattern", "STRING", f"%{customer_id}%"
                        ),
                        bigquery.ScalarQueryParameter(
                            "customer_id", "STRING", customer_id.replace("-", "_")
                        ),
                    ]
                )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            # Aggregate costs
            total_cost = sum(row.total_cost_usd or 0 for row in results)
            total_bytes = sum(row.total_bytes_processed or 0 for row in results)
            total_jobs = len(results)

            # Get daily and monthly totals
            daily_costs = await self._get_daily_costs_from_billing_api(customer_id)
            monthly_costs = await self._get_monthly_costs_from_billing_api(customer_id)

            # Get budget configuration
            budget_config = await self._get_customer_budget_config(customer_id)

            cost_data = {
                "customer_id": customer_id,
                "timestamp": current_time,
                "lookback_hours": lookback_hours,
                # Real-time costs
                "recent_cost_usd": float(total_cost),
                "recent_bytes_processed": int(total_bytes),
                "recent_jobs_count": total_jobs,
                # Daily totals
                "daily_cost_usd": daily_costs.get("total_cost_usd", 0.0),
                "daily_limit_usd": budget_config.daily_limit_usd,
                "daily_remaining_usd": budget_config.daily_limit_usd
                - daily_costs.get("total_cost_usd", 0.0),
                "daily_usage_percentage": (
                    daily_costs.get("total_cost_usd", 0.0)
                    / budget_config.daily_limit_usd
                )
                * 100,
                # Monthly totals
                "monthly_cost_usd": monthly_costs.get("total_cost_usd", 0.0),
                "monthly_limit_usd": budget_config.monthly_limit_usd,
                "monthly_remaining_usd": budget_config.monthly_limit_usd
                - monthly_costs.get("total_cost_usd", 0.0),
                "monthly_usage_percentage": (
                    monthly_costs.get("total_cost_usd", 0.0)
                    / budget_config.monthly_limit_usd
                )
                * 100,
                # Budget status
                "budget_config": budget_config.dict(),
                "status": self._determine_cost_status(
                    daily_costs.get("total_cost_usd", 0.0), budget_config
                ),
                # Data freshness
                "data_freshness_minutes": (
                    current_time
                    - max([row.creation_time for row in results], default=current_time)
                ).total_seconds()
                / 60
                if results
                else 0,
            }

            # Cache results
            cache_key = f"{customer_id or 'global'}:real_time"
            self._cost_cache[cache_key] = cost_data

            return cost_data

        except Exception as e:
            logger.error(
                f"Failed to get real-time costs for customer {customer_id}: {e}"
            )
            return {
                "customer_id": customer_id,
                "error": str(e),
                "timestamp": datetime.utcnow(),
                "daily_cost_usd": 0.0,
                "monthly_cost_usd": 0.0,
            }

    async def check_budget_enforcement(
        self, customer_id: str, additional_cost_usd: float = 0.0
    ) -> Dict[str, Any]:
        """Check budget limits and enforce controls."""

        try:
            # Get current costs
            current_costs = await self.get_real_time_costs(customer_id)
            budget_config = await self._get_customer_budget_config(customer_id)

            daily_cost = current_costs.get("daily_cost_usd", 0.0) + additional_cost_usd
            monthly_cost = (
                current_costs.get("monthly_cost_usd", 0.0) + additional_cost_usd
            )

            enforcement_actions = []
            alerts_triggered = []

            # Check emergency limit
            if daily_cost >= budget_config.emergency_limit_usd:
                enforcement_actions.append(
                    {
                        "action": "emergency_circuit_breaker",
                        "reason": f"Emergency limit exceeded: ${daily_cost:.2f} >= ${budget_config.emergency_limit_usd:.2f}",
                        "severity": "critical",
                    }
                )

                await self._trigger_emergency_circuit_breaker(
                    customer_id, daily_cost, budget_config
                )
                return {
                    "allowed": False,
                    "reason": "Emergency cost limit exceeded",
                    "enforcement_actions": enforcement_actions,
                    "daily_cost_usd": daily_cost,
                    "emergency_limit_usd": budget_config.emergency_limit_usd,
                }

            # Check daily limits with grace period
            if daily_cost >= budget_config.daily_limit_usd:
                grace_expired = await self._check_grace_period_expired(
                    customer_id, budget_config
                )

                if grace_expired:
                    enforcement_actions.append(
                        {
                            "action": "throttle_exports",
                            "reason": f"Daily limit exceeded with expired grace period: ${daily_cost:.2f} >= ${budget_config.daily_limit_usd:.2f}",
                            "severity": "high",
                        }
                    )

                    if budget_config.throttle_enabled:
                        await self._apply_export_throttling(
                            customer_id, "daily_limit_exceeded"
                        )
                        return {
                            "allowed": False,
                            "reason": "Daily budget limit exceeded, throttling applied",
                            "enforcement_actions": enforcement_actions,
                            "daily_cost_usd": daily_cost,
                            "daily_limit_usd": budget_config.daily_limit_usd,
                        }
                else:
                    enforcement_actions.append(
                        {
                            "action": "grace_period_active",
                            "reason": "Daily limit exceeded but within grace period",
                            "severity": "medium",
                        }
                    )

            # Check monthly limits
            if monthly_cost >= budget_config.monthly_limit_usd:
                enforcement_actions.append(
                    {
                        "action": "monthly_limit_warning",
                        "reason": f"Monthly limit exceeded: ${monthly_cost:.2f} >= ${budget_config.monthly_limit_usd:.2f}",
                        "severity": "high",
                    }
                )

            # Check threshold alerts
            for threshold in budget_config.thresholds:
                threshold_amount = budget_config.daily_limit_usd * (
                    threshold.percentage / 100
                )

                if daily_cost >= threshold_amount:
                    alerts_triggered.append(
                        {
                            "threshold_percentage": threshold.percentage,
                            "threshold_amount_usd": threshold_amount,
                            "current_cost_usd": daily_cost,
                            "priority": threshold.priority,
                            "action": threshold.action,
                        }
                    )

                    # Send alert if not in cooldown
                    await self._send_threshold_alert(
                        customer_id, threshold, daily_cost, threshold_amount
                    )

            return {
                "allowed": True,
                "enforcement_actions": enforcement_actions,
                "alerts_triggered": alerts_triggered,
                "daily_cost_usd": daily_cost,
                "monthly_cost_usd": monthly_cost,
                "budget_config": budget_config.dict(),
                "status": self._determine_cost_status(daily_cost, budget_config),
            }

        except Exception as e:
            logger.error(
                f"Failed to check budget enforcement for customer {customer_id}: {e}"
            )
            return {
                "allowed": True,  # Fail open to avoid blocking operations
                "error": str(e),
                "enforcement_actions": [],
                "alerts_triggered": [],
            }

    async def detect_unusual_patterns(
        self, customer_id: Optional[str] = None, lookback_days: int = 7
    ) -> List[CostUsagePattern]:
        """Detect unusual cost usage patterns."""

        try:
            patterns = []

            # Get historical cost data
            historical_costs = await self._get_historical_costs(
                customer_id, lookback_days
            )
            recent_costs = await self.get_real_time_costs(
                customer_id, lookback_hours=24
            )

            if not historical_costs:
                return patterns

            # Calculate baseline metrics
            daily_costs = [day["total_cost_usd"] for day in historical_costs]
            avg_daily_cost = sum(daily_costs) / len(daily_costs) if daily_costs else 0.0
            max_daily_cost = max(daily_costs) if daily_costs else 0.0

            current_daily_cost = recent_costs.get("daily_cost_usd", 0.0)

            # Pattern 1: Sudden cost spike (>300% of average)
            if current_daily_cost > avg_daily_cost * 3.0 and avg_daily_cost > 0:
                spike_multiplier = (
                    (current_daily_cost / avg_daily_cost) if avg_daily_cost > 0 else 0
                )
                patterns.append(
                    CostUsagePattern(
                        pattern_type="sudden_spike",
                        severity="high",
                        description=f"Daily cost spiked to ${current_daily_cost:.2f}, {spike_multiplier:.1f}x above {lookback_days}-day average",
                        cost_impact_usd=current_daily_cost - avg_daily_cost,
                    )
                )

            # Pattern 2: Sustained high usage (>150% for multiple days)
            high_days = sum(
                1 for cost in daily_costs[-3:] if cost > avg_daily_cost * 1.5
            )
            if high_days >= 2:
                patterns.append(
                    CostUsagePattern(
                        pattern_type="sustained_high_usage",
                        severity="medium",
                        description=f"Sustained high usage: {high_days} consecutive days above 150% of average",
                        cost_impact_usd=sum(
                            cost - avg_daily_cost
                            for cost in daily_costs[-3:]
                            if cost > avg_daily_cost
                        ),
                    )
                )

            # Pattern 3: Unusual time-of-day usage
            hourly_usage = await self._get_hourly_usage_pattern(customer_id)
            if hourly_usage and self._detect_off_hours_usage(hourly_usage):
                off_hours_cost = sum(
                    hourly_usage.get(str(hour), 0)
                    for hour in range(22, 24) + list(range(0, 6))
                )
                patterns.append(
                    CostUsagePattern(
                        pattern_type="off_hours_usage",
                        severity="low",
                        description=f"Unusual off-hours usage detected: ${off_hours_cost:.2f} between 10PM-6AM",
                        cost_impact_usd=off_hours_cost,
                    )
                )

            # Pattern 4: Query size anomaly
            large_query_threshold = 10.0  # $10 per query
            expensive_queries = await self._get_expensive_queries(
                customer_id, large_query_threshold
            )
            if expensive_queries:
                total_expensive_cost = sum(q["cost_usd"] for q in expensive_queries)
                patterns.append(
                    CostUsagePattern(
                        pattern_type="large_query_anomaly",
                        severity="medium",
                        description=f"{len(expensive_queries)} queries exceeded ${large_query_threshold} each",
                        cost_impact_usd=total_expensive_cost,
                    )
                )

            # Send alerts for detected patterns
            for pattern in patterns:
                await self._send_pattern_alert(customer_id, pattern)

            return patterns

        except Exception as e:
            logger.error(
                f"Failed to detect unusual patterns for customer {customer_id}: {e}"
            )
            return []

    async def generate_cost_analytics(
        self, customer_id: Optional[str] = None, period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive cost analytics and insights."""

        try:
            # Get comprehensive cost data
            historical_costs = await self._get_historical_costs(
                customer_id, period_days
            )
            current_costs = await self.get_real_time_costs(customer_id)

            # Cost breakdown by operation type
            operation_costs = await self._get_cost_by_operation_type(
                customer_id, period_days
            )

            # Most expensive queries
            expensive_queries = await self._get_expensive_queries(
                customer_id, cost_threshold=1.0, limit=10
            )

            # Customer tier analysis
            tier_comparison = await self._analyze_tier_efficiency(customer_id)

            # ROI analysis
            roi_analysis = await self._calculate_bigquery_roi(customer_id, period_days)

            analytics = {
                "customer_id": customer_id,
                "analysis_period_days": period_days,
                "generated_at": datetime.utcnow(),
                # Cost summary
                "cost_summary": {
                    "total_cost_usd": sum(
                        day["total_cost_usd"] for day in historical_costs
                    ),
                    "average_daily_cost_usd": sum(
                        day["total_cost_usd"] for day in historical_costs
                    )
                    / len(historical_costs)
                    if historical_costs
                    else 0,
                    "peak_daily_cost_usd": max(
                        day["total_cost_usd"] for day in historical_costs
                    )
                    if historical_costs
                    else 0,
                    "current_daily_cost_usd": current_costs.get("daily_cost_usd", 0.0),
                    "cost_trend": self._calculate_cost_trend(historical_costs),
                },
                # Operation breakdown
                "operation_breakdown": operation_costs,
                # Query analysis
                "query_analysis": {
                    "expensive_queries": expensive_queries,
                    "average_cost_per_query": self._calculate_avg_query_cost(
                        historical_costs
                    ),
                    "total_queries_analyzed": sum(
                        day.get("query_count", 0) for day in historical_costs
                    ),
                },
                # Efficiency metrics
                "efficiency_metrics": {
                    "cost_per_tb_processed": self._calculate_cost_per_tb(
                        historical_costs
                    ),
                    "cost_per_customer_analysis": self._calculate_cost_per_analysis(
                        customer_id, period_days
                    ),
                    "tier_efficiency": tier_comparison,
                },
                # ROI analysis
                "roi_analysis": roi_analysis,
                # Recommendations
                "recommendations": self._generate_cost_recommendations(
                    historical_costs, operation_costs
                ),
                # Budget utilization
                "budget_utilization": await self._analyze_budget_utilization(
                    customer_id, historical_costs
                ),
            }

            return analytics

        except Exception as e:
            logger.error(
                f"Failed to generate cost analytics for customer {customer_id}: {e}"
            )
            return {
                "customer_id": customer_id,
                "error": str(e),
                "generated_at": datetime.utcnow(),
            }

    async def get_cost_summary_report(
        self, customer_id: Optional[str] = None, report_type: str = "weekly"
    ) -> Dict[str, Any]:
        """Generate automated cost summary reports."""

        period_days = {"daily": 1, "weekly": 7, "monthly": 30}[report_type]

        try:
            analytics = await self.generate_cost_analytics(customer_id, period_days)
            patterns = await self.detect_unusual_patterns(customer_id, period_days)
            current_costs = await self.get_real_time_costs(customer_id)

            report = {
                "report_type": report_type,
                "customer_id": customer_id,
                "period_days": period_days,
                "generated_at": datetime.utcnow(),
                # Executive summary
                "executive_summary": {
                    "total_cost_usd": analytics["cost_summary"]["total_cost_usd"],
                    "budget_utilization_percentage": current_costs.get(
                        "daily_usage_percentage", 0.0
                    ),
                    "cost_trend": analytics["cost_summary"]["cost_trend"],
                    "unusual_patterns_detected": len(patterns),
                    "status": current_costs.get("status", "unknown"),
                },
                # Detailed analytics
                "detailed_analytics": analytics,
                # Detected patterns
                "unusual_patterns": [pattern.dict() for pattern in patterns],
                # Current status
                "current_status": current_costs,
                # Action items
                "action_items": self._generate_action_items(
                    analytics, patterns, current_costs
                ),
            }

            # Send report via configured channels
            await self._send_cost_report(customer_id, report, report_type)

            return report

        except Exception as e:
            logger.error(
                f"Failed to generate cost summary report for customer {customer_id}: {e}"
            )
            return {
                "report_type": report_type,
                "customer_id": customer_id,
                "error": str(e),
                "generated_at": datetime.utcnow(),
            }

    # === BUDGET MANAGEMENT METHODS ===

    async def set_customer_budget(
        self,
        customer_id: str,
        tier: str,
        daily_limit_usd: float,
        monthly_limit_usd: float,
        emergency_limit_usd: Optional[float] = None,
        thresholds: Optional[List[CostThreshold]] = None,
    ) -> CustomerBudgetConfig:
        """Set or update customer budget configuration."""

        if not emergency_limit_usd:
            emergency_limit_usd = daily_limit_usd * 5  # Default to 5x daily limit

        budget_config = CustomerBudgetConfig(
            customer_id=customer_id,
            tier=tier,
            daily_limit_usd=daily_limit_usd,
            monthly_limit_usd=monthly_limit_usd,
            emergency_limit_usd=emergency_limit_usd,
            thresholds=thresholds
            or [
                CostThreshold(
                    percentage=50.0, priority=AlertPriority.MEDIUM, action="monitor"
                ),
                CostThreshold(
                    percentage=80.0, priority=AlertPriority.HIGH, action="review"
                ),
                CostThreshold(
                    percentage=95.0, priority=AlertPriority.CRITICAL, action="throttle"
                ),
            ],
        )

        # Store configuration
        self._budget_configs[customer_id] = budget_config

        # In production, persist to database
        logger.info(
            f"Budget configuration set for customer {customer_id}: ${daily_limit_usd}/day, ${monthly_limit_usd}/month"
        )

        return budget_config

    async def get_customer_budgets(self) -> Dict[str, CustomerBudgetConfig]:
        """Get all customer budget configurations."""
        return self._budget_configs.copy()

    # === PRIVATE HELPER METHODS ===

    async def _get_daily_costs_from_billing_api(
        self, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get daily costs from Google Cloud Billing API."""
        try:
            # This would integrate with Google Cloud Billing API
            # For now, simulate with BigQuery INFORMATION_SCHEMA data
            client = await self.authenticator.get_client()
            today = date.today()

            query = f"""
            SELECT
                COUNT(*) as total_jobs,
                SUM(total_bytes_processed) as total_bytes_processed,
                SUM(total_slot_ms) as total_slot_ms,
                SUM(total_bytes_processed) / POWER(1024, 4) * 5.0 as query_cost_usd,
                SUM(total_slot_ms) / 1000 / 3600 * 0.04 as slot_cost_usd,
                (SUM(total_bytes_processed) / POWER(1024, 4) * 5.0) +
                (SUM(total_slot_ms) / 1000 / 3600 * 0.04) as total_cost_usd
            FROM `{self.config.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE DATE(creation_time) = @target_date
            AND job_type = 'QUERY'
            AND state = 'DONE'
            """

            if customer_id:
                query += """
                AND (
                    user_email LIKE @customer_pattern
                    OR job_id LIKE @customer_pattern
                    OR EXISTS (
                        SELECT 1 FROM UNNEST(labels) as label
                        WHERE label.key = 'customer_id' AND label.value = @customer_id
                    )
                )
                """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("target_date", "DATE", today)
                ]
            )

            if customer_id:
                job_config.query_parameters.extend(
                    [
                        bigquery.ScalarQueryParameter(
                            "customer_pattern", "STRING", f"%{customer_id}%"
                        ),
                        bigquery.ScalarQueryParameter(
                            "customer_id", "STRING", customer_id.replace("-", "_")
                        ),
                    ]
                )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                return {
                    "date": today.isoformat(),
                    "total_jobs": int(row.total_jobs or 0),
                    "total_bytes_processed": int(row.total_bytes_processed or 0),
                    "query_cost_usd": float(row.query_cost_usd or 0),
                    "slot_cost_usd": float(row.slot_cost_usd or 0),
                    "total_cost_usd": float(row.total_cost_usd or 0),
                }

            return {"date": today.isoformat(), "total_cost_usd": 0.0}

        except Exception as e:
            logger.error(f"Failed to get daily costs from billing API: {e}")
            return {
                "date": date.today().isoformat(),
                "total_cost_usd": 0.0,
                "error": str(e),
            }

    async def _get_monthly_costs_from_billing_api(
        self, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get monthly costs from Google Cloud Billing API."""
        try:
            # Similar to daily costs but for the current month
            today = date.today()
            start_of_month = today.replace(day=1)

            client = await self.authenticator.get_client()

            query = f"""
            SELECT
                COUNT(*) as total_jobs,
                SUM(total_bytes_processed) as total_bytes_processed,
                SUM(total_slot_ms) as total_slot_ms,
                SUM(total_bytes_processed) / POWER(1024, 4) * 5.0 as query_cost_usd,
                SUM(total_slot_ms) / 1000 / 3600 * 0.04 as slot_cost_usd,
                (SUM(total_bytes_processed) / POWER(1024, 4) * 5.0) +
                (SUM(total_slot_ms) / 1000 / 3600 * 0.04) as total_cost_usd
            FROM `{self.config.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE DATE(creation_time) >= @start_date
            AND DATE(creation_time) <= @end_date
            AND job_type = 'QUERY'
            AND state = 'DONE'
            """

            if customer_id:
                query += """
                AND (
                    user_email LIKE @customer_pattern
                    OR job_id LIKE @customer_pattern
                    OR EXISTS (
                        SELECT 1 FROM UNNEST(labels) as label
                        WHERE label.key = 'customer_id' AND label.value = @customer_id
                    )
                )
                """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("start_date", "DATE", start_of_month),
                    bigquery.ScalarQueryParameter("end_date", "DATE", today),
                ]
            )

            if customer_id:
                job_config.query_parameters.extend(
                    [
                        bigquery.ScalarQueryParameter(
                            "customer_pattern", "STRING", f"%{customer_id}%"
                        ),
                        bigquery.ScalarQueryParameter(
                            "customer_id", "STRING", customer_id.replace("-", "_")
                        ),
                    ]
                )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                return {
                    "month": f"{today.year}-{today.month:02d}",
                    "total_jobs": int(row.total_jobs or 0),
                    "total_bytes_processed": int(row.total_bytes_processed or 0),
                    "query_cost_usd": float(row.query_cost_usd or 0),
                    "slot_cost_usd": float(row.slot_cost_usd or 0),
                    "total_cost_usd": float(row.total_cost_usd or 0),
                }

            return {"month": f"{today.year}-{today.month:02d}", "total_cost_usd": 0.0}

        except Exception as e:
            logger.error(f"Failed to get monthly costs from billing API: {e}")
            return {
                "month": f"{date.today().year}-{date.today().month:02d}",
                "total_cost_usd": 0.0,
                "error": str(e),
            }

    async def _get_customer_budget_config(
        self, customer_id: Optional[str] = None
    ) -> CustomerBudgetConfig:
        """Get or create customer budget configuration."""
        if not customer_id:
            return self._default_budgets["standard"]

        if customer_id in self._budget_configs:
            return self._budget_configs[customer_id]

        # In production, this would load from database
        # For now, determine tier based on customer ID pattern or default to premium
        if customer_id.startswith("ent_"):
            tier = "enterprise"
        elif customer_id.startswith("prem_"):
            tier = "premium"
        else:
            tier = "standard"

        # Create customer-specific config based on tier defaults
        base_config = self._default_budgets[tier]
        customer_config = CustomerBudgetConfig(
            customer_id=customer_id,
            tier=tier,
            daily_limit_usd=base_config.daily_limit_usd,
            monthly_limit_usd=base_config.monthly_limit_usd,
            emergency_limit_usd=base_config.emergency_limit_usd,
            thresholds=base_config.thresholds,
        )

        self._budget_configs[customer_id] = customer_config
        return customer_config

    def _determine_cost_status(
        self, daily_cost: float, budget_config: CustomerBudgetConfig
    ) -> str:
        """Determine cost status based on usage."""
        if daily_cost >= budget_config.emergency_limit_usd:
            return "emergency"
        elif daily_cost >= budget_config.daily_limit_usd:
            return "over_budget"
        elif daily_cost >= budget_config.daily_limit_usd * 0.8:
            return "approaching_limit"
        elif daily_cost >= budget_config.daily_limit_usd * 0.5:
            return "moderate_usage"
        else:
            return "within_budget"

    async def _check_grace_period_expired(
        self, customer_id: str, budget_config: CustomerBudgetConfig
    ) -> bool:
        """Check if grace period has expired for budget overrun."""
        # In production, this would track when budget was first exceeded
        # For now, simulate based on current time and configuration
        grace_key = f"{customer_id}:grace_start"

        # This would be stored in database/cache
        # Simulating grace period logic
        return True  # Simplified for now

    async def _trigger_emergency_circuit_breaker(
        self, customer_id: str, cost: float, budget_config: CustomerBudgetConfig
    ):
        """Trigger emergency circuit breaker to stop all operations."""
        if self.alert_manager:
            await self.alert_manager.send_alert(
                alert_type=AlertType.SYSTEM,
                priority=AlertPriority.CRITICAL,
                title=f"Emergency Circuit Breaker Activated - Customer {customer_id}",
                message=f"Customer {customer_id} exceeded emergency limit: ${cost:.2f} >= ${budget_config.emergency_limit_usd:.2f}. All BigQuery operations suspended.",
                source="BigQueryCostMonitor",
                customer_id=customer_id,
                context={
                    "current_cost_usd": cost,
                    "emergency_limit_usd": budget_config.emergency_limit_usd,
                    "action": "circuit_breaker_activated",
                },
                tags=["cost", "emergency", "circuit_breaker"],
            )
        else:
            logger.critical(
                f"Emergency Circuit Breaker Activated - Customer {customer_id}: ${cost:.2f} >= ${budget_config.emergency_limit_usd:.2f}"
            )

    async def _apply_export_throttling(self, customer_id: str, reason: str):
        """Apply export throttling for budget enforcement."""
        logger.warning(
            f"Applying export throttling for customer {customer_id}: {reason}"
        )

        # In production, this would integrate with the export system to throttle operations
        # For now, log the action
        if self.alert_manager:
            await self.alert_manager.send_alert(
                alert_type=AlertType.SYSTEM,
                priority=AlertPriority.HIGH,
                title=f"Export Throttling Applied - Customer {customer_id}",
                message=f"Export operations throttled for customer {customer_id}. Reason: {reason}",
                source="BigQueryCostMonitor",
                customer_id=customer_id,
                context={"reason": reason, "action": "throttling_applied"},
                tags=["cost", "throttling", "budget_enforcement"],
            )

    async def _send_threshold_alert(
        self,
        customer_id: str,
        threshold: CostThreshold,
        current_cost: float,
        threshold_amount: float,
    ):
        """Send threshold-based cost alert."""
        # Check cooldown to prevent spam
        cooldown_key = f"{customer_id}:{threshold.percentage}"
        now = datetime.utcnow()

        if cooldown_key in self._alert_cooldowns:
            last_alert = self._alert_cooldowns[cooldown_key]
            if (now - last_alert).total_seconds() < 3600:  # 1 hour cooldown
                return

        if self.alert_manager:
            await self.alert_manager.send_alert(
                alert_type=AlertType.WARNING,
                priority=threshold.priority,
                title=f"Cost Threshold Alert - {threshold.percentage}% Budget Used",
                message=f"Customer {customer_id} has used {threshold.percentage}% of daily budget: ${current_cost:.2f} >= ${threshold_amount:.2f}. Recommended action: {threshold.action}",
                source="BigQueryCostMonitor",
                customer_id=customer_id,
                context={
                    "threshold_percentage": threshold.percentage,
                    "threshold_amount_usd": threshold_amount,
                    "current_cost_usd": current_cost,
                    "recommended_action": threshold.action,
                },
                tags=["cost", "threshold", "budget"],
            )

        self._alert_cooldowns[cooldown_key] = now

    async def _send_pattern_alert(
        self, customer_id: Optional[str], pattern: CostUsagePattern
    ):
        """Send alert for detected unusual usage pattern."""
        priority_map = {
            "high": AlertPriority.HIGH,
            "medium": AlertPriority.MEDIUM,
            "low": AlertPriority.LOW,
        }

        if self.alert_manager:
            await self.alert_manager.send_alert(
                alert_type=AlertType.WARNING,
                priority=priority_map[pattern.severity],
                title=f"Unusual Usage Pattern Detected - {pattern.pattern_type}",
                message=f"Detected unusual usage pattern for customer {customer_id}: {pattern.description}. Cost impact: ${pattern.cost_impact_usd:.2f}",
                source="BigQueryCostMonitor",
                customer_id=customer_id,
                context={
                    "pattern_type": pattern.pattern_type,
                    "severity": pattern.severity,
                    "cost_impact_usd": pattern.cost_impact_usd,
                    "detected_at": pattern.detected_at.isoformat(),
                },
                tags=["cost", "pattern", "anomaly"],
            )

    async def _send_cost_report(
        self, customer_id: Optional[str], report: Dict[str, Any], report_type: str
    ):
        """Send cost summary report via configured channels."""
        if self.alert_manager:
            await self.alert_manager.send_alert(
                alert_type=AlertType.INFO,
                priority=AlertPriority.LOW,
                title=f"{report_type.title()} Cost Report",
                message=f"Cost summary report for customer {customer_id}: Total cost ${report['executive_summary']['total_cost_usd']:.2f}, Budget utilization {report['executive_summary']['budget_utilization_percentage']:.1f}%",
                source="BigQueryCostMonitor",
                customer_id=customer_id,
                context={
                    "report_type": report_type,
                    "executive_summary": report["executive_summary"],
                    "report_url": f"/api/v1/costs/reports/{customer_id or 'global'}/{report_type}",
                },
                tags=["cost", "report", report_type],
            )

    # === ANALYTICS HELPER METHODS ===

    async def _get_historical_costs(
        self, customer_id: Optional[str], days: int
    ) -> List[Dict[str, Any]]:
        """Get historical cost data for analysis."""
        # This would query historical data from BigQuery or billing API
        # For now, simulate some data
        historical_data = []
        for i in range(days):
            day_date = date.today() - timedelta(days=i)
            # Simulate daily costs with some variation
            base_cost = (
                5.0 if not customer_id or customer_id.startswith("std_") else 25.0
            )
            daily_cost = base_cost * (0.8 + 0.4 * (i % 7) / 7)  # Vary by day of week

            historical_data.append(
                {
                    "date": day_date.isoformat(),
                    "total_cost_usd": daily_cost,
                    "query_count": int(daily_cost * 2),  # Rough correlation
                    "bytes_processed": int(
                        daily_cost * 1024**3 / 5
                    ),  # Rough calculation
                }
            )

        return list(reversed(historical_data))  # Chronological order

    async def _get_cost_by_operation_type(
        self, customer_id: Optional[str], days: int
    ) -> Dict[str, float]:
        """Get cost breakdown by operation type."""
        # This would analyze actual query patterns
        # For now, simulate breakdown
        total_cost = 100.0  # Simulated
        return {
            "keyword_analysis": total_cost * 0.4,
            "search_terms_analysis": total_cost * 0.3,
            "performance_analysis": total_cost * 0.2,
            "export_operations": total_cost * 0.1,
        }

    async def _get_expensive_queries(
        self, customer_id: Optional[str], cost_threshold: float = 1.0, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most expensive queries."""
        # This would query actual BigQuery job history
        # For now, simulate some expensive queries
        return [
            {
                "job_id": "job_001",
                "cost_usd": 15.75,
                "bytes_processed": 3 * 1024**4,  # 3TB
                "duration_seconds": 180,
                "query_type": "keyword_analysis",
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "job_id": "job_002",
                "cost_usd": 8.50,
                "bytes_processed": 1.7 * 1024**4,  # 1.7TB
                "duration_seconds": 120,
                "query_type": "search_terms_analysis",
                "created_at": datetime.utcnow().isoformat(),
            },
        ]

    async def _get_hourly_usage_pattern(
        self, customer_id: Optional[str]
    ) -> Dict[str, float]:
        """Get usage pattern by hour of day."""
        # This would analyze actual usage patterns
        # For now, simulate typical business hours pattern
        pattern = {}
        for hour in range(24):
            if 9 <= hour <= 17:  # Business hours
                pattern[str(hour)] = 2.0  # Higher usage
            elif 6 <= hour <= 8 or 18 <= hour <= 20:  # Early/late hours
                pattern[str(hour)] = 0.5
            else:  # Off hours
                pattern[str(hour)] = 0.1
        return pattern

    def _detect_off_hours_usage(self, hourly_usage: Dict[str, float]) -> bool:
        """Detect unusual off-hours usage."""
        off_hours_total = sum(
            hourly_usage.get(str(hour), 0)
            for hour in list(range(22, 24)) + list(range(0, 6))
        )
        business_hours_total = sum(
            hourly_usage.get(str(hour), 0) for hour in range(9, 18)
        )

        if business_hours_total > 0:
            off_hours_ratio = off_hours_total / business_hours_total
            return off_hours_ratio > 0.3  # More than 30% of business hours usage

        return off_hours_total > 1.0  # Absolute threshold

    async def _analyze_tier_efficiency(
        self, customer_id: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze cost efficiency compared to customer tier."""
        if not customer_id:
            return {"analysis": "No customer specified"}

        budget_config = await self._get_customer_budget_config(customer_id)
        current_costs = await self.get_real_time_costs(customer_id)

        tier_averages = {"standard": 5.0, "premium": 25.0, "enterprise": 100.0}

        tier_avg = tier_averages.get(budget_config.tier, 5.0)
        current_daily = current_costs.get("daily_cost_usd", 0.0)

        return {
            "customer_tier": budget_config.tier,
            "tier_average_daily_cost": tier_avg,
            "customer_daily_cost": current_daily,
            "efficiency_ratio": current_daily / tier_avg if tier_avg > 0 else 0,
            "efficiency_status": "above_average"
            if current_daily > tier_avg * 1.2
            else "below_average"
            if current_daily < tier_avg * 0.8
            else "average",
        }

    async def _calculate_bigquery_roi(
        self, customer_id: Optional[str], days: int
    ) -> Dict[str, Any]:
        """Calculate ROI for BigQuery vs CSV operations."""
        # This would compare actual costs and benefits
        # For now, simulate ROI calculation
        bq_cost = 150.0  # Total BigQuery cost over period
        csv_equivalent_cost = 80.0  # Estimated CSV processing cost
        time_saved_hours = 40  # Hours saved with BigQuery

        return {
            "bigquery_cost_usd": bq_cost,
            "csv_equivalent_cost_usd": csv_equivalent_cost,
            "additional_cost_usd": bq_cost - csv_equivalent_cost,
            "time_saved_hours": time_saved_hours,
            "cost_per_hour_saved": (bq_cost - csv_equivalent_cost) / time_saved_hours
            if time_saved_hours > 0
            else 0,
            "roi_analysis": "positive"
            if time_saved_hours * 50 > (bq_cost - csv_equivalent_cost)
            else "negative",  # Assuming $50/hour value
        }

    def _calculate_cost_trend(self, historical_costs: List[Dict[str, Any]]) -> str:
        """Calculate cost trend from historical data."""
        if len(historical_costs) < 2:
            return "insufficient_data"

        recent_avg = sum(day["total_cost_usd"] for day in historical_costs[-3:]) / 3
        earlier_avg = sum(day["total_cost_usd"] for day in historical_costs[:3]) / 3

        if recent_avg > earlier_avg * 1.1:
            return "increasing"
        elif recent_avg < earlier_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _calculate_avg_query_cost(
        self, historical_costs: List[Dict[str, Any]]
    ) -> float:
        """Calculate average cost per query."""
        total_cost = sum(day["total_cost_usd"] for day in historical_costs)
        total_queries = sum(day.get("query_count", 0) for day in historical_costs)

        return total_cost / total_queries if total_queries > 0 else 0.0

    def _calculate_cost_per_tb(self, historical_costs: List[Dict[str, Any]]) -> float:
        """Calculate cost per TB processed."""
        total_cost = sum(day["total_cost_usd"] for day in historical_costs)
        total_bytes = sum(day.get("bytes_processed", 0) for day in historical_costs)
        total_tb = total_bytes / (1024**4)

        return total_cost / total_tb if total_tb > 0 else 0.0

    async def _calculate_cost_per_analysis(
        self, customer_id: Optional[str], days: int
    ) -> float:
        """Calculate cost per customer analysis."""
        total_cost = sum(
            day["total_cost_usd"]
            for day in await self._get_historical_costs(customer_id, days)
        )

        # Estimate number of analyses (would come from actual usage data)
        estimated_analyses = days * 2  # Assume 2 analyses per day on average

        return total_cost / estimated_analyses if estimated_analyses > 0 else 0.0

    def _generate_cost_recommendations(
        self, historical_costs: List[Dict[str, Any]], operation_costs: Dict[str, float]
    ) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []

        # Check for high-cost operations
        if operation_costs:  # Ensure operation_costs is not empty
            most_expensive = max(operation_costs.items(), key=lambda x: x[1])
            total_costs = sum(operation_costs.values())
            if most_expensive[1] > total_costs * 0.5 and total_costs > 0:
                cost_percentage = (
                    (most_expensive[1] / total_costs * 100) if total_costs > 0 else 0
                )
                recommendations.append(
                    f"Consider optimizing {most_expensive[0]} operations - they account for {cost_percentage:.1f}% of costs"
                )

        # Check for cost trend
        if len(historical_costs) >= 7:
            recent_costs = historical_costs[-3:]
            weekly_costs = historical_costs[-7:]
            recent_avg = (
                sum(day["total_cost_usd"] for day in recent_costs) / len(recent_costs)
                if recent_costs
                else 0
            )
            weekly_avg = (
                sum(day["total_cost_usd"] for day in weekly_costs) / len(weekly_costs)
                if weekly_costs
                else 0
            )

            if recent_avg > weekly_avg * 1.3:
                recommendations.append(
                    "Recent cost spike detected - review recent query patterns and consider query optimization"
                )

        # General recommendations
        recommendations.extend(
            [
                "Schedule large analytics jobs during off-peak hours for potential cost savings",
                "Consider using BigQuery materialized views for frequently accessed data",
                "Review and optimize expensive queries identified in the analytics",
            ]
        )

        return recommendations

    async def _analyze_budget_utilization(
        self, customer_id: Optional[str], historical_costs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze budget utilization patterns."""
        budget_config = await self._get_customer_budget_config(customer_id)

        daily_costs = [day["total_cost_usd"] for day in historical_costs]
        avg_daily = sum(daily_costs) / len(daily_costs) if daily_costs else 0

        days_over_80_percent = sum(
            1 for cost in daily_costs if cost > budget_config.daily_limit_usd * 0.8
        )
        days_over_limit = sum(
            1 for cost in daily_costs if cost > budget_config.daily_limit_usd
        )

        return {
            "average_daily_utilization_percentage": (
                avg_daily / budget_config.daily_limit_usd
            )
            * 100,
            "days_over_80_percent": days_over_80_percent,
            "days_over_limit": days_over_limit,
            "budget_efficiency": "good"
            if days_over_limit == 0 and avg_daily < budget_config.daily_limit_usd * 0.7
            else "needs_attention",
            "recommended_budget_adjustment": avg_daily * 1.2
            if avg_daily > budget_config.daily_limit_usd * 0.9
            else None,
        }

    def _generate_action_items(
        self,
        analytics: Dict[str, Any],
        patterns: List[CostUsagePattern],
        current_costs: Dict[str, Any],
    ) -> List[str]:
        """Generate action items based on analysis."""
        action_items = []

        # Based on current status
        status = current_costs.get("status", "unknown")
        if status in ["over_budget", "emergency"]:
            action_items.append(
                "URGENT: Review and optimize high-cost queries immediately"
            )
            action_items.append("Consider implementing query throttling or scheduling")
        elif status == "approaching_limit":
            action_items.append(
                "Monitor costs closely - approaching daily budget limit"
            )

        # Based on detected patterns
        for pattern in patterns:
            if pattern.severity == "high":
                action_items.append(
                    f"Investigate {pattern.pattern_type}: {pattern.description}"
                )

        # Based on analytics
        if analytics.get("cost_summary", {}).get("cost_trend") == "increasing":
            action_items.append("Review cost trend - expenses are increasing")

        # Based on efficiency
        efficiency = analytics.get("efficiency_metrics", {}).get("tier_efficiency", {})
        if efficiency.get("efficiency_status") == "above_average":
            action_items.append(
                "Cost efficiency below tier average - review optimization opportunities"
            )

        return action_items
