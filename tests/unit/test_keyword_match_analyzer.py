"""Unit tests for KeywordMatchAnalyzer."""

from datetime import datetime

import pytest

from paidsearchnav_mcp.analyzers.keyword_match import KeywordMatchAnalyzer
from paidsearchnav_mcp.models import (
    Keyword,
    KeywordMatchType,
    KeywordStatus,
    RecommendationPriority,
    RecommendationType,
)


class MockDataProvider:
    """Mock data provider for testing."""

    def __init__(self):
        self.keywords_data = []

    async def get_keywords(
        self,
        customer_id,
        campaigns=None,
        ad_groups=None,
        campaign_id=None,
        include_metrics=True,
        start_date=None,
        end_date=None,
        page_size=None,
        max_results=None,
    ):
        """Return mock keywords data."""
        return self.keywords_data

    async def get_campaigns(
        self,
        customer_id,
        campaign_types=None,
        start_date=None,
        end_date=None,
        page_size=None,
        max_results=None,
    ):
        """Return mock campaigns data."""
        return []

    async def get_search_terms(
        self,
        customer_id,
        start_date,
        end_date,
        campaigns=None,
        ad_groups=None,
        page_size=None,
        max_results=None,
    ):
        """Return mock search terms data."""
        return []

    async def get_negative_keywords(self, customer_id, include_shared_sets=True):
        """Return mock negative keywords data."""
        return []


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    return MockDataProvider()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create a KeywordMatchAnalyzer instance."""
    return KeywordMatchAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=100,
        high_cost_threshold=100.0,
        low_roi_threshold=1.5,
        max_broad_cpa_multiplier=2.0,
    )


@pytest.fixture
def sample_keywords():
    """Sample keywords data with different match types."""
    return [
        Keyword(
            keyword_id="1",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="widgets",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=8,
            impressions=10000,
            clicks=500,
            cost=1500.0,
            conversions=20.0,
            conversion_value=2000.0,
        ),
        Keyword(
            keyword_id="2",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="widget store",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=9,
            impressions=5000,
            clicks=300,
            cost=600.0,
            conversions=30.0,
            conversion_value=3000.0,
        ),
        Keyword(
            keyword_id="3",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="buy widgets online",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=10,
            impressions=2000,
            clicks=200,
            cost=400.0,
            conversions=40.0,
            conversion_value=4000.0,
        ),
        # High-cost, low-performing broad match
        Keyword(
            keyword_id="4",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="cheap stuff",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=5,
            impressions=8000,
            clicks=400,
            cost=2000.0,
            conversions=5.0,
            conversion_value=500.0,
        ),
        # Low quality keyword
        Keyword(
            keyword_id="5",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="457",
            ad_group_name="Another Ad Group",
            text="discount widgets",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=4,
            impressions=3000,
            clicks=100,
            cost=300.0,
            conversions=2.0,
            conversion_value=200.0,
        ),
    ]


@pytest.fixture
def duplicate_keywords():
    """Keywords with same text but different match types."""
    return [
        Keyword(
            keyword_id="10",
            campaign_id="123",
            campaign_name="Campaign 1",
            ad_group_id="456",
            ad_group_name="Ad Group 1",
            text="widget store",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=7,
            impressions=5000,
            clicks=200,
            cost=500.0,
            conversions=5.0,
            conversion_value=500.0,
        ),
        Keyword(
            keyword_id="11",
            campaign_id="123",
            campaign_name="Campaign 1",
            ad_group_id="456",
            ad_group_name="Ad Group 1",
            text="widget store",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=8,
            impressions=3000,
            clicks=150,
            cost=300.0,
            conversions=10.0,
            conversion_value=1000.0,
        ),
        Keyword(
            keyword_id="12",
            campaign_id="123",
            campaign_name="Campaign 1",
            ad_group_id="456",
            ad_group_name="Ad Group 1",
            text="widget store",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=9,
            impressions=1000,
            clicks=100,
            cost=200.0,
            conversions=15.0,
            conversion_value=1500.0,
        ),
    ]


class TestKeywordMatchAnalyzer:
    """Test KeywordMatchAnalyzer functionality."""

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer is properly initialized."""
        assert analyzer.min_impressions == 100
        assert analyzer.high_cost_threshold == 100.0
        assert analyzer.low_roi_threshold == 1.5
        assert analyzer.max_broad_cpa_multiplier == 2.0

    def test_analyzer_metadata(self, analyzer):
        """Test analyzer metadata methods."""
        assert analyzer.get_name() == "Keyword Match Type Analyzer"
        assert "match types" in analyzer.get_description().lower()

    @pytest.mark.asyncio
    async def test_analyze_basic(self, analyzer, mock_data_provider, sample_keywords):
        """Test basic analysis functionality."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.customer_id == "12345"
        assert result.total_keywords == 5
        assert len(result.match_type_stats) == 3  # BROAD, PHRASE, EXACT

        # Check match type distribution
        assert result.match_type_stats["BROAD"]["count"] == 2
        assert result.match_type_stats["PHRASE"]["count"] == 2
        assert result.match_type_stats["EXACT"]["count"] == 1

    @pytest.mark.asyncio
    async def test_match_type_statistics(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test calculation of match type statistics."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check broad match stats
        broad_stats = result.match_type_stats["BROAD"]
        assert broad_stats["impressions"] == 18000
        assert broad_stats["clicks"] == 900
        assert broad_stats["cost"] == 3500.0
        assert broad_stats["conversions"] == 25.0
        assert broad_stats["cpa"] == pytest.approx(140.0)  # 3500/25

        # Check exact match stats
        exact_stats = result.match_type_stats["EXACT"]
        assert exact_stats["impressions"] == 2000
        assert exact_stats["clicks"] == 200
        assert exact_stats["cost"] == 400.0
        assert exact_stats["conversions"] == 40.0
        assert exact_stats["cpa"] == pytest.approx(10.0)  # 400/40

    @pytest.mark.asyncio
    async def test_high_cost_broad_detection(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test detection of high-cost, low-ROI broad match keywords."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.high_cost_broad_keywords) == 2
        # Should be sorted by cost descending
        assert result.high_cost_broad_keywords[0].text == "cheap stuff"
        assert result.high_cost_broad_keywords[0].cost == 2000.0

    @pytest.mark.asyncio
    async def test_low_quality_detection(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test detection of low quality score keywords."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.low_quality_keywords) == 2
        # Keywords with quality score < 7
        quality_scores = [k.quality_score for k in result.low_quality_keywords]
        assert all(score < 7 for score in quality_scores)

    @pytest.mark.asyncio
    async def test_duplicate_detection(
        self, analyzer, mock_data_provider, duplicate_keywords
    ):
        """Test detection of duplicate keyword opportunities."""
        mock_data_provider.keywords_data = duplicate_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.duplicate_opportunities) == 1
        opportunity = result.duplicate_opportunities[0]
        assert opportunity["keyword_text"] == "widget store"
        assert len(opportunity["match_types_found"]) == 3
        # PHRASE has best CPA (300/10 = 30) vs EXACT (200/15 = 13.33)
        assert opportunity["recommended_match_type"] == "EXACT"
        assert opportunity["potential_savings"] == 800.0  # 500 + 300

    @pytest.mark.asyncio
    async def test_recommendations_generation(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test generation of recommendations."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.recommendations) > 0

        # Check for broad match recommendation
        broad_recommendations = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.PAUSE_KEYWORDS
        ]
        assert len(broad_recommendations) > 0

        # Check for quality score recommendation
        quality_recommendations = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.IMPROVE_QUALITY_SCORE
        ]
        assert len(quality_recommendations) > 0

    @pytest.mark.asyncio
    async def test_potential_savings_calculation(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test calculation of potential savings."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.potential_savings > 0
        # Should have savings from optimizing high-cost broad keywords

    @pytest.mark.asyncio
    async def test_minimum_impressions_filter(self, analyzer, mock_data_provider):
        """Test that keywords below minimum impressions are filtered."""
        low_impression_keywords = [
            Keyword(
                keyword_id="1",
                campaign_id="123",
                campaign_name="Campaign",
                ad_group_id="456",
                ad_group_name="Ad Group",
                text="rare keyword",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
                quality_score=8,
                impressions=50,  # Below minimum
                clicks=5,
                cost=10.0,
                conversions=0.0,
                conversion_value=0.0,
            )
        ]

        mock_data_provider.keywords_data = low_impression_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.total_keywords == 0

    @pytest.mark.asyncio
    async def test_summary_dict_generation(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test generation of summary dictionary."""
        mock_data_provider.keywords_data = sample_keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        summary = result.to_summary_dict()

        assert summary["account"] == "12345"
        assert summary["summary"]["total_keywords"] == 5
        assert "match_type_distribution" in summary["summary"]
        assert "potential_savings" in summary["summary"]
        assert summary["issues"]["high_cost_broad"] == 2
        assert summary["issues"]["low_quality"] == 2

    @pytest.mark.asyncio
    async def test_exact_match_coverage_recommendation(
        self, analyzer, mock_data_provider
    ):
        """Test recommendation for increasing exact match coverage."""
        # Create keywords with low exact match ratio
        keywords = [
            Keyword(
                keyword_id=str(i),
                campaign_id="123",
                campaign_name="Campaign",
                ad_group_id="456",
                ad_group_name="Ad Group",
                text=f"keyword {i}",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
                quality_score=8,
                impressions=1000,
                clicks=100,
                cost=200.0,
                conversions=10.0,
                conversion_value=1000.0,
            )
            for i in range(10)
        ]

        mock_data_provider.keywords_data = keywords

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should recommend increasing exact match coverage
        exact_recommendations = [
            r
            for r in result.recommendations
            if "exact match" in r.title.lower()
            and r.type == RecommendationType.ADD_KEYWORD
        ]
        assert len(exact_recommendations) > 0
        assert exact_recommendations[0].priority == RecommendationPriority.LOW
