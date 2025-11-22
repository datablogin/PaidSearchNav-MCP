"""Video and Creative Asset Performance Analyzer for fitness industry marketing campaigns."""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.video_creative import (
    AssetSource,
    AssetStatus,
    AssetType,
    ChannelLinkedStatus,
    CreativeAsset,
    CreativeRecommendation,
    VideoCreativeAnalysisResult,
    VideoCreativeAnalysisSummary,
    VideoCreativeInsight,
    VideoCreativeMetrics,
    VideoPerformance,
)

logger = logging.getLogger(__name__)


class VideoCreativeAnalyzer(Analyzer):
    """Analyzes video content and creative asset performance for optimization opportunities."""

    # Business logic thresholds
    HIGH_PERFORMER_THRESHOLD = 80.0
    MODERATE_PERFORMER_THRESHOLD = 60.0
    LOW_PERFORMER_THRESHOLD = 40.0

    # Data quality thresholds
    MIN_IMPRESSIONS_THRESHOLD = 100
    MIN_VIEWS_THRESHOLD = 10
    MIN_COVERAGE_PERCENTAGE = 80.0
    MIN_COMPLETENESS_SCORE = 90.0

    # Performance variance thresholds
    SIGNIFICANT_VIEW_RATE_VARIANCE = 25.0  # 25% difference
    SIGNIFICANT_COST_VARIANCE = 30.0  # 30% difference
    MIN_ACTIONABLE_RECOMMENDATIONS = 3
    MIN_ROI_IMPACT_POTENTIAL = 15.0  # 15% budget reallocation potential

    def __init__(
        self,
        min_impressions: int = 100,
        min_views: int = 10,
        performance_variance_threshold: float = 0.25,
        cost_variance_threshold: float = 0.30,
    ):
        """Initialize the video creative analyzer.

        Args:
            min_impressions: Minimum impressions required for analysis
            min_views: Minimum views required for analysis
            performance_variance_threshold: Threshold for significant performance variance
            cost_variance_threshold: Threshold for significant cost variance
        """
        self.min_impressions = min_impressions
        self.min_views = min_views
        self.performance_variance_threshold = performance_variance_threshold
        self.cost_variance_threshold = cost_variance_threshold
        self._csv_data: Optional[pd.DataFrame] = None

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "VideoCreativeAnalyzer":
        """Create a VideoCreativeAnalyzer instance from an ad asset CSV file.

        Parses Google Ads Ad Asset CSV report and prepares data for analysis.

        Args:
            file_path: Path to the ad asset CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            VideoCreativeAnalyzer instance with loaded data

        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid or file too large
            PermissionError: If the file path attempts directory traversal
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Resolve to absolute path for security
        file_path = file_path.resolve()

        # Path traversal protection (cross-platform)
        cwd = Path.cwd()
        temp_dir = Path(tempfile.gettempdir())  # Cross-platform temp directory
        var_folders = (
            Path("/var/folders") if Path("/var/folders").exists() else temp_dir
        )

        if not (
            file_path.is_relative_to(cwd)
            or file_path.is_relative_to(temp_dir)
            or file_path.is_relative_to(var_folders)
        ):
            raise PermissionError(f"Access denied: {file_path}")

        # Check file exists
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_file_size_mb}MB)"
            )

        # Create analyzer instance
        analyzer = cls()

        # Parse CSV and store the data
        analyzer._csv_data = analyzer._parse_ad_asset_csv(file_path)

        return analyzer

    def _parse_ad_asset_csv(self, file_path: Path) -> pd.DataFrame:
        """Parse ad asset CSV file from Google Ads.

        Args:
            file_path: Path to CSV file

        Returns:
            DataFrame with parsed ad asset data

        Raises:
            ValueError: If CSV format is invalid
        """
        try:
            # Read CSV file
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Find the header row (skip report title and date range)
            header_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("Asset status") or (
                    "Asset" in line and "Asset type" in line
                ):
                    header_idx = i
                    break

            # Read CSV starting from header row
            df = pd.read_csv(
                file_path, skiprows=header_idx, thousands=",", on_bad_lines="skip"
            )

            # Validate required columns
            required_columns = [
                "Asset",
                "Asset type",
                "Level",
                "Status",
                "Impr.",
                "Cost",
                "Clicks",
            ]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")

            logger.info(f"Successfully parsed {len(df)} ad assets from CSV")
            return df

        except Exception as e:
            logger.error(f"Error parsing ad asset CSV: {e}")
            raise ValueError(f"Failed to parse ad asset CSV: {e}")

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> VideoCreativeAnalysisResult:
        """Analyze video and creative asset performance for a customer.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (video_data, asset_data)

        Returns:
            Video and creative asset performance analysis result
        """
        logger.info(f"Starting video creative analysis for customer {customer_id}")

        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )

        # Check for large date ranges that may affect analysis reliability
        date_range_days = (end_date - start_date).days
        if date_range_days > 365:
            logger.warning(
                f"Analysis period ({date_range_days} days) exceeds 1 year - "
                "results may be less reliable due to seasonal variations and data drift"
            )

        try:
            # Extract video and asset data from kwargs or load from files
            video_data = kwargs.get("video_data")
            asset_data = kwargs.get("asset_data")

            # Use CSV data if available
            if self._csv_data is not None:
                logger.info(f"Using CSV data with {len(self._csv_data)} assets")
                asset_data = self._csv_data
                # For CSV-only mode, video_data might be None
                if video_data is None:
                    video_data = pd.DataFrame()  # Empty dataframe for videos
            elif video_data is None and asset_data is None:
                logger.warning("No data provided for analysis")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Convert raw data to structured models
            video_performances = self._convert_to_video_performances(video_data)
            creative_assets = self._convert_to_creative_assets(asset_data)

            # Filter by minimum thresholds
            filtered_videos = self._filter_videos_by_thresholds(video_performances)
            filtered_assets = self._filter_assets_by_thresholds(creative_assets)

            # Calculate combined metrics
            combined_metrics = self._calculate_combined_metrics(
                filtered_videos, filtered_assets
            )

            # Generate insights
            insights = self._generate_video_creative_insights(
                filtered_videos, filtered_assets, combined_metrics
            )

            # Generate recommendations
            recommendations = self._generate_optimization_recommendations(
                filtered_videos, filtered_assets, insights
            )

            # Generate analysis summary
            summary = self._generate_analysis_summary(
                customer_id,
                filtered_videos,
                filtered_assets,
                insights,
                recommendations,
                start_date,
                end_date,
            )

            # Calculate data quality metrics
            video_coverage = self._calculate_video_coverage(video_performances)
            asset_coverage = self._calculate_asset_coverage(creative_assets)
            data_quality_score = self._calculate_data_quality_score(
                video_performances, creative_assets
            )

            # Create analysis result
            result = VideoCreativeAnalysisResult(
                analyzer_name=self.get_name(),
                customer_id=customer_id,
                analysis_type="video_creative_performance",
                start_date=start_date,
                end_date=end_date,
                video_performances=filtered_videos,
                creative_assets=filtered_assets,
                combined_metrics=combined_metrics,
                insights=insights,
                video_creative_recommendations=recommendations,
                summary=summary,
                video_coverage_percentage=video_coverage,
                asset_coverage_percentage=asset_coverage,
                data_quality_score=data_quality_score,
                performance_variance_detected=len(insights) > 0,
                optimization_opportunities_count=len(recommendations),
                estimated_budget_reallocation_potential=self._calculate_budget_reallocation_potential(
                    recommendations
                ),
            )

            logger.info(
                f"Video creative analysis completed for customer {customer_id}: "
                f"{len(filtered_videos)} videos, {len(filtered_assets)} assets analyzed"
            )

            return result

        except Exception as e:
            logger.error(f"Error during video creative analysis: {str(e)}")
            raise

    def _convert_to_video_performances(
        self, video_data: pd.DataFrame
    ) -> List[VideoPerformance]:
        """Convert video CSV data to VideoPerformance models."""
        video_performances = []

        # Handle empty dataframe
        if video_data.empty:
            return video_performances

        for _, row in video_data.iterrows():
            try:
                # Parse numeric values, handling missing data
                impressions = self._parse_numeric(row.get("Impr.", 0))
                views = self._parse_numeric(row.get("Views", 0))
                cost = self._parse_numeric(row.get("Cost", 0.0))
                conversions = self._parse_numeric(
                    row.get("Conv. (Platform Comparable)", 0.0)
                )
                cost_per_conv = self._parse_numeric(
                    row.get("Cost / Conv. (Platform Comparable)", 0.0)
                )
                conv_value_cost = self._parse_numeric(
                    row.get("Conv. value / Cost (Platform Comparable)", 0.0)
                )
                avg_cpm = self._parse_numeric(row.get("Avg. CPM", 0.0))
                enhancements = self._parse_numeric(
                    row.get("Number of video enhancements"), allow_none=True
                )

                # Determine channel linked status
                channel_status = ChannelLinkedStatus.UNKNOWN
                if pd.notna(row.get("Channel Linked Status")):
                    status_str = str(row["Channel Linked Status"]).strip()
                    if status_str == "Linked":
                        channel_status = ChannelLinkedStatus.LINKED
                    elif status_str == "Not Linked":
                        channel_status = ChannelLinkedStatus.NOT_LINKED

                video_performance = VideoPerformance(
                    video_title=str(row.get("Video", "")),
                    video_url=str(row.get("Video URL", ""))
                    if pd.notna(row.get("Video URL"))
                    else None,
                    duration=str(row.get("Duration", ""))
                    if pd.notna(row.get("Duration"))
                    else None,
                    channel_name=str(row.get("Channel Name", ""))
                    if pd.notna(row.get("Channel Name"))
                    else None,
                    channel_linked_status=channel_status,
                    video_enhancements=enhancements,
                    impressions=impressions,
                    views=views,
                    currency_code=str(row.get("Currency code", "USD")),
                    avg_cpm=avg_cpm,
                    cost=cost,
                    conversions=conversions,
                    cost_per_conversion=cost_per_conv,
                    conv_value_cost_ratio=conv_value_cost,
                )

                video_performances.append(video_performance)

            except Exception as e:
                logger.warning(f"Error processing video row: {e}")
                continue

        return video_performances

    def _convert_to_creative_assets(
        self, asset_data: pd.DataFrame
    ) -> List[CreativeAsset]:
        """Convert asset CSV data to CreativeAsset models."""
        creative_assets = []

        # Handle empty dataframe
        if asset_data.empty:
            return creative_assets

        for _, row in asset_data.iterrows():
            try:
                # Parse numeric values
                impressions = self._parse_numeric(row.get("Impr.", 0))
                interactions = self._parse_numeric(row.get("Interactions", 0))
                interaction_rate = self._parse_numeric(row.get("Interaction rate", 0.0))
                avg_cost = self._parse_numeric(row.get("Avg. cost", 0.0))
                cost = self._parse_numeric(row.get("Cost", 0.0))
                clicks = self._parse_numeric(row.get("Clicks", 0))
                conversions = self._parse_numeric(row.get("Conversions", 0.0))
                conv_value = self._parse_numeric(row.get("Conv. value", 0.0))
                avg_cpm = self._parse_numeric(row.get("Avg. CPM", 0.0))

                # Determine asset type
                asset_type = AssetType.UNKNOWN
                if pd.notna(row.get("Asset type")):
                    type_str = str(row["Asset type"]).strip()
                    if type_str == "Business logo":
                        asset_type = AssetType.BUSINESS_LOGO
                    elif type_str == "Video":
                        asset_type = AssetType.VIDEO
                    elif type_str == "Image":
                        asset_type = AssetType.IMAGE

                # Determine asset status (check both possible column names)
                asset_status = AssetStatus.UNKNOWN
                status_col = row.get("Asset status") or row.get("Status")
                if pd.notna(status_col):
                    status_str = str(status_col).strip()
                    if status_str in ["Enabled", "Eligible"]:
                        asset_status = AssetStatus.ENABLED
                    elif status_str == "Paused":
                        asset_status = AssetStatus.PAUSED
                    elif status_str == "Removed":
                        asset_status = AssetStatus.REMOVED

                # Determine asset source
                asset_source = AssetSource.UNKNOWN
                if pd.notna(row.get("Source")):
                    source_str = str(row["Source"]).strip()
                    if "Automatically created" in source_str:
                        asset_source = AssetSource.AUTOMATIC
                    elif "Manually created" in source_str:
                        asset_source = AssetSource.MANUAL

                # Parse last updated date
                last_updated = None
                if pd.notna(row.get("Last updated")):
                    try:
                        last_updated = pd.to_datetime(row["Last updated"])
                    except Exception:
                        last_updated = None

                creative_asset = CreativeAsset(
                    asset_url=str(row.get("Asset", "")),
                    asset_type=asset_type,
                    asset_status=asset_status,
                    level=str(row.get("Level", "")),
                    status_reason=str(row.get("Status reason", ""))
                    if pd.notna(row.get("Status reason"))
                    else None,
                    source=asset_source,
                    last_updated=last_updated,
                    currency_code=str(row.get("Currency code", "USD")),
                    avg_cpm=avg_cpm,
                    impressions=impressions,
                    interactions=interactions,
                    interaction_rate=interaction_rate,
                    avg_cost=avg_cost,
                    cost=cost,
                    clicks=clicks,
                    conversions=conversions,
                    conv_value=conv_value,
                )

                # Check for stale asset data that may need refreshing
                if (
                    last_updated
                    and (datetime.now() - last_updated).days > 180
                    and impressions
                    > 1000  # Only warn for assets with significant traffic
                ):
                    logger.info(
                        f"Asset {creative_asset.asset_url[:50]}... is potentially stale "
                        f"(last updated {(datetime.now() - last_updated).days} days ago)"
                    )

                creative_assets.append(creative_asset)

            except Exception as e:
                logger.warning(f"Error processing asset row: {e}")
                continue

        return creative_assets

    def _parse_numeric(self, value: Any, allow_none: bool = False) -> Any:
        """Parse numeric value from potentially problematic data."""
        if pd.isna(value) or value == "" or value == "--":
            return None if allow_none else 0

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):
            # Remove common formatting (including currency symbols)
            cleaned = value.replace(",", "").replace("%", "").replace("$", "").strip()
            try:
                if "." in cleaned:
                    return float(cleaned)
                else:
                    return int(cleaned)
            except ValueError:
                return None if allow_none else 0

        return None if allow_none else 0

    def _filter_videos_by_thresholds(
        self, videos: List[VideoPerformance]
    ) -> List[VideoPerformance]:
        """Filter videos by minimum thresholds."""
        return [
            video
            for video in videos
            if video.impressions >= self.min_impressions
            or video.views >= self.min_views
        ]

    def _filter_assets_by_thresholds(
        self, assets: List[CreativeAsset]
    ) -> List[CreativeAsset]:
        """Filter assets by minimum thresholds."""
        return [asset for asset in assets if asset.impressions >= self.min_impressions]

    def _calculate_combined_metrics(
        self, videos: List[VideoPerformance], assets: List[CreativeAsset]
    ) -> VideoCreativeMetrics:
        """Calculate combined metrics from videos and assets."""
        total_video_impressions = sum(v.impressions for v in videos)
        total_video_views = sum(v.views for v in videos)
        total_video_cost = sum(v.cost for v in videos)
        total_video_conversions = sum(v.conversions for v in videos)

        total_asset_impressions = sum(a.impressions for a in assets)
        total_asset_cost = sum(a.cost for a in assets)
        total_asset_conversions = sum(a.conversions for a in assets)
        total_asset_conv_value = sum(a.conv_value for a in assets)

        # Calculate aggregated metrics
        avg_view_rate = 0.0
        if total_video_impressions > 0:
            avg_view_rate = (total_video_views / total_video_impressions) * 100

        avg_cost_per_view = 0.0
        if total_video_views > 0:
            avg_cost_per_view = total_video_cost / total_video_views

        total_conversions = total_video_conversions + total_asset_conversions
        total_cost = total_video_cost + total_asset_cost

        avg_cost_per_conversion = 0.0
        if total_conversions > 0:
            avg_cost_per_conversion = total_cost / total_conversions

        total_roas = 0.0
        if total_cost > 0:
            total_roas = total_asset_conv_value / total_cost

        # Calculate performance ratios
        shorts_performance_ratio = self._calculate_shorts_performance_ratio(videos)
        auto_vs_manual_ratio = self._calculate_auto_vs_manual_ratio(assets)
        top_duration_range = self._find_top_performing_duration_range(videos)

        return VideoCreativeMetrics(
            video_count=len(videos),
            asset_count=len(assets),
            total_impressions=total_video_impressions + total_asset_impressions,
            total_views=total_video_views,
            total_cost=total_cost,
            total_conversions=total_conversions,
            total_conv_value=total_asset_conv_value,
            avg_view_rate=avg_view_rate,
            avg_cost_per_view=avg_cost_per_view,
            avg_cost_per_conversion=avg_cost_per_conversion,
            total_roas=total_roas,
            shorts_performance_ratio=shorts_performance_ratio,
            auto_vs_manual_asset_ratio=auto_vs_manual_ratio,
            top_performing_duration_range=top_duration_range,
        )

    def _calculate_shorts_performance_ratio(
        self, videos: List[VideoPerformance]
    ) -> float:
        """Calculate performance ratio of Shorts vs regular videos."""
        shorts_videos = [v for v in videos if v.is_shorts]
        regular_videos = [v for v in videos if not v.is_shorts]

        if not shorts_videos or not regular_videos:
            return 0.0

        shorts_avg_view_rate = sum(v.view_rate for v in shorts_videos) / len(
            shorts_videos
        )
        regular_avg_view_rate = sum(v.view_rate for v in regular_videos) / len(
            regular_videos
        )

        if regular_avg_view_rate == 0:
            return 0.0

        return shorts_avg_view_rate / regular_avg_view_rate

    def _calculate_auto_vs_manual_ratio(self, assets: List[CreativeAsset]) -> float:
        """Calculate performance ratio of auto vs manual assets."""
        auto_assets = [a for a in assets if a.source == AssetSource.AUTOMATIC]
        manual_assets = [a for a in assets if a.source == AssetSource.MANUAL]

        if not auto_assets or not manual_assets:
            return 0.0

        auto_avg_conversion_rate = sum(a.conversion_rate for a in auto_assets) / len(
            auto_assets
        )
        manual_avg_conversion_rate = sum(
            a.conversion_rate for a in manual_assets
        ) / len(manual_assets)

        if manual_avg_conversion_rate == 0:
            return 0.0

        return auto_avg_conversion_rate / manual_avg_conversion_rate

    def _find_top_performing_duration_range(
        self, videos: List[VideoPerformance]
    ) -> Optional[str]:
        """Find the best performing video duration range."""
        duration_performance = {}

        for video in videos:
            if video.duration_seconds is None:
                continue

            # Categorize by duration ranges
            if video.duration_seconds <= 15:
                duration_range = "0-15s"
            elif video.duration_seconds <= 30:
                duration_range = "16-30s"
            elif video.duration_seconds <= 60:
                duration_range = "31-60s"
            else:
                duration_range = "60s+"

            if duration_range not in duration_performance:
                duration_performance[duration_range] = []

            duration_performance[duration_range].append(video.view_rate)

        # Find range with highest average view rate
        best_range = None
        best_avg_rate = 0.0

        for duration_range, view_rates in duration_performance.items():
            if view_rates:
                avg_rate = sum(view_rates) / len(view_rates)
                if avg_rate > best_avg_rate:
                    best_avg_rate = avg_rate
                    best_range = duration_range

        return best_range

    def _generate_video_creative_insights(
        self,
        videos: List[VideoPerformance],
        assets: List[CreativeAsset],
        metrics: VideoCreativeMetrics,
    ) -> List[VideoCreativeInsight]:
        """Generate insights from video and creative analysis."""
        insights = []

        # Video performance insights
        insights.extend(self._generate_video_insights(videos, metrics))

        # Asset performance insights
        insights.extend(self._generate_asset_insights(assets, metrics))

        # Combined insights
        insights.extend(self._generate_combined_insights(videos, assets, metrics))

        return insights

    def _generate_video_insights(
        self, videos: List[VideoPerformance], metrics: VideoCreativeMetrics
    ) -> List[VideoCreativeInsight]:
        """Generate video-specific insights."""
        insights = []

        # Shorts vs regular video performance
        if metrics.shorts_performance_ratio > 1.2:
            insights.append(
                VideoCreativeInsight(
                    insight_type="shorts_outperforming",
                    category="performance",
                    title="YouTube Shorts Outperforming Regular Videos",
                    description=f"YouTube Shorts are performing {metrics.shorts_performance_ratio:.1f}x better than regular videos in view rate.",
                    supporting_data={
                        "shorts_ratio": metrics.shorts_performance_ratio,
                        "avg_view_rate": metrics.avg_view_rate,
                    },
                    confidence_score=85.0,
                    business_impact="medium",
                )
            )

        # Duration optimization opportunity
        if metrics.top_performing_duration_range:
            insights.append(
                VideoCreativeInsight(
                    insight_type="duration_optimization",
                    category="optimization",
                    title=f"Optimal Video Duration: {metrics.top_performing_duration_range}",
                    description=f"Videos in the {metrics.top_performing_duration_range} range show the highest view rates.",
                    supporting_data={
                        "top_duration_range": metrics.top_performing_duration_range,
                        "video_count": len(videos),
                    },
                    confidence_score=75.0,
                    business_impact="medium",
                )
            )

        # Low view rate videos
        low_performing_videos = [
            v for v in videos if v.view_rate < 5.0 and v.impressions > 1000
        ]
        if len(low_performing_videos) > 0:
            insights.append(
                VideoCreativeInsight(
                    insight_type="low_view_rate",
                    category="opportunity",
                    title="Low View Rate Videos Identified",
                    description=f"{len(low_performing_videos)} videos have view rates below 5% despite significant impressions.",
                    supporting_data={
                        "low_performing_count": len(low_performing_videos),
                        "threshold_view_rate": 5.0,
                    },
                    confidence_score=90.0,
                    business_impact="high",
                )
            )

        return insights

    def _generate_asset_insights(
        self, assets: List[CreativeAsset], metrics: VideoCreativeMetrics
    ) -> List[VideoCreativeInsight]:
        """Generate asset-specific insights."""
        insights = []

        # Auto vs manual asset performance
        if metrics.auto_vs_manual_asset_ratio > 1.0:
            insights.append(
                VideoCreativeInsight(
                    insight_type="auto_assets_performing",
                    category="optimization",
                    title="Automatically Created Assets Outperforming Manual",
                    description=f"Auto-created assets show {metrics.auto_vs_manual_asset_ratio:.1f}x better conversion rates than manual assets.",
                    supporting_data={
                        "auto_manual_ratio": metrics.auto_vs_manual_asset_ratio,
                        "asset_count": len(assets),
                    },
                    confidence_score=80.0,
                    business_impact="medium",
                )
            )

        # Asset type performance
        business_logo_assets = [
            a for a in assets if a.asset_type == AssetType.BUSINESS_LOGO
        ]
        if business_logo_assets:
            avg_logo_conversion_rate = sum(
                a.conversion_rate for a in business_logo_assets
            ) / len(business_logo_assets)
            if avg_logo_conversion_rate > 10.0:
                insights.append(
                    VideoCreativeInsight(
                        insight_type="logo_high_conversion",
                        category="performance",
                        title="Business Logo Assets Show Strong Performance",
                        description=f"Business logo assets achieve {avg_logo_conversion_rate:.1f}% average conversion rate.",
                        supporting_data={
                            "logo_conversion_rate": avg_logo_conversion_rate,
                            "logo_asset_count": len(business_logo_assets),
                        },
                        confidence_score=85.0,
                        business_impact="medium",
                    )
                )

        return insights

    def _generate_combined_insights(
        self,
        videos: List[VideoPerformance],
        assets: List[CreativeAsset],
        metrics: VideoCreativeMetrics,
    ) -> List[VideoCreativeInsight]:
        """Generate insights from combined video and asset analysis."""
        insights = []

        # Overall ROAS performance
        if metrics.total_roas > 3.0:
            insights.append(
                VideoCreativeInsight(
                    insight_type="strong_roas",
                    category="performance",
                    title="Strong Return on Ad Spend Achieved",
                    description=f"Combined video and asset campaigns achieve {metrics.total_roas:.2f}x ROAS.",
                    supporting_data={
                        "total_roas": metrics.total_roas,
                        "total_cost": metrics.total_cost,
                        "total_conv_value": metrics.total_conv_value,
                    },
                    confidence_score=95.0,
                    business_impact="high",
                )
            )

        return insights

    def _generate_optimization_recommendations(
        self,
        videos: List[VideoPerformance],
        assets: List[CreativeAsset],
        insights: List[VideoCreativeInsight],
    ) -> List[CreativeRecommendation]:
        """Generate optimization recommendations."""
        recommendations = []

        # Video optimization recommendations
        recommendations.extend(self._generate_video_recommendations(videos, insights))

        # Asset optimization recommendations
        recommendations.extend(self._generate_asset_recommendations(assets, insights))

        # Budget optimization recommendations
        recommendations.extend(
            self._generate_budget_recommendations(videos, assets, insights)
        )

        return recommendations

    def _generate_video_recommendations(
        self, videos: List[VideoPerformance], insights: List[VideoCreativeInsight]
    ) -> List[CreativeRecommendation]:
        """Generate video-specific recommendations."""
        recommendations = []

        # Recommend focusing on Shorts if they perform better
        shorts_insight = next(
            (i for i in insights if i.insight_type == "shorts_outperforming"), None
        )
        if shorts_insight:
            recommendations.append(
                CreativeRecommendation(
                    recommendation_type="video_format_optimization",
                    priority="high",
                    title="Increase YouTube Shorts Production",
                    description="Shift creative budget toward YouTube Shorts format due to superior view rates.",
                    impact_potential=25.0,
                    current_performance=shorts_insight.supporting_data.get(
                        "avg_view_rate", 0
                    ),
                    target_performance=shorts_insight.supporting_data.get(
                        "avg_view_rate", 0
                    )
                    * 1.25,
                    affected_assets=[v.video_title for v in videos if v.is_shorts][:5],
                    action_items=[
                        "Create 5-10 new YouTube Shorts in next campaign cycle",
                        "Reallocate 30% of video production budget to Shorts format",
                        "Test vertical video creative adapted for Shorts",
                    ],
                )
            )

        # Recommend pausing low-performing videos
        low_performing_videos = [
            v
            for v in videos
            if v.view_rate < 2.0 and v.impressions > 1000 and v.cost > 100
        ]
        if len(low_performing_videos) >= 3:
            recommendations.append(
                CreativeRecommendation(
                    recommendation_type="video_performance_optimization",
                    priority="medium",
                    title="Pause Underperforming Video Content",
                    description=f"Pause {len(low_performing_videos)} videos with view rates below 2% to reduce wasted spend.",
                    impact_potential=15.0,
                    current_performance=sum(v.cost for v in low_performing_videos),
                    target_performance=0.0,
                    affected_assets=[v.video_title for v in low_performing_videos][:5],
                    action_items=[
                        "Review and pause videos with <2% view rate",
                        "Reallocate budget to top-performing videos",
                        "Analyze creative elements of underperforming content",
                    ],
                )
            )

        return recommendations

    def _generate_asset_recommendations(
        self, assets: List[CreativeAsset], insights: List[VideoCreativeInsight]
    ) -> List[CreativeRecommendation]:
        """Generate asset-specific recommendations."""
        recommendations = []

        # Recommend leveraging auto-created assets if they perform better
        auto_insight = next(
            (i for i in insights if i.insight_type == "auto_assets_performing"), None
        )
        if auto_insight:
            recommendations.append(
                CreativeRecommendation(
                    recommendation_type="asset_source_optimization",
                    priority="medium",
                    title="Leverage Automatically Created Assets",
                    description="Enable more auto-asset creation due to superior conversion performance.",
                    impact_potential=20.0,
                    current_performance=auto_insight.supporting_data.get(
                        "auto_manual_ratio", 1.0
                    ),
                    target_performance=auto_insight.supporting_data.get(
                        "auto_manual_ratio", 1.0
                    )
                    * 1.2,
                    affected_assets=[
                        a.asset_url for a in assets if a.source == AssetSource.AUTOMATIC
                    ][:3],
                    action_items=[
                        "Enable auto-asset generation for all campaigns",
                        "Reduce manual asset creation by 50%",
                        "Monitor auto-asset performance monthly",
                    ],
                )
            )

        # Recommend asset refresh for old assets
        old_assets = [
            a
            for a in assets
            if a.last_updated
            and (datetime.now() - a.last_updated).days > 90
            and a.impressions > 10000
        ]
        if len(old_assets) >= 5:
            recommendations.append(
                CreativeRecommendation(
                    recommendation_type="asset_refresh",
                    priority="low",
                    title="Refresh Aging Creative Assets",
                    description=f"Refresh {len(old_assets)} assets that haven't been updated in 90+ days.",
                    impact_potential=10.0,
                    current_performance=sum(a.conversion_rate for a in old_assets)
                    / len(old_assets)
                    if old_assets
                    else 0,
                    target_performance=(
                        sum(a.conversion_rate for a in old_assets)
                        / len(old_assets)
                        * 1.1
                    )
                    if old_assets
                    else 0,
                    affected_assets=[a.asset_url for a in old_assets][:5],
                    action_items=[
                        "Create updated versions of top-performing old assets",
                        "Test new creative variations against existing assets",
                        "Implement monthly asset refresh schedule",
                    ],
                )
            )

        return recommendations

    def _generate_budget_recommendations(
        self,
        videos: List[VideoPerformance],
        assets: List[CreativeAsset],
        insights: List[VideoCreativeInsight],
    ) -> List[CreativeRecommendation]:
        """Generate budget optimization recommendations."""
        recommendations = []

        # Calculate potential budget reallocation
        high_performers = [v for v in videos if v.view_rate > 15.0 and v.cost > 0]
        low_performers = [v for v in videos if v.view_rate < 5.0 and v.cost > 100]

        if high_performers and low_performers:
            potential_reallocation = sum(v.cost for v in low_performers) * 0.7
            recommendations.append(
                CreativeRecommendation(
                    recommendation_type="budget_reallocation",
                    priority="high",
                    title="Reallocate Budget to High-Performing Videos",
                    description=f"Shift ${potential_reallocation:.2f} from low to high-performing videos.",
                    impact_potential=30.0,
                    current_performance=sum(v.view_rate for v in videos) / len(videos)
                    if videos
                    else 0,
                    target_performance=(
                        sum(v.view_rate for v in videos) / len(videos) * 1.3
                    )
                    if videos
                    else 0,
                    affected_assets=[v.video_title for v in high_performers[:3]],
                    action_items=[
                        f"Increase budget for top {len(high_performers)} performing videos by 50%",
                        f"Reduce budget for bottom {len(low_performers)} performing videos by 70%",
                        "Monitor performance changes weekly for 4 weeks",
                    ],
                )
            )

        return recommendations

    def _generate_analysis_summary(
        self,
        customer_id: str,
        videos: List[VideoPerformance],
        assets: List[CreativeAsset],
        insights: List[VideoCreativeInsight],
        recommendations: List[CreativeRecommendation],
        start_date: datetime,
        end_date: datetime,
    ) -> VideoCreativeAnalysisSummary:
        """Generate analysis summary."""
        # Find top and bottom performers
        videos_by_view_rate = sorted(videos, key=lambda x: x.view_rate, reverse=True)
        assets_by_conversion_rate = sorted(
            assets, key=lambda x: x.conversion_rate, reverse=True
        )

        top_videos = [v.video_title for v in videos_by_view_rate[:5]]
        bottom_videos = [v.video_title for v in videos_by_view_rate[-5:]]
        top_assets = [a.asset_url for a in assets_by_conversion_rate[:5]]
        bottom_assets = [a.asset_url for a in assets_by_conversion_rate[-5:]]

        # Calculate overall performance score
        avg_view_rate = sum(v.view_rate for v in videos) / len(videos) if videos else 0
        avg_conversion_rate = (
            sum(a.conversion_rate for a in assets) / len(assets) if assets else 0
        )
        overall_score = min(100, (avg_view_rate * 2 + avg_conversion_rate) / 3 * 10)

        return VideoCreativeAnalysisSummary(
            analysis_period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            total_videos_analyzed=len(videos),
            total_assets_analyzed=len(assets),
            top_performing_videos=top_videos,
            bottom_performing_videos=bottom_videos,
            top_performing_assets=top_assets,
            bottom_performing_assets=bottom_assets,
            key_insights_count=len(insights),
            recommendations_count=len(recommendations),
            overall_performance_score=overall_score,
        )

    def _calculate_video_coverage(self, videos: List[VideoPerformance]) -> float:
        """Calculate percentage of videos with meaningful data."""
        if not videos:
            return 0.0

        videos_with_data = [
            v for v in videos if v.impressions > 0 or v.views > 0 or v.cost > 0
        ]

        return (len(videos_with_data) / len(videos)) * 100

    def _calculate_asset_coverage(self, assets: List[CreativeAsset]) -> float:
        """Calculate percentage of assets with meaningful data."""
        if not assets:
            return 0.0

        assets_with_data = [
            a for a in assets if a.impressions > 0 or a.clicks > 0 or a.cost > 0
        ]

        return (len(assets_with_data) / len(assets)) * 100

    def _calculate_data_quality_score(
        self, videos: List[VideoPerformance], assets: List[CreativeAsset]
    ) -> float:
        """Calculate overall data quality score."""
        video_coverage = self._calculate_video_coverage(videos)
        asset_coverage = self._calculate_asset_coverage(assets)

        # Factor in data completeness
        video_completeness = 100.0
        if videos:
            complete_videos = [
                v for v in videos if v.video_title and v.duration and v.impressions >= 0
            ]
            video_completeness = (len(complete_videos) / len(videos)) * 100

        asset_completeness = 100.0
        if assets:
            complete_assets = [
                a
                for a in assets
                if a.asset_url
                and a.asset_type != AssetType.UNKNOWN
                and a.impressions >= 0
            ]
            asset_completeness = (len(complete_assets) / len(assets)) * 100

        return (
            video_coverage + asset_coverage + video_completeness + asset_completeness
        ) / 4

    def _calculate_budget_reallocation_potential(
        self, recommendations: List[CreativeRecommendation]
    ) -> float:
        """Calculate estimated budget reallocation potential from recommendations."""
        total_potential = 0.0

        for rec in recommendations:
            if rec.recommendation_type in [
                "budget_reallocation",
                "video_performance_optimization",
            ]:
                total_potential += rec.impact_potential

        return min(50.0, total_potential)  # Cap at 50%

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> VideoCreativeAnalysisResult:
        """Create empty analysis result when no data is available."""
        return VideoCreativeAnalysisResult(
            analyzer_name=self.get_name(),
            customer_id=customer_id,
            analysis_type="video_creative_performance",
            start_date=start_date,
            end_date=end_date,
            video_performances=[],
            creative_assets=[],
            combined_metrics=VideoCreativeMetrics(),
            insights=[],
            video_creative_recommendations=[],
            summary=VideoCreativeAnalysisSummary(
                analysis_period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                total_videos_analyzed=0,
                total_assets_analyzed=0,
                top_performing_videos=[],
                bottom_performing_videos=[],
                top_performing_assets=[],
                bottom_performing_assets=[],
                key_insights_count=0,
                recommendations_count=0,
                overall_performance_score=0.0,
            ),
        )

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Video and Creative Asset Performance Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return "Analyzes video content and creative asset performance to identify optimization opportunities for fitness industry marketing campaigns."
