"""Tests for Campaign Overlap Analyzer."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from paidsearchnav_mcp.analyzers.campaign_overlap import CampaignOverlapAnalyzer
from paidsearchnav_mcp.models.analysis import CampaignOverlapAnalysisResult
from paidsearchnav_mcp.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav_mcp.models.keyword import Keyword, KeywordMatchType, KeywordStatus
from paidsearchnav_mcp.models.search_term import SearchTerm, SearchTermMetrics


@pytest.fixture
def mock_data_provider():
    """Mock data provider."""
    return AsyncMock()


@pytest.fixture
def sample_campaigns():
    """Sample campaigns for testing."""
    return [
        Campaign(
            campaign_id="123",
            customer_id="123456789",
            name="Search Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.MANUAL_CPC,
            cost=1000.0,
            impressions=10000,
            clicks=500,
            conversions=25.0,
            conversion_value=2500.0,
        ),
        Campaign(
            campaign_id="456",
            customer_id="123456789",
            name="Performance Max Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.PERFORMANCE_MAX,
            budget_amount=150.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.MAXIMIZE_CONVERSION_VALUE,
            cost=1500.0,
            impressions=15000,
            clicks=750,
            conversions=30.0,
            conversion_value=3000.0,
        ),
        Campaign(
            campaign_id="789",
            customer_id="123456789",
            name="Shopping Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SHOPPING,
            budget_amount=80.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.MAXIMIZE_CLICKS,
            cost=800.0,
            impressions=8000,
            clicks=400,
            conversions=20.0,
            conversion_value=2000.0,
        ),
    ]


@pytest.fixture
def sample_search_terms():
    """Sample search terms for testing."""
    return [
        SearchTerm(
            campaign_id="123",
            campaign_name="Search Campaign",
            ad_group_id="ag1",
            ad_group_name="Ad Group 1",
            search_term="running shoes",
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=50,
                cost=100.0,
                conversions=5.0,
                conversion_value=500.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Search Campaign",
            ad_group_id="ag1",
            ad_group_name="Ad Group 1",
            search_term="nike running shoes",
            metrics=SearchTermMetrics(
                impressions=800,
                clicks=40,
                cost=80.0,
                conversions=4.0,
                conversion_value=400.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Search Campaign",
            ad_group_id="ag1",
            ad_group_name="Ad Group 1",
            search_term="best running shoes",
            metrics=SearchTermMetrics(
                impressions=600,
                clicks=30,
                cost=60.0,
                conversions=3.0,
                conversion_value=300.0,
            ),
        ),
    ]


@pytest.fixture
def sample_negative_keywords():
    """Sample negative keywords for testing."""
    return [
        Keyword(
            keyword_id="neg1",
            campaign_id="456",
            campaign_name="Test Campaign",
            ad_group_id="ag1",
            ad_group_name="Test Ad Group",
            text="free",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        ),
        Keyword(
            keyword_id="neg2",
            campaign_id="456",
            campaign_name="Test Campaign",
            ad_group_id="ag1",
            ad_group_name="Test Ad Group",
            text="brand shoes",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
        ),
        Keyword(
            keyword_id="neg3",
            campaign_id="456",
            campaign_name="Test Campaign",
            ad_group_id="ag1",
            ad_group_name="Test Ad Group",
            text="company name",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
        ),
    ]


@pytest.fixture
def analyzer(mock_data_provider):
    """Campaign overlap analyzer instance."""
    return CampaignOverlapAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=100,
        min_spend_threshold=25.0,
        overlap_threshold=0.7,
        conflict_threshold=0.8,
    )


class TestCampaignOverlapAnalyzer:
    """Test Campaign Overlap Analyzer."""

    def test_initialization(self, mock_data_provider):
        """Test analyzer initialization."""
        analyzer = CampaignOverlapAnalyzer(
            data_provider=mock_data_provider,
            min_impressions=200,
            min_spend_threshold=50.0,
            overlap_threshold=0.6,
            conflict_threshold=0.9,
        )

        assert analyzer.data_provider == mock_data_provider
        assert analyzer.min_impressions == 200
        assert analyzer.min_spend_threshold == 50.0
        assert analyzer.overlap_threshold == 0.6
        assert analyzer.conflict_threshold == 0.9

    def test_get_name(self, analyzer):
        """Test get_name method."""
        assert analyzer.get_name() == "Campaign Overlap Analyzer"

    def test_get_description(self, analyzer):
        """Test get_description method."""
        description = analyzer.get_description()
        assert "overlap" in description.lower()
        assert "channel" in description.lower()

    @pytest.mark.asyncio
    async def test_analyze_basic_functionality(
        self, analyzer, sample_campaigns, sample_search_terms, sample_negative_keywords
    ):
        """Test basic analyze functionality."""
        # Mock data provider responses
        analyzer.data_provider.get_campaigns.return_value = sample_campaigns
        analyzer.data_provider.get_search_terms.return_value = sample_search_terms
        analyzer.data_provider.get_negative_keywords.return_value = (
            sample_negative_keywords
        )

        # Run analysis
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result type and basic structure
        assert isinstance(result, CampaignOverlapAnalysisResult)
        assert result.customer_id == "123456789"
        assert result.analysis_type == "campaign_overlap"
        assert result.total_campaigns == 3
        assert result.total_spend == 3300.0
        assert result.total_conversions == 75.0

        # Verify channel performance analysis
        assert "channels" in result.channel_performance
        assert len(result.channel_performance["channels"]) > 0

        # Verify overlap analysis
        assert "overlaps" in result.overlap_analysis
        assert "overlap_count" in result.overlap_analysis

        # Verify recommendations
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_analyze_with_no_campaigns(self, analyzer):
        """Test analyze with no campaigns."""
        analyzer.data_provider.get_campaigns.return_value = []

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.total_campaigns == 0
        assert result.total_spend == 0.0
        assert result.total_conversions == 0.0
        assert len(result.channel_performance.get("channels", [])) == 0

    @pytest.mark.asyncio
    async def test_analyze_channel_performance(self, analyzer, sample_campaigns):
        """Test channel performance analysis."""
        result = await analyzer._analyze_channel_performance(
            customer_id="123456789",
            campaigns=sample_campaigns,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert "channels" in result
        assert "insights" in result
        assert len(result["channels"]) == 3  # Search, Performance Max, Shopping

        # Verify channel data structure
        for channel in result["channels"]:
            assert "channel" in channel
            assert "spend" in channel
            assert "conversions" in channel
            assert "cpa" in channel
            assert "roas" in channel

    @pytest.mark.asyncio
    async def test_detect_campaign_overlaps(
        self, analyzer, sample_campaigns, sample_search_terms
    ):
        """Test campaign overlap detection."""
        # Mock search terms for each campaign
        analyzer.data_provider.get_search_terms.return_value = sample_search_terms

        result = await analyzer._detect_campaign_overlaps(
            customer_id="123456789",
            campaigns=sample_campaigns,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert "overlaps" in result
        assert "overlap_count" in result
        assert "total_overlap_cost" in result
        assert isinstance(result["overlaps"], list)

    @pytest.mark.asyncio
    async def test_analyze_brand_conflicts(
        self, analyzer, sample_campaigns, sample_negative_keywords
    ):
        """Test brand conflict analysis."""

        # Mock negative keywords for Performance Max campaign
        def mock_get_negative_keywords(customer_id, campaign_id):
            if campaign_id == "456":  # Performance Max campaign
                return sample_negative_keywords
            return []

        analyzer.data_provider.get_negative_keywords.side_effect = (
            mock_get_negative_keywords
        )

        result = await analyzer._analyze_brand_conflicts(
            customer_id="123456789",
            campaigns=sample_campaigns,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert "conflicts" in result
        assert "conflict_count" in result
        assert isinstance(result["conflicts"], list)

    @pytest.mark.asyncio
    async def test_analyze_budget_optimization(self, analyzer, sample_campaigns):
        """Test budget optimization analysis."""
        # Mock channel performance data
        channel_performance = {
            "channels": [
                {
                    "channel": "Search",
                    "spend": 1000.0,
                    "conversions": 25.0,
                    "cpa": 40.0,
                },
                {
                    "channel": "Performance Max",
                    "spend": 1500.0,
                    "conversions": 30.0,
                    "cpa": 50.0,
                },
                {
                    "channel": "Shopping",
                    "spend": 800.0,
                    "conversions": 20.0,
                    "cpa": 120.0,  # High CPA
                },
            ]
        }

        result = await analyzer._analyze_budget_optimization(
            customer_id="123456789",
            campaigns=sample_campaigns,
            channel_performance=channel_performance,
        )

        assert "opportunities" in result
        assert "total_potential_savings" in result
        assert isinstance(result["opportunities"], list)

    def test_calculate_overlap(self, analyzer, sample_campaigns, sample_search_terms):
        """Test overlap calculation between campaigns."""
        campaign1 = sample_campaigns[0]  # Search
        campaign2 = sample_campaigns[1]  # Performance Max

        # Same search terms for both campaigns (high overlap)
        overlap_data = analyzer._calculate_overlap(
            campaign1, campaign2, sample_search_terms, sample_search_terms
        )

        assert overlap_data["campaign1_id"] == campaign1.campaign_id
        assert overlap_data["campaign2_id"] == campaign2.campaign_id
        assert overlap_data["overlap_percentage"] == 100.0
        assert "overlapping_terms" in overlap_data

    def test_generate_channel_insights(self, analyzer):
        """Test channel insights generation."""
        channels = [
            {
                "channel": "Search",
                "spend": 2000.0,  # 80% of total spend
                "conversions": 20.0,
                "cpa": 100.0,
                "roas": 1.5,
            },
            {
                "channel": "Performance Max",
                "spend": 500.0,
                "conversions": 15.0,
                "cpa": 33.33,
                "roas": 3.0,
            },
        ]

        insights = analyzer._generate_channel_insights(channels)

        assert len(insights) > 0
        # Should identify channel dominance
        dominance_insight = next(
            (i for i in insights if i["type"] == "channel_dominance"), None
        )
        assert dominance_insight is not None

    def test_get_channel_name(self, analyzer):
        """Test channel name mapping."""
        assert analyzer._get_channel_name("SEARCH") == "Search"
        assert analyzer._get_channel_name("PERFORMANCE_MAX") == "Performance Max"
        assert analyzer._get_channel_name("SHOPPING") == "Shopping"
        assert analyzer._get_channel_name("UNKNOWN") == "Unknown"

    def test_normalize_query(self, analyzer):
        """Test query normalization."""
        assert analyzer._normalize_query("Running Shoes!") == "running shoes"
        assert analyzer._normalize_query("  Nike-Air  ") == "nike air"
        assert analyzer._normalize_query("Best [shoes] (2024)") == "best shoes 2024"

    def test_calculate_metrics(self, analyzer):
        """Test metric calculation methods."""
        # Test CPA calculation
        assert analyzer._calculate_cpa(100.0, 10.0) == 10.0
        assert analyzer._calculate_cpa(100.0, 0.0) == float("inf")

        # Test CTR calculation
        assert analyzer._calculate_ctr(50, 1000) == 5.0
        assert analyzer._calculate_ctr(50, 0) == 0.0

        # Test ROAS calculation
        assert analyzer._calculate_roas(200.0, 100.0) == 2.0
        assert analyzer._calculate_roas(200.0, 0.0) == 0.0

    def test_generate_recommendations(self, analyzer):
        """Test recommendation generation."""
        # Mock analysis data
        channel_performance = {
            "insights": [
                {
                    "type": "efficiency_gap",
                    "severity": "HIGH",
                    "message": "Large efficiency gap detected",
                    "recommendation": "Reallocate budget",
                }
            ]
        }

        overlap_analysis = {
            "high_conflict_overlaps": [
                {
                    "campaign1_type": "SEARCH",
                    "campaign2_type": "PERFORMANCE_MAX",
                    "overlap_percentage": 85.0,
                    "overlap_cost": 500.0,
                }
            ]
        }

        brand_conflicts = {
            "conflicts": [
                {
                    "campaign_name": "Test Campaign",
                    "details": "Brand exclusion conflict",
                }
            ]
        }

        budget_optimization = {
            "opportunities": [
                {
                    "type": "budget_reallocation",
                    "impact": "Reduce CPA by $10",
                    "potential_savings": 200.0,
                }
            ]
        }

        recommendations = analyzer._generate_recommendations(
            channel_performance, overlap_analysis, brand_conflicts, budget_optimization
        )

        assert len(recommendations) >= 4  # At least one from each category
        assert all(hasattr(r, "title") for r in recommendations)
        assert all(hasattr(r, "description") for r in recommendations)
        assert all(hasattr(r, "priority") for r in recommendations)

    @pytest.mark.asyncio
    async def test_analyze_with_data_provider_errors(self, analyzer):
        """Test analyze method with data provider errors."""
        # Mock data provider to raise exceptions
        analyzer.data_provider.get_campaigns.return_value = [
            Campaign(
                campaign_id="123",
                customer_id="123456789",
                name="Test Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=50.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MANUAL_CPC,
                cost=100.0,
                impressions=1000,
                clicks=50,
                conversions=5.0,
                conversion_value=500.0,
            )
        ]
        analyzer.data_provider.get_search_terms.side_effect = Exception("API Error")
        analyzer.data_provider.get_negative_keywords.side_effect = Exception(
            "API Error"
        )

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should still return a result even with errors
        assert isinstance(result, CampaignOverlapAnalysisResult)
        assert result.total_campaigns == 1
        # Overlap analysis should handle the error gracefully
        assert result.overlap_analysis.get("overlap_count", 0) == 0

    @pytest.mark.asyncio
    async def test_analyze_filters_low_spend_campaigns(self, analyzer):
        """Test that low-spend campaigns are filtered out."""
        low_spend_campaigns = [
            Campaign(
                campaign_id="123",
                customer_id="123456789",
                name="Low Spend Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=10.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MANUAL_CPC,
                cost=10.0,  # Below min_spend_threshold
                impressions=100,
                clicks=5,
                conversions=1.0,
                conversion_value=50.0,
            )
        ]

        analyzer.data_provider.get_campaigns.return_value = low_spend_campaigns

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.total_campaigns == 0  # Filtered out
        assert result.total_spend == 0.0

    @pytest.mark.asyncio
    async def test_analyze_filters_low_impression_campaigns(self, analyzer):
        """Test that low-impression campaigns are filtered out."""
        low_impression_campaigns = [
            Campaign(
                campaign_id="123",
                customer_id="123456789",
                name="Low Impression Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=50.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MANUAL_CPC,
                cost=100.0,
                impressions=50,  # Below min_impressions
                clicks=5,
                conversions=1.0,
                conversion_value=50.0,
            )
        ]

        analyzer.data_provider.get_campaigns.return_value = low_impression_campaigns

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.total_campaigns == 0  # Filtered out
        assert result.total_spend == 0.0


class TestCampaignOverlapAnalysisResult:
    """Test Campaign Overlap Analysis Result."""

    def test_initialization(self):
        """Test result initialization."""
        result = CampaignOverlapAnalysisResult(
            customer_id="123456789",
            analyzer_name="Test Analyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            recommendations=[],
            channel_performance={},
            overlap_analysis={"high_conflict_overlaps": []},
            brand_conflicts={},
            budget_optimization={"opportunities": []},
            total_campaigns=5,
            total_spend=5000.0,
            total_conversions=100.0,
            avg_roas=2.0,
            overlap_count=3,
            total_overlap_cost=500.0,
        )

        assert result.analysis_type == "campaign_overlap"
        assert result.total_campaigns == 5
        assert result.total_spend == 5000.0
        assert result.overlap_count == 3

    def test_get_methods(self):
        """Test getter methods."""
        result = CampaignOverlapAnalysisResult(
            customer_id="123456789",
            analyzer_name="Test Analyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            recommendations=[],
            channel_performance={"insights": [{"type": "test"}]},
            overlap_analysis={"high_conflict_overlaps": [{"test": "data"}]},
            brand_conflicts={},
            budget_optimization={"opportunities": [{"type": "test"}]},
            total_campaigns=0,
            total_spend=0.0,
            total_conversions=0.0,
            avg_roas=0.0,
            overlap_count=0,
            total_overlap_cost=0.0,
        )

        assert len(result.get_high_priority_overlaps()) == 1
        assert len(result.get_optimization_opportunities()) == 1
        assert len(result.get_channel_insights()) == 1

    def test_to_summary_dict(self):
        """Test summary dictionary generation."""
        result = CampaignOverlapAnalysisResult(
            customer_id="123456789",
            analyzer_name="Test Analyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            recommendations=[],
            channel_performance={"channels": [{"channel": "Search"}]},
            overlap_analysis={"high_conflict_overlaps": []},
            brand_conflicts={},
            budget_optimization={"total_potential_savings": 300.0, "opportunities": []},
            total_campaigns=3,
            total_spend=3000.0,
            total_conversions=50.0,
            avg_roas=1.8,
            overlap_count=2,
            total_overlap_cost=200.0,
        )

        summary = result.to_summary_dict()

        assert "analysis_date" in summary
        assert "summary" in summary
        assert "insights" in summary
        assert summary["summary"]["total_campaigns"] == 3
        assert summary["summary"]["total_spend"] == 3000.0
        assert summary["insights"]["channel_count"] == 1
        assert summary["insights"]["potential_savings"] == 300.0
