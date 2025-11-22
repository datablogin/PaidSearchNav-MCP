"""Integration test for CompetitorInsightsAnalyzer CSV parsing with sample data."""

from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav.analyzers.competitor_insights import CompetitorInsightsAnalyzer
from paidsearchnav.core.models import RecommendationType


class TestCompetitorInsightsCSVIntegration:
    """Integration tests for CSV parsing with actual sample data."""

    @pytest.fixture
    def sample_csv_path(self):
        """Get path to sample auction insights CSV."""
        return Path("test_data/exports/auction_insights_sample.csv")

    def test_parse_sample_csv_file(self, sample_csv_path):
        """Test parsing the actual sample CSV file."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_path)

        # Verify data was loaded
        assert hasattr(analyzer, "_csv_data")
        assert len(analyzer._csv_data) > 0

        # Check data structure
        for insight in analyzer._csv_data:
            assert insight.competitor_domain
            assert insight.competitor_domain != "yourdomain.com"
            # At least overlap_rate should be present for competitors
            assert insight.overlap_rate is not None

        # Verify specific competitors from sample
        domains = [d.competitor_domain for d in analyzer._csv_data]
        expected_domains = [
            "competitor1.com",
            "competitor2.com",
            "competitor3.com",
            "competitor4.com",
            "competitor5.com",
            "localstore.com",
            "cityshop.net",
        ]
        for domain in expected_domains:
            assert domain in domains

    @pytest.mark.asyncio
    async def test_analyze_sample_csv_data(self, sample_csv_path):
        """Test full analysis with sample CSV data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        # Load CSV data
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_path)

        # Run analysis
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime(2024, 12, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Verify results
        assert len(result.auction_data) == 7  # 7 competitors in sample
        assert len(result.competitor_rankings) == 7

        # Check top competitor
        top_competitor = result.competitor_rankings[0]
        assert top_competitor["domain"] in ["competitor1.com", "competitor2.com"]
        assert top_competitor["threat_score"] > 0

        # Verify recommendations were generated
        assert len(result.recommendations) > 0
        rec_types = [rec.type for rec in result.recommendations]
        assert RecommendationType.ADJUST_BID in rec_types

    def test_csv_parsing_performance(self, sample_csv_path):
        """Test CSV parsing performance metrics."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        import time

        start_time = time.time()
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_path)
        parse_time = time.time() - start_time

        # Should parse quickly (under 1 second for small file)
        assert parse_time < 1.0
        assert len(analyzer._csv_data) == 7

    @pytest.mark.asyncio
    async def test_csv_data_validation(self, sample_csv_path):
        """Test that CSV data is properly validated."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_path)

        # Verify data ranges
        for insight in analyzer._csv_data:
            # All percentage values should be between 0 and 1
            if insight.impression_share is not None:
                assert 0 <= insight.impression_share <= 1
            if insight.overlap_rate is not None:
                assert 0 <= insight.overlap_rate <= 1
            if insight.top_of_page_rate is not None:
                assert 0 <= insight.top_of_page_rate <= 1
            if insight.abs_top_of_page_rate is not None:
                assert 0 <= insight.abs_top_of_page_rate <= 1
            if insight.outranking_share is not None:
                assert 0 <= insight.outranking_share <= 1
            if insight.position_above_rate is not None:
                assert 0 <= insight.position_above_rate <= 1

    @pytest.mark.asyncio
    async def test_competitive_analysis_accuracy(self, sample_csv_path):
        """Test accuracy of competitive analysis with real data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_path)
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime(2024, 12, 1),
            end_date=datetime(2024, 12, 31),
        )

        # Competitor1 should be high threat (high overlap, position above)
        competitor1_ranking = next(
            (r for r in result.competitor_rankings if r["domain"] == "competitor1.com"),
            None,
        )
        assert competitor1_ranking is not None
        assert competitor1_ranking["avg_overlap_rate"] > 0.15
        assert competitor1_ranking["avg_position_above_rate"] > 0.20

        # Should identify aggressive competitors
        if result.aggressive_competitors:
            aggressive_domains = [c["domain"] for c in result.aggressive_competitors]
            # Competitor1 or competitor2 should be marked as aggressive
            assert any(
                domain in aggressive_domains
                for domain in ["competitor1.com", "competitor2.com"]
            )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
