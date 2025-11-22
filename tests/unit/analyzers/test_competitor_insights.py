"""Unit tests for CompetitorInsightsAnalyzer."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav.analyzers.competitor_insights import (
    CompetitorInsightsAnalyzer,
    CompetitorInsightsResult,
)
from paidsearchnav.core.models import (
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.platforms.google import AuctionInsights


class TestCompetitorInsightsAnalyzer:
    """Test cases for CompetitorInsightsAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return CompetitorInsightsAnalyzer()

    @pytest.fixture
    def sample_auction_data(self):
        """Create sample auction insights data."""
        return [
            AuctionInsights(
                competitor_domain="competitor1.com",
                impression_share=0.25,
                overlap_rate=0.75,
                top_of_page_rate=0.80,
                abs_top_of_page_rate=0.60,
                outranking_share=0.20,
                position_above_rate=0.70,
                campaign_name="Brand Campaign",
                campaign_id="123",
                date_range="2024-01-01 - 2024-01-31",
            ),
            AuctionInsights(
                competitor_domain="competitor2.com",
                impression_share=0.30,
                overlap_rate=0.50,
                top_of_page_rate=0.70,
                abs_top_of_page_rate=0.50,
                outranking_share=0.40,
                position_above_rate=0.45,
                campaign_name="Generic Campaign",
                campaign_id="456",
                date_range="2024-01-01 - 2024-01-31",
            ),
            AuctionInsights(
                competitor_domain="competitor1.com",
                impression_share=0.20,
                overlap_rate=0.80,
                top_of_page_rate=0.85,
                abs_top_of_page_rate=0.65,
                outranking_share=0.15,
                position_above_rate=0.75,
                campaign_name="Generic Campaign",
                campaign_id="456",
                date_range="2024-01-01 - 2024-01-31",
            ),
            AuctionInsights(
                competitor_domain="competitor3.com",
                impression_share=0.15,
                overlap_rate=0.20,
                top_of_page_rate=0.60,
                abs_top_of_page_rate=0.40,
                outranking_share=0.70,
                position_above_rate=0.25,
                campaign_name="Local Campaign",
                campaign_id="789",
                date_range="2024-01-01 - 2024-01-31",
            ),
        ]

    @pytest.mark.asyncio
    async def test_analyze_empty_data(self, analyzer):
        """Test analysis with empty data."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=[],
        )

        assert isinstance(result, CompetitorInsightsResult)
        assert result.auction_data == []
        assert result.competitor_rankings == []
        assert len(result.recommendations) == 0

    @pytest.mark.asyncio
    async def test_analyze_competitor_rankings(self, analyzer, sample_auction_data):
        """Test competitor ranking analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert len(result.competitor_rankings) == 3

        # Check top competitor (should be competitor1.com due to high threat)
        top_competitor = result.competitor_rankings[0]
        assert top_competitor["domain"] == "competitor1.com"
        assert top_competitor["threat_score"] > 0.5
        assert top_competitor["campaigns_affected"] == 2
        assert "Brand Campaign" in top_competitor["campaign_names"]
        assert "Generic Campaign" in top_competitor["campaign_names"]

    @pytest.mark.asyncio
    async def test_analyze_campaign_competition(self, analyzer, sample_auction_data):
        """Test campaign-level competition analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert "Brand Campaign" in result.campaign_competition
        assert "Generic Campaign" in result.campaign_competition
        assert "Local Campaign" in result.campaign_competition

        # Check Generic Campaign (high competition)
        generic_comp = result.campaign_competition["Generic Campaign"]
        assert len(generic_comp["competitors"]) == 2
        assert generic_comp["competitive_pressure"] == "high"
        assert generic_comp["avg_overlap"] > 0.6

    @pytest.mark.asyncio
    async def test_analyze_position_metrics(self, analyzer, sample_auction_data):
        """Test position metrics analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        position_metrics = result.position_metrics
        assert "avg_top_of_page_rate" in position_metrics
        assert "avg_abs_top_rate" in position_metrics
        assert "position_loss_frequency" in position_metrics
        assert "primary_position_threats" in position_metrics

        # Check position loss analysis
        assert len(result.position_loss_analysis) > 0
        for loss in result.position_loss_analysis:
            assert loss["position_above_rate"] > 0.5

    @pytest.mark.asyncio
    async def test_identify_aggressive_competitors(self, analyzer, sample_auction_data):
        """Test aggressive competitor identification."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert len(result.aggressive_competitors) > 0

        # Check competitor1.com is identified as aggressive
        aggressive_domains = [c["domain"] for c in result.aggressive_competitors]
        assert "competitor1.com" in aggressive_domains

        # Check reasons are provided
        for competitor in result.aggressive_competitors:
            assert len(competitor["reasons"]) > 0
            assert "campaigns_affected" in competitor

    @pytest.mark.asyncio
    async def test_analyze_keyword_themes(self, analyzer, sample_auction_data):
        """Test keyword theme pressure analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert len(result.keyword_theme_pressure) > 0

        # Check themes are extracted
        themes = list(result.keyword_theme_pressure.keys())
        assert "Brand" in themes
        assert "Generic/Non-Brand" in themes or "Other" in themes

    @pytest.mark.asyncio
    async def test_identify_competitive_gaps(self, analyzer, sample_auction_data):
        """Test competitive gap identification."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert isinstance(result.competitive_gaps, list)

        # Check for opportunity types
        gap_types = [gap["type"] for gap in result.competitive_gaps]
        assert any(
            t in gap_types
            for t in [
                "low_competition_opportunity",
                "position_improvement",
                "market_share",
            ]
        )

    @pytest.mark.asyncio
    async def test_analyze_competitive_trends(self, analyzer, sample_auction_data):
        """Test competitive trend analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert isinstance(result.competitive_trends, dict)
        assert isinstance(result.share_changes, dict)

        # Check trends are tracked by competitor
        if result.competitive_trends:
            for domain, trends in result.competitive_trends.items():
                assert isinstance(trends, list)
                for trend in trends:
                    assert "date_range" in trend

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, analyzer, sample_auction_data):
        """Test recommendation generation."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        assert len(result.recommendations) > 0

        # Check recommendation types
        rec_types = [rec.type for rec in result.recommendations]
        assert RecommendationType.ADJUST_BID in rec_types

        # Check recommendation priorities
        high_priority_recs = [
            rec
            for rec in result.recommendations
            if rec.priority == RecommendationPriority.HIGH
        ]
        assert len(high_priority_recs) > 0

    @pytest.mark.asyncio
    async def test_single_competitor_analysis(self, analyzer):
        """Test analysis with single competitor."""
        single_data = [
            AuctionInsights(
                competitor_domain="solo-competitor.com",
                impression_share=0.40,
                overlap_rate=0.90,
                top_of_page_rate=0.95,
                abs_top_of_page_rate=0.85,
                outranking_share=0.10,
                position_above_rate=0.85,
                campaign_name="Main Campaign",
            )
        ]

        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=single_data,
        )

        assert len(result.competitor_rankings) == 1
        assert result.competitor_rankings[0]["domain"] == "solo-competitor.com"
        assert result.competitor_rankings[0]["threat_score"] > 0.7

    @pytest.mark.asyncio
    async def test_missing_metrics_handling(self, analyzer):
        """Test handling of missing metrics."""
        incomplete_data = [
            AuctionInsights(
                competitor_domain="incomplete.com",
                impression_share=None,
                overlap_rate=0.5,
                top_of_page_rate=None,
                abs_top_of_page_rate=None,
                outranking_share=0.3,
                position_above_rate=None,
            )
        ]

        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=incomplete_data,
        )

        # Should still generate results with available data
        assert len(result.competitor_rankings) == 1
        assert result.competitor_rankings[0]["domain"] == "incomplete.com"

    @pytest.mark.asyncio
    async def test_campaign_name_theme_extraction(self, analyzer):
        """Test campaign name theme extraction."""
        themed_data = [
            AuctionInsights(
                competitor_domain="test.com",
                overlap_rate=0.5,
                campaign_name="Brand - Core Terms",
            ),
            AuctionInsights(
                competitor_domain="test2.com",
                overlap_rate=0.6,
                campaign_name="Competitor - Defensive",
            ),
            AuctionInsights(
                competitor_domain="test3.com",
                overlap_rate=0.4,
                campaign_name="Local - Store Locations",
            ),
            AuctionInsights(
                competitor_domain="test4.com",
                overlap_rate=0.5,
                campaign_name="Shopping - Products",
            ),
            AuctionInsights(
                competitor_domain="test5.com",
                overlap_rate=0.3,
                campaign_name="Generic Non-Brand",
            ),
        ]

        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=themed_data,
        )

        themes = list(result.keyword_theme_pressure.keys())
        assert "Brand" in themes
        assert "Competitor" in themes
        assert "Local/Geo" in themes
        assert "Product/Shopping" in themes
        assert any(theme in themes for theme in ["Generic/Non-Brand", "Other"])

    @pytest.mark.asyncio
    async def test_low_competition_opportunity_detection(self, analyzer):
        """Test detection of low competition opportunities."""
        low_comp_data = [
            AuctionInsights(
                competitor_domain="weak-competitor.com",
                impression_share=0.05,
                overlap_rate=0.10,
                top_of_page_rate=0.30,
                abs_top_of_page_rate=0.20,
                outranking_share=0.90,
                position_above_rate=0.05,
                campaign_name="Low Competition Campaign",
            )
        ]

        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=low_comp_data,
        )

        # Should identify low competition opportunity
        low_comp_gaps = [
            gap
            for gap in result.competitive_gaps
            if gap["type"] == "low_competition_opportunity"
        ]
        assert len(low_comp_gaps) > 0

    @pytest.mark.asyncio
    async def test_market_share_analysis(self, analyzer, sample_auction_data):
        """Test market share analysis."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        # Check for market share recommendations
        market_share_recs = [
            rec
            for rec in result.recommendations
            if rec.type == RecommendationType.OTHER
        ]

        # With low impression share in sample data, should recommend expansion
        if any(
            d.impression_share < 0.3 for d in sample_auction_data if d.impression_share
        ):
            assert len(market_share_recs) > 0

    @pytest.mark.asyncio
    async def test_result_completeness(self, analyzer, sample_auction_data):
        """Test that all result fields are populated."""
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            data=sample_auction_data,
        )

        # Check all major result attributes are set
        assert result.auction_data == sample_auction_data
        assert isinstance(result.competitor_rankings, list)
        assert isinstance(result.aggressive_competitors, list)
        assert isinstance(result.campaign_competition, dict)
        assert isinstance(result.position_metrics, dict)
        assert isinstance(result.position_loss_analysis, list)
        assert isinstance(result.keyword_theme_pressure, dict)
        assert isinstance(result.competitive_gaps, list)
        assert isinstance(result.competitive_trends, dict)
        assert isinstance(result.share_changes, dict)
        assert isinstance(result.recommendations, list)


class TestCompetitorInsightsCSVParsing:
    """Test cases for CSV parsing functionality."""

    @pytest.fixture
    def sample_csv_content(self):
        """Create sample CSV content matching Google Ads format."""
        return """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
yourdomain.com,32.1%,--,--,--,--,--
competitor1.com,25.5%,18.2%,45.3%,12.1%,38.7%,22.4%
competitor2.com,18.9%,15.6%,32.8%,8.9%,29.3%,18.7%
competitor3.com,12.3%,10.4%,28.1%,7.2%,22.6%,15.3%
"""

    @pytest.fixture
    def sample_csv_file(self, sample_csv_content):
        """Create a temporary CSV file with sample content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(sample_csv_content)
            tmp_path = Path(tmp_file.name)
        yield tmp_path
        # Cleanup
        tmp_path.unlink(missing_ok=True)

    def test_from_csv_creates_analyzer(self, sample_csv_file):
        """Test that from_csv creates an analyzer instance."""
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_file)
        assert isinstance(analyzer, CompetitorInsightsAnalyzer)
        assert hasattr(analyzer, "_csv_data")
        assert len(analyzer._csv_data) == 3  # Should have 3 competitors

    def test_from_csv_parses_data_correctly(self, sample_csv_file):
        """Test that CSV data is parsed correctly."""
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_file)

        # Check first competitor
        first_competitor = analyzer._csv_data[0]
        assert first_competitor.competitor_domain == "competitor1.com"
        assert pytest.approx(first_competitor.impression_share, 0.001) == 0.255
        assert pytest.approx(first_competitor.overlap_rate, 0.001) == 0.182
        assert pytest.approx(first_competitor.top_of_page_rate, 0.001) == 0.453
        assert pytest.approx(first_competitor.abs_top_of_page_rate, 0.001) == 0.121
        assert pytest.approx(first_competitor.outranking_share, 0.001) == 0.387
        assert pytest.approx(first_competitor.position_above_rate, 0.001) == 0.224

    def test_from_csv_skips_own_domain(self, sample_csv_file):
        """Test that own domain row is skipped."""
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_file)
        domains = [data.competitor_domain for data in analyzer._csv_data]
        assert "yourdomain.com" not in domains

    def test_from_csv_handles_missing_values(self):
        """Test handling of missing values in CSV."""
        csv_content = """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
yourdomain.com,32.1%,--,--,--,--,--
competitor1.com,,15.0%,,,30.0%,
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(csv_content)
            tmp_path = Path(tmp_file.name)

        try:
            analyzer = CompetitorInsightsAnalyzer.from_csv(tmp_path)
            assert len(analyzer._csv_data) == 1
            competitor = analyzer._csv_data[0]
            assert competitor.impression_share is None
            assert competitor.overlap_rate == 0.15
            assert competitor.top_of_page_rate is None
            assert competitor.outranking_share == 0.30
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_from_csv_file_not_found(self):
        """Test error handling for non-existent file."""
        with pytest.raises(FileNotFoundError):
            CompetitorInsightsAnalyzer.from_csv("non_existent_file.csv")

    def test_from_csv_invalid_file_type(self):
        """Test error handling for non-CSV file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with pytest.raises(ValueError, match="Expected .csv file"):
                CompetitorInsightsAnalyzer.from_csv(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_from_csv_missing_required_columns(self):
        """Test error handling for CSV with missing required columns."""
        csv_content = """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Wrong Column,Another Column
value1,value2
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(csv_content)
            tmp_path = Path(tmp_file.name)

        try:
            with pytest.raises(ValueError, match="CSV missing required columns"):
                CompetitorInsightsAnalyzer.from_csv(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_from_csv_empty_data(self):
        """Test error handling for CSV with no valid competitor data."""
        csv_content = """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
yourdomain.com,32.1%,--,--,--,--,--
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(csv_content)
            tmp_path = Path(tmp_file.name)

        try:
            with pytest.raises(ValueError, match="No valid competitor data found"):
                CompetitorInsightsAnalyzer.from_csv(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_analyze_with_csv_data(self, sample_csv_file):
        """Test that analyze works with CSV-loaded data."""
        analyzer = CompetitorInsightsAnalyzer.from_csv(sample_csv_file)

        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
        )

        assert isinstance(result, CompetitorInsightsResult)
        assert len(result.auction_data) == 3
        assert len(result.competitor_rankings) == 3
        assert result.competitor_rankings[0]["domain"] in [
            "competitor1.com",
            "competitor2.com",
            "competitor3.com",
        ]

    def test_from_csv_with_extended_format(self):
        """Test parsing CSV with campaign information."""
        csv_content = """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate,Campaign,Campaign ID
yourdomain.com,32.1%,--,--,--,--,--,Brand Campaign,123
competitor1.com,25.5%,18.2%,45.3%,12.1%,38.7%,22.4%,Brand Campaign,123
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(csv_content)
            tmp_path = Path(tmp_file.name)

        try:
            analyzer = CompetitorInsightsAnalyzer.from_csv(tmp_path)
            assert len(analyzer._csv_data) == 1
            competitor = analyzer._csv_data[0]
            assert competitor.campaign_name == "Brand Campaign"
            assert competitor.campaign_id == "123"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_from_csv_with_actual_sample_file(self):
        """Test with the actual sample CSV file if it exists."""
        sample_file = Path("test_data/exports/auction_insights_sample.csv")
        if sample_file.exists():
            analyzer = CompetitorInsightsAnalyzer.from_csv(sample_file)
            assert hasattr(analyzer, "_csv_data")
            assert len(analyzer._csv_data) > 0

            # Verify data is properly parsed
            for auction_insight in analyzer._csv_data:
                assert isinstance(auction_insight, AuctionInsights)
                assert auction_insight.competitor_domain
                assert auction_insight.overlap_rate is not None

    def test_from_csv_file_size_validation(self):
        """Test that file size validation works."""
        csv_content = """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
competitor1.com,25.5%,18.2%,45.3%,12.1%,38.7%,22.4%
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            tmp_file.write(csv_content)
            tmp_path = Path(tmp_file.name)

        try:
            # Should work with default size limit
            analyzer = CompetitorInsightsAnalyzer.from_csv(tmp_path)
            assert len(analyzer._csv_data) == 1

            # Should fail with very small size limit
            with pytest.raises(ValueError, match="CSV file too large"):
                CompetitorInsightsAnalyzer.from_csv(tmp_path, max_file_size_mb=0.0001)
        finally:
            tmp_path.unlink(missing_ok=True)
