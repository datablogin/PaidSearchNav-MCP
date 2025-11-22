"""Unit tests for PerformanceMaxAnalyzer."""

from datetime import date, datetime

import pytest

from paidsearchnav.analyzers.pmax import PerformanceMaxAnalyzer, PerformanceMaxConfig
from paidsearchnav.core.models.analysis import (
    PerformanceMaxAnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav.core.models.search_term import SearchTerm, SearchTermMetrics


class MockDataProvider:
    """Mock data provider for testing."""

    def __init__(self):
        self.campaigns_data = []
        self.search_terms_data = []

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
        if campaign_types:
            # Handle both string and enum campaign types
            type_values = []
            for ct in campaign_types:
                if hasattr(ct, "value"):
                    type_values.append(ct.value)
                else:
                    type_values.append(ct)

            return [
                c
                for c in self.campaigns_data
                if c.type in type_values
                or (hasattr(c.type, "value") and c.type.value in type_values)
            ]
        return self.campaigns_data

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
        if campaigns:
            return [st for st in self.search_terms_data if st.campaign_id in campaigns]
        return self.search_terms_data

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
    """Create a PerformanceMaxAnalyzer instance."""
    config = PerformanceMaxConfig(
        min_impressions=100,
        min_spend_threshold=50.0,
        overlap_threshold=0.8,
        low_performance_threshold=1.5,
    )
    return PerformanceMaxAnalyzer(
        data_provider=mock_data_provider,
        config=config,
    )


@pytest.fixture
def sample_pmax_campaign():
    """Create a sample Performance Max campaign."""
    return Campaign(
        campaign_id="123456789",
        customer_id="987654321",
        name="Test PMax Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.PERFORMANCE_MAX,
        budget_amount=1000.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_ROAS,
        target_roas=3.0,
        impressions=10000,
        clicks=500,
        cost=200.0,
        conversions=50.0,
        conversion_value=1500.0,
    )


@pytest.fixture
def sample_search_campaign():
    """Create a sample Search campaign."""
    return Campaign(
        campaign_id="987654321",
        customer_id="987654321",
        name="Test Search Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SEARCH,
        budget_amount=800.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_CPA,
        target_cpa=20.0,
        impressions=8000,
        clicks=400,
        cost=150.0,
        conversions=30.0,
        conversion_value=900.0,
    )


@pytest.fixture
def sample_pmax_search_terms():
    """Create sample Performance Max search terms."""
    return [
        SearchTerm(
            campaign_id="123456789",
            campaign_name="Test PMax Campaign",
            ad_group_id="111111111",
            ad_group_name="Asset Group 1",
            search_term="running shoes",
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=50,
                cost=25.0,
                conversions=5.0,
                conversion_value=150.0,
            ),
            date_start=date(2023, 1, 1),
            date_end=date(2023, 1, 31),
        ),
        SearchTerm(
            campaign_id="123456789",
            campaign_name="Test PMax Campaign",
            ad_group_id="111111111",
            ad_group_name="Asset Group 1",
            search_term="cheap shoes",
            metrics=SearchTermMetrics(
                impressions=500,
                clicks=25,
                cost=50.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
            date_start=date(2023, 1, 1),
            date_end=date(2023, 1, 31),
        ),
        SearchTerm(
            campaign_id="123456789",
            campaign_name="Test PMax Campaign",
            ad_group_id="111111111",
            ad_group_name="Asset Group 1",
            search_term="running shoes near me",
            metrics=SearchTermMetrics(
                impressions=800,
                clicks=40,
                cost=20.0,
                conversions=4.0,
                conversion_value=120.0,
            ),
            date_start=date(2023, 1, 1),
            date_end=date(2023, 1, 31),
        ),
    ]


@pytest.fixture
def sample_search_terms():
    """Create sample Search campaign search terms."""
    return [
        SearchTerm(
            campaign_id="987654321",
            campaign_name="Test Search Campaign",
            ad_group_id="222222222",
            ad_group_name="Ad Group 1",
            search_term="running shoes",
            metrics=SearchTermMetrics(
                impressions=1200,
                clicks=60,
                cost=30.0,
                conversions=6.0,
                conversion_value=180.0,
            ),
            date_start=date(2023, 1, 1),
            date_end=date(2023, 1, 31),
        ),
        SearchTerm(
            campaign_id="987654321",
            campaign_name="Test Search Campaign",
            ad_group_id="222222222",
            ad_group_name="Ad Group 1",
            search_term="basketball shoes",
            metrics=SearchTermMetrics(
                impressions=600,
                clicks=30,
                cost=15.0,
                conversions=3.0,
                conversion_value=90.0,
            ),
            date_start=date(2023, 1, 1),
            date_end=date(2023, 1, 31),
        ),
    ]


class TestPerformanceMaxAnalyzer:
    """Test cases for PerformanceMaxAnalyzer."""

    def test_analyzer_initialization(self, mock_data_provider):
        """Test analyzer initialization with custom parameters."""
        config = PerformanceMaxConfig(
            min_impressions=200,
            min_spend_threshold=100.0,
            overlap_threshold=0.9,
            low_performance_threshold=2.0,
        )
        analyzer = PerformanceMaxAnalyzer(
            data_provider=mock_data_provider,
            config=config,
        )

        assert analyzer.data_provider == mock_data_provider
        assert analyzer.config.min_impressions == 200
        assert analyzer.config.min_spend_threshold == 100.0
        assert analyzer.config.overlap_threshold == 0.9
        assert analyzer.config.low_performance_threshold == 2.0

    def test_get_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.get_name() == "Performance Max Analyzer"

    def test_get_description(self, analyzer):
        """Test analyzer description."""
        description = analyzer.get_description()
        assert "Performance Max" in description
        assert "optimization opportunities" in description

    @pytest.mark.asyncio
    async def test_analyze_no_pmax_campaigns(self, analyzer, mock_data_provider):
        """Test analysis with no Performance Max campaigns."""
        # Setup mock data with no PMax campaigns
        mock_data_provider.campaigns_data = []

        result = await analyzer.analyze(
            customer_id="987654321",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert isinstance(result, PerformanceMaxAnalysisResult)
        assert result.customer_id == "987654321"
        assert result.total_pmax_campaigns == 0
        assert result.total_pmax_spend == 0.0
        assert len(result.findings) == 0
        assert len(result.recommendations) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_pmax_campaigns(
        self, analyzer, mock_data_provider, sample_pmax_campaign, sample_search_campaign
    ):
        """Test analysis with Performance Max campaigns."""
        # Setup mock data
        mock_data_provider.campaigns_data = [
            sample_pmax_campaign,
            sample_search_campaign,
        ]

        result = await analyzer.analyze(
            customer_id="987654321",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert isinstance(result, PerformanceMaxAnalysisResult)
        assert result.customer_id == "987654321"
        assert result.total_pmax_campaigns == 1
        assert result.total_pmax_spend == 200.0
        assert result.total_pmax_conversions == 50.0
        assert result.avg_pmax_roas == 7.5  # 1500/200

    @pytest.mark.asyncio
    async def test_analyze_low_performance_campaign(self, analyzer, mock_data_provider):
        """Test analysis with low-performing PMax campaign."""
        # Create a low-performing campaign
        low_performance_campaign = Campaign(
            campaign_id="123456789",
            customer_id="987654321",
            name="Low Performance PMax",
            status=CampaignStatus.ENABLED,
            type=CampaignType.PERFORMANCE_MAX,
            budget_amount=1000.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_ROAS,
            target_roas=3.0,
            impressions=10000,
            clicks=500,
            cost=500.0,
            conversions=50.0,
            conversion_value=600.0,  # ROAS = 1.2, below threshold of 1.5
        )

        mock_data_provider.campaigns_data = [low_performance_campaign]

        result = await analyzer.analyze(
            customer_id="987654321",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        # Check for performance findings
        performance_findings = [
            f for f in result.findings if f.get("type") == "performance_issue"
        ]
        assert len(performance_findings) > 0
        assert performance_findings[0]["severity"] in ["HIGH", "MEDIUM"]

        # Check for optimization recommendations
        optimization_recs = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.OPTIMIZE_BIDDING
        ]
        assert len(optimization_recs) > 0
        assert optimization_recs[0].priority == RecommendationPriority.HIGH

    @pytest.mark.asyncio
    async def test_search_term_analysis(
        self,
        analyzer,
        mock_data_provider,
        sample_pmax_campaign,
        sample_pmax_search_terms,
    ):
        """Test search term analysis functionality."""
        mock_data_provider.campaigns_data = [sample_pmax_campaign]
        mock_data_provider.search_terms_data = sample_pmax_search_terms

        result = await analyzer.analyze(
            customer_id="987654321",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        # Check search term analysis results
        search_analysis = result.search_term_analysis
        assert search_analysis["total_terms"] == 3

        # Check for local intent detection
        local_terms = search_analysis.get("local_intent_terms", [])
        assert len(local_terms) > 0
        assert any("near me" in term.search_term for term in local_terms)

        # Check for irrelevant terms (high cost, no conversions)
        irrelevant_terms = search_analysis.get("irrelevant_terms", [])
        assert len(irrelevant_terms) > 0  # "cheap shoes" should be flagged

    @pytest.mark.asyncio
    async def test_overlap_analysis(
        self,
        analyzer,
        mock_data_provider,
        sample_pmax_campaign,
        sample_search_campaign,
        sample_pmax_search_terms,
        sample_search_terms,
    ):
        """Test overlap analysis between PMax and Search campaigns."""
        mock_data_provider.campaigns_data = [
            sample_pmax_campaign,
            sample_search_campaign,
        ]
        mock_data_provider.search_terms_data = (
            sample_pmax_search_terms + sample_search_terms
        )

        result = await analyzer.analyze(
            customer_id="987654321",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        # Check overlap analysis
        overlap_analysis = result.overlap_analysis
        assert "overlapping_terms" in overlap_analysis
        assert "overlap_percentage" in overlap_analysis

        # Should detect "running shoes" as overlapping
        overlapping_terms = overlap_analysis["overlapping_terms"]
        assert len(overlapping_terms) > 0

        overlap_queries = [term["query"] for term in overlapping_terms]
        assert "running shoes" in overlap_queries

        # Check if high overlap triggers findings
        if overlap_analysis["overlap_percentage"] > 20:
            overlap_findings = [
                f for f in result.findings if f.get("type") == "campaign_overlap"
            ]
            assert len(overlap_findings) > 0

    def test_normalize_query(self, analyzer):
        """Test query normalization."""
        assert analyzer._normalize_query("Running Shoes") == "running shoes"
        assert analyzer._normalize_query("  NEAR ME  ") == "near me"
        assert analyzer._normalize_query("Test Query") == "test query"

    def test_campaign_performance_analysis(self, analyzer, sample_pmax_campaign):
        """Test campaign performance analysis."""
        campaigns = [sample_pmax_campaign]

        performance_analysis = analyzer._analyze_campaign_performance(campaigns)

        assert "campaigns" in performance_analysis
        assert "avg_roas" in performance_analysis
        assert "total_spend" in performance_analysis
        assert "low_performance_count" in performance_analysis

        assert performance_analysis["total_spend"] == 200.0
        assert performance_analysis["avg_roas"] == 7.5  # 1500/200
        assert performance_analysis["low_performance_count"] == 0  # Good performance

    def test_search_term_analysis_with_empty_list(self, analyzer):
        """Test search term analysis with empty search terms."""
        result = analyzer._analyze_pmax_search_terms([])

        assert result["total_terms"] == 0
        assert len(result["high_volume_terms"]) == 0
        assert len(result["high_performing_terms"]) == 0
        assert len(result["irrelevant_terms"]) == 0
        assert len(result["local_intent_terms"]) == 0
        assert len(result["brand_terms"]) == 0
        assert len(result["port_to_search_candidates"]) == 0
        assert len(result["negative_keyword_candidates"]) == 0

    def test_overlap_analysis_with_empty_lists(self, analyzer):
        """Test overlap analysis with empty lists."""
        # Test with empty PMax terms
        result = analyzer._analyze_search_overlap([], [])
        assert result["overlap_percentage"] == 0.0
        assert len(result["overlapping_terms"]) == 0

    def test_generate_performance_findings(self, analyzer):
        """Test performance findings generation."""
        # Mock analysis with performance issues
        analysis = {
            "campaigns": [
                {
                    "campaign": Campaign(
                        campaign_id="123",
                        customer_id="456",
                        name="Test Campaign",
                        status=CampaignStatus.ENABLED,
                        type=CampaignType.PERFORMANCE_MAX,
                        budget_amount=1000.0,
                        budget_currency="USD",
                        bidding_strategy=BiddingStrategy.TARGET_ROAS,
                        cost=100.0,
                        conversions=10.0,
                        conversion_value=100.0,  # Low ROAS
                    ),
                    "roas": 1.0,
                    "needs_optimization": True,
                }
            ],
            "avg_roas": 1.0,
            "low_performance_count": 1,
        }

        findings = analyzer._generate_performance_findings(analysis)

        assert len(findings) >= 1
        assert findings[0]["type"] == "performance_issue"
        assert findings[0]["severity"] == "MEDIUM"  # 1 campaign

    def test_generate_search_term_findings(self, analyzer, sample_pmax_search_terms):
        """Test search term findings generation."""
        analysis = analyzer._analyze_pmax_search_terms(sample_pmax_search_terms)
        findings = analyzer._generate_search_term_findings(analysis)

        # Should have findings for irrelevant terms
        irrelevant_findings = [
            f for f in findings if f.get("type") == "irrelevant_search_terms"
        ]
        assert len(irrelevant_findings) > 0

        # Should have findings for local intent
        local_findings = [
            f for f in findings if f.get("type") == "local_intent_opportunity"
        ]
        assert len(local_findings) > 0

    def test_generate_enhanced_search_term_recommendations(self, analyzer):
        """Test enhanced search term recommendations generation."""
        # Create analysis with various candidates
        analysis = {
            "port_to_search_candidates": [
                {
                    "search_term": SearchTerm(
                        campaign_id="123",
                        campaign_name="PMax",
                        ad_group_id="456",
                        ad_group_name="AG1",
                        search_term="high value term",
                        metrics=SearchTermMetrics(
                            impressions=1000,
                            clicks=100,
                            cost=50,
                            conversions=10,
                            conversion_value=500,
                        ),
                        date_start=date(2023, 1, 1),
                        date_end=date(2023, 1, 31),
                    ),
                    "priority": "HIGH",
                    "estimated_impact": "$500.00 revenue",
                }
            ],
            "negative_keyword_candidates": [
                {
                    "search_term": SearchTerm(
                        campaign_id="123",
                        campaign_name="PMax",
                        ad_group_id="456",
                        ad_group_name="AG1",
                        search_term="irrelevant term",
                        metrics=SearchTermMetrics(
                            impressions=1000,
                            clicks=50,
                            cost=100,
                            conversions=0,
                            conversion_value=0,
                        ),
                        date_start=date(2023, 1, 1),
                        date_end=date(2023, 1, 31),
                    ),
                    "reason": "high_cost_no_conversions",
                    "priority": "HIGH",
                    "potential_savings": "$100.00",
                }
            ],
            "local_intent_terms": [
                SearchTerm(
                    campaign_id="123",
                    campaign_name="PMax",
                    ad_group_id="456",
                    ad_group_name="AG1",
                    search_term="stores near me",
                    metrics=SearchTermMetrics(
                        impressions=500,
                        clicks=25,
                        cost=20,
                        conversions=5,
                        conversion_value=150,
                    ),
                    date_start=date(2023, 1, 1),
                    date_end=date(2023, 1, 31),
                )
            ]
            * 15,  # 15 local terms to trigger recommendation
        }

        recommendations = analyzer._generate_search_term_recommendations(analysis)

        # Should have recommendation for porting to Search
        port_recs = [
            r for r in recommendations if r.type == RecommendationType.ADD_KEYWORD
        ]
        assert len(port_recs) > 0
        assert port_recs[0].priority == RecommendationPriority.HIGH

        # Should have recommendation for negative keywords
        negative_recs = [
            r
            for r in recommendations
            if r.type == RecommendationType.ADD_NEGATIVE_KEYWORDS
        ]
        assert len(negative_recs) > 0
        assert "$100.00" in negative_recs[0].estimated_impact

        # Should have recommendation for local intent optimization
        local_recs = [
            r for r in recommendations if r.type == RecommendationType.OPTIMIZE_ASSETS
        ]
        assert len(local_recs) > 0

    def test_generate_overlap_findings(self, analyzer):
        """Test overlap findings generation."""
        # High overlap scenario
        analysis = {
            "overlap_percentage": 60.0,
            "overlapping_terms": [{"query": "test", "total_cost": 100}],
            "high_cost_overlaps": [{"query": "expensive term", "total_cost": 60}],
        }

        findings = analyzer._generate_overlap_findings(analysis)

        # Should have high overlap finding
        overlap_findings = [f for f in findings if f.get("type") == "campaign_overlap"]
        assert len(overlap_findings) > 0
        assert overlap_findings[0]["severity"] == "HIGH"  # >50% overlap

        # Should have high cost overlap finding
        cost_findings = [f for f in findings if f.get("type") == "high_cost_overlap"]
        assert len(cost_findings) > 0

    @pytest.mark.asyncio
    async def test_fetch_pmax_search_terms(
        self, analyzer, mock_data_provider, sample_pmax_campaign
    ):
        """Test fetching PMax search terms."""
        mock_data_provider.search_terms_data = []

        result = await analyzer._fetch_pmax_search_terms(
            customer_id="987654321",
            campaigns=[sample_pmax_campaign],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_search_terms(
        self, analyzer, mock_data_provider, sample_search_campaign
    ):
        """Test fetching Search campaign search terms."""
        mock_data_provider.search_terms_data = []

        result = await analyzer._fetch_search_terms(
            customer_id="987654321",
            campaigns=[sample_search_campaign],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert isinstance(result, list)

    def test_generate_summary(self, analyzer, sample_pmax_campaign):
        """Test summary generation."""
        campaigns = [sample_pmax_campaign]
        search_analysis = {
            "total_terms": 10,
            "high_performing_terms": [1, 2, 3],
            "port_to_search_candidates": [
                {"priority": "HIGH", "estimated_impact": "$100"}
            ],
            "negative_keyword_candidates": [
                {"potential_savings": "$50.00"},
                {"potential_savings": "$25.00"},
            ],
        }
        overlap_analysis = {
            "overlap_percentage": 25.0,
            "total_overlap_cost": 300.0,
            "performance_comparison": [
                {"potential_savings": 100.0},
                {"potential_savings": 50.0},
            ],
        }
        budget_allocation = {
            "transparency_score": 75.0,
            "channels": [
                {"channel": "Shopping", "percentage": 40.0},
                {"channel": "Search", "percentage": 30.0},
            ],
        }
        channel_performance = {
            "channels": [
                {"channel": "Shopping", "roas": 4.5},
                {"channel": "Search", "roas": 3.2},
            ],
        }
        asset_performance = {
            "total_assets": 50,
            "zombie_products": 5,
            "zombie_percentage": 10.0,
        }

        summary = analyzer._generate_summary(
            campaigns,
            search_analysis,
            overlap_analysis,
            budget_allocation,
            channel_performance,
            asset_performance,
        )

        assert "total_campaigns" in summary
        assert "total_spend" in summary
        assert "total_conversions" in summary
        assert "average_roas" in summary
        assert "search_terms_analyzed" in summary
        assert "high_performing_terms" in summary
        assert "port_to_search_candidates" in summary
        assert "negative_keyword_candidates" in summary
        assert "overlap_percentage" in summary
        assert "total_overlap_cost" in summary
        assert "optimization_opportunities" in summary
        assert "total_potential_savings" in summary

        assert summary["total_campaigns"] == 1
        assert summary["total_spend"] == 200.0
        assert summary["search_terms_analyzed"] == 10
        assert summary["overlap_percentage"] == 25.0
        assert summary["total_overlap_cost"] == 300.0
        assert summary["high_performing_terms"] == 3
        assert summary["port_to_search_candidates"] == 1
        assert summary["negative_keyword_candidates"] == 2
        assert summary["total_potential_savings"] == 225.0  # 75 + 150

    def test_result_to_summary_dict(self, analyzer):
        """Test conversion of result to summary dictionary."""
        # Create a minimal result for testing
        result = PerformanceMaxAnalysisResult(
            customer_id="987654321",
            analyzer_name="Performance Max Analyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            total_pmax_campaigns=2,
            total_pmax_spend=500.0,
            total_pmax_conversions=25.0,
            avg_pmax_roas=3.0,
            overlap_percentage=15.0,
        )

        summary_dict = result.to_summary_dict()

        assert "analysis_date" in summary_dict
        assert "date_range" in summary_dict
        assert "account" in summary_dict
        assert "summary" in summary_dict
        assert "findings" in summary_dict
        assert "top_recommendations" in summary_dict

        assert summary_dict["account"] == "987654321"
        assert summary_dict["summary"]["total_campaigns"] == 2
        assert summary_dict["summary"]["total_spend"] == 500.0
        assert summary_dict["summary"]["overlap_percentage"] == 15.0

    def test_get_high_priority_issues(self, analyzer):
        """Test getting high priority issues."""
        result = PerformanceMaxAnalysisResult(
            customer_id="987654321",
            analyzer_name="Performance Max Analyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            findings=[
                {"severity": "HIGH", "type": "test_high"},
                {"severity": "MEDIUM", "type": "test_medium"},
                {"severity": "HIGH", "type": "test_high_2"},
            ],
        )

        high_priority = result.get_high_priority_issues()
        assert len(high_priority) == 2
        assert all(f["severity"] == "HIGH" for f in high_priority)

    def test_get_optimization_opportunities(self, analyzer):
        """Test getting optimization opportunities count."""
        from paidsearchnav.core.models.analysis import Recommendation

        result = PerformanceMaxAnalysisResult(
            customer_id="987654321",
            analyzer_name="Performance Max Analyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            recommendations=[
                Recommendation(
                    type=RecommendationType.OPTIMIZE_BIDDING,
                    priority=RecommendationPriority.HIGH,
                    title="Test High Priority",
                    description="Test Description",
                ),
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title="Test Medium Priority",
                    description="Test Description",
                ),
                Recommendation(
                    type=RecommendationType.RESOLVE_CONFLICTS,
                    priority=RecommendationPriority.CRITICAL,
                    title="Test Critical Priority",
                    description="Test Description",
                ),
            ],
        )

        opportunities = result.get_optimization_opportunities()
        assert opportunities == 2  # HIGH + CRITICAL

    def test_high_performing_search_terms_identification(self, analyzer):
        """Test identification of high-performing search terms for porting to Search campaigns."""
        # Create high-performing search terms
        high_performing_terms = [
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="best running shoes",
                metrics=SearchTermMetrics(
                    impressions=2000,
                    clicks=100,
                    cost=50.0,
                    conversions=10.0,
                    conversion_value=500.0,  # ROAS = 10.0
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="professional running shoes",
                metrics=SearchTermMetrics(
                    impressions=1500,
                    clicks=75,
                    cost=40.0,
                    conversions=8.0,
                    conversion_value=320.0,  # ROAS = 8.0
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        result = analyzer._analyze_pmax_search_terms(high_performing_terms)

        assert len(result["high_performing_terms"]) == 2
        assert len(result["port_to_search_candidates"]) == 2

        # Check that high-priority candidates are identified
        high_priority_ports = [
            c for c in result["port_to_search_candidates"] if c["priority"] == "HIGH"
        ]
        assert len(high_priority_ports) > 0
        assert "best running shoes" in [
            c["search_term"].search_term for c in high_priority_ports
        ]

    def test_negative_keyword_candidates_identification(self, analyzer):
        """Test identification of search terms for negative keyword list."""
        # Create irrelevant search terms with different issues
        irrelevant_terms = [
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="free shoes",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=50,
                    cost=100.0,  # High cost
                    conversions=0.0,  # No conversions
                    conversion_value=0.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="shoe repair",
                metrics=SearchTermMetrics(
                    impressions=2000,
                    clicks=5,  # 0.25% CTR < 0.5%
                    cost=20.0,
                    conversions=0.0,
                    conversion_value=0.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="luxury shoes",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=25,
                    cost=250.0,
                    conversions=1.0,  # Excessive CPA = 250
                    conversion_value=200.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        result = analyzer._analyze_pmax_search_terms(irrelevant_terms)

        assert len(result["irrelevant_terms"]) == 3
        assert len(result["negative_keyword_candidates"]) == 3

        # Check different reasons for negative keywords
        reasons = [c["reason"] for c in result["negative_keyword_candidates"]]
        assert "high_cost_no_conversions" in reasons
        assert "very_low_ctr" in reasons
        assert "excessive_cpa" in reasons

        # Check high priority negatives
        high_priority_negatives = [
            c for c in result["negative_keyword_candidates"] if c["priority"] == "HIGH"
        ]
        assert (
            len(high_priority_negatives) > 0
        )  # "free shoes" with $100 cost should be HIGH

    def test_enhanced_overlap_analysis(self, analyzer):
        """Test enhanced overlap analysis with performance comparison."""
        # Create overlapping search terms with different performance
        pmax_terms = [
            SearchTerm(
                campaign_id="123456789",
                campaign_name="Test PMax Campaign",
                ad_group_id="111111111",
                ad_group_name="Asset Group 1",
                search_term="running shoes",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=50,
                    cost=50.0,
                    conversions=5.0,
                    conversion_value=150.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        search_terms = [
            SearchTerm(
                campaign_id="987654321",
                campaign_name="Test Search Campaign",
                ad_group_id="222222222",
                ad_group_name="Ad Group 1",
                search_term="running shoes",
                metrics=SearchTermMetrics(
                    impressions=1200,
                    clicks=60,
                    cost=30.0,
                    conversions=6.0,  # Better CPA than PMax
                    conversion_value=180.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        result = analyzer._analyze_search_overlap(pmax_terms, search_terms)

        assert "performance_comparison" in result
        assert "total_overlap_cost" in result
        assert result["total_overlap_cost"] == 80.0  # 50 + 30

        # Check performance comparison
        performance_comp = result["performance_comparison"]
        assert len(performance_comp) > 0
        assert "recommendation" in performance_comp[0]
        assert "potential_savings" in performance_comp[0]

        # Search campaign has better CPA (5 vs 10), so should recommend negative in PMax
        overlap_term = result["overlapping_terms"][0]
        assert overlap_term["better_performer"] == "search"

    def test_get_overlap_recommendation(self, analyzer):
        """Test overlap recommendation generation."""
        # Test when Search performs better
        overlap_data = {
            "query": "test term",
            "better_performer": "search",
            "search_cpa": 5.0,
            "pmax_cpa": 10.0,
            "search_conversions": 10,
            "pmax_conversions": 5,
        }

        recommendation = analyzer._get_overlap_recommendation(overlap_data)
        assert "negative to PMax" in recommendation

        # Test when PMax significantly outperforms
        overlap_data["better_performer"] = "pmax"
        overlap_data["pmax_conversions"] = 25  # More than 2x search

        recommendation = analyzer._get_overlap_recommendation(overlap_data)
        assert "pausing" in recommendation and "Search" in recommendation

    def test_calculate_overlap_savings(self, analyzer):
        """Test overlap savings calculation."""
        # Test significant performance difference
        overlap_data = {
            "better_performer": "search",
            "search_cpa": 5.0,
            "pmax_cpa": 20.0,  # 4x worse
            "pmax_cost": 100.0,
            "search_cost": 50.0,
            "total_cost": 150.0,
        }

        savings = analyzer._calculate_overlap_savings(overlap_data)
        assert savings == 100.0  # Should save full PMax cost

        # Test similar performance
        overlap_data["pmax_cpa"] = 6.0  # Similar to search

        savings = analyzer._calculate_overlap_savings(overlap_data)
        assert savings == 45.0  # 30% of total cost

    def test_ngrams_analysis(self, analyzer):
        """Test N-grams analysis functionality."""
        search_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="best running shoes for men",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=50,
                    cost=25.0,
                    conversions=5.0,
                    conversion_value=150.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="best running shoes for women",
                metrics=SearchTermMetrics(
                    impressions=1200,
                    clicks=60,
                    cost=30.0,
                    conversions=6.0,
                    conversion_value=180.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="running shoes on sale",
                metrics=SearchTermMetrics(
                    impressions=800,
                    clicks=40,
                    cost=20.0,
                    conversions=3.0,
                    conversion_value=90.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        # Add more instances to meet threshold
        for i in range(3):
            search_terms.append(
                SearchTerm(
                    campaign_id="123",
                    campaign_name="PMax",
                    ad_group_id="456",
                    ad_group_name="AG1",
                    search_term=f"running shoes variant {i}",
                    metrics=SearchTermMetrics(
                        impressions=500,
                        clicks=25,
                        cost=15.0,
                        conversions=2.0,
                        conversion_value=60.0,
                    ),
                    date_start=date(2023, 1, 1),
                    date_end=date(2023, 1, 31),
                )
            )

        result = analyzer._analyze_ngrams(search_terms)

        assert "bigrams" in result
        assert "trigrams" in result
        assert "patterns" in result
        assert "total_unique_bigrams" in result
        assert "total_unique_trigrams" in result

        # Check bigrams
        bigrams = result["bigrams"]
        assert len(bigrams) > 0

        # "running shoes" should be a top bigram
        running_shoes_bigram = next(
            (b for b in bigrams if b["ngram"] == "running shoes"), None
        )
        assert running_shoes_bigram is not None
        assert running_shoes_bigram["count"] >= 3
        assert running_shoes_bigram["cost"] > 0
        assert running_shoes_bigram["conversions"] > 0
        assert "cpa" in running_shoes_bigram

        # Check trigrams
        trigrams = result["trigrams"]
        if len(trigrams) > 0:
            assert "ngram" in trigrams[0]
            assert "count" in trigrams[0]
            assert "cost" in trigrams[0]
            assert "conversions" in trigrams[0]
            assert "cpa" in trigrams[0]

    def test_identify_search_patterns(self, analyzer):
        """Test search pattern identification."""
        search_terms = [
            # Question patterns
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="what are the best running shoes",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=25,
                    cost=15.0,
                    conversions=2.0,
                    conversion_value=60.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="how to choose running shoes",
                metrics=SearchTermMetrics(
                    impressions=400,
                    clicks=20,
                    cost=10.0,
                    conversions=1.0,
                    conversion_value=30.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Comparison patterns
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="nike vs adidas running shoes",
                metrics=SearchTermMetrics(
                    impressions=600,
                    clicks=30,
                    cost=20.0,
                    conversions=3.0,
                    conversion_value=90.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="best running shoes review",
                metrics=SearchTermMetrics(
                    impressions=700,
                    clicks=35,
                    cost=25.0,
                    conversions=4.0,
                    conversion_value=120.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Price patterns
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="cheap running shoes",
                metrics=SearchTermMetrics(
                    impressions=800,
                    clicks=40,
                    cost=15.0,
                    conversions=2.0,
                    conversion_value=40.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="running shoes on sale",
                metrics=SearchTermMetrics(
                    impressions=900,
                    clicks=45,
                    cost=18.0,
                    conversions=3.0,
                    conversion_value=60.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        patterns = analyzer._identify_search_patterns(search_terms)

        # Check question patterns
        question_pattern = next((p for p in patterns if p["type"] == "questions"), None)
        assert question_pattern is not None
        assert question_pattern["count"] == 2
        assert question_pattern["cost"] == 25.0
        assert question_pattern["conversions"] == 3.0
        assert len(question_pattern["examples"]) > 0

        # Check comparison patterns
        comparison_pattern = next(
            (p for p in patterns if p["type"] == "comparisons"), None
        )
        assert comparison_pattern is not None
        assert (
            comparison_pattern["count"] == 3
        )  # "nike vs adidas", "best running shoes review", and "what are the best running shoes"
        assert comparison_pattern["cost"] == 60.0  # 20.0 + 25.0 + 15.0
        assert comparison_pattern["conversions"] == 9.0  # 3.0 + 4.0 + 2.0

        # Check price patterns
        price_pattern = next(
            (p for p in patterns if p["type"] == "price_sensitive"), None
        )
        assert price_pattern is not None
        assert price_pattern["count"] == 2
        assert price_pattern["cost"] == 33.0
        assert price_pattern["conversions"] == 5.0

    def test_calculate_brand_metrics(self, analyzer):
        """Test brand vs. non-brand metrics calculation."""
        brand_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="acme brand shoes",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=100,
                    cost=50.0,
                    conversions=10.0,
                    conversion_value=300.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="acme store locations",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=50,
                    cost=25.0,
                    conversions=5.0,
                    conversion_value=150.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        non_brand_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="running shoes",
                metrics=SearchTermMetrics(
                    impressions=2000,
                    clicks=100,
                    cost=100.0,
                    conversions=8.0,
                    conversion_value=240.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="athletic footwear",
                metrics=SearchTermMetrics(
                    impressions=1500,
                    clicks=75,
                    cost=75.0,
                    conversions=6.0,
                    conversion_value=180.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        metrics = analyzer._calculate_brand_metrics(brand_terms, non_brand_terms)

        assert "brand" in metrics
        assert "non_brand" in metrics
        assert "efficiency_comparison" in metrics

        # Check brand metrics
        brand_data = metrics["brand"]
        assert brand_data["count"] == 2
        assert brand_data["cost"] == 75.0
        assert brand_data["conversions"] == 15.0
        assert brand_data["conversion_value"] == 450.0
        assert brand_data["cpa"] == 5.0  # 75/15
        assert brand_data["roas"] == 6.0  # 450/75
        assert brand_data["cost_percentage"] == 30.0  # 75/(75+175)*100

        # Check non-brand metrics
        non_brand_data = metrics["non_brand"]
        assert non_brand_data["count"] == 2
        assert non_brand_data["cost"] == 175.0
        assert non_brand_data["conversions"] == 14.0
        assert non_brand_data["conversion_value"] == 420.0
        assert non_brand_data["cpa"] == 12.5  # 175/14
        assert non_brand_data["roas"] == 2.4  # 420/175
        assert non_brand_data["cost_percentage"] == 70.0  # 175/(75+175)*100

        # Check efficiency comparison
        efficiency = metrics["efficiency_comparison"]
        assert "cpa_difference" in efficiency
        assert "roas_difference" in efficiency
        assert efficiency["cpa_difference"] == 7.5  # |5.0 - 12.5|
        assert efficiency["roas_difference"] == 3.6  # |6.0 - 2.4|

    @pytest.mark.asyncio
    async def test_analyze_budget_allocation(self, analyzer, mock_data_provider):
        """Test budget allocation analysis."""
        campaigns = [
            Campaign(
                campaign_id="123456789",
                customer_id="987654321",
                name="Test PMax Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.PERFORMANCE_MAX,
                budget_amount=5000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_ROAS,
                target_roas=4.0,
                impressions=100000,
                clicks=5000,
                cost=1000.0,
                conversions=100.0,
                conversion_value=4000.0,
            ),
        ]

        result = await analyzer._analyze_budget_allocation(
            customer_id="987654321",
            campaigns=campaigns,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert "channels" in result
        assert "total_spend" in result
        assert "transparency_score" in result
        assert "allocation_insights" in result
        assert "optimization_opportunities" in result

        # Check channel allocation
        channels = result["channels"]
        assert len(channels) == 4  # Shopping, Search, Display, Video

        # Check Shopping channel (should be largest)
        shopping = next(c for c in channels if c["channel"] == "Shopping")
        assert shopping["percentage"] == 45.0
        assert shopping["spend"] == 450.0  # 45% of 1000
        assert "cpa" in shopping
        assert "ctr" in shopping
        assert "conversion_rate" in shopping

        # Check transparency score
        assert result["transparency_score"] > 0
        assert result["transparency_score"] <= 100

        # Check total spend
        assert result["total_spend"] == 1000.0

    @pytest.mark.asyncio
    async def test_analyze_channel_performance(self, analyzer, mock_data_provider):
        """Test channel performance analysis."""
        campaigns = [
            Campaign(
                campaign_id="123456789",
                customer_id="987654321",
                name="Test PMax Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.PERFORMANCE_MAX,
                budget_amount=5000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_ROAS,
                target_roas=4.0,
                impressions=100000,
                clicks=5000,
                cost=1000.0,
                conversions=100.0,
                conversion_value=4000.0,
            ),
        ]

        result = await analyzer._analyze_channel_performance(
            customer_id="987654321",
            campaigns=campaigns,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert "channels" in result
        assert "rankings" in result
        assert "insights" in result

        # Check rankings
        rankings = result["rankings"]
        assert "by_efficiency" in rankings
        assert "by_volume" in rankings
        assert len(rankings["by_efficiency"]) > 0
        assert len(rankings["by_volume"]) > 0

        # Check if insights are generated when there's a mismatch
        if rankings["by_efficiency"][0] != rankings["by_volume"][0]:
            assert len(result["insights"]) > 0
            assert result["insights"][0]["type"] == "efficiency_vs_volume_mismatch"

    @pytest.mark.asyncio
    async def test_analyze_asset_performance(self, analyzer, mock_data_provider):
        """Test asset performance analysis with zombie product detection."""
        campaigns = [
            Campaign(
                campaign_id="123456789",
                customer_id="987654321",
                name="Test PMax Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.PERFORMANCE_MAX,
                budget_amount=5000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_ROAS,
                target_roas=4.0,
                impressions=100000,
                clicks=5000,
                cost=1000.0,
                conversions=100.0,
                conversion_value=4000.0,
            ),
        ]

        result = await analyzer._analyze_asset_performance(
            customer_id="987654321",
            campaigns=campaigns,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        assert "asset_groups" in result
        assert "zombie_products" in result
        assert "zombie_products_count" in result
        assert "zombie_products_value" in result
        assert "low_performing_asset_groups" in result
        assert "avg_asset_group_cpa" in result
        assert "total_asset_groups" in result

        # Check zombie products
        assert result["zombie_products_count"] > 0
        assert result["zombie_products_value"] > 0
        assert len(result["zombie_products"]) > 0

        zombie_product = result["zombie_products"][0]
        assert "product_id" in zombie_product
        assert "impressions" in zombie_product
        assert zombie_product["clicks"] == 0  # Definition of zombie product
        assert "spend" in zombie_product
        assert "category" in zombie_product

        # Check asset groups
        assert len(result["asset_groups"]) > 0
        asset_group = result["asset_groups"][0]
        assert "campaign_id" in asset_group
        assert "asset_group_id" in asset_group
        assert "name" in asset_group
        assert "spend" in asset_group
        assert "conversions" in asset_group
        assert "cpa" in asset_group
        assert "performance_score" in asset_group

    def test_generate_budget_allocation_findings(self, analyzer):
        """Test budget allocation findings generation."""
        analysis = {
            "transparency_score": 40.0,  # Low score
            "channels": [  # Need channels for low transparency finding
                {"channel": "Shopping", "percentage": 65.0},
                {"channel": "Display", "percentage": 35.0},
            ],
            "allocation_insights": [
                {
                    "type": "imbalanced_allocation",
                    "severity": "HIGH",
                    "message": "Shopping is consuming 65% of budget",
                    "recommendation": "Consider diversifying channel mix",
                },
                {
                    "type": "inefficient_channel",
                    "severity": "MEDIUM",
                    "message": "Display has CPA $50.00 (50% above average)",
                    "recommendation": "Review Display targeting",
                },
            ],
        }

        findings = analyzer._generate_budget_allocation_findings(analysis)

        # Should have low transparency finding
        transparency_findings = [
            f for f in findings if f.get("type") == "low_transparency"
        ]
        assert len(transparency_findings) == 1
        assert transparency_findings[0]["severity"] == "HIGH"
        assert "40/100" in transparency_findings[0]["title"]

        # Should have budget imbalance finding
        imbalance_findings = [
            f for f in findings if f.get("type") == "budget_imbalance"
        ]
        assert len(imbalance_findings) == 1
        assert imbalance_findings[0]["severity"] == "HIGH"

    def test_generate_asset_performance_findings(self, analyzer):
        """Test asset performance findings generation."""
        analysis = {
            "zombie_products_count": 50,
            "zombie_products_value": 1500.0,
            "low_performing_asset_groups": [
                {"asset_group_id": "AG1", "cpa": 100.0},
                {"asset_group_id": "AG2", "cpa": 120.0},
            ],
        }

        findings = analyzer._generate_asset_performance_findings(analysis)

        # Should have zombie products finding
        zombie_findings = [f for f in findings if f.get("type") == "zombie_products"]
        assert len(zombie_findings) == 1
        assert zombie_findings[0]["severity"] == "HIGH"  # Value > 1000
        assert "50 zombie products" in zombie_findings[0]["title"]
        assert "$1500.00" in zombie_findings[0]["title"]

        # Should have low performing assets finding
        asset_findings = [
            f for f in findings if f.get("type") == "low_performing_assets"
        ]
        assert len(asset_findings) == 1
        assert asset_findings[0]["severity"] == "MEDIUM"
        assert "2 asset groups" in asset_findings[0]["title"]

    def test_export_transparency_data(self, analyzer):
        """Test export functionality for transparency data."""
        # Create a comprehensive result
        result = PerformanceMaxAnalysisResult(
            customer_id="987654321",
            analyzer_name="Performance Max Analyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            pmax_campaigns=[],
            search_term_analysis={
                "total_terms": 100,
                "brand_terms": [{"search_term": "brand1"}, {"search_term": "brand2"}],
                "non_brand_terms": [{"search_term": "generic1"}],
                "brand_vs_non_brand_metrics": {
                    "brand": {"count": 2, "cost": 100, "conversions": 10, "roas": 5.0},
                    "non_brand": {
                        "count": 1,
                        "cost": 200,
                        "conversions": 8,
                        "roas": 2.0,
                    },
                },
                "ngrams_analysis": {
                    "bigrams": [
                        {
                            "ngram": "running shoes",
                            "count": 10,
                            "cost": 50,
                            "conversions": 5,
                        }
                    ],
                    "trigrams": [
                        {
                            "ngram": "best running shoes",
                            "count": 5,
                            "cost": 25,
                            "conversions": 3,
                        }
                    ],
                    "patterns": [
                        {
                            "type": "questions",
                            "count": 20,
                            "cost": 100,
                            "conversions": 8,
                        }
                    ],
                },
                "port_to_search_candidates": [
                    {
                        "search_term": {"search_term": "high value term"},
                        "priority": "HIGH",
                    }
                ],
                "negative_keyword_candidates": [
                    {
                        "search_term": {"search_term": "irrelevant"},
                        "potential_savings": "$50",
                    }
                ],
            },
            budget_allocation={
                "transparency_score": 75.0,
                "channels": [{"channel": "Shopping", "spend": 450, "percentage": 45.0}],
                "total_spend": 1000.0,
                "allocation_insights": [
                    {"type": "imbalanced", "message": "Shopping dominates"}
                ],
                "optimization_opportunities": [
                    {"from_channel": "Display", "to_channel": "Shopping", "amount": 100}
                ],
            },
            channel_performance={
                "channels": [{"channel": "Shopping", "conversions": 50}],
                "rankings": {
                    "by_efficiency": ["Shopping", "Search"],
                    "by_volume": ["Shopping", "Display"],
                },
                "insights": [
                    {"type": "mismatch", "message": "Efficiency vs volume mismatch"}
                ],
            },
            asset_performance={
                "zombie_products_count": 25,
                "zombie_products_value": 500.0,
                "zombie_products": [
                    {"product_id": "PROD_1", "impressions": 1000, "clicks": 0}
                ],
                "low_performing_asset_groups": [
                    {"asset_group_id": "AG_1", "cpa": 100.0}
                ],
                "total_asset_groups": 5,
                "avg_asset_group_cpa": 50.0,
            },
            overlap_analysis={
                "overlap_percentage": 30.0,
                "total_overlap_cost": 300.0,
                "high_cost_overlaps": [{"query": "expensive term", "total_cost": 100}],
                "performance_comparison": [
                    {
                        "query": "test",
                        "recommendation": "Add negative",
                        "potential_savings": 50,
                    }
                ],
            },
            summary={
                "total_potential_savings": 850.0,
                "optimization_opportunities": 15,
            },
            total_pmax_campaigns=3,
            total_pmax_spend=1000.0,
            total_pmax_conversions=100.0,
            avg_pmax_roas=4.0,
            recommendations=[
                Recommendation(
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.OPTIMIZE_BIDDING,
                    title="Optimize Shopping channel",
                    description="Improve Shopping performance",
                    estimated_impact="20% improvement",
                )
            ],
        )

        exported_data = analyzer.export_transparency_data(result)

        # Check metadata
        assert "metadata" in exported_data
        assert exported_data["metadata"]["customer_id"] == "987654321"
        assert "analysis_date" in exported_data["metadata"]
        assert "date_range" in exported_data["metadata"]

        # Check budget allocation export
        assert "budget_allocation" in exported_data
        assert exported_data["budget_allocation"]["transparency_score"] == 75.0
        assert len(exported_data["budget_allocation"]["channels"]) == 1
        assert exported_data["budget_allocation"]["total_spend"] == 1000.0

        # Check channel performance export
        assert "channel_performance" in exported_data
        assert len(exported_data["channel_performance"]["channels"]) == 1
        assert "rankings" in exported_data["channel_performance"]
        assert len(exported_data["channel_performance"]["insights"]) == 1

        # Check search terms export
        assert "search_terms" in exported_data
        assert exported_data["search_terms"]["total_analyzed"] == 100
        assert exported_data["search_terms"]["brand_terms"]["count"] == 2
        assert exported_data["search_terms"]["non_brand_terms"]["count"] == 1
        assert len(exported_data["search_terms"]["ngrams"]["top_bigrams"]) == 1
        assert len(exported_data["search_terms"]["ngrams"]["patterns"]) == 1

        # Check asset performance export
        assert "asset_performance" in exported_data
        assert exported_data["asset_performance"]["zombie_products"]["count"] == 25
        assert (
            exported_data["asset_performance"]["zombie_products"]["wasted_spend"]
            == 500.0
        )
        assert (
            len(exported_data["asset_performance"]["zombie_products"]["products"]) == 1
        )

        # Check overlap analysis export
        assert "overlap_analysis" in exported_data
        assert exported_data["overlap_analysis"]["overlap_percentage"] == 30.0
        assert exported_data["overlap_analysis"]["total_overlap_cost"] == 300.0

        # Check summary export
        assert "summary" in exported_data
        assert exported_data["summary"]["total_campaigns"] == 3
        assert exported_data["summary"]["total_spend"] == 1000.0
        assert exported_data["summary"]["avg_roas"] == 4.0
        assert exported_data["summary"]["potential_savings"] == 850.0

        # Check recommendations export
        assert "recommendations" in exported_data
        assert len(exported_data["recommendations"]) == 1
        assert exported_data["recommendations"][0]["priority"] == "HIGH"
        assert exported_data["recommendations"][0]["type"] == "OPTIMIZE_BIDDING"

    def test_enhanced_local_intent_detection(self, analyzer):
        """Test enhanced local intent detection with patterns and geo-modifiers."""
        search_terms = [
            # Direct patterns
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="stores near me",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=50,
                    cost=25.0,
                    conversions=5.0,
                    conversion_value=150.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Geo-modifier patterns
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="running shoes in Chicago",
                metrics=SearchTermMetrics(
                    impressions=800,
                    clicks=40,
                    cost=20.0,
                    conversions=4.0,
                    conversion_value=120.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # ZIP code pattern
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="shoe store 60601",
                metrics=SearchTermMetrics(
                    impressions=600,
                    clicks=30,
                    cost=15.0,
                    conversions=3.0,
                    conversion_value=90.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Directional pattern
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="downtown running store",
                metrics=SearchTermMetrics(
                    impressions=700,
                    clicks=35,
                    cost=17.5,
                    conversions=3.5,
                    conversion_value=105.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Service location pattern
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="shoe store hours",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=25,
                    cost=12.5,
                    conversions=2.5,
                    conversion_value=75.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
            # Non-local term for comparison
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="best running shoes",
                metrics=SearchTermMetrics(
                    impressions=1200,
                    clicks=60,
                    cost=30.0,
                    conversions=6.0,
                    conversion_value=180.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        local_terms = analyzer._detect_local_intent_terms(search_terms)

        # Should detect all local intent terms except the last one
        assert len(local_terms) == 5

        # Verify specific patterns were detected
        local_search_terms = [st.search_term for st in local_terms]
        assert "stores near me" in local_search_terms
        assert "running shoes in Chicago" in local_search_terms
        assert "shoe store 60601" in local_search_terms
        assert "downtown running store" in local_search_terms
        assert "shoe store hours" in local_search_terms
        assert "best running shoes" not in local_search_terms

    def test_enhanced_asset_performance_analysis(self, analyzer):
        """Test enhanced asset performance analysis with new metrics."""
        campaigns = [
            Campaign(
                campaign_id="123456789",
                customer_id="987654321",
                name="Test PMax Campaign",
                status=CampaignStatus.ENABLED,
                type=CampaignType.PERFORMANCE_MAX,
                budget_amount=5000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_ROAS,
                target_roas=4.0,
                impressions=100000,
                clicks=5000,
                cost=2000.0,
                conversions=200.0,
                conversion_value=8000.0,
            ),
        ]

        # Mock the enhanced asset performance methods
        asset_analysis = analyzer._analyze_image_assets(campaigns, 2000.0)

        assert "total_images" in asset_analysis
        assert "underperforming_images" in asset_analysis
        assert "avg_ctr_by_image_type" in asset_analysis
        assert "spend_distribution" in asset_analysis

        # Check image CTR analysis
        assert (
            asset_analysis["avg_ctr_by_image_type"]["lifestyle"]
            > asset_analysis["avg_ctr_by_image_type"]["product_only"]
        )

        # Test video asset analysis
        video_analysis = analyzer._analyze_video_assets(campaigns, 2000.0)
        assert "total_videos" in video_analysis
        assert "avg_view_rate" in video_analysis
        assert "optimal_duration_seconds" in video_analysis

        # Test text asset analysis
        headline_analysis = analyzer._analyze_text_assets(campaigns, "headlines")
        assert "total_headlines" in headline_analysis
        assert "top_performing_patterns" in headline_analysis
        assert "Free Shipping" in headline_analysis["top_performing_patterns"]

        # Test zombie product detection
        zombie_analysis = analyzer._detect_zombie_products(campaigns, 2000.0)
        assert zombie_analysis["count"] > 0
        assert zombie_analysis["wasted_spend"] > 0
        assert "categories_affected" in zombie_analysis

        # Test asset combination analysis
        asset_groups = analyzer._analyze_asset_groups(campaigns)
        combination_analysis = analyzer._analyze_asset_combinations(asset_groups)

        assert "top_combinations" in combination_analysis
        assert "weak_combinations" in combination_analysis
        assert len(combination_analysis["top_combinations"]) > 0
        assert combination_analysis["top_combinations"][0]["performance_index"] > 1.0

        # Test asset health score calculation
        health_score = analyzer._calculate_asset_health_score(
            {"images": asset_analysis}, zombie_analysis, asset_groups
        )

        assert 0 <= health_score <= 100

    def test_configurable_thresholds(self, mock_data_provider):
        """Test that configurable thresholds work correctly."""
        # Create custom config
        custom_config = PerformanceMaxConfig(
            min_impressions=500,
            high_roas_threshold=5.0,
            excellent_roas_threshold=8.0,
            good_cpa_threshold=30.0,
            excessive_cpa_threshold=300.0,
            negative_keyword_min_cost=20.0,
            very_low_ctr_threshold=0.3,
            local_intent_patterns=["near me", "nearby", "directions", "store hours"],
            zombie_product_threshold=0.1,  # 10% instead of 5%
            imbalanced_allocation_threshold=0.7,  # 70% instead of 60%
        )

        analyzer = PerformanceMaxAnalyzer(
            data_provider=mock_data_provider,
            config=custom_config,
        )

        # Test that custom thresholds are used
        assert analyzer.config.min_impressions == 500
        assert analyzer.config.high_roas_threshold == 5.0
        assert analyzer.config.zombie_product_threshold == 0.1

        # Create search terms that test thresholds
        search_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="PMax",
                ad_group_id="456",
                ad_group_name="AG1",
                search_term="test term",
                metrics=SearchTermMetrics(
                    impressions=600,  # Above custom min_impressions
                    clicks=30,
                    cost=25.0,  # Above custom negative_keyword_min_cost
                    conversions=0.0,
                    conversion_value=0.0,
                ),
                date_start=date(2023, 1, 1),
                date_end=date(2023, 1, 31),
            ),
        ]

        result = analyzer._analyze_pmax_search_terms(search_terms)

        # Should be identified as negative candidate due to custom thresholds
        assert len(result["negative_keyword_candidates"]) > 0

    def test_asset_specific_recommendations(self, analyzer):
        """Test generation of asset-specific recommendations."""
        asset_analysis = {
            "images": {
                "recommended_refresh_count": 15,
            }
        }

        zombie_analysis = {
            "count": 50,
            "wasted_spend": 1000.0,
        }

        combination_analysis = {
            "weak_combinations": [
                {"headline": "Learn More", "description": "Click here"}
            ]
        }

        recommendations = analyzer._generate_asset_specific_recommendations(
            asset_analysis, zombie_analysis, combination_analysis
        )

        # Should have image refresh recommendation
        image_recs = [r for r in recommendations if r["type"] == "image_refresh"]
        assert len(image_recs) == 1
        assert image_recs[0]["priority"] == "HIGH"
        assert "15" in image_recs[0]["action"]

        # Should have zombie removal recommendation
        zombie_recs = [r for r in recommendations if r["type"] == "remove_zombies"]
        assert len(zombie_recs) == 1
        assert "$1000.00" in zombie_recs[0]["expected_impact"]

        # Should have combination improvement recommendation
        combo_recs = [r for r in recommendations if r["type"] == "improve_combinations"]
        assert len(combo_recs) == 1
        assert combo_recs[0]["priority"] == "MEDIUM"
