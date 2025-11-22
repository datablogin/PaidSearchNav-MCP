"""Integration tests for Ad Group Performance Analyzer with CSV data."""

from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.ad_group_performance import AdGroupPerformanceAnalyzer
from paidsearchnav_mcp.models.analysis import (
    RecommendationPriority,
    RecommendationType,
)


@pytest.mark.integration
class TestAdGroupCSVIntegration:
    """Integration tests using real CSV data."""

    @pytest.fixture
    def sample_csv_path(self):
        """Get path to sample ad group CSV file."""
        csv_path = Path("test_data/exports/test_ad_groups.csv")
        if not csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {csv_path}")
        return csv_path

    def test_load_sample_csv(self, sample_csv_path):
        """Test loading the actual sample CSV file."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        assert analyzer._csv_data is not None
        assert len(analyzer._csv_data) > 0

        # Verify some expected data from the sample
        campaign_names = {ag.campaign_name for ag in analyzer._csv_data}
        assert "Test Campaign 1" in campaign_names

        # Check that data is properly parsed
        for ad_group in analyzer._csv_data:
            assert ad_group.campaign_name
            assert ad_group.ad_group_name
            assert ad_group.status
            assert ad_group.impressions >= 0
            assert ad_group.clicks >= 0
            assert ad_group.cost >= 0

    @pytest.mark.asyncio
    async def test_analyze_sample_data(self, sample_csv_path):
        """Test full analysis with sample CSV data."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        assert result.status == "completed"
        assert result.customer_id == "test_customer"
        assert result.analysis_type == "ad_group_performance"

        # Check metrics
        assert result.metrics.custom_metrics["total_ad_groups_analyzed"] > 0
        assert result.metrics.total_campaigns_analyzed > 0

        # Check raw data
        assert "total_ad_groups" in result.raw_data
        assert "active_ad_groups" in result.raw_data
        assert "performance_summary" in result.raw_data

        # Verify performance summary
        perf_summary = result.raw_data["performance_summary"]
        assert perf_summary["total_impressions"] > 0
        assert perf_summary["total_clicks"] > 0
        assert perf_summary["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_recommendations_generated(self, sample_csv_path):
        """Test that appropriate recommendations are generated."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        # Check for various types of recommendations
        rec_types = {r.type for r in result.recommendations}

        # The sample data should generate some recommendations
        assert len(result.recommendations) > 0

        # Check recommendation priorities
        priorities = {r.priority for r in result.recommendations}

        # Verify recommendation structure
        for rec in result.recommendations:
            assert rec.title
            assert rec.description
            assert rec.type in RecommendationType.__members__.values()
            assert rec.priority in RecommendationPriority.__members__.values()

    @pytest.mark.asyncio
    async def test_campaign_level_analysis(self, sample_csv_path):
        """Test campaign-level analysis and insights."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        # Check campaign breakdown in raw data
        assert "campaign_breakdown" in result.raw_data
        campaign_breakdown = result.raw_data["campaign_breakdown"]

        # Verify campaigns are properly grouped
        assert len(campaign_breakdown) > 0

        for campaign_name, ad_groups in campaign_breakdown.items():
            assert isinstance(ad_groups, list)
            assert len(ad_groups) > 0
            # All ad groups should belong to the same campaign
            for ag in ad_groups:
                assert ag.campaign_name == campaign_name

    @pytest.mark.asyncio
    async def test_performance_thresholds(self, sample_csv_path):
        """Test analysis with custom performance thresholds."""
        # Use strict thresholds to generate more recommendations
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)
        analyzer.low_ctr_threshold = 10.0  # Very high CTR threshold
        analyzer.high_cpa_threshold = 10.0  # Very low CPA threshold

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        # With strict thresholds, we should get more recommendations
        assert len(result.recommendations) > 0

        # Check for specific recommendation types
        low_ctr_recs = [r for r in result.recommendations if "Low CTR" in r.title]
        high_cpa_recs = [r for r in result.recommendations if "High CPA" in r.title]

        # At least one of these should be present with strict thresholds
        assert len(low_ctr_recs) > 0 or len(high_cpa_recs) > 0

    def test_csv_with_special_characters(self, tmp_path):
        """Test CSV parsing with special characters in names."""
        csv_content = """Campaign,Ad group,Ad group state,Impr.,Clicks,Cost,Conversions
"Campaign with, comma","Ad Group (special)",Enabled,"1,000",50,100.00,5
"Campaign - dash","Ad Group & symbol",Enabled,"2,000",100,200.00,10
"""
        csv_file = tmp_path / "special_chars.csv"
        csv_file.write_text(csv_content)

        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        assert len(analyzer._csv_data) == 2
        assert analyzer._csv_data[0].campaign_name == "Campaign with, comma"
        assert analyzer._csv_data[0].ad_group_name == "Ad Group (special)"
        assert analyzer._csv_data[1].campaign_name == "Campaign - dash"
        assert analyzer._csv_data[1].ad_group_name == "Ad Group & symbol"

    @pytest.mark.asyncio
    async def test_paused_ad_groups_excluded(self, sample_csv_path):
        """Test that paused ad groups are excluded from active analysis."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        # Check that paused ad groups are counted but not analyzed
        total_ad_groups = result.raw_data["total_ad_groups"]
        active_ad_groups = result.raw_data["active_ad_groups"]
        paused_ad_groups = result.raw_data["paused_ad_groups"]

        # There should be some paused ad groups in the sample
        assert paused_ad_groups >= 0
        assert active_ad_groups + paused_ad_groups <= total_ad_groups

    @pytest.mark.asyncio
    async def test_metrics_calculation(self, sample_csv_path):
        """Test that metrics are calculated correctly."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
        )

        # Check calculated metrics
        metrics = result.metrics
        assert metrics.issues_found == len(result.recommendations)
        assert metrics.critical_issues == len(
            [
                r
                for r in result.recommendations
                if r.priority == RecommendationPriority.CRITICAL
            ]
        )
        assert metrics.potential_cost_savings > 0

        # Check custom metrics
        assert "total_ad_groups_analyzed" in metrics.custom_metrics
        assert "underperforming_ad_groups" in metrics.custom_metrics
        assert "bidding_issues" in metrics.custom_metrics
        assert "quality_issues" in metrics.custom_metrics

    def test_csv_error_handling(self, tmp_path):
        """Test error handling for malformed CSV data."""
        # CSV with inconsistent columns
        csv_content = """Campaign,Ad group,Ad group state,Impr.,Clicks
Test Campaign,Ad Group 1,Enabled,1000
Test Campaign,Ad Group 2,Enabled,2000,100,Extra,Column
"""
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(csv_content)

        # Should handle gracefully and parse what it can
        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        # At least one row should be parsed
        assert len(analyzer._csv_data) >= 1

    @pytest.mark.asyncio
    async def test_empty_data_handling(self, tmp_path):
        """Test handling of CSV with valid headers but no data."""
        csv_content = """Campaign,Ad group,Ad group state,Impr.,Clicks,Cost,Conversions
"""
        csv_file = tmp_path / "empty_data.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="No valid ad group data found"):
            AdGroupPerformanceAnalyzer.from_csv(csv_file)
