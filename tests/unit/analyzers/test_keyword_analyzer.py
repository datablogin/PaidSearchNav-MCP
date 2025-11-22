"""Unit tests for KeywordAnalyzer."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav_mcp.analyzers.keyword_analyzer import (
    KeywordAnalysisResult,
    KeywordAnalyzer,
)
from paidsearchnav_mcp.models.analysis import (
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.models.keyword import Keyword, KeywordMatchType, KeywordStatus


@pytest.fixture
def mock_data_provider():
    """Create mock data provider."""
    return Mock()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create analyzer instance with default configuration."""
    return KeywordAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=10,
        high_cost_threshold=100.0,
        low_ctr_threshold=1.0,
        high_ctr_threshold=5.0,
        quality_score_threshold=5,
    )


@pytest.fixture
def sample_keywords():
    """Create sample keywords for testing."""
    return [
        # High performer
        Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy running shoes",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=9,
            impressions=5000,
            clicks=500,
            cost=250.0,
            conversions=25.0,
            conversion_value=1250.0,
        ),
        # Budget waster
        Keyword(
            keyword_id="2",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="expensive broad keyword",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=3,
            impressions=2000,
            clicks=20,
            cost=150.0,
            conversions=0.0,
            conversion_value=0.0,
        ),
        # Low quality keyword
        Keyword(
            keyword_id="3",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1001",
            ad_group_name="Ad Group 2",
            text="poor quality keyword",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=2,
            impressions=1000,
            clicks=50,
            cost=75.0,
            conversions=1.0,
            conversion_value=25.0,
        ),
        # High impressions, low CTR
        Keyword(
            keyword_id="4",
            campaign_id="101",
            campaign_name="Campaign 2",
            ad_group_id="1002",
            ad_group_name="Ad Group 3",
            text="high volume low ctr",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=6,
            impressions=15000,
            clicks=75,  # 0.5% CTR
            cost=45.0,
            conversions=2.0,
            conversion_value=100.0,
        ),
        # Good CTR, low impressions
        Keyword(
            keyword_id="5",
            campaign_id="101",
            campaign_name="Campaign 2",
            ad_group_id="1002",
            ad_group_name="Ad Group 3",
            text="high ctr low volume",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=8,
            impressions=50,
            clicks=5,  # 10% CTR
            cost=25.0,
            conversions=2.0,
            conversion_value=200.0,
        ),
        # CPA outlier
        Keyword(
            keyword_id="6",
            campaign_id="102",
            campaign_name="Campaign 3",
            ad_group_id="1003",
            ad_group_name="Ad Group 4",
            text="expensive conversion",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=7,
            impressions=1000,
            clicks=100,
            cost=300.0,
            conversions=1.0,  # $300 CPA
            conversion_value=50.0,
        ),
        # No impressions
        Keyword(
            keyword_id="7",
            campaign_id="102",
            campaign_name="Campaign 3",
            ad_group_id="1003",
            ad_group_name="Ad Group 4",
            text="no impressions keyword",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=5,
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        ),
        # Low impressions (filtered out of main analysis)
        Keyword(
            keyword_id="8",
            campaign_id="102",
            campaign_name="Campaign 3",
            ad_group_id="1003",
            ad_group_name="Ad Group 4",
            text="very low impressions",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=6,
            impressions=5,  # Below min_impressions threshold
            clicks=1,
            cost=2.0,
            conversions=0.0,
            conversion_value=0.0,
        ),
    ]


@pytest.fixture
def empty_keywords():
    """Create empty keyword list."""
    return []


class TestKeywordAnalyzer:
    """Test cases for KeywordAnalyzer."""

    def test_get_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.get_name() == "Keyword Analyzer"

    def test_get_description(self, analyzer):
        """Test analyzer description."""
        description = analyzer.get_description()
        assert "keyword performance" in description.lower()
        assert "optimization opportunities" in description.lower()

    @pytest.mark.asyncio
    async def test_analyze_with_empty_keywords(self, analyzer, empty_keywords):
        """Test analysis with no keywords."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=empty_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert isinstance(result, KeywordAnalysisResult)
        assert result.customer_id == "123"
        assert result.total_keywords_analyzed == 0
        assert len(result.recommendations) == 0
        assert result.metrics.total_keywords_analyzed == 0

    @pytest.mark.asyncio
    async def test_analyze_with_sample_keywords(self, analyzer, sample_keywords):
        """Test analysis with sample keywords."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert isinstance(result, KeywordAnalysisResult)
        assert result.customer_id == "123"
        assert result.analyzer_name == "Keyword Analyzer"
        assert result.total_keywords_analyzed > 0

        # Should filter out keywords with < min_impressions
        # Keywords 1-6 have >= 10 impressions, keyword 8 has only 5
        assert result.total_keywords_analyzed == 6

        # Should have recommendations
        assert len(result.recommendations) > 0

        # Should have analysis results
        assert result.avg_quality_score > 0
        assert result.optimization_opportunities > 0

    @pytest.mark.asyncio
    async def test_performance_analysis(self, analyzer, sample_keywords):
        """Test performance analysis functionality."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should identify top performer (keyword 1 with highest conversion value)
        assert len(result.top_performers) > 0
        top_performer = result.top_performers[0]
        assert top_performer.keyword_id == "1"
        assert top_performer.conversion_value == 1250.0

        # Should identify bottom performers (high cost, no/low conversions)
        assert len(result.bottom_performers) > 0
        # Budget waster should be in bottom performers
        budget_waster_found = any(
            kw.keyword_id == "2" for kw in result.bottom_performers
        )
        assert budget_waster_found

    @pytest.mark.asyncio
    async def test_quality_score_analysis(self, analyzer, sample_keywords):
        """Test quality score analysis."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should have quality score distribution
        assert len(result.quality_score_distribution) > 0

        # Should identify low quality keywords (quality score < 5)
        assert len(result.low_quality_keywords) > 0
        low_quality_ids = [kw.keyword_id for kw in result.low_quality_keywords]
        assert "2" in low_quality_ids  # Quality score 3
        assert "3" in low_quality_ids  # Quality score 2

        # Should calculate average quality score
        assert result.avg_quality_score > 0

    @pytest.mark.asyncio
    async def test_cost_efficiency_analysis(self, analyzer, sample_keywords):
        """Test cost efficiency analysis."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should identify budget wasters (high cost, no conversions)
        assert len(result.budget_wasters) > 0
        budget_waster_ids = [kw.keyword_id for kw in result.budget_wasters]
        assert "2" in budget_waster_ids  # $150 cost, 0 conversions

        # Should identify high cost, low conversion keywords
        assert len(result.high_cost_low_conversion) > 0

        # Should identify CPA outliers
        assert len(result.cpa_outliers) > 0
        cpa_outlier_ids = [kw.keyword_id for kw in result.cpa_outliers]
        assert "6" in cpa_outlier_ids  # $300 CPA

    @pytest.mark.asyncio
    async def test_opportunity_identification(self, analyzer, sample_keywords):
        """Test opportunity identification."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should identify high impression, low CTR keywords
        assert len(result.high_impression_low_ctr) > 0
        high_imp_low_ctr_ids = [kw.keyword_id for kw in result.high_impression_low_ctr]
        assert "4" in high_imp_low_ctr_ids  # 15000 impressions, 0.5% CTR

        # Should identify good CTR, low impression keywords
        assert len(result.good_ctr_low_impression) > 0
        good_ctr_low_imp_ids = [kw.keyword_id for kw in result.good_ctr_low_impression]
        assert "5" in good_ctr_low_imp_ids  # 50 impressions, 10% CTR

        # Should identify no impression keywords
        assert len(result.no_impression_keywords) > 0
        no_imp_ids = [kw.keyword_id for kw in result.no_impression_keywords]
        assert "7" in no_imp_ids  # 0 impressions

        # Should have negative keyword candidates
        assert len(result.negative_candidates) >= 0

    @pytest.mark.asyncio
    async def test_recommendations_generation(self, analyzer, sample_keywords):
        """Test recommendations generation."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should generate recommendations
        assert len(result.recommendations) > 0

        # Should have different priority levels
        priorities = [rec.priority for rec in result.recommendations]
        assert RecommendationPriority.CRITICAL in priorities  # Budget wasters
        assert RecommendationPriority.HIGH in priorities  # Low quality or CPA outliers

        # Should have different recommendation types
        rec_types = [rec.type for rec in result.recommendations]
        assert RecommendationType.PAUSE_KEYWORDS in rec_types  # Budget wasters
        assert RecommendationType.IMPROVE_QUALITY_SCORE in rec_types  # Low quality
        assert RecommendationType.ADJUST_BID in rec_types  # Bid opportunities

        # Critical recommendations should have cost savings
        critical_recs = [
            rec
            for rec in result.recommendations
            if rec.priority == RecommendationPriority.CRITICAL
        ]
        for rec in critical_recs:
            if rec.estimated_cost_savings is not None:
                assert rec.estimated_cost_savings > 0

    @pytest.mark.asyncio
    async def test_summary_metrics_calculation(self, analyzer, sample_keywords):
        """Test summary metrics calculation."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should calculate valid metrics
        assert result.avg_quality_score > 0
        assert result.median_cpc > 0
        assert result.median_cpa > 0
        assert 0 <= result.cost_efficiency_score <= 100

        # Custom metrics should be populated
        assert "avg_quality_score" in result.metrics.custom_metrics
        assert "cost_efficiency_score" in result.metrics.custom_metrics

    @pytest.mark.asyncio
    async def test_potential_savings_calculation(self, analyzer, sample_keywords):
        """Test potential savings calculation."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should calculate potential savings
        assert result.metrics.potential_cost_savings >= 0

        # Should be based on budget wasters and other inefficiencies
        if result.budget_wasters:
            budget_waste = sum(kw.cost for kw in result.budget_wasters)
            # Savings calculation includes multiple sources, so it might be higher than just budget waste
            # Just verify it's reasonable (not more than total cost of all analyzed keywords)
            total_cost = sum(kw.cost for kw in sample_keywords if kw.impressions >= 10)
            assert result.metrics.potential_cost_savings <= total_cost

    @pytest.mark.asyncio
    async def test_analysis_with_campaigns_filter(self, analyzer, sample_keywords):
        """Test analysis with campaign filter."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaigns=["100"],
        )

        # Should call data provider with campaign filter
        analyzer.data_provider.get_keywords.assert_called_once_with(
            customer_id="123",
            campaigns=["100"],
            ad_groups=None,
        )

        # Should still return valid results
        assert isinstance(result, KeywordAnalysisResult)

    @pytest.mark.asyncio
    async def test_raw_data_population(self, analyzer, sample_keywords):
        """Test that raw data is properly populated."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should populate raw data
        assert "keyword_dataframe" in result.raw_data
        assert "total_keywords" in result.raw_data
        assert "filtered_keywords" in result.raw_data
        assert "analysis_parameters" in result.raw_data

        # Should have correct counts
        assert result.raw_data["total_keywords"] == len(sample_keywords)
        assert result.raw_data["filtered_keywords"] == result.total_keywords_analyzed

        # Should include analysis parameters
        params = result.raw_data["analysis_parameters"]
        assert "min_impressions" in params
        assert "high_cost_threshold" in params

    def test_analyzer_configuration(self):
        """Test analyzer with custom configuration."""
        mock_provider = Mock()

        analyzer = KeywordAnalyzer(
            data_provider=mock_provider,
            min_impressions=50,
            high_cost_threshold=200.0,
            low_ctr_threshold=0.5,
            high_ctr_threshold=10.0,
            quality_score_threshold=6,
            cpa_outlier_multiplier=2.5,
        )

        # Should store configuration
        assert analyzer.min_impressions == 50
        assert analyzer.high_cost_threshold == 200.0
        assert analyzer.low_ctr_threshold == 0.5
        assert analyzer.high_ctr_threshold == 10.0
        assert analyzer.quality_score_threshold == 6
        assert analyzer.cpa_outlier_multiplier == 2.5

    @pytest.mark.asyncio
    async def test_error_handling(self, analyzer):
        """Test error handling in analysis."""
        # Mock data provider to raise exception
        analyzer.data_provider.get_keywords = AsyncMock(
            side_effect=Exception("API Error")
        )

        # Should raise the exception
        with pytest.raises(Exception, match="API Error"):
            await analyzer.analyze(
                customer_id="123",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )

    @pytest.mark.asyncio
    async def test_dataframe_creation_with_empty_list(self, analyzer):
        """Test DataFrame creation with empty keyword list."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=[])

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should handle empty DataFrame gracefully
        assert result.total_keywords_analyzed == 0
        assert len(result.recommendations) == 0
        assert result.raw_data["keyword_dataframe"] == []

    @pytest.mark.asyncio
    async def test_analysis_metrics(self, analyzer, sample_keywords):
        """Test that AnalysisMetrics are properly populated."""
        analyzer.data_provider.get_keywords = AsyncMock(return_value=sample_keywords)

        result = await analyzer.analyze(
            customer_id="123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        metrics = result.metrics

        # Should have basic metrics
        assert metrics.total_keywords_analyzed > 0
        assert metrics.issues_found >= 0
        assert metrics.critical_issues >= 0
        assert metrics.potential_cost_savings >= 0

        # Should have custom metrics
        custom_metrics = metrics.custom_metrics
        assert "avg_quality_score" in custom_metrics
        assert "median_cpc" in custom_metrics
        assert "median_cpa" in custom_metrics
        assert "cost_efficiency_score" in custom_metrics

        # Custom metrics should be reasonable
        assert 0 <= custom_metrics["avg_quality_score"] <= 10
        assert custom_metrics["median_cpc"] >= 0
        assert custom_metrics["median_cpa"] >= 0
        assert 0 <= custom_metrics["cost_efficiency_score"] <= 100
