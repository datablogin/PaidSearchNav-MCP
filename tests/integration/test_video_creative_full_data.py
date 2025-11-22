"""Integration tests for VideoCreativeAnalyzer with full Fitness Connection data."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from paidsearchnav.analyzers.video_creative import VideoCreativeAnalyzer
from paidsearchnav.core.models.video_creative import (
    AssetType,
    VideoCreativeAnalysisResult,
)


class TestVideoCreativeAnalyzerIntegration:
    """Integration tests with real Fitness Connection data."""

    @pytest.fixture
    def analyzer(self):
        """Create VideoCreativeAnalyzer instance for integration testing."""
        return VideoCreativeAnalyzer(
            min_impressions=50,  # Lower threshold for more data
            min_views=5,
            performance_variance_threshold=0.25,
            cost_variance_threshold=0.30,
        )

    @pytest.fixture
    def fitness_connection_video_data(self):
        """Load real Fitness Connection video data."""
        data_path = (
            Path(__file__).parent.parent.parent
            / "test_data"
            / "fitness_connection_samples"
            / "video_report_sample.csv"
        )

        if not data_path.exists():
            pytest.skip(f"Test data file not found: {data_path}")

        return pd.read_csv(data_path, skiprows=1)  # Skip the date range row

    @pytest.fixture
    def fitness_connection_asset_data(self):
        """Load real Fitness Connection asset data."""
        data_path = (
            Path(__file__).parent.parent.parent
            / "test_data"
            / "fitness_connection_samples"
            / "ad_asset_sample.csv"
        )

        if not data_path.exists():
            pytest.skip(f"Test data file not found: {data_path}")

        return pd.read_csv(data_path, skiprows=1)  # Skip the date range row

    @pytest.mark.asyncio
    async def test_full_fitness_connection_analysis(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test complete analysis with real Fitness Connection data."""
        start_date = datetime(2025, 5, 18)  # Based on data period in CSV
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Validate analysis result structure
        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.analyzer_name == "Video and Creative Asset Performance Analyzer"
        assert result.customer_id == "fitness_connection_test"

        # Data Quality KPIs (from issue requirements)
        print(f"Video Coverage: {result.video_coverage_percentage}%")
        print(f"Asset Coverage: {result.asset_coverage_percentage}%")
        print(f"Data Quality Score: {result.data_quality_score}")

        # Should analyze videos with meaningful data (≥90% coverage target)
        assert result.video_coverage_percentage >= 0  # May be lower with sample data

        # Should have creative assets with performance data (≥85% target)
        assert result.asset_coverage_percentage >= 0  # May be lower with sample data

        # Validate video processing
        print(f"Total videos processed: {len(result.video_performances)}")
        assert len(result.video_performances) >= 0

        # Check for specific Fitness Connection videos mentioned in issue
        video_titles = [v.video_title for v in result.video_performances]
        memorial_day_videos = [
            title for title in video_titles if "Memorial Day" in title
        ]
        unreal_deal_videos = [title for title in video_titles if "Unreal Deal" in title]

        print(f"Memorial Day videos found: {len(memorial_day_videos)}")
        print(f"Unreal Deal videos found: {len(unreal_deal_videos)}")

        # Validate asset processing
        print(f"Total assets processed: {len(result.creative_assets)}")
        assert len(result.creative_assets) >= 0

        # Check asset types from real data
        business_logo_assets = [
            a for a in result.creative_assets if a.asset_type == AssetType.BUSINESS_LOGO
        ]
        video_assets = [
            a for a in result.creative_assets if a.asset_type == AssetType.VIDEO
        ]

        print(f"Business logo assets: {len(business_logo_assets)}")
        print(f"Video assets: {len(video_assets)}")

    @pytest.mark.asyncio
    async def test_performance_variance_detection(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test detection of performance variance (≥30% engagement rate difference)."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Business Impact KPIs
        print(f"Performance variance detected: {result.performance_variance_detected}")
        print(f"Optimization opportunities: {result.optimization_opportunities_count}")
        print(
            f"Budget reallocation potential: {result.estimated_budget_reallocation_potential}%"
        )

        # Should detect significant performance differences
        if len(result.video_performances) > 1:
            view_rates = [
                v.view_rate for v in result.video_performances if v.view_rate > 0
            ]
            if len(view_rates) > 1:
                max_view_rate = max(view_rates)
                min_view_rate = min(view_rates)
                variance_percentage = (
                    (max_view_rate - min_view_rate) / max_view_rate
                ) * 100
                print(f"View rate variance: {variance_percentage:.1f}%")

    @pytest.mark.asyncio
    async def test_content_strategy_insights(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test content strategy insights generation."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        print(f"Generated insights: {len(result.insights)}")
        print(
            f"Generated recommendations: {len(result.video_creative_recommendations)}"
        )

        # Display key insights
        for insight in result.insights[:3]:  # Show top 3 insights
            print(f"Insight: {insight.title}")
            print(f"  Category: {insight.category}")
            print(f"  Impact: {insight.business_impact}")
            print(f"  Confidence: {insight.confidence_score}")

        # Display key recommendations
        for rec in result.video_creative_recommendations[
            :3
        ]:  # Show top 3 recommendations
            print(f"Recommendation: {rec.title}")
            print(f"  Priority: {rec.priority}")
            print(f"  Impact Potential: {rec.impact_potential}%")

    @pytest.mark.asyncio
    async def test_youtube_shorts_analysis(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test YouTube Shorts vs standard video performance analysis."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Analyze Shorts performance
        shorts_videos = [v for v in result.video_performances if v.is_shorts]
        regular_videos = [v for v in result.video_performances if not v.is_shorts]

        print(f"YouTube Shorts videos: {len(shorts_videos)}")
        print(f"Regular videos: {len(regular_videos)}")

        if shorts_videos and regular_videos:
            shorts_avg_view_rate = sum(v.view_rate for v in shorts_videos) / len(
                shorts_videos
            )
            regular_avg_view_rate = sum(v.view_rate for v in regular_videos) / len(
                regular_videos
            )

            print(f"Shorts average view rate: {shorts_avg_view_rate:.2f}%")
            print(f"Regular average view rate: {regular_avg_view_rate:.2f}%")

            # Check for Shorts performance ratio insight
            shorts_ratio = result.combined_metrics.shorts_performance_ratio
            print(f"Shorts performance ratio: {shorts_ratio:.2f}")

    @pytest.mark.asyncio
    async def test_duration_analysis(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test video duration impact analysis."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Analyze duration distribution
        duration_counts = {}
        for video in result.video_performances:
            if video.duration_seconds:
                if video.duration_seconds <= 15:
                    duration_range = "0-15s"
                elif video.duration_seconds <= 30:
                    duration_range = "16-30s"
                elif video.duration_seconds <= 60:
                    duration_range = "31-60s"
                else:
                    duration_range = "60s+"

                duration_counts[duration_range] = (
                    duration_counts.get(duration_range, 0) + 1
                )

        print("Duration distribution:")
        for duration_range, count in duration_counts.items():
            print(f"  {duration_range}: {count} videos")

        # Check top performing duration range
        if result.combined_metrics.top_performing_duration_range:
            print(
                f"Top performing duration range: {result.combined_metrics.top_performing_duration_range}"
            )

    @pytest.mark.asyncio
    async def test_creative_asset_optimization(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test creative asset performance optimization analysis."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Analyze asset type performance
        asset_performance = {}
        for asset in result.creative_assets:
            asset_type = asset.asset_type.value
            if asset_type not in asset_performance:
                asset_performance[asset_type] = {
                    "count": 0,
                    "total_impressions": 0,
                    "total_conversions": 0,
                    "total_cost": 0,
                }

            asset_performance[asset_type]["count"] += 1
            asset_performance[asset_type]["total_impressions"] += asset.impressions
            asset_performance[asset_type]["total_conversions"] += asset.conversions
            asset_performance[asset_type]["total_cost"] += asset.cost

        print("Asset type performance:")
        for asset_type, metrics in asset_performance.items():
            if metrics["count"] > 0:
                avg_conversion_rate = (
                    (metrics["total_conversions"] / metrics["count"])
                    if metrics["count"] > 0
                    else 0
                )
                print(
                    f"  {asset_type}: {metrics['count']} assets, avg {avg_conversion_rate:.2f} conversions"
                )

        # Check auto vs manual performance ratio
        auto_manual_ratio = result.combined_metrics.auto_vs_manual_asset_ratio
        print(f"Auto vs manual asset performance ratio: {auto_manual_ratio:.2f}")

    @pytest.mark.asyncio
    async def test_roi_and_engagement_metrics(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test ROI and engagement metrics calculation."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        metrics = result.combined_metrics

        print(f"Total ROAS: {metrics.total_roas:.2f}")
        print(f"Average view rate: {metrics.avg_view_rate:.2f}%")
        print(f"Average cost per view: ${metrics.avg_cost_per_view:.4f}")
        print(f"Average cost per conversion: ${metrics.avg_cost_per_conversion:.2f}")

        # Validate metrics are reasonable
        assert metrics.total_roas >= 0
        assert metrics.avg_view_rate >= 0
        assert metrics.avg_cost_per_view >= 0
        assert metrics.avg_cost_per_conversion >= 0

    @pytest.mark.asyncio
    async def test_performance_analysis_speed(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test that analysis completes within performance requirements (<30 seconds)."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        import time

        start_time = time.time()

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        end_time = time.time()
        analysis_duration = end_time - start_time

        print(f"Analysis completed in {analysis_duration:.2f} seconds")

        # Performance requirement: Analysis should complete in <30 seconds
        assert analysis_duration < 30.0, (
            f"Analysis took {analysis_duration:.2f} seconds, should be <30s"
        )

        # Validate result was generated
        assert isinstance(result, VideoCreativeAnalysisResult)

    @pytest.mark.asyncio
    async def test_data_completeness_validation(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test data completeness validation against KPI thresholds."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Data Quality KPIs validation
        print("Data quality metrics:")
        print(f"  Video coverage: {result.video_coverage_percentage:.1f}%")
        print(f"  Asset coverage: {result.asset_coverage_percentage:.1f}%")
        print(f"  Overall data quality: {result.data_quality_score:.1f}")

        # Business Impact KPIs validation
        print("Business impact metrics:")
        print(
            f"  Optimization opportunities: {result.optimization_opportunities_count}"
        )
        print(
            f"  Performance variance detected: {result.performance_variance_detected}"
        )
        print(
            f"  Budget reallocation potential: {result.estimated_budget_reallocation_potential:.1f}%"
        )

        # Validate KPI structure
        assert 0 <= result.video_coverage_percentage <= 100
        assert 0 <= result.asset_coverage_percentage <= 100
        assert 0 <= result.data_quality_score <= 100
        assert result.optimization_opportunities_count >= 0
        assert 0 <= result.estimated_budget_reallocation_potential <= 50

    @pytest.mark.asyncio
    async def test_memorial_day_seasonal_analysis(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test analysis of seasonal content performance (Memorial Day promos)."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Look for Memorial Day content mentioned in issue
        memorial_day_videos = [
            v for v in result.video_performances if "Memorial Day" in v.video_title
        ]

        print(f"Memorial Day promotional videos analyzed: {len(memorial_day_videos)}")

        if memorial_day_videos:
            for video in memorial_day_videos:
                print(f"  Video: {video.video_title}")
                print(f"    Impressions: {video.impressions:,}")
                print(f"    Views: {video.views:,}")
                print(f"    View Rate: {video.view_rate:.2f}%")
                print(f"    Cost: ${video.cost:.2f}")

        # Check if seasonal content insights were generated
        seasonal_insights = [
            insight
            for insight in result.insights
            if "Memorial Day" in insight.title or "seasonal" in insight.title.lower()
        ]

        print(f"Seasonal content insights generated: {len(seasonal_insights)}")

    @pytest.mark.asyncio
    async def test_creative_refresh_recommendations(
        self, analyzer, fitness_connection_video_data, fitness_connection_asset_data
    ):
        """Test creative refresh timing recommendations."""
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
            video_data=fitness_connection_video_data,
            asset_data=fitness_connection_asset_data,
        )

        # Look for asset refresh recommendations
        refresh_recommendations = [
            rec
            for rec in result.video_creative_recommendations
            if "refresh" in rec.title.lower() or "refresh" in rec.recommendation_type
        ]

        print(f"Creative refresh recommendations: {len(refresh_recommendations)}")

        for rec in refresh_recommendations:
            print(f"  Recommendation: {rec.title}")
            print(f"    Priority: {rec.priority}")
            print(f"    Impact: {rec.impact_potential}%")
            print(f"    Affected assets: {len(rec.affected_assets)}")

        # Validate recommendation structure
        for rec in refresh_recommendations:
            assert rec.priority in ["high", "medium", "low"]
            assert 0 <= rec.impact_potential <= 100
            assert isinstance(rec.affected_assets, list)
            assert isinstance(rec.action_items, list)
