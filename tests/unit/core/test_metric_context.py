"""Tests for metric context functionality."""

from datetime import datetime, timezone

from paidsearchnav_mcp.models.analysis import AnalysisMetrics, AnalysisResult
from paidsearchnav_mcp.models.base import (
    EnhancedKeyMetrics,
    MetricPeriod,
    MetricWithContext,
)
from paidsearchnav_mcp.models.bid_adjustment import (
    BidAdjustmentAnalysisResult,
    BidAdjustmentAnalysisSummary,
    BidOptimization,
)


class TestMetricWithContext:
    """Test MetricWithContext model."""

    def test_metric_with_context_creation(self):
        """Test creating a MetricWithContext object."""
        metric = MetricWithContext(
            value=123.45,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test metric",
            calculation_method="Test calculation",
        )

        assert metric.value == 123.45
        assert metric.period == MetricPeriod.MONTHLY_PROJECTION
        assert metric.unit == "USD"
        assert metric.description == "Test metric"
        assert metric.calculation_method == "Test calculation"

    def test_metric_with_context_optional_fields(self):
        """Test MetricWithContext with optional fields."""
        metric = MetricWithContext(
            value=100,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="count",
            description="Test metric without calculation method",
        )

        assert metric.calculation_method is None


class TestEnhancedKeyMetrics:
    """Test EnhancedKeyMetrics model."""

    def test_enhanced_key_metrics_creation(self):
        """Test creating an EnhancedKeyMetrics object."""
        metric1 = MetricWithContext(
            value=100,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="count",
            description="Test metric 1",
        )

        metric2 = MetricWithContext(
            value=50.0,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test metric 2",
        )

        enhanced_metrics = EnhancedKeyMetrics(
            reporting_period="2025-08-24 to 2025-08-31 (7 days)",
            metrics={"metric1": metric1, "metric2": metric2},
        )

        assert enhanced_metrics.reporting_period == "2025-08-24 to 2025-08-31 (7 days)"
        assert len(enhanced_metrics.metrics) == 2
        assert "metric1" in enhanced_metrics.metrics
        assert "metric2" in enhanced_metrics.metrics
        assert enhanced_metrics.metrics["metric1"].value == 100
        assert enhanced_metrics.metrics["metric2"].value == 50.0


class TestAnalysisResultKeyMetrics:
    """Test key_metrics property on AnalysisResult."""

    def test_analysis_result_key_metrics(self):
        """Test key_metrics property on AnalysisResult."""
        start_date = datetime(2025, 8, 24, tzinfo=timezone.utc)
        end_date = datetime(2025, 8, 31, tzinfo=timezone.utc)

        metrics = AnalysisMetrics(
            total_keywords_analyzed=100,
            total_campaigns_analyzed=10,
            issues_found=25,
            critical_issues=5,
            potential_cost_savings=1234.56,
            custom_metrics={
                "negative_suggestions_found": 15,
                "waste_blocked": 500.0,
                "revenue_loss": 750.0,
            },
        )

        result = AnalysisResult(
            customer_id="123456789",
            analysis_type="test_analysis",
            analyzer_name="TestAnalyzer",
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            recommendations=[],
        )

        key_metrics = result.key_metrics

        # Test basic structure
        assert isinstance(key_metrics, EnhancedKeyMetrics)
        assert key_metrics.reporting_period == "2025-08-24 to 2025-08-31 (8 days)"

        # Test core metrics
        assert "total_analyzed" in key_metrics.metrics
        assert "issues_found" in key_metrics.metrics
        assert "critical_issues" in key_metrics.metrics
        assert "potential_cost_savings" in key_metrics.metrics
        assert "total_recommendations" in key_metrics.metrics

        # Test metric values
        assert key_metrics.metrics["total_analyzed"].value == 100
        assert key_metrics.metrics["issues_found"].value == 25
        assert key_metrics.metrics["critical_issues"].value == 5
        assert key_metrics.metrics["potential_cost_savings"].value == 1234.56

        # Test metric periods
        assert (
            key_metrics.metrics["issues_found"].period == MetricPeriod.REPORTING_PERIOD
        )
        assert (
            key_metrics.metrics["potential_cost_savings"].period
            == MetricPeriod.MONTHLY_PROJECTION
        )

        # Test custom metrics
        assert "negative_suggestions_found" in key_metrics.metrics
        assert "waste_blocked" in key_metrics.metrics
        assert "revenue_loss" in key_metrics.metrics

        # Test custom metric periods
        assert (
            key_metrics.metrics["negative_suggestions_found"].period
            == MetricPeriod.REPORTING_PERIOD
        )
        assert (
            key_metrics.metrics["waste_blocked"].period == MetricPeriod.MONTHLY_CURRENT
        )
        assert (
            key_metrics.metrics["revenue_loss"].period
            == MetricPeriod.MONTHLY_PROJECTION
        )


class TestBidAdjustmentAnalysisKeyMetrics:
    """Test key_metrics property on BidAdjustmentAnalysisResult."""

    def test_bid_adjustment_key_metrics(self):
        """Test key_metrics property on BidAdjustmentAnalysisResult."""
        start_date = datetime(2025, 8, 24, tzinfo=timezone.utc)
        end_date = datetime(2025, 8, 31, tzinfo=timezone.utc)

        # Create optimization opportunities
        optimizations = [
            BidOptimization(
                adjustment_id="opt1",
                campaign_name="Test Campaign 1",
                current_bid_modifier=1.50,
                recommended_bid_modifier=2.00,
                expected_impact="Increase conversions by 15%",
                reasoning="Performance analysis suggests bid increase",
                priority="High",
                estimated_cost_savings=250.0,
                confidence_score=0.85,
            ),
            BidOptimization(
                adjustment_id="opt2",
                campaign_name="Test Campaign 2",
                current_bid_modifier=3.00,
                recommended_bid_modifier=2.25,
                expected_impact="Reduce CPA by 10%",
                reasoning="Over-bidding detected",
                priority="Medium",
                estimated_cost_savings=150.0,
                confidence_score=0.75,
            ),
        ]

        summary = BidAdjustmentAnalysisSummary(
            total_campaigns_analyzed=5,
            total_bid_adjustments=25,
            total_impressions=10000,
            total_clicks=500,
            total_conversions=50.0,
            total_cost=2500.0,
            avg_roi=2.5,
            optimal_adjustments_count=15,
            over_bidding_count=5,
            under_bidding_count=5,
            top_optimization_opportunities=optimizations,
            key_insights=["Test insight 1", "Test insight 2"],
            data_quality_score=85.0,
            analysis_confidence=80.0,
        )

        result = BidAdjustmentAnalysisResult(
            customer_id="123456789",
            analysis_date=datetime.now(timezone.utc),
            start_date=start_date,
            end_date=end_date,
            bid_adjustments=[],
            bid_strategies=[],
            optimizations=optimizations,
            competitive_insights=None,
            summary=summary,
        )

        key_metrics = result.key_metrics

        # Test structure
        assert isinstance(key_metrics, EnhancedKeyMetrics)
        assert key_metrics.reporting_period == "2025-08-24 to 2025-08-31 (8 days)"

        # Test specific metrics
        assert "device_adjustments" in key_metrics.metrics
        assert "campaigns_analyzed" in key_metrics.metrics
        assert "potential_savings" in key_metrics.metrics
        assert "optimization_status" in key_metrics.metrics

        # Test metric values
        assert key_metrics.metrics["device_adjustments"].value == 25
        assert key_metrics.metrics["campaigns_analyzed"].value == 5
        assert (
            key_metrics.metrics["potential_savings"].value == 400.0
        )  # sum of optimizations

        # Test metric periods
        assert (
            key_metrics.metrics["device_adjustments"].period
            == MetricPeriod.REPORTING_PERIOD
        )
        assert (
            key_metrics.metrics["potential_savings"].period
            == MetricPeriod.MONTHLY_PROJECTION
        )

        # Test complex metric values
        optimization_status = key_metrics.metrics["optimization_status"].value
        assert optimization_status["optimal"] == 15
        assert optimization_status["over_bidding"] == 5
        assert optimization_status["under_bidding"] == 5
