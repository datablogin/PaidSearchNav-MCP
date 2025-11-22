"""Unit tests for Ad Group Performance Analyzer."""

from datetime import datetime
from unittest.mock import patch

import pytest

from paidsearchnav.analyzers.ad_group_performance import (
    AdGroupPerformance,
    AdGroupPerformanceAnalyzer,
    AdGroupStatus,
)
from paidsearchnav.core.models.analysis import RecommendationType


class TestAdGroupPerformanceModel:
    """Test AdGroupPerformance data model."""

    def test_ctr_calculation(self):
        """Test CTR calculation."""
        ad_group = AdGroupPerformance(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            status=AdGroupStatus.ENABLED,
            impressions=1000,
            clicks=50,
            cost=100.0,
            conversions=5.0,
        )
        assert ad_group.ctr == 5.0  # 50/1000 * 100

    def test_ctr_with_zero_impressions(self):
        """Test CTR calculation with zero impressions."""
        ad_group = AdGroupPerformance(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            status=AdGroupStatus.ENABLED,
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
        )
        assert ad_group.ctr == 0.0

    def test_cpa_calculation(self):
        """Test CPA calculation."""
        ad_group = AdGroupPerformance(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            status=AdGroupStatus.ENABLED,
            impressions=1000,
            clicks=50,
            cost=200.0,
            conversions=4.0,
        )
        assert ad_group.cpa == 50.0  # 200/4

    def test_cpa_with_zero_conversions(self):
        """Test CPA calculation with zero conversions."""
        ad_group = AdGroupPerformance(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            status=AdGroupStatus.ENABLED,
            impressions=1000,
            clicks=50,
            cost=200.0,
            conversions=0.0,
        )
        assert ad_group.cpa == 0.0

    def test_roas_not_implemented(self):
        """Test that ROAS calculation raises NotImplementedError."""
        ad_group = AdGroupPerformance(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            status=AdGroupStatus.ENABLED,
            impressions=1000,
            clicks=50,
            cost=200.0,
            conversions=5.0,
        )
        import pytest

        with pytest.raises(NotImplementedError, match="ROAS calculation requires"):
            _ = ad_group.roas


class TestAdGroupPerformanceAnalyzer:
    """Test AdGroupPerformanceAnalyzer class."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization with custom parameters."""
        analyzer = AdGroupPerformanceAnalyzer(
            min_impressions=500,
            min_clicks=20,
            low_ctr_threshold=2.0,
            high_cpa_threshold=150.0,
        )
        assert analyzer.min_impressions == 500
        assert analyzer.min_clicks == 20
        assert analyzer.low_ctr_threshold == 2.0
        assert analyzer.high_cpa_threshold == 150.0

    def test_analyzer_name_and_description(self):
        """Test analyzer name and description methods."""
        analyzer = AdGroupPerformanceAnalyzer()
        assert analyzer.get_name() == "Ad Group Performance Analyzer"
        assert "optimization opportunities" in analyzer.get_description()

    @pytest.mark.asyncio
    async def test_analyze_with_csv_data(self):
        """Test analyze method with CSV data loaded."""
        analyzer = AdGroupPerformanceAnalyzer()

        # Mock CSV data
        analyzer._csv_data = [
            AdGroupPerformance(
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 1",
                status=AdGroupStatus.ENABLED,
                impressions=10000,
                clicks=100,
                cost=150.0,
                conversions=5.0,
                conversion_rate=5.0,
                avg_cpc=1.5,
            ),
            AdGroupPerformance(
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 2",
                status=AdGroupStatus.ENABLED,
                impressions=5000,
                clicks=25,
                cost=500.0,
                conversions=2.0,
                conversion_rate=8.0,
                avg_cpc=20.0,
            ),
        ]

        result = await analyzer.analyze(
            customer_id="123456",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )

        assert result.status == "completed"
        assert result.customer_id == "123456"
        assert result.analysis_type == "ad_group_performance"
        assert len(result.recommendations) > 0
        assert result.metrics.custom_metrics["total_ad_groups_analyzed"] == 2

    @pytest.mark.asyncio
    async def test_analyze_identifies_low_ctr(self):
        """Test that analyzer identifies ad groups with low CTR."""
        analyzer = AdGroupPerformanceAnalyzer(low_ctr_threshold=2.0)

        analyzer._csv_data = [
            AdGroupPerformance(
                campaign_name="Campaign 1",
                ad_group_name="Low CTR Ad Group",
                status=AdGroupStatus.ENABLED,
                impressions=10000,
                clicks=50,  # 0.5% CTR
                cost=100.0,
                conversions=2.0,
            ),
        ]

        result = await analyzer.analyze(
            customer_id="123456",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )

        # Check for low CTR recommendation
        low_ctr_recs = [r for r in result.recommendations if "Low CTR" in r.title]
        assert len(low_ctr_recs) > 0
        assert low_ctr_recs[0].type == RecommendationType.IMPROVE_QUALITY

    @pytest.mark.asyncio
    async def test_analyze_identifies_high_cpa(self):
        """Test that analyzer identifies ad groups with high CPA."""
        analyzer = AdGroupPerformanceAnalyzer(high_cpa_threshold=50.0)

        analyzer._csv_data = [
            AdGroupPerformance(
                campaign_name="Campaign 1",
                ad_group_name="High CPA Ad Group",
                status=AdGroupStatus.ENABLED,
                impressions=5000,
                clicks=100,
                cost=500.0,
                conversions=5.0,  # $100 CPA
            ),
        ]

        result = await analyzer.analyze(
            customer_id="123456",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )

        # Check for high CPA recommendation
        high_cpa_recs = [r for r in result.recommendations if "High CPA" in r.title]
        assert len(high_cpa_recs) > 0
        assert high_cpa_recs[0].type == RecommendationType.OPTIMIZE_BIDDING

    @pytest.mark.asyncio
    async def test_analyze_with_no_data(self):
        """Test analyze method with no data source."""
        analyzer = AdGroupPerformanceAnalyzer()

        result = await analyzer.analyze(
            customer_id="123456",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )

        assert result.status == "error"
        assert len(result.errors) > 0
        assert "No data source available" in result.errors[0]


class TestAdGroupCSVParsing:
    """Test CSV parsing functionality."""

    @pytest.fixture
    def sample_csv_content(self):
        """Provide sample CSV content."""
        return """# Ad group report
# Downloaded from Google Ads on 2025-07-30
Campaign,Ad group,Ad group state,Default max. CPC,Target CPA,Target ROAS,Impr.,Clicks,Cost,Conversions,Conv. rate,Avg. CPC
Test Campaign,Ad Group 1,Enabled,1.50,,,"10,000",500,750.00,25,5.00,1.50
Test Campaign,Ad Group 2,Paused,2.00,50.00,,"5,000",200,400.00,10,5.00,2.00
"""

    @pytest.fixture
    def temp_csv_file(self, tmp_path, sample_csv_content):
        """Create a temporary CSV file."""
        csv_file = tmp_path / "test_ad_groups.csv"
        csv_file.write_text(sample_csv_content)
        return csv_file

    def test_from_csv_success(self, temp_csv_file):
        """Test successful CSV loading."""
        analyzer = AdGroupPerformanceAnalyzer.from_csv(temp_csv_file)

        assert analyzer._csv_data is not None
        assert len(analyzer._csv_data) == 2

        # Check first ad group
        ad_group1 = analyzer._csv_data[0]
        assert ad_group1.campaign_name == "Test Campaign"
        assert ad_group1.ad_group_name == "Ad Group 1"
        assert ad_group1.status == "Enabled"
        assert ad_group1.impressions == 10000
        assert ad_group1.clicks == 500
        assert ad_group1.cost == 750.0
        assert ad_group1.conversions == 25.0

        # Check second ad group
        ad_group2 = analyzer._csv_data[1]
        assert ad_group2.target_cpa == 50.0

    def test_from_csv_file_not_found(self):
        """Test CSV loading with non-existent file."""
        with pytest.raises(FileNotFoundError):
            AdGroupPerformanceAnalyzer.from_csv("non_existent_file.csv")

    def test_from_csv_file_too_large(self, tmp_path):
        """Test CSV loading with file size limit."""
        csv_file = tmp_path / "large_file.csv"
        csv_file.write_text("x" * (101 * 1024 * 1024))  # 101 MB

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            AdGroupPerformanceAnalyzer.from_csv(csv_file, max_file_size_mb=100)

    def test_from_csv_invalid_format(self, tmp_path):
        """Test CSV loading with invalid format."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("Invalid,CSV,Format\n1,2,3")

        with pytest.raises(ValueError, match="Failed to parse ad group CSV"):
            AdGroupPerformanceAnalyzer.from_csv(csv_file)

    def test_from_csv_missing_required_columns(self, tmp_path):
        """Test CSV loading with missing required columns."""
        csv_file = tmp_path / "missing_columns.csv"
        csv_file.write_text("Campaign,Clicks,Cost\nTest,100,50.00")

        with pytest.raises(ValueError, match="Failed to parse ad group CSV"):
            AdGroupPerformanceAnalyzer.from_csv(csv_file)

    def test_parse_csv_handles_empty_values(self, tmp_path):
        """Test CSV parsing handles empty/null values correctly."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Target CPA,Impr.,Clicks,Cost,Conversions
Test Campaign,Ad Group 1,Enabled,,,1000,50,100.00,
"""
        csv_file = tmp_path / "empty_values.csv"
        csv_file.write_text(csv_content)

        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        assert len(analyzer._csv_data) == 1
        ad_group = analyzer._csv_data[0]
        assert ad_group.bid_amount is None
        assert ad_group.target_cpa is None
        assert ad_group.conversions == 0.0

    def test_parse_csv_handles_currency_symbols(self, tmp_path):
        """Test CSV parsing handles currency symbols."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Cost,Conversions
Test Campaign,Ad Group 1,Enabled,$2.50,"$1,234.56",10
"""
        csv_file = tmp_path / "currency.csv"
        csv_file.write_text(csv_content)

        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        ad_group = analyzer._csv_data[0]
        assert ad_group.bid_amount == 2.50
        assert ad_group.cost == 1234.56

    def test_parse_csv_handles_negative_values(self, tmp_path):
        """Test CSV parsing handles negative values in parentheses."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Cost,Conversions
Test Campaign,Ad Group 1,Enabled,($2.50),\"($100.00)\",5
"""
        csv_file = tmp_path / "negative_values.csv"
        csv_file.write_text(csv_content)

        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        ad_group = analyzer._csv_data[0]
        assert ad_group.bid_amount == -2.50
        assert ad_group.cost == -100.00

    def test_parse_csv_handles_percentages(self, tmp_path):
        """Test CSV parsing handles percentage values."""
        csv_content = """Campaign,Ad group,Ad group state,Conv. rate,Search impr. share
Test Campaign,Ad Group 1,Enabled,12.5%,75.3%
"""
        csv_file = tmp_path / "percentages.csv"
        csv_file.write_text(csv_content)

        analyzer = AdGroupPerformanceAnalyzer.from_csv(csv_file)

        ad_group = analyzer._csv_data[0]
        assert ad_group.conversion_rate == 12.5
        assert ad_group.search_impression_share == 75.3

    @patch("paidsearchnav.analyzers.ad_group_performance.Path.cwd")
    def test_path_traversal_protection(self, mock_cwd, tmp_path):
        """Test protection against path traversal attacks."""
        mock_cwd.return_value = tmp_path / "safe_dir"

        # Try to access file outside allowed directories
        unsafe_path = "/etc/passwd"

        with pytest.raises(PermissionError, match="Access denied"):
            AdGroupPerformanceAnalyzer.from_csv(unsafe_path)


class TestAdGroupAnalysisMethods:
    """Test internal analysis methods."""

    def test_group_by_campaign(self):
        """Test grouping ad groups by campaign."""
        analyzer = AdGroupPerformanceAnalyzer()

        ad_groups = [
            AdGroupPerformance(
                campaign_name="Campaign A",
                ad_group_name="AG1",
                status=AdGroupStatus.ENABLED,
            ),
            AdGroupPerformance(
                campaign_name="Campaign A",
                ad_group_name="AG2",
                status=AdGroupStatus.ENABLED,
            ),
            AdGroupPerformance(
                campaign_name="Campaign B",
                ad_group_name="AG3",
                status=AdGroupStatus.ENABLED,
            ),
        ]

        grouped = analyzer._group_by_campaign(ad_groups)

        assert len(grouped) == 2
        assert len(grouped["Campaign A"]) == 2
        assert len(grouped["Campaign B"]) == 1

    def test_analyze_performance_identifies_issues(self):
        """Test performance analysis identifies issues correctly."""
        analyzer = AdGroupPerformanceAnalyzer(
            low_ctr_threshold=2.0, high_cpa_threshold=50.0
        )

        ad_groups = [
            AdGroupPerformance(
                campaign_name="Campaign",
                ad_group_name="Low CTR Group",
                status=AdGroupStatus.ENABLED,
                impressions=1000,
                clicks=5,  # 0.5% CTR
                cost=100.0,
                conversions=1.0,
            ),
            AdGroupPerformance(
                campaign_name="Campaign",
                ad_group_name="High CPA Group",
                status=AdGroupStatus.ENABLED,
                impressions=1000,
                clicks=50,
                cost=600.0,
                conversions=5.0,  # $120 CPA
            ),
        ]

        result = analyzer._analyze_performance(ad_groups)

        assert result["count"] > 0
        assert len(result["recommendations"]) > 0

    def test_analyze_bidding_with_target_cpa(self):
        """Test bidding analysis with target CPA."""
        analyzer = AdGroupPerformanceAnalyzer()

        ad_groups = [
            AdGroupPerformance(
                campaign_name="Campaign",
                ad_group_name="Over Target CPA",
                status=AdGroupStatus.ENABLED,
                target_cpa=50.0,
                cost=360.0,
                conversions=6.0,  # $60 CPA vs $50 target
            ),
        ]

        result = analyzer._analyze_bidding(ad_groups)

        assert result["count"] == 1
        assert len(result["recommendations"]) == 1
        assert "Missing Target CPA" in result["recommendations"][0].title

    def test_analyze_quality_score(self):
        """Test quality score analysis."""
        analyzer = AdGroupPerformanceAnalyzer()

        ad_groups = [
            AdGroupPerformance(
                campaign_name="Campaign",
                ad_group_name="Low Quality",
                status=AdGroupStatus.ENABLED,
                quality_score=3.0,
            ),
            AdGroupPerformance(
                campaign_name="Campaign",
                ad_group_name="Low Impression Share",
                status=AdGroupStatus.ENABLED,
                search_impression_share=30.0,
            ),
        ]

        result = analyzer._analyze_quality(ad_groups)

        assert result["count"] >= 1
        assert len(result["recommendations"]) >= 2

    def test_analyze_campaigns_identifies_inconsistency(self):
        """Test campaign-level analysis identifies inconsistent performance."""
        analyzer = AdGroupPerformanceAnalyzer()

        campaign_groups = {
            "Campaign A": [
                AdGroupPerformance(
                    campaign_name="Campaign A",
                    ad_group_name="Good Performer",
                    status=AdGroupStatus.ENABLED,
                    cost=100.0,
                    conversions=10.0,  # $10 CPA
                ),
                AdGroupPerformance(
                    campaign_name="Campaign A",
                    ad_group_name="Poor Performer",
                    status=AdGroupStatus.ENABLED,
                    cost=400.0,
                    conversions=10.0,  # $40 CPA
                ),
            ]
        }

        result = analyzer._analyze_campaigns(campaign_groups)

        assert len(result["recommendations"]) > 0
        assert "Inconsistent Performance" in result["recommendations"][0].title
