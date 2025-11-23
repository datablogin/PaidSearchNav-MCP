"""Tests for BigQuery cost monitoring API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from paidsearchnav_mcp.alerts.models import AlertPriority
from paidsearchnav_mcp.api.routes.bigquery import router
from paidsearchnav_mcp.platforms.bigquery.cost_monitor_enhanced import (
    CostUsagePattern,
    CustomerBudgetConfig,
)


@pytest.fixture
def app():
    """Create FastAPI test application."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_bigquery_service():
    """Mock BigQuery service."""
    service = MagicMock()
    service.is_enabled = True
    service.is_premium = True
    service.is_enterprise = True

    # Mock cost monitor
    service.cost_monitor = AsyncMock()

    return service


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    return {"user_id": "test_user", "customer_id": "test_customer", "tier": "premium"}


class TestCostMonitoringEndpoints:
    """Test cases for cost monitoring API endpoints."""

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_real_time_costs_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test successful real-time cost retrieval."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock cost monitor response
        mock_cost_data = {
            "customer_id": "test_customer",
            "timestamp": datetime.utcnow(),
            "daily_cost_usd": 25.50,
            "monthly_cost_usd": 650.00,
            "status": "moderate_usage",
            "data_freshness_minutes": 2.5,
        }
        mock_bigquery_service.cost_monitor.get_real_time_costs.return_value = (
            mock_cost_data
        )

        response = client.get(
            "/bigquery/cost-monitoring/real-time?customer_id=test_customer&lookback_hours=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["customer_id"] == "test_customer"
        assert data["data"]["daily_cost_usd"] == 25.50
        assert data["data"]["status"] == "moderate_usage"

        mock_bigquery_service.cost_monitor.get_real_time_costs.assert_called_once_with(
            "test_customer", 2
        )

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_real_time_costs_not_enabled(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test real-time costs when BigQuery is not enabled."""
        mock_get_user.return_value = mock_current_user

        mock_service = MagicMock()
        mock_service.is_enabled = False
        mock_get_service.return_value = mock_service

        response = client.get("/bigquery/cost-monitoring/real-time")

        assert response.status_code == 402
        assert "BigQuery integration not enabled" in response.json()["detail"]

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_check_budget_enforcement_allowed(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test budget enforcement when operation is allowed."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock enforcement response - operation allowed
        mock_enforcement_result = {
            "allowed": True,
            "enforcement_actions": [],
            "alerts_triggered": [
                {
                    "threshold_percentage": 80.0,
                    "threshold_amount_usd": 40.0,
                    "current_cost_usd": 42.0,
                    "priority": AlertPriority.HIGH,
                    "action": "review",
                }
            ],
            "daily_cost_usd": 42.0,
            "status": "approaching_limit",
        }
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = (
            mock_enforcement_result
        )

        response = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?customer_id=test_customer&additional_cost_usd=5.0"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["allowed"] is True
        assert len(data["data"]["alerts_triggered"]) == 1
        assert data["customer_id"] == "test_customer"

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_check_budget_enforcement_blocked(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test budget enforcement when operation is blocked."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock enforcement response - operation blocked
        mock_enforcement_result = {
            "allowed": False,
            "reason": "Emergency cost limit exceeded",
            "enforcement_actions": [
                {
                    "action": "emergency_circuit_breaker",
                    "reason": "Emergency limit exceeded: $250.00 >= $200.00",
                    "severity": "critical",
                }
            ],
            "daily_cost_usd": 250.0,
            "emergency_limit_usd": 200.0,
        }
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = (
            mock_enforcement_result
        )

        response = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?customer_id=test_customer&additional_cost_usd=50.0"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["allowed"] is False
        assert "Emergency cost limit exceeded" in data["data"]["reason"]
        assert len(data["data"]["enforcement_actions"]) == 1

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_check_budget_enforcement_premium_required(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test budget enforcement requires premium tier."""
        mock_get_user.return_value = mock_current_user

        mock_service = MagicMock()
        mock_service.is_premium = False
        mock_get_service.return_value = mock_service

        response = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?customer_id=test_customer"
        )

        assert response.status_code == 402
        assert "Premium tier required" in response.json()["detail"]

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_detect_cost_anomalies_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test successful cost anomaly detection."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock detected patterns
        mock_patterns = [
            CostUsagePattern(
                pattern_type="sudden_spike",
                severity="high",
                description="Daily cost spiked to $85.00, 3.4x above 7-day average",
                cost_impact_usd=60.0,
            ),
            CostUsagePattern(
                pattern_type="off_hours_usage",
                severity="low",
                description="Unusual off-hours usage detected: $12.50 between 10PM-6AM",
                cost_impact_usd=12.5,
            ),
        ]
        mock_bigquery_service.cost_monitor.detect_unusual_patterns.return_value = (
            mock_patterns
        )

        response = client.get(
            "/bigquery/cost-monitoring/anomaly-detection?customer_id=test_customer&lookback_days=14"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["anomalies_detected"] == 2
        assert data["data"]["customer_id"] == "test_customer"
        assert data["data"]["analysis_period_days"] == 14

        patterns = data["data"]["patterns"]
        assert len(patterns) == 2
        assert patterns[0]["pattern_type"] == "sudden_spike"
        assert patterns[0]["severity"] == "high"
        assert patterns[1]["pattern_type"] == "off_hours_usage"

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_cost_analytics_comprehensive(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test comprehensive cost analytics endpoint."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock analytics response
        mock_analytics = {
            "customer_id": "test_customer",
            "analysis_period_days": 30,
            "generated_at": datetime.utcnow(),
            "cost_summary": {
                "total_cost_usd": 850.0,
                "average_daily_cost_usd": 28.33,
                "peak_daily_cost_usd": 65.0,
                "cost_trend": "increasing",
            },
            "operation_breakdown": {
                "keyword_analysis": 340.0,
                "search_terms_analysis": 255.0,
                "performance_analysis": 170.0,
                "export_operations": 85.0,
            },
            "query_analysis": {
                "expensive_queries": [{"job_id": "job_001", "cost_usd": 25.75}],
                "average_cost_per_query": 1.42,
                "total_queries_analyzed": 600,
            },
            "efficiency_metrics": {
                "cost_per_tb_processed": 5.12,
                "tier_efficiency": {
                    "customer_tier": "premium",
                    "efficiency_status": "average",
                },
            },
            "roi_analysis": {
                "roi_analysis": "positive",
                "bigquery_cost_usd": 850.0,
                "csv_equivalent_cost_usd": 680.0,
            },
            "recommendations": [
                "Optimize keyword_analysis operations",
                "Schedule large jobs during off-peak hours",
            ],
        }
        mock_bigquery_service.cost_monitor.generate_cost_analytics.return_value = (
            mock_analytics
        )

        response = client.get(
            "/bigquery/cost-monitoring/analytics?customer_id=test_customer&period_days=30"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        analytics = data["data"]
        assert analytics["customer_id"] == "test_customer"
        assert analytics["cost_summary"]["total_cost_usd"] == 850.0
        assert analytics["cost_summary"]["cost_trend"] == "increasing"
        assert len(analytics["recommendations"]) == 2

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_cost_summary_report_weekly(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test weekly cost summary report endpoint."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock report response
        mock_report = {
            "report_type": "weekly",
            "customer_id": "test_customer",
            "period_days": 7,
            "generated_at": datetime.utcnow(),
            "executive_summary": {
                "total_cost_usd": 175.0,
                "budget_utilization_percentage": 70.0,
                "cost_trend": "stable",
                "unusual_patterns_detected": 1,
                "status": "moderate_usage",
            },
            "detailed_analytics": {"cost_summary": {"total_cost_usd": 175.0}},
            "unusual_patterns": [
                {
                    "pattern_type": "sustained_high_usage",
                    "severity": "medium",
                    "description": "Sustained high usage: 3 consecutive days above 150% of average",
                }
            ],
            "action_items": [
                "Monitor costs closely - approaching daily budget limit",
                "Review recent query patterns",
            ],
        }
        mock_bigquery_service.cost_monitor.get_cost_summary_report.return_value = (
            mock_report
        )

        response = client.get(
            "/bigquery/cost-monitoring/reports/weekly?customer_id=test_customer"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        report = data["data"]
        assert report["report_type"] == "weekly"
        assert report["executive_summary"]["total_cost_usd"] == 175.0
        assert len(report["action_items"]) == 2

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_cost_summary_report_invalid_type(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test cost summary report with invalid report type."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        response = client.get(
            "/bigquery/cost-monitoring/reports/invalid?customer_id=test_customer"
        )

        assert response.status_code == 400
        assert (
            "Report type must be daily, weekly, or monthly" in response.json()["detail"]
        )

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_set_customer_budget_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test successful customer budget configuration."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock budget config response
        mock_budget_config = CustomerBudgetConfig(
            customer_id="test_customer",
            tier="premium",
            daily_limit_usd=75.0,
            monthly_limit_usd=2250.0,
            emergency_limit_usd=300.0,
        )
        mock_bigquery_service.cost_monitor.set_customer_budget.return_value = (
            mock_budget_config
        )

        response = client.post(
            "/bigquery/cost-monitoring/budget-config?"
            "customer_id=test_customer&tier=premium&daily_limit_usd=75.0&monthly_limit_usd=2250.0"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Budget configuration updated" in data["message"]
        budget_data = data["data"]
        assert budget_data["customer_id"] == "test_customer"
        assert budget_data["tier"] == "premium"
        assert budget_data["daily_limit_usd"] == 75.0

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_set_customer_budget_invalid_tier(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test customer budget configuration with invalid tier."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        response = client.post(
            "/bigquery/cost-monitoring/budget-config?"
            "customer_id=test_customer&tier=invalid&daily_limit_usd=75.0&monthly_limit_usd=2250.0"
        )

        assert response.status_code == 400
        assert (
            "Tier must be standard, premium, or enterprise" in response.json()["detail"]
        )

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_get_customer_budgets_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test successful retrieval of all customer budgets."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock budget configurations
        mock_budgets = {
            "customer_1": CustomerBudgetConfig(
                customer_id="customer_1",
                tier="standard",
                daily_limit_usd=25.0,
                monthly_limit_usd=750.0,
                emergency_limit_usd=100.0,
            ),
            "customer_2": CustomerBudgetConfig(
                customer_id="customer_2",
                tier="premium",
                daily_limit_usd=75.0,
                monthly_limit_usd=2250.0,
                emergency_limit_usd=300.0,
            ),
        }
        mock_bigquery_service.cost_monitor.get_customer_budgets.return_value = (
            mock_budgets
        )

        response = client.get("/bigquery/cost-monitoring/budget-config")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_customers"] == 2

        budgets = data["data"]
        assert "customer_1" in budgets
        assert "customer_2" in budgets
        assert budgets["customer_1"]["tier"] == "standard"
        assert budgets["customer_2"]["tier"] == "premium"

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_endpoint_error_handling(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test error handling in cost monitoring endpoints."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock service method to raise an exception
        mock_bigquery_service.cost_monitor.get_real_time_costs.side_effect = Exception(
            "Database connection failed"
        )

        response = client.get("/bigquery/cost-monitoring/real-time")

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

    def test_parameter_validation(self, client):
        """Test parameter validation for cost monitoring endpoints."""
        # Test invalid lookback_hours
        response = client.get("/bigquery/cost-monitoring/real-time?lookback_hours=0")
        assert response.status_code == 422

        # Test invalid period_days
        response = client.get("/bigquery/cost-monitoring/analytics?period_days=0")
        assert response.status_code == 422

        # Test negative additional_cost_usd
        response = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?customer_id=test&additional_cost_usd=-1"
        )
        assert response.status_code == 422

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_rate_limiting_simulation(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test that rate limiting is properly configured (simulation)."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Mock successful response
        mock_bigquery_service.cost_monitor.get_real_time_costs.return_value = {
            "customer_id": "test_customer",
            "daily_cost_usd": 10.0,
        }

        # Make multiple requests - in real scenario with Redis this would hit rate limits
        for i in range(5):
            response = client.get("/bigquery/cost-monitoring/real-time")
            # All should succeed in test environment (no Redis)
            assert response.status_code == 200


class TestCostMonitoringIntegration:
    """Integration tests for cost monitoring features."""

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_cost_monitoring_workflow(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test complete cost monitoring workflow."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Step 1: Set up customer budget
        mock_budget_config = CustomerBudgetConfig(
            customer_id="workflow_customer",
            tier="premium",
            daily_limit_usd=100.0,
            monthly_limit_usd=3000.0,
            emergency_limit_usd=400.0,
        )
        mock_bigquery_service.cost_monitor.set_customer_budget.return_value = (
            mock_budget_config
        )

        budget_response = client.post(
            "/bigquery/cost-monitoring/budget-config?"
            "customer_id=workflow_customer&tier=premium&daily_limit_usd=100.0&monthly_limit_usd=3000.0"
        )
        assert budget_response.status_code == 200

        # Step 2: Check real-time costs
        mock_bigquery_service.cost_monitor.get_real_time_costs.return_value = {
            "customer_id": "workflow_customer",
            "daily_cost_usd": 75.0,
            "status": "moderate_usage",
        }

        costs_response = client.get(
            "/bigquery/cost-monitoring/real-time?customer_id=workflow_customer"
        )
        assert costs_response.status_code == 200
        assert costs_response.json()["data"]["daily_cost_usd"] == 75.0

        # Step 3: Check budget enforcement (should be allowed)
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = {
            "allowed": True,
            "daily_cost_usd": 85.0,
            "alerts_triggered": [{"threshold_percentage": 80.0, "action": "review"}],
        }

        enforcement_response = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?"
            "customer_id=workflow_customer&additional_cost_usd=10.0"
        )
        assert enforcement_response.status_code == 200
        assert enforcement_response.json()["data"]["allowed"] is True

        # Step 4: Generate analytics
        mock_bigquery_service.cost_monitor.generate_cost_analytics.return_value = {
            "customer_id": "workflow_customer",
            "cost_summary": {"total_cost_usd": 2100.0},
            "recommendations": ["Optimize high-cost operations"],
        }

        analytics_response = client.get(
            "/bigquery/cost-monitoring/analytics?customer_id=workflow_customer"
        )
        assert analytics_response.status_code == 200
        assert (
            analytics_response.json()["data"]["cost_summary"]["total_cost_usd"]
            == 2100.0
        )

    @patch("paidsearchnav.api.routes.bigquery.get_bigquery_service")
    @patch("paidsearchnav.api.routes.bigquery.get_current_user")
    def test_escalating_cost_scenario(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_bigquery_service,
        mock_current_user,
    ):
        """Test escalating cost scenario with progressive enforcement."""
        mock_get_user.return_value = mock_current_user
        mock_get_service.return_value = mock_bigquery_service

        # Scenario: Customer approaching budget limits

        # Stage 1: 60% of budget - should be allowed with monitoring
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = {
            "allowed": True,
            "daily_cost_usd": 60.0,
            "alerts_triggered": [{"threshold_percentage": 50.0, "action": "monitor"}],
        }

        response1 = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?"
            "customer_id=escalation_test&additional_cost_usd=10.0"
        )
        assert response1.status_code == 200
        assert response1.json()["data"]["allowed"] is True

        # Stage 2: 90% of budget - should be allowed but with warnings
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = {
            "allowed": True,
            "daily_cost_usd": 90.0,
            "alerts_triggered": [
                {"threshold_percentage": 80.0, "action": "review"},
                {"threshold_percentage": 95.0, "action": "throttle"},
            ],
        }

        response2 = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?"
            "customer_id=escalation_test&additional_cost_usd=15.0"
        )
        assert response2.status_code == 200
        assert response2.json()["data"]["allowed"] is True
        assert len(response2.json()["data"]["alerts_triggered"]) == 2

        # Stage 3: Emergency limit exceeded - should be blocked
        mock_bigquery_service.cost_monitor.check_budget_enforcement.return_value = {
            "allowed": False,
            "reason": "Emergency cost limit exceeded",
            "daily_cost_usd": 250.0,
            "enforcement_actions": [
                {"action": "emergency_circuit_breaker", "severity": "critical"}
            ],
        }

        response3 = client.post(
            "/bigquery/cost-monitoring/budget-enforcement?"
            "customer_id=escalation_test&additional_cost_usd=100.0"
        )
        assert response3.status_code == 200
        assert response3.json()["data"]["allowed"] is False
        assert "Emergency cost limit exceeded" in response3.json()["data"]["reason"]
