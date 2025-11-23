"""Integration tests for DaypartingAnalyzer CSV functionality."""

from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.dayparting import (
    DaypartingAnalysisResult,
    DaypartingAnalyzer,
)
from paidsearchnav_mcp.models import RecommendationPriority, RecommendationType


class TestDaypartingCSVIntegration:
    """Integration tests for DaypartingAnalyzer with real CSV data."""

    @pytest.fixture
    def test_csv_path(self):
        """Path to test CSV file."""
        return Path("test_data/exports/test_ad_schedule.csv")

    async def test_analyze_with_real_csv_file(self, test_csv_path):
        """Test analysis with real CSV file from test_data."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        # Load CSV data
        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)

        # Run analysis
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Verify result structure
        assert isinstance(result, DaypartingAnalysisResult)
        assert result.customer_id == "test_customer"
        assert result.analyzer_name == "dayparting"
        assert result.analysis_type == "ad_schedule_optimization"

        # Verify data was loaded and processed
        assert len(result.schedule_data) > 0
        assert len(result.day_performance) > 0

        # Verify expected days are present
        expected_days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        for day in result.day_performance.keys():
            assert day in expected_days

        # Verify metrics are calculated
        for day, metrics in result.day_performance.items():
            assert "impressions" in metrics
            assert "clicks" in metrics
            assert "conversions" in metrics
            assert "cost" in metrics
            assert "ctr" in metrics
            assert "conversion_rate" in metrics
            assert "cpa" in metrics
            assert "avg_cpc" in metrics

        # Verify best/worst performers identified
        assert len(result.best_performing_days) > 0
        # Worst performers may be empty if all days perform similarly
        assert isinstance(result.worst_performing_days, list)

        # Verify recommendations list exists (may be empty if no issues found)
        assert isinstance(result.recommendations, list)
        # If recommendations exist, verify they're valid
        for rec in result.recommendations:
            assert rec.type in RecommendationType.__members__.values()
            assert rec.priority in RecommendationPriority.__members__.values()
            assert rec.title
            assert rec.description

    async def test_hour_performance_analysis(self, test_csv_path):
        """Test hour-based performance analysis from CSV."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check hour performance (if data has hourly breakdowns)
        if result.hour_performance:
            for hour, metrics in result.hour_performance.items():
                assert "impressions" in metrics
                assert "clicks" in metrics
                assert "conversions" in metrics
                assert "cost" in metrics
                assert "ctr" in metrics
                assert "conversion_rate" in metrics

            # Check best/worst hours if identified
            if result.best_performing_hours:
                assert len(result.best_performing_hours) > 0
                for hour_data in result.best_performing_hours:
                    assert "hour" in hour_data
                    assert "conversion_rate" in hour_data

    async def test_bid_adjustment_recommendations(self, test_csv_path):
        """Test bid adjustment recommendations from CSV data."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check bid adjustment recommendations
        if result.bid_adjustment_recommendations:
            for bid_rec in result.bid_adjustment_recommendations:
                assert "day" in bid_rec or "hour" in bid_rec
                assert "recommended_bid_adjustment" in bid_rec
                assert "reason" in bid_rec

                # Verify bid adjustments are within reasonable bounds
                if "recommended_bid_adjustment" in bid_rec:
                    adj = bid_rec["recommended_bid_adjustment"]
                    assert -50 <= adj <= 30  # Between -50% and +30%

    async def test_variance_analysis(self, test_csv_path):
        """Test variance metrics calculation from CSV data."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check variance metrics
        assert hasattr(result, "conversion_rate_variance_by_day")
        assert isinstance(result.conversion_rate_variance_by_day, float)
        assert result.conversion_rate_variance_by_day >= 0

        assert hasattr(result, "cost_efficiency_variance")
        assert isinstance(result.cost_efficiency_variance, float)
        assert result.cost_efficiency_variance >= 0

    async def test_potential_improvements(self, test_csv_path):
        """Test calculation of potential improvements from CSV data."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check potential improvements
        assert hasattr(result, "potential_savings")
        assert isinstance(result.potential_savings, float)
        assert result.potential_savings >= 0

        assert hasattr(result, "potential_conversion_increase")
        assert isinstance(result.potential_conversion_increase, float)
        assert result.potential_conversion_increase >= 0

    async def test_campaign_filtering(self, test_csv_path):
        """Test that campaign names are preserved from CSV."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)

        # Check that campaign names were loaded
        campaigns_in_data = set()
        for record in analyzer._csv_data:
            if record.campaign_name:
                campaigns_in_data.add(record.campaign_name)

        assert len(campaigns_in_data) > 0

        # Run analysis
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Verify schedule data includes campaign information
        for schedule_record in result.schedule_data:
            if schedule_record.campaign_name:
                assert schedule_record.campaign_name in campaigns_in_data

    async def test_schedule_recommendations(self, test_csv_path):
        """Test schedule expansion and reduction recommendations."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check schedule recommendations
        if result.schedule_expansion_recommendations:
            for rec in result.schedule_expansion_recommendations:
                assert isinstance(rec, str)
                assert len(rec) > 0

        if result.schedule_reduction_recommendations:
            for rec in result.schedule_reduction_recommendations:
                assert isinstance(rec, str)
                assert len(rec) > 0

    async def test_minimum_threshold_filtering(self, test_csv_path):
        """Test that minimum impression threshold is applied."""
        if not test_csv_path.exists():
            pytest.skip(f"Test CSV file not found: {test_csv_path}")

        # Create analyzer with high minimum thresholds
        analyzer = DaypartingAnalyzer.from_csv(test_csv_path)
        analyzer.min_impressions = 5000  # High threshold

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 30),
        )

        # Check that filtering was applied
        for record in result.schedule_data:
            assert record.impressions >= analyzer.min_impressions
