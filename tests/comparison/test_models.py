"""Tests for comparison data models."""

from datetime import datetime

from paidsearchnav_mcp.comparison.models import (
    ComparisonMetrics,
    ComparisonOptions,
    ComparisonRequest,
    ComparisonResult,
    MetricType,
    TrendAnalysis,
    TrendDataPoint,
    TrendGranularity,
    TrendRequest,
)


class TestComparisonModels:
    """Test comparison data models."""

    def test_metric_type_enum(self):
        """Test MetricType enum values."""
        assert MetricType.TOTAL_SPEND.value == "total_spend"
        assert MetricType.CTR.value == "ctr"
        assert MetricType.CONVERSIONS.value == "conversions"

    def test_comparison_metrics_creation(self):
        """Test ComparisonMetrics dataclass creation."""
        metrics = ComparisonMetrics(
            total_spend_change=1000.0,
            total_spend_change_pct=10.5,
            wasted_spend_reduction=500.0,
            wasted_spend_reduction_pct=25.0,
            cost_per_conversion_change=-5.0,
            cost_per_conversion_change_pct=-8.0,
            roas_change=0.5,
            roas_change_pct=12.5,
            ctr_improvement=0.5,
            ctr_improvement_pct=10.0,
            conversion_rate_change=0.2,
            conversion_rate_change_pct=5.0,
            quality_score_trend=0.8,
            impressions_change=10000,
            impressions_change_pct=15.0,
            clicks_change=500,
            clicks_change_pct=12.0,
            conversions_change=50,
            conversions_change_pct=20.0,
            recommendations_implemented=15,
            recommendations_pending=5,
            issues_resolved=10,
            new_issues_found=3,
            keywords_analyzed_change=100,
            negative_keywords_added=50,
            match_type_optimizations=20,
        )

        assert metrics.total_spend_change == 1000.0
        assert metrics.wasted_spend_reduction_pct == 25.0
        assert metrics.ctr_improvement == 0.5
        assert metrics.recommendations_implemented == 15

    def test_comparison_options_defaults(self):
        """Test ComparisonOptions default values."""
        options = ComparisonOptions()

        assert options.include_statistical_tests is True
        assert options.confidence_level == 0.95
        assert options.minimum_sample_size == 30
        assert options.adjust_for_seasonality is False
        assert options.breakdown_by_campaign is False

    def test_comparison_result_creation(self):
        """Test ComparisonResult creation."""
        metrics = ComparisonMetrics(
            total_spend_change=1000.0,
            total_spend_change_pct=10.0,
            wasted_spend_reduction=500.0,
            wasted_spend_reduction_pct=20.0,
            cost_per_conversion_change=-5.0,
            cost_per_conversion_change_pct=-10.0,
            roas_change=0.5,
            roas_change_pct=15.0,
            ctr_improvement=0.3,
            ctr_improvement_pct=8.0,
            conversion_rate_change=0.2,
            conversion_rate_change_pct=5.0,
            quality_score_trend=0.5,
            impressions_change=5000,
            impressions_change_pct=10.0,
            clicks_change=200,
            clicks_change_pct=8.0,
            conversions_change=20,
            conversions_change_pct=10.0,
            recommendations_implemented=10,
            recommendations_pending=5,
            issues_resolved=8,
            new_issues_found=2,
            keywords_analyzed_change=50,
            negative_keywords_added=30,
            match_type_optimizations=15,
        )

        result = ComparisonResult(
            baseline_audit_id="audit-1",
            comparison_audit_id="audit-2",
            baseline_date=datetime(2024, 1, 1),
            comparison_date=datetime(2024, 2, 1),
            metrics=metrics,
            insights=["CTR improved significantly", "Wasted spend reduced"],
            warnings=["Quality score declining in some campaigns"],
        )

        assert result.baseline_audit_id == "audit-1"
        assert result.comparison_audit_id == "audit-2"
        assert len(result.insights) == 2
        assert len(result.warnings) == 1
        assert result.metrics.total_spend_change == 1000.0

    def test_trend_data_point(self):
        """Test TrendDataPoint creation."""
        point = TrendDataPoint(
            timestamp=datetime(2024, 1, 15),
            value=1500.0,
            metric_type=MetricType.TOTAL_SPEND,
            is_anomaly=True,
            anomaly_score=3.2,
        )

        assert point.timestamp.day == 15
        assert point.value == 1500.0
        assert point.metric_type == MetricType.TOTAL_SPEND
        assert point.is_anomaly is True
        assert point.anomaly_score == 3.2

    def test_trend_analysis_creation(self):
        """Test TrendAnalysis creation."""
        data_points = [
            TrendDataPoint(
                timestamp=datetime(2024, 1, i),
                value=1000.0 + i * 100,
                metric_type=MetricType.CONVERSIONS,
            )
            for i in range(1, 11)
        ]

        analysis = TrendAnalysis(
            customer_id="customer-123",
            metric_type=MetricType.CONVERSIONS,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            granularity=TrendGranularity.DAILY,
            data_points=data_points,
            trend_direction="increasing",
            trend_strength=0.85,
            seasonality_detected=False,
            anomalies_detected=0,
        )

        assert analysis.customer_id == "customer-123"
        assert len(analysis.data_points) == 10
        assert analysis.trend_direction == "increasing"
        assert analysis.trend_strength == 0.85

    def test_comparison_request_validation(self):
        """Test ComparisonRequest model."""
        request = ComparisonRequest(
            baseline_audit_id="audit-123",
            comparison_audit_id="audit-456",
        )

        assert request.baseline_audit_id == "audit-123"
        assert request.comparison_audit_id == "audit-456"
        assert request.options is None

    def test_trend_request_validation(self):
        """Test TrendRequest model."""
        request = TrendRequest(
            customer_id="customer-123",
            metric_types=[MetricType.CTR, MetricType.CONVERSIONS],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            granularity=TrendGranularity.MONTHLY,
            include_forecast=True,
            forecast_periods=3,
        )

        assert request.customer_id == "customer-123"
        assert len(request.metric_types) == 2
        assert request.granularity == TrendGranularity.MONTHLY
        assert request.include_forecast is True
        assert request.forecast_periods == 3
