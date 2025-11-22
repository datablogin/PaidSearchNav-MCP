"""Integration test for VideoCreativeAnalyzer CSV parsing with real sample data."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.video_creative import VideoCreativeAnalyzer
from paidsearchnav_mcp.models.video_creative import (
    AssetSource,
    AssetStatus,
    AssetType,
    VideoCreativeAnalysisResult,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def sample_csv_path():
    """Get path to sample ad asset CSV file."""
    return Path("test_data/fitness_connection_samples/ad_asset_sample.csv")


class TestVideoCreativeCSVIntegration:
    """Integration tests for VideoCreativeAnalyzer with real CSV data."""

    def test_parse_real_sample_csv(self, sample_csv_path):
        """Test parsing real sample ad asset CSV file."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV not found: {sample_csv_path}")

        analyzer = VideoCreativeAnalyzer.from_csv(sample_csv_path)

        assert analyzer is not None
        assert analyzer._csv_data is not None
        assert len(analyzer._csv_data) > 0

        # Verify the data was parsed correctly
        df = analyzer._csv_data
        assert "Asset" in df.columns
        assert "Asset type" in df.columns
        assert "Impr." in df.columns
        assert "Cost" in df.columns

    @pytest.mark.asyncio
    async def test_analyze_real_sample_data(self, sample_csv_path):
        """Test full analysis with real sample CSV data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV not found: {sample_csv_path}")

        # Load analyzer with CSV data
        analyzer = VideoCreativeAnalyzer.from_csv(sample_csv_path)

        # Run analysis
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify result structure
        assert isinstance(result, VideoCreativeAnalysisResult)
        assert result.customer_id == "fitness_connection_test"
        assert result.analysis_type == "video_creative_performance"

        # Verify assets were parsed
        assert len(result.creative_assets) > 0

        # All assets in sample are Business logos
        logo_assets = [
            a for a in result.creative_assets if a.asset_type == AssetType.BUSINESS_LOGO
        ]
        assert len(logo_assets) == len(result.creative_assets)

        # All assets should be automatically created based on sample
        auto_assets = [
            a for a in result.creative_assets if a.source == AssetSource.AUTOMATIC
        ]
        assert len(auto_assets) == len(result.creative_assets)

        # Verify metrics are calculated
        metrics = result.combined_metrics
        assert metrics.asset_count > 0
        assert metrics.total_impressions > 0
        assert metrics.total_cost > 0
        assert metrics.total_conversions > 0

        # Verify insights are generated
        assert isinstance(result.insights, list)

        # Check for specific insights based on the data
        if metrics.auto_vs_manual_asset_ratio > 0:
            # Should have insight about auto assets if ratio calculated
            auto_insights = [
                i for i in result.insights if i.insight_type == "auto_assets_performing"
            ]
            # May or may not have this insight depending on performance

        # Verify recommendations
        assert isinstance(result.video_creative_recommendations, list)

        # Verify summary
        assert result.summary.total_assets_analyzed > 0
        assert result.summary.analysis_period is not None

        # Verify data quality metrics
        assert result.asset_coverage_percentage > 0
        assert result.data_quality_score > 0

    def test_csv_data_validation(self, sample_csv_path):
        """Test data validation for real CSV file."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV not found: {sample_csv_path}")

        analyzer = VideoCreativeAnalyzer.from_csv(sample_csv_path)
        df = analyzer._csv_data

        # Verify numeric columns are parsed correctly
        for col in ["Impr.", "Clicks", "Cost", "Conversions", "Conv. value"]:
            if col in df.columns:
                # Check that we can convert to numeric without errors
                try:
                    # Values should be strings initially but convertible
                    for val in df[col]:
                        if val and val != "--":
                            # Should be able to parse as number after removing commas
                            cleaned = str(val).replace(",", "").replace("%", "")
                            if cleaned:
                                float(cleaned)
                except (ValueError, TypeError) as e:
                    pytest.fail(f"Failed to validate numeric column {col}: {e}")

    def test_asset_status_parsing(self, sample_csv_path):
        """Test that asset statuses are parsed correctly."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV not found: {sample_csv_path}")

        analyzer = VideoCreativeAnalyzer.from_csv(sample_csv_path)

        # Run analysis to get parsed assets
        result = analyzer.analyze(
            customer_id="test",
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now(),
        )

        # Wait for async result
        import asyncio

        result = asyncio.run(result)

        # Check asset statuses
        for asset in result.creative_assets:
            # In sample data, all are "Eligible" which maps to ENABLED
            assert asset.asset_status in [AssetStatus.ENABLED, AssetStatus.UNKNOWN]

    def test_performance_metrics_calculation(self, sample_csv_path):
        """Test that performance metrics are calculated correctly from CSV data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV not found: {sample_csv_path}")

        analyzer = VideoCreativeAnalyzer.from_csv(sample_csv_path)

        # Run analysis
        import asyncio

        result = asyncio.run(
            analyzer.analyze(
                customer_id="test",
                start_date=datetime(2025, 5, 18),
                end_date=datetime(2025, 8, 15),
            )
        )

        # Verify individual asset metrics
        for asset in result.creative_assets:
            if asset.clicks > 0:
                assert asset.cost_per_click >= 0
            if asset.conversions > 0:
                assert asset.cost_per_conversion >= 0
            if asset.clicks > 0 and asset.conversions > 0:
                assert asset.conversion_rate >= 0

        # Verify combined metrics
        metrics = result.combined_metrics
        if metrics.total_conversions > 0:
            assert metrics.avg_cost_per_conversion > 0
        if metrics.total_cost > 0 and metrics.total_conv_value > 0:
            assert metrics.total_roas > 0

    def test_csv_parsing_with_different_date_formats(self, tmp_path):
        """Test CSV parsing handles various date formats."""
        csv_content = """Ad asset report
"Date range"
Asset status,Asset,Asset type,Level,Status,Status reason,Source,Last updated,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Clicks,Conversions,Conv. value
Enabled,https://example.com/asset1,Business logo,Campaign,Eligible,,Automatically created,"2024-10-15",USD,100.00,"1,000",50,5.00%,2.00,100.00,50,5.00,500.00
Enabled,https://example.com/asset2,Video,Campaign,Eligible,,Automatically created,"Oct 15, 2024",USD,100.00,"1,000",50,5.00%,2.00,100.00,50,5.00,500.00
Enabled,https://example.com/asset3,Image,Campaign,Eligible,,Manually created,"10/15/2024",USD,100.00,"1,000",50,5.00%,2.00,100.00,50,5.00,500.00
"""
        csv_file = tmp_path / "date_formats.csv"
        csv_file.write_text(csv_content)

        analyzer = VideoCreativeAnalyzer.from_csv(csv_file)
        assert len(analyzer._csv_data) == 3

        # Run analysis to ensure dates are handled
        import asyncio

        result = asyncio.run(
            analyzer.analyze(
                customer_id="test",
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
            )
        )

        assert len(result.creative_assets) == 3
