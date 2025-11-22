"""Tests for metric context enhancements - validation, aggregation, and formatting."""

import pytest

from paidsearchnav_mcp.models.base import (
    EnhancedKeyMetrics,
    MetricPeriod,
    MetricWithContext,
)


class TestMetricValidation:
    """Test metric validation rules."""

    def test_negative_savings_validation_error(self):
        """Test that negative savings values raise validation error."""
        with pytest.raises(
            ValueError, match="Savings and revenue metrics must be non-negative"
        ):
            MetricWithContext(
                value=-100.0,
                period=MetricPeriod.MONTHLY_PROJECTION,
                unit="USD",
                description="Test savings metric",
            )

    def test_negative_revenue_validation_error(self):
        """Test that negative revenue values raise validation error."""
        with pytest.raises(
            ValueError, match="Savings and revenue metrics must be non-negative"
        ):
            MetricWithContext(
                value=-500.0,
                period=MetricPeriod.MONTHLY_PROJECTION,
                unit="USD",
                description="Test revenue opportunity",
            )

    def test_percentage_out_of_range_validation_error(self):
        """Test that percentage values outside 0-100 range raise validation error."""
        with pytest.raises(
            ValueError, match="Percentage values must be between 0 and 100"
        ):
            MetricWithContext(
                value=150.0,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="percentage",
                description="Test percentage metric",
            )

        with pytest.raises(
            ValueError, match="Percentage values must be between 0 and 100"
        ):
            MetricWithContext(
                value=-10.0,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="percentage",
                description="Test percentage metric",
            )

    def test_negative_count_validation_error(self):
        """Test that negative count values raise validation error."""
        with pytest.raises(ValueError, match="Count metrics must be non-negative"):
            MetricWithContext(
                value=-5,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Test count metric",
            )

    def test_valid_values_pass_validation(self):
        """Test that valid values pass validation."""
        # Valid savings metric
        metric1 = MetricWithContext(
            value=1000.0,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test savings metric",
        )
        assert metric1.value == 1000.0

        # Valid percentage metric
        metric2 = MetricWithContext(
            value=85.5,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="percentage",
            description="Test percentage metric",
        )
        assert metric2.value == 85.5

        # Valid count metric
        metric3 = MetricWithContext(
            value=100,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="count",
            description="Test count metric",
        )
        assert metric3.value == 100


class TestMetricFormatting:
    """Test metric formatting for different locales and currencies."""

    def test_usd_formatting_us_locale(self):
        """Test USD formatting for US locale."""
        metric = MetricWithContext(
            value=1234.56,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test savings",
        )

        formatted = metric.format_value(locale="en_US")
        assert formatted == "$1,234.56"

    def test_usd_formatting_gb_locale(self):
        """Test USD formatting for GB locale with different currencies."""
        metric = MetricWithContext(
            value=1234.56,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test savings",
        )

        # USD in GB format
        formatted_usd = metric.format_value(locale="en_GB", currency="USD")
        assert formatted_usd == "$1,234.56"

        # EUR in GB format
        formatted_eur = metric.format_value(locale="en_GB", currency="EUR")
        assert formatted_eur == "€1,234.56"

        # GBP in GB format
        formatted_gbp = metric.format_value(locale="en_GB", currency="GBP")
        assert formatted_gbp == "£1,234.56"

    def test_usd_formatting_german_locale(self):
        """Test USD formatting for German locale."""
        metric = MetricWithContext(
            value=1234.56,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Test savings",
        )

        formatted = metric.format_value(locale="de_DE")
        assert formatted == "1.234,56 $"

    def test_percentage_formatting(self):
        """Test percentage formatting for different locales."""
        metric = MetricWithContext(
            value=85.5,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="percentage",
            description="Test percentage",
        )

        # US locale
        formatted_us = metric.format_value(locale="en_US")
        assert formatted_us == "85.5%"

        # German locale
        formatted_de = metric.format_value(locale="de_DE")
        assert formatted_de == "85,5%"

    def test_count_formatting(self):
        """Test count formatting for different locales."""
        metric = MetricWithContext(
            value=12345,
            period=MetricPeriod.REPORTING_PERIOD,
            unit="count",
            description="Test count",
        )

        # US locale
        formatted_us = metric.format_value(locale="en_US")
        assert formatted_us == "12,345"

        # German locale
        formatted_de = metric.format_value(locale="de_DE")
        assert formatted_de == "12.345"

    def test_to_display_dict(self):
        """Test conversion to display dictionary."""
        metric = MetricWithContext(
            value=1500.75,
            period=MetricPeriod.MONTHLY_PROJECTION,
            unit="USD",
            description="Monthly savings estimate",
            calculation_method="Based on 7-day analysis",
        )

        display_dict = metric.to_display_dict(locale="en_US", currency="USD")

        assert display_dict["raw_value"] == 1500.75
        assert display_dict["formatted_value"] == "$1,500.75"
        assert display_dict["unit"] == "USD"
        assert display_dict["period"] == "monthly_projection"
        assert display_dict["period_label"] == "Monthly Projection"
        assert display_dict["description"] == "Monthly savings estimate"
        assert display_dict["calculation_method"] == "Based on 7-day analysis"


class TestMetricAggregation:
    """Test metric aggregation utilities."""

    def create_sample_metrics(self) -> EnhancedKeyMetrics:
        """Create sample metrics for testing."""
        return EnhancedKeyMetrics(
            reporting_period="2025-08-24 to 2025-08-31 (7 days)",
            metrics={
                "total_cost": MetricWithContext(
                    value=1000.0,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="USD",
                    description="Total cost",
                ),
                "conversion_rate": MetricWithContext(
                    value=5.5,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="percentage",
                    description="Conversion rate",
                ),
                "total_clicks": MetricWithContext(
                    value=500,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="count",
                    description="Total clicks",
                ),
                "potential_savings": MetricWithContext(
                    value=200.0,
                    period=MetricPeriod.MONTHLY_PROJECTION,
                    unit="USD",
                    description="Potential monthly savings",
                ),
            },
        )

    def test_get_metrics_by_period(self):
        """Test filtering metrics by period type."""
        metrics = self.create_sample_metrics()

        # Get reporting period metrics
        reporting_metrics = metrics.get_metrics_by_period(MetricPeriod.REPORTING_PERIOD)
        assert len(reporting_metrics) == 3  # total_cost, conversion_rate, total_clicks
        assert "total_cost" in reporting_metrics
        assert "conversion_rate" in reporting_metrics
        assert "total_clicks" in reporting_metrics

        # Get monthly projection metrics
        projection_metrics = metrics.get_metrics_by_period(
            MetricPeriod.MONTHLY_PROJECTION
        )
        assert len(projection_metrics) == 1  # potential_savings
        assert "potential_savings" in projection_metrics

    def test_get_financial_metrics(self):
        """Test filtering financial metrics."""
        metrics = self.create_sample_metrics()

        financial_metrics = metrics.get_financial_metrics()
        assert len(financial_metrics) == 2  # total_cost, potential_savings
        assert "total_cost" in financial_metrics
        assert "potential_savings" in financial_metrics
        assert financial_metrics["total_cost"].unit == "USD"
        assert financial_metrics["potential_savings"].unit == "USD"

    def test_get_summary_for_dashboard(self):
        """Test dashboard summary generation."""
        metrics = self.create_sample_metrics()

        summary = metrics.get_summary_for_dashboard()

        assert summary["reporting_period"] == "2025-08-24 to 2025-08-31 (7 days)"

        # Check financial summary
        assert "total_cost" in summary["financial_summary"]
        assert "potential_savings" in summary["financial_summary"]
        assert summary["financial_summary"]["total_cost"]["value"] == 1000.0
        assert (
            summary["financial_summary"]["potential_savings"]["period"]
            == "monthly_projection"
        )

        # Check performance summary
        assert "conversion_rate" in summary["performance_summary"]
        assert summary["performance_summary"]["conversion_rate"]["value"] == 5.5
        assert summary["performance_summary"]["conversion_rate"]["unit"] == "percentage"

        # Check operational summary
        assert "total_clicks" in summary["operational_summary"]
        assert summary["operational_summary"]["total_clicks"]["value"] == 500

    def test_aggregate_multiple_metrics(self):
        """Test aggregating multiple EnhancedKeyMetrics instances."""
        # Create two metrics instances
        metrics1 = EnhancedKeyMetrics(
            reporting_period="Analysis 1",
            metrics={
                "total_cost": MetricWithContext(
                    value=1000.0,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="USD",
                    description="Total cost",
                ),
                "total_clicks": MetricWithContext(
                    value=500,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="count",
                    description="Total clicks",
                ),
                "conversion_rate": MetricWithContext(
                    value=5.0,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="percentage",
                    description="Conversion rate",
                ),
            },
        )

        metrics2 = EnhancedKeyMetrics(
            reporting_period="Analysis 2",
            metrics={
                "total_cost": MetricWithContext(
                    value=1500.0,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="USD",
                    description="Total cost",
                ),
                "total_clicks": MetricWithContext(
                    value=750,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="count",
                    description="Total clicks",
                ),
                "conversion_rate": MetricWithContext(
                    value=7.0,
                    period=MetricPeriod.REPORTING_PERIOD,
                    unit="percentage",
                    description="Conversion rate",
                ),
            },
        )

        # Aggregate the metrics
        aggregated = EnhancedKeyMetrics.aggregate_multiple_metrics(
            [metrics1, metrics2], "Combined Campaign Analysis"
        )

        assert aggregated.reporting_period == "Combined Campaign Analysis (2 analyses)"

        # Check aggregated values
        assert aggregated.metrics["total_cost"].value == 2500.0  # 1000 + 1500
        assert aggregated.metrics["total_clicks"].value == 1250  # 500 + 750
        assert aggregated.metrics["conversion_rate"].value == 6.0  # (5 + 7) / 2

        # Check that metadata is preserved
        assert all("aggregated" in m.description for m in aggregated.metrics.values())
        assert all(
            "Aggregated from 2 analyses" in m.calculation_method
            for m in aggregated.metrics.values()
        )

    def test_aggregate_empty_metrics_list(self):
        """Test aggregating empty metrics list."""
        aggregated = EnhancedKeyMetrics.aggregate_multiple_metrics([])

        assert aggregated.reporting_period == "No data"
        assert len(aggregated.metrics) == 0
