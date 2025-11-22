"""Ad Group Performance Analyzer.

This analyzer evaluates ad group performance metrics and identifies optimization
opportunities for improving campaign efficiency.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.base import BasePSNModel

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


def parse_currency(value: str) -> float:
    """Parse currency string to float, handling $ and commas."""
    if not value or value == "--" or value == "":
        return 0.0
    # Handle parentheses for negative values (e.g., "($100.00)")
    is_negative = "(" in str(value) and ")" in str(value)
    # Remove currency symbols, commas, quotes, and parentheses
    cleaned = str(value).replace("$", "").replace(",", "").replace('"', "")
    cleaned = cleaned.replace("(", "").replace(")", "").strip()
    try:
        result = float(cleaned)
        return -result if is_negative else result
    except (ValueError, TypeError):
        return 0.0


def clean_percentage(value: str) -> float:
    """Parse percentage string to float."""
    if not value or value == "--" or value == "":
        return 0.0
    # Remove % symbol and convert
    cleaned = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def validate_csv_headers(df: pd.DataFrame, required_columns: list[str]) -> None:
    """Validate that required columns exist in DataFrame.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names

    Raises:
        ValueError: If required columns are missing
    """
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")


class AdGroupStatus(str):
    """Ad group status values."""

    ENABLED = "Enabled"
    PAUSED = "Paused"
    REMOVED = "Removed"


class AdGroupPerformance(BasePSNModel):
    """Ad group performance data model."""

    campaign_name: str
    ad_group_name: str
    status: str
    bid_amount: Optional[float] = None
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: float = 0.0
    conversion_rate: float = 0.0
    avg_cpc: float = 0.0
    quality_score: Optional[float] = None
    search_impression_share: Optional[float] = None

    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def cpa(self) -> float:
        """Calculate Cost Per Acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        """Calculate Return On Ad Spend.

        Note: ROAS calculation requires conversion value data which is not
        available in the standard ad group CSV format. Override this method
        or set conversion values if you have this data.

        Raises:
            NotImplementedError: ROAS calculation not supported without conversion value data
        """
        raise NotImplementedError(
            "ROAS calculation requires conversion value data. "
            "Please provide conversion values or override this method."
        )


class AdGroupPerformanceAnalyzer(Analyzer):
    """Analyzes ad group performance and provides optimization recommendations."""

    # Performance thresholds
    DEFAULT_MIN_IMPRESSIONS = 100
    DEFAULT_MIN_CLICKS = 10
    DEFAULT_LOW_CTR_THRESHOLD = 1.0  # %
    DEFAULT_HIGH_CPA_THRESHOLD = 100.0
    DEFAULT_LOW_CONVERSION_RATE = 2.0  # %
    DEFAULT_LOW_QUALITY_SCORE = 5.0
    DEFAULT_LOW_IMPRESSION_SHARE = 50.0  # %

    # Analysis constants
    ESTIMATED_SAVINGS_RATE = 0.15  # 15% estimated savings
    BIDDING_SAVINGS_RATE = 0.2  # 20% savings from bid optimization
    CPA_TOLERANCE_MULTIPLIER = 1.2  # 20% tolerance over target CPA
    PERFORMANCE_VARIANCE_THRESHOLD = 3.0  # 3x variance threshold

    def __init__(
        self,
        data_provider: Optional[DataProvider] = None,
        min_impressions: int = DEFAULT_MIN_IMPRESSIONS,
        min_clicks: int = DEFAULT_MIN_CLICKS,
        low_ctr_threshold: float = DEFAULT_LOW_CTR_THRESHOLD,
        high_cpa_threshold: float = DEFAULT_HIGH_CPA_THRESHOLD,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Optional data provider for API-based analysis
            min_impressions: Minimum impressions to include in analysis
            min_clicks: Minimum clicks to include in analysis
            low_ctr_threshold: CTR threshold for underperforming ad groups
            high_cpa_threshold: CPA threshold for expensive ad groups
        """
        self.data_provider = data_provider
        self.min_impressions = min_impressions
        self.min_clicks = min_clicks
        self.low_ctr_threshold = low_ctr_threshold
        self.high_cpa_threshold = high_cpa_threshold
        self._csv_data: Optional[list[AdGroupPerformance]] = None

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "AdGroupPerformanceAnalyzer":
        """Create an AdGroupPerformanceAnalyzer instance from a CSV file.

        Parses Google Ads Ad Group CSV report and prepares data for analysis.

        Args:
            file_path: Path to the ad group CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            AdGroupPerformanceAnalyzer instance with loaded data

        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid or file too large
            PermissionError: If the file path attempts directory traversal
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Resolve to absolute path for security
        file_path = file_path.resolve()

        # Path traversal protection
        cwd = Path.cwd()
        temp_dir = Path("/tmp")
        var_folders = Path("/var/folders")
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

        # Parse CSV
        analyzer._csv_data = analyzer._parse_csv(file_path)

        return analyzer

    def _parse_csv(self, file_path: Path) -> list[AdGroupPerformance]:
        """Parse ad group CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            List of AdGroupPerformance objects

        Raises:
            ValueError: If CSV format is invalid
        """
        try:
            # Read CSV, skipping initial comment lines
            # Use on_bad_lines='skip' to handle inconsistent columns
            df = pd.read_csv(
                file_path,
                comment="#",
                thousands=",",
                on_bad_lines="skip",
                engine="python",
            )

            # Expected column mappings (handle variations)
            column_mappings = {
                "Campaign": "campaign_name",
                "Ad group": "ad_group_name",
                "Ad group state": "ad_group_state",
                "Default max. CPC": "bid_amount",
                "Target CPA": "target_cpa",
                "Target ROAS": "target_roas",
                "Impr.": "impressions",
                "Clicks": "clicks",
                "Cost": "cost",
                "Conversions": "conversions",
                "Conv. rate": "conversion_rate",
                "Avg. CPC": "avg_cpc",
                "Quality Score": "quality_score",
                "Search impr. share": "search_impression_share",
            }

            # Validate required columns
            required_columns = ["Campaign", "Ad group", "Ad group state"]
            validate_csv_headers(df, required_columns)

            # Rename columns
            df.rename(columns=column_mappings, inplace=True)

            # Parse data - use to_dict for better performance
            ad_groups = []
            for row in df.to_dict("records"):
                try:
                    # Parse numeric values with better NaN handling
                    imp_val = row.get("impressions", 0)
                    if pd.isna(imp_val):
                        impressions = 0
                    else:
                        impressions = int(str(imp_val).replace(",", "") or 0)

                    click_val = row.get("clicks", 0)
                    if pd.isna(click_val):
                        clicks = 0
                    else:
                        clicks = int(str(click_val).replace(",", "") or 0)
                    cost = parse_currency(str(row.get("cost", 0)))

                    # Handle conversions - may be empty/NaN
                    conv_val = row.get("conversions", 0)
                    if pd.isna(conv_val) or str(conv_val).strip() == "":
                        conversions = 0.0
                    else:
                        conversions = float(str(conv_val).replace(",", "") or 0)

                    # Parse optional values
                    bid_amount = None
                    if pd.notna(row.get("bid_amount")):
                        bid_amount = parse_currency(str(row["bid_amount"]))

                    target_cpa = None
                    if pd.notna(row.get("target_cpa")):
                        target_cpa = parse_currency(str(row["target_cpa"]))

                    target_roas = None
                    if pd.notna(row.get("target_roas")):
                        target_roas = clean_percentage(str(row["target_roas"]))

                    conversion_rate = clean_percentage(
                        str(row.get("conversion_rate", 0))
                    )
                    avg_cpc = parse_currency(str(row.get("avg_cpc", 0)))

                    quality_score = None
                    if pd.notna(row.get("quality_score")):
                        quality_score = float(row["quality_score"])

                    search_impression_share = None
                    if pd.notna(row.get("search_impression_share")):
                        search_impression_share = clean_percentage(
                            str(row["search_impression_share"])
                        )

                    ad_group = AdGroupPerformance(
                        campaign_name=str(row["campaign_name"]).strip(),
                        ad_group_name=str(row["ad_group_name"]).strip(),
                        status=str(row.get("ad_group_state", "Unknown")).strip(),
                        bid_amount=bid_amount,
                        target_cpa=target_cpa,
                        target_roas=target_roas,
                        impressions=impressions,
                        clicks=clicks,
                        cost=cost,
                        conversions=conversions,
                        conversion_rate=conversion_rate,
                        avg_cpc=avg_cpc,
                        quality_score=quality_score,
                        search_impression_share=search_impression_share,
                    )

                    ad_groups.append(ad_group)

                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue

            if not ad_groups:
                raise ValueError("No valid ad group data found in CSV")

            logger.info(f"Successfully parsed {len(ad_groups)} ad groups from CSV")
            return ad_groups

        except Exception as e:
            logger.error(f"Error parsing ad group CSV: {e}")
            raise ValueError(f"Failed to parse ad group CSV: {e}")

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Ad Group Performance Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes ad group performance metrics to identify optimization opportunities "
            "for improving campaign efficiency and reducing wasted spend."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run ad group performance analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional parameters

        Returns:
            Analysis results with performance insights and recommendations
        """
        recommendations = []
        metrics = AnalysisMetrics()
        raw_data = {}

        try:
            # Use CSV data if available, otherwise fetch from API
            if self._csv_data:
                ad_groups = self._csv_data
                logger.info(f"Using CSV data with {len(ad_groups)} ad groups")
            elif self.data_provider:
                # This would fetch from API - not implemented yet
                logger.warning("API-based ad group fetching not yet implemented")
                ad_groups = []
            else:
                raise ValueError("No data source available for analysis")

            # Filter by minimum thresholds
            active_ad_groups = [
                ag
                for ag in ad_groups
                if ag.status == AdGroupStatus.ENABLED
                and ag.impressions >= self.min_impressions
            ]

            # Analyze performance
            performance_issues = self._analyze_performance(active_ad_groups)
            recommendations.extend(performance_issues["recommendations"])

            # Analyze bidding efficiency
            bidding_issues = self._analyze_bidding(active_ad_groups)
            recommendations.extend(bidding_issues["recommendations"])

            # Analyze quality and impression share
            quality_issues = self._analyze_quality(active_ad_groups)
            recommendations.extend(quality_issues["recommendations"])

            # Group ad groups by campaign for campaign-level insights
            campaign_groups = self._group_by_campaign(active_ad_groups)
            campaign_insights = self._analyze_campaigns(campaign_groups)
            recommendations.extend(campaign_insights["recommendations"])

            # Update metrics
            metrics.total_campaigns_analyzed = len(campaign_groups)
            metrics.custom_metrics["total_ad_groups_analyzed"] = len(active_ad_groups)
            metrics.custom_metrics["underperforming_ad_groups"] = performance_issues[
                "count"
            ]
            metrics.custom_metrics["bidding_issues"] = bidding_issues["count"]
            metrics.custom_metrics["quality_issues"] = quality_issues["count"]
            metrics.issues_found = len(recommendations)
            metrics.critical_issues = len(
                [
                    r
                    for r in recommendations
                    if r.priority == RecommendationPriority.CRITICAL
                ]
            )

            # Calculate potential savings
            total_cost = sum(ag.cost for ag in active_ad_groups)
            metrics.potential_cost_savings = total_cost * self.ESTIMATED_SAVINGS_RATE

            # Store raw data for detailed review
            raw_data = {
                "total_ad_groups": len(ad_groups),
                "active_ad_groups": len(active_ad_groups),
                "paused_ad_groups": len(
                    [ag for ag in ad_groups if ag.status == AdGroupStatus.PAUSED]
                ),
                "performance_summary": {
                    "total_impressions": sum(ag.impressions for ag in active_ad_groups),
                    "total_clicks": sum(ag.clicks for ag in active_ad_groups),
                    "total_cost": total_cost,
                    "total_conversions": sum(ag.conversions for ag in active_ad_groups),
                    "average_ctr": self._calculate_average_ctr(active_ad_groups),
                    "average_cpa": (
                        total_cost / sum(ag.conversions for ag in active_ad_groups)
                        if sum(ag.conversions for ag in active_ad_groups) > 0
                        else 0
                    ),
                },
                "campaign_breakdown": campaign_groups,
            }

        except Exception as e:
            logger.error(f"Error in ad group analysis: {e}")
            return AnalysisResult(
                customer_id=customer_id,
                analysis_type="ad_group_performance",
                analyzer_name=self.get_name(),
                start_date=start_date,
                end_date=end_date,
                status="error",
                errors=[str(e)],
            )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="ad_group_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            status="completed",
            metrics=metrics,
            recommendations=recommendations,
            raw_data=raw_data,
        )

    def _analyze_performance(
        self, ad_groups: list[AdGroupPerformance]
    ) -> dict[str, Any]:
        """Analyze ad group performance metrics.

        Args:
            ad_groups: List of ad groups to analyze

        Returns:
            Dictionary with recommendations and issue count
        """
        recommendations = []
        underperforming_count = 0

        for ag in ad_groups:
            issues = []

            # Check CTR
            if (
                ag.ctr < self.low_ctr_threshold
                and ag.impressions >= self.min_impressions
            ):
                issues.append("low_ctr")
                underperforming_count += 1

            # Check conversion rate
            if (
                ag.conversion_rate < self.DEFAULT_LOW_CONVERSION_RATE
                and ag.clicks >= self.min_clicks
            ):
                issues.append("low_conversion_rate")

            # Check CPA
            if ag.cpa > self.high_cpa_threshold and ag.conversions > 0:
                issues.append("high_cpa")

            # Create recommendations based on issues
            if "low_ctr" in issues:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.IMPROVE_QUALITY,
                        priority=RecommendationPriority.HIGH,
                        title=f"Low CTR in '{ag.ad_group_name}'",
                        description=(
                            f"Ad group '{ag.ad_group_name}' in campaign '{ag.campaign_name}' "
                            f"has a CTR of {ag.ctr:.2f}% (below {self.low_ctr_threshold}%). "
                            "Consider improving ad copy, adding extensions, or refining targeting."
                        ),
                        estimated_impact="Improved CTR could reduce CPC by 20-30%",
                        action_data={
                            "ad_group": ag.ad_group_name,
                            "campaign": ag.campaign_name,
                            "current_ctr": ag.ctr,
                            "threshold": self.low_ctr_threshold,
                        },
                    )
                )

            if "high_cpa" in issues:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.OPTIMIZE_BIDDING,
                        priority=RecommendationPriority.HIGH,
                        title=f"High CPA in '{ag.ad_group_name}'",
                        description=(
                            f"Ad group '{ag.ad_group_name}' has a CPA of ${ag.cpa:.2f} "
                            f"(above ${self.high_cpa_threshold}). "
                            "Consider lowering bids, adding negative keywords, or pausing poor performers."
                        ),
                        estimated_cost_savings=ag.cost * self.BIDDING_SAVINGS_RATE,
                        action_data={
                            "ad_group": ag.ad_group_name,
                            "campaign": ag.campaign_name,
                            "current_cpa": ag.cpa,
                            "threshold": self.high_cpa_threshold,
                        },
                    )
                )

        return {"recommendations": recommendations, "count": underperforming_count}

    def _analyze_bidding(self, ad_groups: list[AdGroupPerformance]) -> dict[str, Any]:
        """Analyze bidding strategy efficiency.

        Args:
            ad_groups: List of ad groups to analyze

        Returns:
            Dictionary with recommendations and issue count
        """
        recommendations = []
        bidding_issues = 0

        for ag in ad_groups:
            # Check if target CPA is being met
            if ag.target_cpa and ag.conversions > 0:
                if ag.cpa >= ag.target_cpa * self.CPA_TOLERANCE_MULTIPLIER:
                    bidding_issues += 1
                    recommendations.append(
                        Recommendation(
                            type=RecommendationType.ADJUST_BID,
                            priority=RecommendationPriority.MEDIUM,
                            title=f"Missing Target CPA in '{ag.ad_group_name}'",
                            description=(
                                f"Ad group is ${ag.cpa - ag.target_cpa:.2f} over target CPA. "
                                f"Current: ${ag.cpa:.2f}, Target: ${ag.target_cpa:.2f}. "
                                "Consider adjusting bids or improving quality score."
                            ),
                            estimated_cost_savings=(ag.cpa - ag.target_cpa)
                            * ag.conversions,
                            action_data={
                                "ad_group": ag.ad_group_name,
                                "campaign": ag.campaign_name,
                                "current_cpa": ag.cpa,
                                "target_cpa": ag.target_cpa,
                            },
                        )
                    )

        return {"recommendations": recommendations, "count": bidding_issues}

    def _analyze_quality(self, ad_groups: list[AdGroupPerformance]) -> dict[str, Any]:
        """Analyze quality score and impression share.

        Args:
            ad_groups: List of ad groups to analyze

        Returns:
            Dictionary with recommendations and issue count
        """
        recommendations = []
        quality_issues = 0

        for ag in ad_groups:
            # Check quality score
            if ag.quality_score and ag.quality_score < self.DEFAULT_LOW_QUALITY_SCORE:
                quality_issues += 1
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.IMPROVE_QUALITY_SCORE,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Low Quality Score in '{ag.ad_group_name}'",
                        description=(
                            f"Quality score of {ag.quality_score:.1f}/10 is below recommended threshold. "
                            "Improve ad relevance, landing page experience, and expected CTR."
                        ),
                        estimated_impact="Improving quality score could reduce CPC by 30-50%",
                        action_data={
                            "ad_group": ag.ad_group_name,
                            "campaign": ag.campaign_name,
                            "quality_score": ag.quality_score,
                        },
                    )
                )

            # Check impression share
            if (
                ag.search_impression_share
                and ag.search_impression_share < self.DEFAULT_LOW_IMPRESSION_SHARE
            ):
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADJUST_BID,
                        priority=RecommendationPriority.LOW,
                        title=f"Low Impression Share in '{ag.ad_group_name}'",
                        description=(
                            f"Search impression share of {ag.search_impression_share:.1f}% "
                            "indicates missed opportunities. Consider increasing bids or budget."
                        ),
                        estimated_impact="Could increase traffic by 20-30%",
                        action_data={
                            "ad_group": ag.ad_group_name,
                            "campaign": ag.campaign_name,
                            "impression_share": ag.search_impression_share,
                        },
                    )
                )

        return {"recommendations": recommendations, "count": quality_issues}

    def _group_by_campaign(
        self, ad_groups: list[AdGroupPerformance]
    ) -> dict[str, list[AdGroupPerformance]]:
        """Group ad groups by campaign.

        Args:
            ad_groups: List of ad groups

        Returns:
            Dictionary mapping campaign names to their ad groups
        """
        campaign_groups = defaultdict(list)
        for ag in ad_groups:
            campaign_groups[ag.campaign_name].append(ag)
        return dict(campaign_groups)

    def _analyze_campaigns(
        self, campaign_groups: dict[str, list[AdGroupPerformance]]
    ) -> dict[str, Any]:
        """Analyze campaign-level patterns.

        Args:
            campaign_groups: Ad groups grouped by campaign

        Returns:
            Dictionary with recommendations
        """
        recommendations = []

        for campaign_name, ad_groups in campaign_groups.items():
            # Calculate campaign-level metrics
            total_cost = sum(ag.cost for ag in ad_groups)
            total_conversions = sum(ag.conversions for ag in ad_groups)
            avg_cpa = total_cost / total_conversions if total_conversions > 0 else 0

            # Check for inconsistent performance
            cpa_values = [ag.cpa for ag in ad_groups if ag.conversions > 0]
            if cpa_values:
                min_cpa = min(cpa_values)
                max_cpa = max(cpa_values)

                if max_cpa > min_cpa * self.PERFORMANCE_VARIANCE_THRESHOLD:
                    recommendations.append(
                        Recommendation(
                            type=RecommendationType.OPTIMIZE_KEYWORDS,
                            priority=RecommendationPriority.MEDIUM,
                            title=f"Inconsistent Performance in '{campaign_name}'",
                            description=(
                                f"Campaign has ad groups with widely varying CPAs "
                                f"(${min_cpa:.2f} to ${max_cpa:.2f}). "
                                "Consider pausing poor performers or reallocating budget."
                            ),
                            estimated_cost_savings=total_cost * 0.1,
                            action_data={
                                "campaign": campaign_name,
                                "min_cpa": min_cpa,
                                "max_cpa": max_cpa,
                                "avg_cpa": avg_cpa,
                            },
                        )
                    )

        return {"recommendations": recommendations}

    def _calculate_average_ctr(self, ad_groups: list[AdGroupPerformance]) -> float:
        """Calculate average CTR safely.

        Args:
            ad_groups: List of ad groups

        Returns:
            Average CTR percentage
        """
        total_impressions = sum(ag.impressions for ag in ad_groups)
        if total_impressions == 0:
            return 0.0
        total_clicks = sum(ag.clicks for ag in ad_groups)
        return (total_clicks / total_impressions) * 100
