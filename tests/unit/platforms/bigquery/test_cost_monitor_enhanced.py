"""Tests for enhanced BigQuery cost monitoring system."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav_mcp.alerts.models import AlertPriority
from paidsearchnav_mcp.platforms.bigquery.cost_monitor_enhanced import (
    CostThreshold,
    CostUsagePattern,
    CustomerBudgetConfig,
    EnhancedBigQueryCostMonitor,
)


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.project_id = "test-project"
    return config


@pytest.fixture
def mock_authenticator():
    """Mock authenticator."""
    authenticator = AsyncMock()
    mock_client = AsyncMock()
    authenticator.get_client.return_value = mock_client
    return authenticator


@pytest.fixture
def mock_alert_manager():
    """Mock alert manager."""
    alert_manager = AsyncMock()
    alert_manager.send_alert.return_value = True
    return alert_manager


@pytest.fixture
def enhanced_monitor(mock_config, mock_authenticator, mock_alert_manager):
    """Enhanced BigQuery cost monitor instance."""
    return EnhancedBigQueryCostMonitor(
        mock_config, mock_authenticator, mock_alert_manager
    )


@pytest.fixture
def sample_budget_config():
    """Sample customer budget configuration."""
    return CustomerBudgetConfig(
        customer_id="test_customer",
        tier="premium",
        daily_limit_usd=50.0,
        monthly_limit_usd=1500.0,
        emergency_limit_usd=200.0,
        thresholds=[
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


class TestEnhancedBigQueryCostMonitor:
    """Test cases for enhanced BigQuery cost monitoring."""

    async def test_get_real_time_costs_success(
        self, enhanced_monitor, mock_authenticator
    ):
        """Test successful real-time cost retrieval."""
        # Mock BigQuery query results
        mock_result = MagicMock()
        mock_result.total_cost_usd = 5.25
        mock_result.total_bytes_processed = 1024**4  # 1TB
        mock_result.creation_time = datetime.utcnow()

        mock_client = AsyncMock()
        mock_query_job = AsyncMock()
        mock_query_job.result.return_value = [mock_result]
        mock_client.query.return_value = mock_query_job
        mock_authenticator.get_client.return_value = mock_client

        # Mock helper methods
        enhanced_monitor._get_daily_costs_from_billing_api = AsyncMock(
            return_value={"total_cost_usd": 25.0}
        )
        enhanced_monitor._get_monthly_costs_from_billing_api = AsyncMock(
            return_value={"total_cost_usd": 150.0}
        )
        enhanced_monitor._get_customer_budget_config = AsyncMock(
            return_value=CustomerBudgetConfig(
                customer_id="test_customer",
                tier="premium",
                daily_limit_usd=50.0,
                monthly_limit_usd=1500.0,
                emergency_limit_usd=200.0,
            )
        )

        result = await enhanced_monitor.get_real_time_costs(
            "test_customer", lookback_hours=2
        )

        assert result["customer_id"] == "test_customer"
        assert result["lookback_hours"] == 2
        assert result["recent_cost_usd"] == 5.25
        assert result["recent_bytes_processed"] == 1024**4
        assert result["daily_cost_usd"] == 25.0
        assert result["monthly_cost_usd"] == 150.0
        assert "timestamp" in result
        assert "status" in result

    async def test_get_real_time_costs_error_handling(
        self, enhanced_monitor, mock_authenticator
    ):
        """Test error handling in real-time cost retrieval."""
        mock_authenticator.get_client.side_effect = Exception(
            "BigQuery connection failed"
        )

        result = await enhanced_monitor.get_real_time_costs("test_customer")

        assert "error" in result
        assert result["customer_id"] == "test_customer"
        assert result["daily_cost_usd"] == 0.0

    async def test_check_budget_enforcement_within_limits(
        self, enhanced_monitor, sample_budget_config
    ):
        """Test budget enforcement when within limits."""
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={
                "daily_cost_usd": 20.0,
                "monthly_cost_usd": 600.0,
            }
        )
        enhanced_monitor._get_customer_budget_config = AsyncMock(
            return_value=sample_budget_config
        )

        result = await enhanced_monitor.check_budget_enforcement("test_customer", 5.0)

        assert result["allowed"] is True
        assert result["daily_cost_usd"] == 25.0  # 20 + 5
        assert result["status"] == "moderate_usage"
        assert len(result["alerts_triggered"]) == 0

    async def test_check_budget_enforcement_emergency_limit(
        self, enhanced_monitor, sample_budget_config
    ):
        """Test emergency circuit breaker activation."""
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={
                "daily_cost_usd": 180.0,
                "monthly_cost_usd": 1200.0,
            }
        )
        enhanced_monitor._get_customer_budget_config = AsyncMock(
            return_value=sample_budget_config
        )
        enhanced_monitor._trigger_emergency_circuit_breaker = AsyncMock()

        result = await enhanced_monitor.check_budget_enforcement("test_customer", 25.0)

        assert result["allowed"] is False
        assert result["reason"] == "Emergency cost limit exceeded"
        assert result["daily_cost_usd"] == 205.0  # 180 + 25
        enhanced_monitor._trigger_emergency_circuit_breaker.assert_called_once()

    async def test_check_budget_enforcement_daily_limit_with_throttling(
        self, enhanced_monitor, sample_budget_config
    ):
        """Test daily limit exceeded with throttling applied."""
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={
                "daily_cost_usd": 45.0,
                "monthly_cost_usd": 900.0,
            }
        )
        enhanced_monitor._get_customer_budget_config = AsyncMock(
            return_value=sample_budget_config
        )
        enhanced_monitor._check_grace_period_expired = AsyncMock(return_value=True)
        enhanced_monitor._apply_export_throttling = AsyncMock()

        result = await enhanced_monitor.check_budget_enforcement("test_customer", 10.0)

        assert result["allowed"] is False
        assert "throttling applied" in result["reason"]
        enhanced_monitor._apply_export_throttling.assert_called_once()

    async def test_check_budget_enforcement_threshold_alerts(
        self, enhanced_monitor, sample_budget_config
    ):
        """Test threshold-based alert triggering."""
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={
                "daily_cost_usd": 40.0,
                "monthly_cost_usd": 800.0,
            }
        )
        enhanced_monitor._get_customer_budget_config = AsyncMock(
            return_value=sample_budget_config
        )
        enhanced_monitor._send_threshold_alert = AsyncMock()

        result = await enhanced_monitor.check_budget_enforcement("test_customer", 5.0)

        assert result["allowed"] is True
        assert len(result["alerts_triggered"]) == 2  # 80% and 95% thresholds

        # Check threshold alerts
        triggered_percentages = [
            alert["threshold_percentage"] for alert in result["alerts_triggered"]
        ]
        assert 80.0 in triggered_percentages
        assert 95.0 in triggered_percentages

    async def test_detect_unusual_patterns_spike_detection(self, enhanced_monitor):
        """Test sudden cost spike pattern detection."""
        # Mock historical data
        historical_costs = [
            {"total_cost_usd": 10.0, "query_count": 20, "bytes_processed": 1024**3},
            {
                "total_cost_usd": 12.0,
                "query_count": 24,
                "bytes_processed": 1.2 * 1024**3,
            },
            {
                "total_cost_usd": 9.0,
                "query_count": 18,
                "bytes_processed": 0.9 * 1024**3,
            },
        ]
        enhanced_monitor._get_historical_costs = AsyncMock(
            return_value=historical_costs
        )
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={"daily_cost_usd": 35.0}
        )  # 3x spike
        enhanced_monitor._get_hourly_usage_pattern = AsyncMock(return_value={})
        enhanced_monitor._get_expensive_queries = AsyncMock(return_value=[])
        enhanced_monitor._send_pattern_alert = AsyncMock()

        patterns = await enhanced_monitor.detect_unusual_patterns("test_customer", 7)

        assert len(patterns) >= 1
        spike_pattern = next(
            (p for p in patterns if p.pattern_type == "sudden_spike"), None
        )
        assert spike_pattern is not None
        assert spike_pattern.severity == "high"
        assert "3.4x above" in spike_pattern.description  # 35 / avg(10.33)

    async def test_detect_unusual_patterns_sustained_high_usage(self, enhanced_monitor):
        """Test sustained high usage pattern detection."""
        # Mock historical data with sustained high usage
        historical_costs = [
            {"total_cost_usd": 10.0, "query_count": 20, "bytes_processed": 1024**3},
            {
                "total_cost_usd": 12.0,
                "query_count": 24,
                "bytes_processed": 1.2 * 1024**3,
            },
            {
                "total_cost_usd": 18.0,
                "query_count": 36,
                "bytes_processed": 1.8 * 1024**3,
            },  # High
            {
                "total_cost_usd": 19.0,
                "query_count": 38,
                "bytes_processed": 1.9 * 1024**3,
            },  # High
            {
                "total_cost_usd": 17.0,
                "query_count": 34,
                "bytes_processed": 1.7 * 1024**3,
            },  # High
        ]
        enhanced_monitor._get_historical_costs = AsyncMock(
            return_value=historical_costs
        )
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={"daily_cost_usd": 15.0}
        )
        enhanced_monitor._get_hourly_usage_pattern = AsyncMock(return_value={})
        enhanced_monitor._get_expensive_queries = AsyncMock(return_value=[])
        enhanced_monitor._send_pattern_alert = AsyncMock()

        patterns = await enhanced_monitor.detect_unusual_patterns("test_customer", 7)

        sustained_pattern = next(
            (p for p in patterns if p.pattern_type == "sustained_high_usage"), None
        )
        assert sustained_pattern is not None
        assert sustained_pattern.severity == "medium"

    async def test_detect_unusual_patterns_off_hours_usage(self, enhanced_monitor):
        """Test off-hours usage pattern detection."""
        # Mock normal historical data
        enhanced_monitor._get_historical_costs = AsyncMock(
            return_value=[
                {"total_cost_usd": 10.0, "query_count": 20, "bytes_processed": 1024**3}
            ]
        )
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={"daily_cost_usd": 10.0}
        )

        # Mock off-hours usage pattern
        off_hours_pattern = {str(hour): 0.1 for hour in range(24)}
        for hour in [22, 23, 0, 1, 2, 3, 4, 5]:  # Off hours
            off_hours_pattern[str(hour)] = 2.0  # High off-hours usage
        enhanced_monitor._get_hourly_usage_pattern = AsyncMock(
            return_value=off_hours_pattern
        )
        enhanced_monitor._detect_off_hours_usage = MagicMock(return_value=True)
        enhanced_monitor._get_expensive_queries = AsyncMock(return_value=[])
        enhanced_monitor._send_pattern_alert = AsyncMock()

        patterns = await enhanced_monitor.detect_unusual_patterns("test_customer", 7)

        off_hours_pattern = next(
            (p for p in patterns if p.pattern_type == "off_hours_usage"), None
        )
        assert off_hours_pattern is not None
        assert off_hours_pattern.severity == "low"

    async def test_detect_unusual_patterns_large_query_anomaly(self, enhanced_monitor):
        """Test large query anomaly detection."""
        enhanced_monitor._get_historical_costs = AsyncMock(
            return_value=[
                {"total_cost_usd": 10.0, "query_count": 20, "bytes_processed": 1024**3}
            ]
        )
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={"daily_cost_usd": 10.0}
        )
        enhanced_monitor._get_hourly_usage_pattern = AsyncMock(return_value={})
        enhanced_monitor._get_expensive_queries = AsyncMock(
            return_value=[
                {"cost_usd": 15.75, "job_id": "job_001"},
                {"cost_usd": 12.50, "job_id": "job_002"},
            ]
        )
        enhanced_monitor._send_pattern_alert = AsyncMock()

        patterns = await enhanced_monitor.detect_unusual_patterns("test_customer", 7)

        query_pattern = next(
            (p for p in patterns if p.pattern_type == "large_query_anomaly"), None
        )
        assert query_pattern is not None
        assert query_pattern.severity == "medium"
        assert "2 queries exceeded" in query_pattern.description

    async def test_generate_cost_analytics_comprehensive(self, enhanced_monitor):
        """Test comprehensive cost analytics generation."""
        # Mock various data sources
        historical_costs = [
            {
                "total_cost_usd": 25.0,
                "query_count": 50,
                "bytes_processed": 2.5 * 1024**3,
            },
            {
                "total_cost_usd": 30.0,
                "query_count": 60,
                "bytes_processed": 3.0 * 1024**3,
            },
        ]
        enhanced_monitor._get_historical_costs = AsyncMock(
            return_value=historical_costs
        )
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value={"daily_cost_usd": 28.0}
        )
        enhanced_monitor._get_cost_by_operation_type = AsyncMock(
            return_value={
                "keyword_analysis": 40.0,
                "search_terms_analysis": 30.0,
                "performance_analysis": 20.0,
                "export_operations": 10.0,
            }
        )
        enhanced_monitor._get_expensive_queries = AsyncMock(
            return_value=[{"job_id": "job_001", "cost_usd": 15.75}]
        )
        enhanced_monitor._analyze_tier_efficiency = AsyncMock(
            return_value={"customer_tier": "premium", "efficiency_status": "average"}
        )
        enhanced_monitor._calculate_bigquery_roi = AsyncMock(
            return_value={
                "roi_analysis": "positive",
                "bigquery_cost_usd": 100.0,
                "csv_equivalent_cost_usd": 80.0,
            }
        )
        enhanced_monitor._generate_cost_recommendations = MagicMock(
            return_value=[
                "Optimize keyword_analysis operations",
                "Schedule large jobs during off-peak hours",
            ]
        )
        enhanced_monitor._analyze_budget_utilization = AsyncMock(
            return_value={
                "average_daily_utilization_percentage": 56.0,
                "budget_efficiency": "good",
            }
        )

        analytics = await enhanced_monitor.generate_cost_analytics("test_customer", 30)

        assert analytics["customer_id"] == "test_customer"
        assert analytics["analysis_period_days"] == 30
        assert "cost_summary" in analytics
        assert "operation_breakdown" in analytics
        assert "query_analysis" in analytics
        assert "efficiency_metrics" in analytics
        assert "roi_analysis" in analytics
        assert "recommendations" in analytics
        assert "budget_utilization" in analytics

        # Check cost summary calculations
        assert analytics["cost_summary"]["total_cost_usd"] == 55.0  # 25 + 30
        assert analytics["cost_summary"]["average_daily_cost_usd"] == 27.5  # 55 / 2

    async def test_get_cost_summary_report_weekly(self, enhanced_monitor):
        """Test weekly cost summary report generation."""
        # Mock dependencies
        mock_analytics = {
            "cost_summary": {"total_cost_usd": 175.0, "cost_trend": "stable"},
        }
        mock_patterns = [
            CostUsagePattern(
                pattern_type="test_pattern",
                severity="medium",
                description="Test pattern",
                cost_impact_usd=5.0,
            )
        ]
        mock_current_costs = {
            "daily_usage_percentage": 65.0,
            "status": "moderate_usage",
        }

        enhanced_monitor.generate_cost_analytics = AsyncMock(
            return_value=mock_analytics
        )
        enhanced_monitor.detect_unusual_patterns = AsyncMock(return_value=mock_patterns)
        enhanced_monitor.get_real_time_costs = AsyncMock(
            return_value=mock_current_costs
        )
        enhanced_monitor._send_cost_report = AsyncMock()
        enhanced_monitor._generate_action_items = MagicMock(
            return_value=["Monitor costs closely", "Review recent queries"]
        )

        report = await enhanced_monitor.get_cost_summary_report(
            "test_customer", "weekly"
        )

        assert report["report_type"] == "weekly"
        assert report["customer_id"] == "test_customer"
        assert report["period_days"] == 7
        assert "executive_summary" in report
        assert "detailed_analytics" in report
        assert "unusual_patterns" in report
        assert "current_status" in report
        assert "action_items" in report

        # Check executive summary
        exec_summary = report["executive_summary"]
        assert exec_summary["total_cost_usd"] == 175.0
        assert exec_summary["budget_utilization_percentage"] == 65.0
        assert exec_summary["unusual_patterns_detected"] == 1

        enhanced_monitor._send_cost_report.assert_called_once()

    async def test_set_customer_budget_configuration(self, enhanced_monitor):
        """Test customer budget configuration setup."""
        budget_config = await enhanced_monitor.set_customer_budget(
            customer_id="test_customer",
            tier="premium",
            daily_limit_usd=75.0,
            monthly_limit_usd=2250.0,
            emergency_limit_usd=300.0,
        )

        assert budget_config.customer_id == "test_customer"
        assert budget_config.tier == "premium"
        assert budget_config.daily_limit_usd == 75.0
        assert budget_config.monthly_limit_usd == 2250.0
        assert budget_config.emergency_limit_usd == 300.0
        assert len(budget_config.thresholds) == 3  # Default thresholds

        # Verify it's stored in the monitor
        stored_budgets = await enhanced_monitor.get_customer_budgets()
        assert "test_customer" in stored_budgets
        assert stored_budgets["test_customer"].daily_limit_usd == 75.0

    async def test_budget_config_tier_defaults(self, enhanced_monitor):
        """Test automatic tier-based budget configuration."""
        # Test enterprise tier customer
        budget_config = await enhanced_monitor._get_customer_budget_config(
            "ent_test_customer"
        )
        assert budget_config.tier == "enterprise"
        assert budget_config.daily_limit_usd == 200.0

        # Test premium tier customer
        budget_config = await enhanced_monitor._get_customer_budget_config(
            "prem_test_customer"
        )
        assert budget_config.tier == "premium"
        assert budget_config.daily_limit_usd == 50.0

        # Test standard tier customer (default)
        budget_config = await enhanced_monitor._get_customer_budget_config(
            "std_test_customer"
        )
        assert budget_config.tier == "standard"
        assert budget_config.daily_limit_usd == 10.0

    async def test_alert_cooldown_mechanism(self, enhanced_monitor, mock_alert_manager):
        """Test alert cooldown to prevent spam."""
        threshold = CostThreshold(
            percentage=80.0, priority=AlertPriority.HIGH, action="review"
        )

        # First alert should be sent
        await enhanced_monitor._send_threshold_alert(
            "test_customer", threshold, 40.0, 40.0
        )
        mock_alert_manager.send_alert.assert_called_once()

        # Reset mock for second call
        mock_alert_manager.reset_mock()

        # Second alert within cooldown period should not be sent
        await enhanced_monitor._send_threshold_alert(
            "test_customer", threshold, 42.0, 40.0
        )
        mock_alert_manager.send_alert.assert_not_called()

    def test_cost_status_determination(self, enhanced_monitor, sample_budget_config):
        """Test cost status determination logic."""
        # Test within budget
        status = enhanced_monitor._determine_cost_status(20.0, sample_budget_config)
        assert status == "moderate_usage"

        # Test approaching limit
        status = enhanced_monitor._determine_cost_status(
            42.0, sample_budget_config
        )  # 84% of 50
        assert status == "approaching_limit"

        # Test over budget
        status = enhanced_monitor._determine_cost_status(55.0, sample_budget_config)
        assert status == "over_budget"

        # Test emergency
        status = enhanced_monitor._determine_cost_status(250.0, sample_budget_config)
        assert status == "emergency"

    def test_off_hours_usage_detection(self, enhanced_monitor):
        """Test off-hours usage detection logic."""
        # Normal business hours pattern
        normal_pattern = {
            str(hour): 2.0 if 9 <= hour <= 17 else 0.1 for hour in range(24)
        }
        assert not enhanced_monitor._detect_off_hours_usage(normal_pattern)

        # High off-hours usage pattern
        off_hours_pattern = {str(hour): 2.0 for hour in range(24)}
        for hour in [22, 23, 0, 1, 2, 3, 4, 5]:
            off_hours_pattern[str(hour)] = 3.0  # High off-hours usage
        assert enhanced_monitor._detect_off_hours_usage(off_hours_pattern)

    def test_cost_trend_calculation(self, enhanced_monitor):
        """Test cost trend calculation from historical data."""
        # Increasing trend
        increasing_costs = [
            {"total_cost_usd": 10.0},
            {"total_cost_usd": 12.0},
            {"total_cost_usd": 14.0},
            {"total_cost_usd": 16.0},
            {"total_cost_usd": 18.0},
            {"total_cost_usd": 20.0},
        ]
        trend = enhanced_monitor._calculate_cost_trend(increasing_costs)
        assert trend == "increasing"

        # Decreasing trend
        decreasing_costs = [
            {"total_cost_usd": 20.0},
            {"total_cost_usd": 18.0},
            {"total_cost_usd": 16.0},
            {"total_cost_usd": 14.0},
            {"total_cost_usd": 12.0},
            {"total_cost_usd": 10.0},
        ]
        trend = enhanced_monitor._calculate_cost_trend(decreasing_costs)
        assert trend == "decreasing"

        # Stable trend
        stable_costs = [
            {"total_cost_usd": 15.0},
            {"total_cost_usd": 15.5},
            {"total_cost_usd": 14.5},
            {"total_cost_usd": 15.2},
            {"total_cost_usd": 14.8},
            {"total_cost_usd": 15.1},
        ]
        trend = enhanced_monitor._calculate_cost_trend(stable_costs)
        assert trend == "stable"

    async def test_error_handling_graceful_degradation(
        self, enhanced_monitor, mock_authenticator
    ):
        """Test graceful error handling and degradation."""
        # Test budget enforcement with error - should fail open
        enhanced_monitor.get_real_time_costs = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await enhanced_monitor.check_budget_enforcement("test_customer", 10.0)

        assert result["allowed"] is True  # Fail open
        assert "error" in result
        assert result["enforcement_actions"] == []
        assert result["alerts_triggered"] == []

    async def test_billing_api_integration_simulation(
        self, enhanced_monitor, mock_authenticator
    ):
        """Test BigQuery billing API integration simulation."""
        # Mock BigQuery client and query results
        mock_result = MagicMock()
        mock_result.total_jobs = 25
        mock_result.total_bytes_processed = 5 * 1024**4  # 5TB
        mock_result.query_cost_usd = 25.0
        mock_result.slot_cost_usd = 2.0
        mock_result.total_cost_usd = 27.0

        mock_client = AsyncMock()
        mock_query_job = AsyncMock()
        mock_query_job.result.return_value = [mock_result]
        mock_client.query.return_value = mock_query_job
        mock_authenticator.get_client.return_value = mock_client

        daily_costs = await enhanced_monitor._get_daily_costs_from_billing_api(
            "test_customer"
        )

        assert daily_costs["total_jobs"] == 25
        assert daily_costs["total_bytes_processed"] == 5 * 1024**4
        assert daily_costs["query_cost_usd"] == 25.0
        assert daily_costs["slot_cost_usd"] == 2.0
        assert daily_costs["total_cost_usd"] == 27.0
        assert "date" in daily_costs


class TestCostThreshold:
    """Test cases for CostThreshold model."""

    def test_cost_threshold_validation(self):
        """Test cost threshold validation."""
        # Valid threshold
        threshold = CostThreshold(
            percentage=75.0, priority=AlertPriority.HIGH, action="review_immediately"
        )
        assert threshold.percentage == 75.0
        assert threshold.priority == AlertPriority.HIGH
        assert threshold.action == "review_immediately"

    def test_cost_threshold_percentage_bounds(self):
        """Test percentage validation bounds."""
        # Test lower bound
        with pytest.raises(ValueError):
            CostThreshold(percentage=-1.0, priority=AlertPriority.LOW, action="test")

        # Test upper bound
        with pytest.raises(ValueError):
            CostThreshold(percentage=101.0, priority=AlertPriority.LOW, action="test")


class TestCustomerBudgetConfig:
    """Test cases for CustomerBudgetConfig model."""

    def test_budget_config_creation(self):
        """Test budget configuration creation."""
        config = CustomerBudgetConfig(
            customer_id="test_customer",
            tier="premium",
            daily_limit_usd=100.0,
            monthly_limit_usd=3000.0,
            emergency_limit_usd=500.0,
        )

        assert config.customer_id == "test_customer"
        assert config.tier == "premium"
        assert config.daily_limit_usd == 100.0
        assert config.monthly_limit_usd == 3000.0
        assert config.emergency_limit_usd == 500.0
        assert len(config.thresholds) == 3  # Default thresholds
        assert config.grace_period_hours == 1
        assert config.throttle_enabled is True
        assert config.alerts_enabled is True

    def test_budget_config_validation(self):
        """Test budget configuration validation."""
        # Test negative limits
        with pytest.raises(ValueError):
            CustomerBudgetConfig(
                customer_id="test",
                tier="standard",
                daily_limit_usd=-10.0,
                monthly_limit_usd=300.0,
                emergency_limit_usd=50.0,
            )


class TestCostUsagePattern:
    """Test cases for CostUsagePattern model."""

    def test_usage_pattern_creation(self):
        """Test usage pattern creation."""
        pattern = CostUsagePattern(
            pattern_type="sudden_spike",
            severity="high",
            description="Cost increased by 300%",
            cost_impact_usd=75.50,
        )

        assert pattern.pattern_type == "sudden_spike"
        assert pattern.severity == "high"
        assert pattern.description == "Cost increased by 300%"
        assert pattern.cost_impact_usd == 75.50
        assert isinstance(pattern.detected_at, datetime)
