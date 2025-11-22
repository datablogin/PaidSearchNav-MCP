"""Unit tests for VideoCreativeAnalyzer."""

import logging
from datetime import datetime, timedelta

import pandas as pd
import pytest

from paidsearchnav_mcp.analyzers.video_creative import VideoCreativeAnalyzer
from paidsearchnav_mcp.models.video_creative import (
    AssetSource,
    AssetStatus,
    AssetType,
    ChannelLinkedStatus,
    CreativeAsset,
    VideoCreativeAnalysisResult,
    VideoPerformance,
)


@pytest.fixture
def analyzer():
    """Create VideoCreativeAnalyzer instance."""
    return VideoCreativeAnalyzer(
        min_impressions=100,
        min_views=10,
        performance_variance_threshold=0.25,
        cost_variance_threshold=0.30,
    )


@pytest.fixture
def sample_video_data():
    """Create sample video data based on real Fitness Connection data."""
    return pd.DataFrame(
        [
            {
                "Video": "Memorial Day $0/$10 (May 2024) - 0:15",
                "Video URL": "https://www.youtube.com/watch?v=FqNe5s0yHTg",
                "Duration": "0:15",
                "Channel Name": "Fitness Connection",
                "Channel Linked Status": "Not Linked",
                "Number of video enhancements": " --",
                "Impr.": "0",
                "Views": "0",
                "Currency code": "USD",
                "Avg. CPM": "0",
                "Cost": "0.00",
                "Conv. (Platform Comparable)": "0.00",
                "Cost / Conv. (Platform Comparable)": "0",
                "Conv. value / Cost (Platform Comparable)": "0",
            },
            {
                "Video": "Unreal Deal (October 2023) - 0:15  (Shorts)",
                "Video URL": "https://www.youtube.com/watch?v=c9QHjC9upRY",
                "Duration": "0:15",
                "Channel Name": "Fitness Connection",
                "Channel Linked Status": "Not Linked",
                "Number of video enhancements": " --",
                "Impr.": "0",
                "Views": "0",
                "Currency code": "USD",
                "Avg. CPM": "0",
                "Cost": "0.00",
                "Conv. (Platform Comparable)": "0.00",
                "Cost / Conv. (Platform Comparable)": "0",
                "Conv. value / Cost (Platform Comparable)": "0",
            },
            {
                "Video": "TikTok_KeepingGenZFocused($0Down)_07.02.25.mp4",
                "Video URL": "https://www.youtube.com/watch?v=MRKkvTDyzaU",
                "Duration": "0:06",
                "Channel Name": "Fitness Connection",
                "Channel Linked Status": "Not Linked",
                "Number of video enhancements": " --",
                "Impr.": "161,486",
                "Views": "28,741",
                "Currency code": "USD",
                "Avg. CPM": "9.05",
                "Cost": "1461.99",
                "Conv. (Platform Comparable)": "6.00",
                "Cost / Conv. (Platform Comparable)": "243.66",
                "Conv. value / Cost (Platform Comparable)": "0.39",
            },
            {
                "Video": "Level Up Mode - 0:15s - SHORTS",
                "Video URL": "https://www.youtube.com/watch?v=Hc2-2rh8SYA",
                "Duration": "0:15",
                "Channel Name": "Fitness Connection",
                "Channel Linked Status": "Not Linked",
                "Number of video enhancements": " --",
                "Impr.": "50000",
                "Views": "12500",
                "Currency code": "USD",
                "Avg. CPM": "8.50",
                "Cost": "425.00",
                "Conv. (Platform Comparable)": "8.50",
                "Cost / Conv. (Platform Comparable)": "50.00",
                "Conv. value / Cost (Platform Comparable)": "2.35",
            },
            {
                "Video": "FC - October 2022 Unreal Deal - Female Ad",
                "Video URL": "https://www.youtube.com/watch?v=Sw8X85sm7OY",
                "Duration": "0:30",
                "Channel Name": "Fitness Connection",
                "Channel Linked Status": "Linked",
                "Number of video enhancements": "2",
                "Impr.": "75000",
                "Views": "3750",
                "Currency code": "USD",
                "Avg. CPM": "12.00",
                "Cost": "900.00",
                "Conv. (Platform Comparable)": "2.50",
                "Cost / Conv. (Platform Comparable)": "360.00",
                "Conv. value / Cost (Platform Comparable)": "1.10",
            },
        ]
    )


@pytest.fixture
def sample_asset_data():
    """Create sample creative asset data based on real Fitness Connection data."""
    return pd.DataFrame(
        [
            {
                "Asset status": "Enabled",
                "Asset": "https://tpc.googlesyndication.com/simgad/9185350335082425073",
                "Asset type": "Business logo",
                "Level": "Campaign",
                "Status": "Eligible",
                "Status reason": "",
                "Source": "Automatically created",
                "Last updated": "Oct 15, 2024, 11:04 AM",
                "Currency code": "USD",
                "Avg. CPM": "258.35",
                "Impr.": "8,658",
                "Interactions": "408",
                "Interaction rate": "4.71%",
                "Avg. cost": "5.48",
                "Cost": "2236.76",
                "Clicks": "408",
                "Conversions": "14.89",
                "Conv. value": "2,089.46",
            },
            {
                "Asset status": "Enabled",
                "Asset": "https://tpc.googlesyndication.com/simgad/9185350335082425074",
                "Asset type": "Business logo",
                "Level": "Campaign",
                "Status": "Eligible",
                "Status reason": "",
                "Source": "Automatically created",
                "Last updated": "Nov 28, 2024, 12:19 PM",
                "Currency code": "USD",
                "Avg. CPM": "71.85",
                "Impr.": "63,159",
                "Interactions": "10,147",
                "Interaction rate": "16.07%",
                "Avg. cost": "0.45",
                "Cost": "4538.00",
                "Clicks": "10,147",
                "Conversions": "917.18",
                "Conv. value": "142,342.99",
            },
            {
                "Asset status": "Enabled",
                "Asset": "https://tpc.googlesyndication.com/simgad/9185350335082425075",
                "Asset type": "Video",
                "Level": "Campaign",
                "Status": "Eligible",
                "Status reason": "",
                "Source": "Manually created",
                "Last updated": "Mar 12, 2025, 1:08 PM",
                "Currency code": "USD",
                "Avg. CPM": "58.40",
                "Impr.": "76,850",
                "Interactions": "11,357",
                "Interaction rate": "14.78%",
                "Avg. cost": "0.40",
                "Cost": "4487.87",
                "Clicks": "11,357",
                "Conversions": "1,344.92",
                "Conv. value": "195,649.94",
            },
            {
                "Asset status": "Paused",
                "Asset": "https://tpc.googlesyndication.com/simgad/9185350335082425076",
                "Asset type": "Image",
                "Level": "Campaign",
                "Status": "Paused",
                "Status reason": "Low performance",
                "Source": "Manually created",
                "Last updated": "Jan 15, 2025, 9:30 AM",
                "Currency code": "USD",
                "Avg. CPM": "125.50",
                "Impr.": "2,500",
                "Interactions": "50",
                "Interaction rate": "2.00%",
                "Avg. cost": "2.50",
                "Cost": "125.00",
                "Clicks": "50",
                "Conversions": "0.50",
                "Conv. value": "25.00",
            },
        ]
    )


class TestVideoCreativeAnalyzer:
    """Test VideoCreativeAnalyzer functionality."""

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = VideoCreativeAnalyzer(
            min_impressions=200,
            min_views=20,
            performance_variance_threshold=0.30,
            cost_variance_threshold=0.35,
        )

        assert analyzer.min_impressions == 200
        assert analyzer.min_views == 20
        assert analyzer.performance_variance_threshold == 0.30
        assert analyzer.cost_variance_threshold == 0.35

    def test_get_name(self, analyzer):
        """Test get_name method."""
        assert analyzer.get_name() == "Video and Creative Asset Performance Analyzer"

    def test_get_description(self, analyzer):
        """Test get_description method."""
        description = analyzer.get_description()
        assert "video content" in description.lower()
        assert "creative asset" in description.lower()
        assert "fitness industry" in description.lower()

    @pytest.mark.asyncio
    async def test_analyze_with_no_data(self, analyzer):
        """Test analyze method with no data provided."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        result = await analyzer.analyze(
            customer_id="1234567890",
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.customer_id == "1234567890"
        assert len(result.video_performances) == 0
        assert len(result.creative_assets) == 0
        assert result.summary.total_videos_analyzed == 0
        assert result.summary.total_assets_analyzed == 0

    @pytest.mark.asyncio
    async def test_analyze_with_sample_data(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test analyze method with sample data."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        result = await analyzer.analyze(
            customer_id="1234567890",
            start_date=start_date,
            end_date=end_date,
            video_data=sample_video_data,
            asset_data=sample_asset_data,
        )

        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.customer_id == "1234567890"
        assert len(result.video_performances) > 0
        assert len(result.creative_assets) > 0
        assert result.summary.total_videos_analyzed > 0
        assert result.summary.total_assets_analyzed > 0

    @pytest.mark.asyncio
    async def test_analyze_invalid_date_range(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test analyze method with invalid date range."""
        start_date = datetime.now()
        end_date = datetime.now() - timedelta(days=30)

        with pytest.raises(ValueError, match="Start date .* must be before end date"):
            await analyzer.analyze(
                customer_id="1234567890",
                start_date=start_date,
                end_date=end_date,
                video_data=sample_video_data,
                asset_data=sample_asset_data,
            )

    @pytest.mark.asyncio
    async def test_analyze_large_date_range_warning(
        self, analyzer, sample_video_data, sample_asset_data, caplog
    ):
        """Test analyze method with large date range generates warning."""
        start_date = datetime.now() - timedelta(days=400)  # More than 365 days
        end_date = datetime.now()

        with caplog.at_level(logging.WARNING):
            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date=start_date,
                end_date=end_date,
                video_data=sample_video_data,
                asset_data=sample_asset_data,
            )

        # Check that warning was logged
        assert any(
            "exceeds 1 year" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
        # Analysis should still complete successfully
        assert isinstance(result, VideoCreativeAnalysisResult)

    def test_convert_to_video_performances(self, analyzer, sample_video_data):
        """Test conversion of video data to VideoPerformance models."""
        videos = analyzer._convert_to_video_performances(sample_video_data)

        assert len(videos) == 5

        # Test first video (Memorial Day)
        memorial_video = videos[0]
        assert memorial_video.video_title == "Memorial Day $0/$10 (May 2024) - 0:15"
        assert memorial_video.duration == "0:15"
        assert memorial_video.duration_seconds == 15
        assert memorial_video.channel_linked_status == ChannelLinkedStatus.NOT_LINKED
        assert memorial_video.impressions == 0
        assert memorial_video.views == 0

        # Test high-performing video (TikTok)
        tiktok_video = videos[2]
        assert (
            tiktok_video.video_title == "TikTok_KeepingGenZFocused($0Down)_07.02.25.mp4"
        )
        assert tiktok_video.duration == "0:06"
        assert tiktok_video.duration_seconds == 6
        assert tiktok_video.impressions == 161486
        assert tiktok_video.views == 28741
        assert tiktok_video.cost == 1461.99
        assert tiktok_video.conversions == 6.00
        assert tiktok_video.view_rate > 0  # Should be calculated

        # Test Shorts detection
        shorts_videos = [v for v in videos if v.is_shorts]
        assert len(shorts_videos) >= 2  # Should detect Shorts videos

    def test_convert_to_creative_assets(self, analyzer, sample_asset_data):
        """Test conversion of asset data to CreativeAsset models."""
        assets = analyzer._convert_to_creative_assets(sample_asset_data)

        assert len(assets) == 4

        # Test business logo asset
        logo_asset = assets[0]
        assert logo_asset.asset_type == AssetType.BUSINESS_LOGO
        assert logo_asset.asset_status == AssetStatus.ENABLED
        assert logo_asset.source == AssetSource.AUTOMATIC
        assert logo_asset.impressions == 8658
        assert logo_asset.interactions == 408
        assert logo_asset.clicks == 408
        assert logo_asset.conversions == 14.89

        # Test video asset
        video_asset = assets[2]
        assert video_asset.asset_type == AssetType.VIDEO
        assert video_asset.source == AssetSource.MANUAL
        assert video_asset.impressions == 76850
        assert video_asset.conversions == 1344.92

        # Test paused asset
        paused_asset = assets[3]
        assert paused_asset.asset_status == AssetStatus.PAUSED
        assert paused_asset.asset_type == AssetType.IMAGE
        assert paused_asset.source == AssetSource.MANUAL

    def test_parse_numeric(self, analyzer):
        """Test numeric parsing method."""
        # Test various input formats
        assert analyzer._parse_numeric("1,234") == 1234
        assert analyzer._parse_numeric("12.34%") == 12.34
        assert analyzer._parse_numeric("--") == 0
        assert analyzer._parse_numeric("") == 0
        assert analyzer._parse_numeric(None) == 0
        assert analyzer._parse_numeric(123) == 123
        assert analyzer._parse_numeric(12.34) == 12.34
        assert analyzer._parse_numeric("invalid", allow_none=True) is None
        assert analyzer._parse_numeric("invalid", allow_none=False) == 0

    def test_filter_videos_by_thresholds(self, analyzer, sample_video_data):
        """Test filtering videos by minimum thresholds."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        filtered_videos = analyzer._filter_videos_by_thresholds(videos)

        # Should filter out videos with 0 impressions and views
        assert len(filtered_videos) < len(videos)

        # All filtered videos should meet minimum thresholds
        for video in filtered_videos:
            assert (
                video.impressions >= analyzer.min_impressions
                or video.views >= analyzer.min_views
            )

    def test_filter_assets_by_thresholds(self, analyzer, sample_asset_data):
        """Test filtering assets by minimum thresholds."""
        assets = analyzer._convert_to_creative_assets(sample_asset_data)
        filtered_assets = analyzer._filter_assets_by_thresholds(assets)

        # All filtered assets should meet minimum impression threshold
        for asset in filtered_assets:
            assert asset.impressions >= analyzer.min_impressions

    def test_calculate_combined_metrics(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test calculation of combined metrics."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        assets = analyzer._convert_to_creative_assets(sample_asset_data)

        filtered_videos = analyzer._filter_videos_by_thresholds(videos)
        filtered_assets = analyzer._filter_assets_by_thresholds(assets)

        metrics = analyzer._calculate_combined_metrics(filtered_videos, filtered_assets)

        assert metrics.video_count == len(filtered_videos)
        assert metrics.asset_count == len(filtered_assets)
        assert metrics.total_impressions > 0
        assert metrics.total_views > 0
        assert metrics.total_cost > 0
        assert metrics.total_conversions > 0
        assert metrics.avg_view_rate >= 0
        assert metrics.total_roas >= 0

    def test_calculate_shorts_performance_ratio(self, analyzer, sample_video_data):
        """Test calculation of Shorts vs regular video performance ratio."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        ratio = analyzer._calculate_shorts_performance_ratio(videos)

        # Should return a ratio or 0 if insufficient data
        assert ratio >= 0

    def test_calculate_auto_vs_manual_ratio(self, analyzer, sample_asset_data):
        """Test calculation of auto vs manual asset performance ratio."""
        assets = analyzer._convert_to_creative_assets(sample_asset_data)
        ratio = analyzer._calculate_auto_vs_manual_ratio(assets)

        # Should return a ratio or 0 if insufficient data
        assert ratio >= 0

    def test_find_top_performing_duration_range(self, analyzer, sample_video_data):
        """Test finding the best performing video duration range."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        top_range = analyzer._find_top_performing_duration_range(videos)

        # Should return a duration range or None
        if top_range:
            assert top_range in ["0-15s", "16-30s", "31-60s", "60s+"]

    def test_generate_video_insights(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test generation of video-specific insights."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        assets = analyzer._convert_to_creative_assets(sample_asset_data)

        filtered_videos = analyzer._filter_videos_by_thresholds(videos)
        filtered_assets = analyzer._filter_assets_by_thresholds(assets)

        metrics = analyzer._calculate_combined_metrics(filtered_videos, filtered_assets)
        insights = analyzer._generate_video_insights(filtered_videos, metrics)

        # Should generate insights based on data patterns
        assert isinstance(insights, list)
        for insight in insights:
            assert hasattr(insight, "insight_type")
            assert hasattr(insight, "category")
            assert hasattr(insight, "title")
            assert hasattr(insight, "confidence_score")

    def test_generate_asset_insights(self, analyzer, sample_asset_data):
        """Test generation of asset-specific insights."""
        assets = analyzer._convert_to_creative_assets(sample_asset_data)
        filtered_assets = analyzer._filter_assets_by_thresholds(assets)

        # Create dummy metrics for testing
        from paidsearchnav.core.models.video_creative import VideoCreativeMetrics

        metrics = VideoCreativeMetrics(
            auto_vs_manual_asset_ratio=1.5,  # Auto assets performing better
            asset_count=len(filtered_assets),
        )

        insights = analyzer._generate_asset_insights(filtered_assets, metrics)

        # Should generate insights based on asset performance
        assert isinstance(insights, list)

    def test_generate_optimization_recommendations(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test generation of optimization recommendations."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        assets = analyzer._convert_to_creative_assets(sample_asset_data)

        filtered_videos = analyzer._filter_videos_by_thresholds(videos)
        filtered_assets = analyzer._filter_assets_by_thresholds(assets)

        # Create dummy insights
        insights = []

        recommendations = analyzer._generate_optimization_recommendations(
            filtered_videos, filtered_assets, insights
        )

        # Should generate recommendations
        assert isinstance(recommendations, list)
        for rec in recommendations:
            assert hasattr(rec, "recommendation_type")
            assert hasattr(rec, "priority")
            assert hasattr(rec, "title")
            assert hasattr(rec, "impact_potential")

    def test_calculate_data_quality_score(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test calculation of data quality score."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        assets = analyzer._convert_to_creative_assets(sample_asset_data)

        score = analyzer._calculate_data_quality_score(videos, assets)

        assert 0 <= score <= 100

    def test_calculate_video_coverage(self, analyzer, sample_video_data):
        """Test calculation of video coverage percentage."""
        videos = analyzer._convert_to_video_performances(sample_video_data)
        coverage = analyzer._calculate_video_coverage(videos)

        assert 0 <= coverage <= 100

    def test_calculate_asset_coverage(self, analyzer, sample_asset_data):
        """Test calculation of asset coverage percentage."""
        assets = analyzer._convert_to_creative_assets(sample_asset_data)
        coverage = analyzer._calculate_asset_coverage(assets)

        assert 0 <= coverage <= 100

    def test_calculate_budget_reallocation_potential(self, analyzer):
        """Test calculation of budget reallocation potential."""
        from paidsearchnav.core.models.video_creative import CreativeRecommendation

        recommendations = [
            CreativeRecommendation(
                recommendation_type="budget_reallocation",
                priority="high",
                title="Test Recommendation",
                description="Test description",
                impact_potential=25.0,
                current_performance=10.0,
                target_performance=15.0,
                affected_assets=[],
                action_items=[],
            ),
            CreativeRecommendation(
                recommendation_type="video_performance_optimization",
                priority="medium",
                title="Test Recommendation 2",
                description="Test description 2",
                impact_potential=15.0,
                current_performance=5.0,
                target_performance=8.0,
                affected_assets=[],
                action_items=[],
            ),
        ]

        potential = analyzer._calculate_budget_reallocation_potential(recommendations)

        assert 0 <= potential <= 50.0  # Capped at 50%
        assert potential == 40.0  # 25 + 15

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(
        self, analyzer, sample_video_data, sample_asset_data
    ):
        """Test complete analysis workflow with real data patterns."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        result = await analyzer.analyze(
            customer_id="1234567890",
            start_date=start_date,
            end_date=end_date,
            video_data=sample_video_data,
            asset_data=sample_asset_data,
        )

        # Validate result structure
        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.analyzer_name == "Video and Creative Asset Performance Analyzer"
        assert result.customer_id == "1234567890"

        # Validate data processing
        assert len(result.video_performances) >= 0
        assert len(result.creative_assets) >= 0

        # Validate metrics calculation
        assert isinstance(result.combined_metrics.video_count, int)
        assert isinstance(result.combined_metrics.asset_count, int)
        assert result.combined_metrics.total_impressions >= 0
        assert result.combined_metrics.total_cost >= 0

        # Validate insights and recommendations
        assert isinstance(result.insights, list)
        assert isinstance(result.video_creative_recommendations, list)

        # Validate summary
        assert result.summary.analysis_period is not None
        assert result.summary.total_videos_analyzed >= 0
        assert result.summary.total_assets_analyzed >= 0
        assert 0 <= result.summary.overall_performance_score <= 100

        # Validate data quality metrics
        assert 0 <= result.video_coverage_percentage <= 100
        assert 0 <= result.asset_coverage_percentage <= 100
        assert 0 <= result.data_quality_score <= 100

        # Validate business KPIs
        assert isinstance(result.performance_variance_detected, bool)
        assert result.optimization_opportunities_count >= 0
        assert 0 <= result.estimated_budget_reallocation_potential <= 50.0

    def test_video_performance_model_calculations(self):
        """Test VideoPerformance model calculations."""
        video = VideoPerformance(
            video_title="Test Video - SHORTS",
            duration="0:15",
            impressions=10000,
            views=2000,
            cost=500.0,
            conversions=50.0,
        )

        # Test derived metrics
        assert video.view_rate == 20.0  # (2000/10000) * 100
        assert video.cost_per_view == 0.25  # 500/2000
        assert video.duration_seconds == 15
        assert video.is_shorts is True  # Should detect "SHORTS" in title

    def test_creative_asset_model_calculations(self):
        """Test CreativeAsset model calculations."""
        asset = CreativeAsset(
            asset_url="https://example.com/asset",
            asset_type=AssetType.BUSINESS_LOGO,
            impressions=5000,
            clicks=500,
            cost=250.0,
            conversions=25.0,
            conv_value=1000.0,
        )

        # Test derived metrics
        assert asset.cost_per_click == 0.5  # 250/500
        assert asset.cost_per_conversion == 10.0  # 250/25
        assert asset.conversion_rate == 5.0  # (25/500) * 100
        assert asset.roas == 4.0  # 1000/250


class TestVideoCreativeAnalyzerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def analyzer(self):
        return VideoCreativeAnalyzer()

    def test_empty_dataframes(self, analyzer):
        """Test handling of empty DataFrames."""
        empty_video_df = pd.DataFrame()
        empty_asset_df = pd.DataFrame()

        videos = analyzer._convert_to_video_performances(empty_video_df)
        assets = analyzer._convert_to_creative_assets(empty_asset_df)

        assert len(videos) == 0
        assert len(assets) == 0

    def test_malformed_data(self, analyzer):
        """Test handling of malformed data."""
        malformed_video_df = pd.DataFrame(
            [
                {
                    "Video": None,
                    "Impr.": "invalid",
                    "Views": "not_a_number",
                    "Cost": "",
                    "Duration": "invalid_duration",
                }
            ]
        )

        videos = analyzer._convert_to_video_performances(malformed_video_df)

        # Should handle malformed data gracefully
        assert len(videos) == 1
        video = videos[0]
        assert video.impressions == 0  # Should default to 0 for invalid data
        assert video.views == 0
        assert video.cost == 0.0
        assert video.duration_seconds is None  # Should handle invalid duration

    def test_missing_columns(self, analyzer):
        """Test handling of missing columns in data."""
        incomplete_video_df = pd.DataFrame(
            [
                {
                    "Video": "Test Video",
                    "Impr.": "1000",
                    # Missing other expected columns
                }
            ]
        )

        videos = analyzer._convert_to_video_performances(incomplete_video_df)

        # Should handle missing columns gracefully
        assert len(videos) == 1
        video = videos[0]
        assert video.video_title == "Test Video"
        assert video.impressions == 1000
        assert video.views == 0  # Should default when missing


class TestVideoCreativeAnalyzerCSVParsing:
    """Test CSV parsing functionality for ad asset reports."""

    @pytest.fixture
    def sample_csv_content(self):
        """Sample ad asset CSV content based on real Google Ads format."""
        return """Ad asset report
"May 18, 2025 - August 15, 2025"
Asset status,Asset,Asset type,Level,Status,Status reason,Source,Last updated,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Clicks,Conversions,Conv. value
Enabled,https://tpc.googlesyndication.com/simgad/9185350335082425073,Business logo,Campaign,Eligible,,Automatically created,"Oct 15, 2024, 11:04 AM",USD,258.35,"8,658",408,4.71%,5.48,2236.76,408,14.89,"2,089.46"
Enabled,https://example.com/video.mp4,Video,Campaign,Eligible,,Automatically created,"Aug 8, 2025, 5:13 PM",USD,290.85,"10,000",500,5.00%,2.76,1500.00,500,25.00,"5,000.00"
Enabled,https://example.com/image.jpg,Image,Ad group,Eligible,,Manually created,"Nov 28, 2024, 12:19 PM",USD,71.85,"63,159","10,147",16.07%,0.45,4538.00,"10,147",917.18,"142,342.99"
"""

    @pytest.fixture
    def temp_csv_file(self, tmp_path, sample_csv_content):
        """Create a temporary CSV file for testing."""
        csv_file = tmp_path / "test_ad_assets.csv"
        csv_file.write_text(sample_csv_content)
        return csv_file

    def test_from_csv_successful_parsing(self, temp_csv_file):
        """Test successful CSV file parsing."""
        analyzer = VideoCreativeAnalyzer.from_csv(temp_csv_file)

        assert analyzer is not None
        assert analyzer._csv_data is not None
        assert len(analyzer._csv_data) == 3

        # Verify columns are present
        expected_columns = [
            "Asset",
            "Asset type",
            "Level",
            "Status",
            "Impr.",
            "Cost",
            "Clicks",
        ]
        for col in expected_columns:
            assert col in analyzer._csv_data.columns

    def test_from_csv_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            VideoCreativeAnalyzer.from_csv("nonexistent_file.csv")

    def test_from_csv_file_too_large(self, tmp_path):
        """Test handling of file size limit."""
        large_file = tmp_path / "large_file.csv"
        # Create a file that appears larger than limit
        large_file.write_text("x" * 1024 * 1024)  # 1MB of data

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            VideoCreativeAnalyzer.from_csv(large_file, max_file_size_mb=0.5)

    def test_from_csv_path_traversal_protection(self):
        """Test path traversal protection."""
        with pytest.raises(PermissionError, match="Access denied"):
            VideoCreativeAnalyzer.from_csv("/etc/passwd")

    def test_parse_ad_asset_csv_missing_columns(self, tmp_path):
        """Test handling of CSV with missing required columns."""
        csv_content = """Asset status,Asset
Enabled,https://example.com/asset1.jpg
"""
        csv_file = tmp_path / "incomplete.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="Missing required columns"):
            VideoCreativeAnalyzer.from_csv(csv_file)

    def test_parse_ad_asset_csv_with_header_rows(self, tmp_path):
        """Test parsing CSV with report header rows."""
        csv_content = """Ad asset report
Report date range: 2025-05-18 to 2025-08-15
Some other metadata line
Asset status,Asset,Asset type,Level,Status,Status reason,Source,Last updated,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Clicks,Conversions,Conv. value
Enabled,https://example.com/asset.jpg,Image,Campaign,Eligible,,Manually created,"Oct 15, 2024",USD,100.00,"1,000",50,5.00%,2.00,100.00,50,5.00,500.00
"""
        csv_file = tmp_path / "with_headers.csv"
        csv_file.write_text(csv_content)

        analyzer = VideoCreativeAnalyzer.from_csv(csv_file)
        assert len(analyzer._csv_data) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_csv_data(self, temp_csv_file):
        """Test analysis using CSV data."""
        analyzer = VideoCreativeAnalyzer.from_csv(temp_csv_file)

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        result = await analyzer.analyze(
            customer_id="1234567890", start_date=start_date, end_date=end_date
        )

        # Verify result structure
        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.customer_id == "1234567890"
        assert result.analysis_type == "video_creative_performance"

        # Should have parsed the asset data
        assert len(result.creative_assets) > 0

        # Check asset parsing
        assets = result.creative_assets
        logo_assets = [a for a in assets if a.asset_type == AssetType.BUSINESS_LOGO]
        video_assets = [a for a in assets if a.asset_type == AssetType.VIDEO]
        image_assets = [a for a in assets if a.asset_type == AssetType.IMAGE]

        assert len(logo_assets) == 1
        assert len(video_assets) == 1
        assert len(image_assets) == 1

        # Verify asset sources
        auto_assets = [a for a in assets if a.source == AssetSource.AUTOMATIC]
        manual_assets = [a for a in assets if a.source == AssetSource.MANUAL]

        assert len(auto_assets) == 2
        assert len(manual_assets) == 1

    def test_parse_numeric_values(self):
        """Test numeric value parsing with various formats."""
        analyzer = VideoCreativeAnalyzer()

        # Test various numeric formats
        assert analyzer._parse_numeric("1,234") == 1234
        assert analyzer._parse_numeric("12.34%") == 12.34
        assert analyzer._parse_numeric("$100.50") == 100.50
        assert analyzer._parse_numeric("--") == 0
        assert analyzer._parse_numeric("") == 0
        assert analyzer._parse_numeric(None) == 0
        assert analyzer._parse_numeric("invalid", allow_none=True) is None

    @pytest.mark.asyncio
    async def test_csv_only_mode_no_video_data(self, temp_csv_file):
        """Test analysis with CSV asset data only (no video data)."""
        analyzer = VideoCreativeAnalyzer.from_csv(temp_csv_file)

        result = await analyzer.analyze(
            customer_id="1234567890",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        )

        # Should handle missing video data gracefully
        assert result.video_performances == []
        assert len(result.creative_assets) > 0
        assert result.combined_metrics.video_count == 0
        assert result.combined_metrics.asset_count > 0
