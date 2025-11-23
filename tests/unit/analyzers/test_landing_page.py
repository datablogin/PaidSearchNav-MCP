"""Unit tests for Landing Page Performance and Conversion Analyzer."""

from datetime import datetime

import pandas as pd
import pytest

from paidsearchnav_mcp.analyzers.landing_page import LandingPageAnalyzer
from paidsearchnav_mcp.models.landing_page import (
    LandingPageAnalysisResult,
    LandingPageMetrics,
    OptimizationType,
    TrafficSource,
)


@pytest.fixture
def analyzer():
    """Create an analyzer instance for testing."""
    return LandingPageAnalyzer(
        min_clicks=50,
        conversion_value=50.0,
        mobile_speed_threshold=50,
    )


@pytest.fixture
def sample_landing_page_data():
    """Create sample landing page data for testing."""
    return pd.DataFrame(
        {
            "Landing page": [
                "https://fitnessconnection.com/gyms/fayetteville",
                "https://fitnessconnection.com/gyms/south-park-mall",
                "https://fitnessconnection.com/gyms/stone-mountain",
                "https://fitnessconnection.com/",
                "https://fitnessconnection.com/join-now/",
            ],
            "Selected by": ["ADVERTISER"] * 5,
            "Mobile speed score": [0, 10, 0, 9, 75],
            "Mobile-friendly click rate": ["--", "--", "--", "--", "95%"],
            "Valid AMP click rate": ["--"] * 5,
            "Clicks": [379, 348, 3027, 113944, 10],
            "Impr.": ["6,114", "4,971", "46,039", "1,414,877", "100"],
            "CTR": ["6.20%", "7.00%", "6.57%", "8.05%", "10.00%"],
            "Currency code": ["USD"] * 5,
            "Avg. CPC": [3.48, 2.00, 1.99, 1.75, 2.50],
            "Cost": [1317.31, 696.78, 6027.85, 199874.74, 25.00],
        }
    )


@pytest.fixture
def high_performance_landing_pages():
    """Create high-performance landing page data for testing."""
    return pd.DataFrame(
        {
            "Landing page": [
                "https://fitnessconnection.com/premium",
                "https://fitnessconnection.com/special-offer",
                "https://fitnessconnection.com/new-member",
            ],
            "Selected by": ["ADVERTISER"] * 3,
            "Mobile speed score": [85, 90, 88],
            "Clicks": [5000, 4500, 6000],
            "Impr.": ["50,000", "40,000", "55,000"],
            "CTR": ["10.00%", "11.25%", "10.91%"],
            "Currency code": ["USD"] * 3,
            "Avg. CPC": [1.50, 1.25, 1.40],
            "Cost": [7500.00, 5625.00, 8400.00],
            "Conversions": [250.0, 270.0, 330.0],
        }
    )


@pytest.fixture
def low_performance_landing_pages():
    """Create low-performance landing page data for testing."""
    return pd.DataFrame(
        {
            "Landing page": [
                "https://fitnessconnection.com/old-page",
                "https://fitnessconnection.com/broken-form",
            ],
            "Selected by": ["ADVERTISER"] * 2,
            "Mobile speed score": [25, 15],
            "Clicks": [1000, 800],
            "Impr.": ["50,000", "40,000"],
            "CTR": ["2.00%", "2.00%"],
            "Currency code": ["USD"] * 2,
            "Avg. CPC": [5.00, 6.00],
            "Cost": [5000.00, 4800.00],
            "Conversions": [2.0, 0.0],
        }
    )


class TestLandingPageAnalyzer:
    """Test Landing Page Analyzer functionality."""

    @pytest.mark.asyncio
    async def test_analyze_with_valid_data(self, analyzer, sample_landing_page_data):
        """Test analysis with valid landing page data."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=sample_landing_page_data,
        )

        assert isinstance(result, LandingPageAnalysisResult)
        assert result.customer_id == "test_customer"
        assert len(result.landing_pages) == 5
        assert result.summary.total_pages_analyzed == 5
        assert result.summary.total_clicks > 0
        assert result.summary.total_cost > 0

    @pytest.mark.asyncio
    async def test_analyze_with_empty_data(self, analyzer):
        """Test analysis with empty data."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=pd.DataFrame(),
        )

        assert isinstance(result, LandingPageAnalysisResult)
        assert len(result.landing_pages) == 0
        assert len(result.optimizations) == 0
        assert result.summary.total_pages_analyzed == 0
        assert "No landing page data available" in result.summary.key_insights[0]

    @pytest.mark.asyncio
    async def test_analyze_with_no_data(self, analyzer):
        """Test analysis with no data provided."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        assert isinstance(result, LandingPageAnalysisResult)
        assert len(result.landing_pages) == 0
        assert result.metadata.get("error") == "No landing page data provided"

    @pytest.mark.asyncio
    async def test_invalid_date_range(self, analyzer, sample_landing_page_data):
        """Test analysis with invalid date range."""
        with pytest.raises(ValueError, match="Start date.*must be before end date"):
            await analyzer.analyze(
                customer_id="test_customer",
                start_date=datetime(2025, 8, 15),
                end_date=datetime(2025, 5, 18),
                landing_page_data=sample_landing_page_data,
            )

    def test_convert_to_landing_pages(self, analyzer, sample_landing_page_data):
        """Test conversion of raw data to LandingPageMetrics objects."""
        landing_pages = analyzer._convert_to_landing_pages(sample_landing_page_data)

        assert len(landing_pages) == 5
        assert all(isinstance(lp, LandingPageMetrics) for lp in landing_pages)

        # Check first landing page
        first = landing_pages[0]
        assert first.url == "https://fitnessconnection.com/gyms/fayetteville"
        assert first.clicks == 379
        assert first.impressions == 6114
        assert first.cost == 1317.31
        assert first.avg_cpc == 3.48

    def test_landing_page_efficiency_score(self, analyzer):
        """Test landing page efficiency score calculation."""
        page = LandingPageMetrics(
            url="test_page",
            clicks=1000,
            impressions=10000,
            ctr=10.0,
            cost=1000.0,
            avg_cpc=1.0,
            conversions=50.0,
            conversion_rate=5.0,
        )

        # Efficiency score should be based on conversion rate, CPC, and CTR
        score = page.efficiency_score
        assert score > 0
        assert score <= 100

    def test_generate_optimizations_low_conversion(self, analyzer):
        """Test optimization generation for low-converting pages."""
        pages = [
            LandingPageMetrics(
                url="low_converting_page",
                clicks=1000,
                impressions=10000,
                ctr=10.0,
                cost=1000.0,
                avg_cpc=1.0,
                conversions=5.0,
                conversion_rate=0.5,  # Very low conversion rate
            )
        ]

        optimizations = analyzer._generate_optimizations(pages)

        assert len(optimizations) > 0
        assert optimizations[0].optimization_type == OptimizationType.CONVERSION_RATE
        assert optimizations[0].priority in ["High", "Medium"]
        assert "conversion rate" in optimizations[0].reasoning.lower()

    def test_generate_optimizations_poor_mobile_speed(self, analyzer):
        """Test optimization generation for poor mobile speed."""
        pages = [
            LandingPageMetrics(
                url="slow_mobile_page",
                clicks=500,
                impressions=5000,
                ctr=10.0,
                cost=500.0,
                avg_cpc=1.0,
                conversions=25.0,
                conversion_rate=5.0,
                mobile_speed_score=25,  # Poor mobile speed
            )
        ]

        optimizations = analyzer._generate_optimizations(pages)

        # Should find mobile speed optimization
        mobile_opts = [
            opt
            for opt in optimizations
            if opt.optimization_type == OptimizationType.PAGE_SPEED
        ]
        assert len(mobile_opts) > 0
        assert "mobile speed" in mobile_opts[0].reasoning.lower()

    def test_identify_ab_test_opportunities(self, analyzer):
        """Test A/B test opportunity identification."""
        pages = [
            LandingPageMetrics(
                url="high_traffic_low_conversion",
                clicks=5000,
                impressions=50000,
                ctr=10.0,
                cost=5000.0,
                avg_cpc=1.0,
                conversions=50.0,
                conversion_rate=1.0,  # Low conversion for high traffic
            )
        ]

        ab_tests = analyzer._identify_ab_test_opportunities(pages)

        assert len(ab_tests) > 0
        assert ab_tests[0].control_page == "high_traffic_low_conversion"
        assert ab_tests[0].priority == "High"
        assert len(ab_tests[0].variant_suggestions) > 0

    def test_analyze_traffic_sources(self, analyzer, sample_landing_page_data):
        """Test traffic source analysis."""
        landing_pages = analyzer._convert_to_landing_pages(sample_landing_page_data)

        # Add traffic source totals to data
        data_with_totals = sample_landing_page_data.copy()
        new_row = pd.DataFrame(
            {
                "Landing page": ["Total: Search"],
                "Clicks": [117698],
                "Impr.": ["1,471,101"],
                "CTR": ["8.00%"],
                "Cost": [208641.68],
                "Avg. CPC": [1.77],
            }
        )
        data_with_totals = pd.concat([data_with_totals, new_row], ignore_index=True)

        traffic_performance = analyzer._analyze_traffic_sources(
            landing_pages, data_with_totals
        )

        assert len(traffic_performance) > 0
        assert traffic_performance[0].source in [
            TrafficSource.SEARCH,
            TrafficSource.DISPLAY,
            TrafficSource.VIDEO,
        ]
        assert traffic_performance[0].total_clicks > 0

    def test_analyze_conversion_funnels(self, analyzer):
        """Test conversion funnel analysis."""
        pages = [
            LandingPageMetrics(
                url="test_page",
                clicks=1000,
                impressions=10000,
                conversions=50.0,
            )
        ]

        funnels = analyzer._analyze_conversion_funnels(pages)

        assert len(funnels) > 0
        assert funnels[0].page_url == "test_page"
        assert funnels[0].clicks == 1000
        assert funnels[0].conversions == 50.0
        assert funnels[0].overall_conversion_rate == 5.0

    def test_create_summary(self, analyzer):
        """Test summary creation."""
        pages = [
            LandingPageMetrics(
                url=f"page_{i}",
                clicks=100 * (i + 1),
                impressions=1000 * (i + 1),
                ctr=10.0,
                cost=100.0 * (i + 1),
                avg_cpc=1.0,
                conversions=5.0 * (i + 1),
                conversion_rate=5.0,
            )
            for i in range(5)
        ]

        optimizations = []
        ab_tests = []

        summary = analyzer._create_summary(pages, optimizations, ab_tests)

        assert summary.total_pages_analyzed == 5
        assert summary.pages_with_sufficient_data == 5
        assert summary.total_clicks == sum(p.clicks for p in pages)
        assert summary.total_cost == sum(p.cost for p in pages)
        assert len(summary.top_performing_pages) <= 5
        assert len(summary.bottom_performing_pages) <= 5

    def test_safe_float_conversion(self, analyzer):
        """Test safe float conversion."""
        assert analyzer._safe_float("123.45") == 123.45
        assert analyzer._safe_float("12.5%") == 12.5
        assert analyzer._safe_float("$1,234.56") == 1234.56
        assert analyzer._safe_float("--") == 0.0
        assert analyzer._safe_float(None) == 0.0
        assert analyzer._safe_float("") == 0.0

    def test_safe_int_conversion(self, analyzer):
        """Test safe integer conversion."""
        assert analyzer._safe_int("123") == 123
        assert analyzer._safe_int("1,234") == 1234
        assert analyzer._safe_int("--") == 0
        assert analyzer._safe_int(None) == 0
        assert analyzer._safe_int("") == 0

    @pytest.mark.asyncio
    async def test_high_performance_pages(
        self, analyzer, high_performance_landing_pages
    ):
        """Test analysis of high-performance landing pages."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=high_performance_landing_pages,
        )

        # High-performance pages should have fewer optimizations
        assert len(result.optimizations) < 5
        assert result.summary.avg_conversion_rate > 4.0

        # Top performers should be identified
        assert len(result.summary.top_performing_pages) > 0

    @pytest.mark.asyncio
    async def test_low_performance_pages(self, analyzer, low_performance_landing_pages):
        """Test analysis of low-performance landing pages."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=low_performance_landing_pages,
        )

        # Low-performance pages should generate multiple optimizations
        assert len(result.optimizations) > 0

        # Should identify mobile speed issues
        mobile_speed_opts = [
            opt
            for opt in result.optimizations
            if opt.optimization_type == OptimizationType.PAGE_SPEED
        ]
        assert len(mobile_speed_opts) > 0

        # Should identify conversion rate issues
        conversion_opts = [
            opt
            for opt in result.optimizations
            if opt.optimization_type == OptimizationType.CONVERSION_RATE
        ]
        assert len(conversion_opts) > 0

    @pytest.mark.asyncio
    async def test_result_to_dict(self, analyzer, sample_landing_page_data):
        """Test conversion of analysis result to dictionary."""
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=sample_landing_page_data,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["customer_id"] == "test_customer"
        assert "landing_pages" in result_dict
        assert "optimizations" in result_dict
        assert "summary" in result_dict
        assert len(result_dict["landing_pages"]) <= 10  # Top 10 only

    @pytest.mark.asyncio
    async def test_data_quality_score(self, analyzer):
        """Test data quality score calculation."""
        # Create data with varying quality
        data = pd.DataFrame(
            {
                "Landing page": [f"page_{i}" for i in range(10)],
                "Clicks": [
                    100 if i < 5 else 10 for i in range(10)
                ],  # Half have sufficient data
                "Impr.": ["1,000"] * 10,
                "CTR": ["10.00%"] * 10,
                "Cost": [100.0] * 10,
                "Avg. CPC": [1.0] * 10,
            }
        )

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            landing_page_data=data,
        )

        # Data quality should reflect that only half have sufficient data
        assert result.summary.data_quality_score == 50.0
        assert result.summary.pages_with_sufficient_data == 5

    @pytest.mark.asyncio
    async def test_missing_columns_error(self, analyzer):
        """Test error handling for missing required columns."""
        invalid_data = pd.DataFrame(
            {
                "URL": ["page1"],  # Wrong column name
                "Views": [100],  # Wrong column name
            }
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            analyzer._validate_landing_page_data(invalid_data)

    @pytest.mark.asyncio
    async def test_traffic_allocation_optimization(self, analyzer):
        """Test traffic allocation optimization for high-cost pages."""
        pages = [
            LandingPageMetrics(
                url="expensive_page",
                clicks=100,
                impressions=1000,
                ctr=10.0,
                cost=5000.0,
                avg_cpc=50.0,
                conversions=2.0,
                conversion_rate=2.0,
                cost_per_conversion=2500.0,  # Very high cost per conversion
            )
        ]

        optimizations = analyzer._generate_optimizations(pages)

        # Should recommend traffic allocation optimization
        traffic_opts = [
            opt
            for opt in optimizations
            if opt.optimization_type == OptimizationType.TRAFFIC_ALLOCATION
        ]
        assert len(traffic_opts) > 0
        assert traffic_opts[0].priority == "High"
        assert "cost per conversion" in traffic_opts[0].reasoning.lower()
