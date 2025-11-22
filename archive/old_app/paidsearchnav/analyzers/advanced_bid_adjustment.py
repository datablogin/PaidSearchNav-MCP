"""Advanced Bid Adjustment Strategy Analyzer for sophisticated bidding optimization."""

import logging
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.bid_adjustment import (
    BidAdjustment,
    BidAdjustmentAnalysisResult,
    BidAdjustmentAnalysisSummary,
    BidAdjustmentDimension,
    BidOptimization,
    BidPerformanceMetrics,
    BidStrategy,
    BidStrategyType,
    CompetitiveInsight,
    InteractionType,
    OptimizationStatus,
)

logger = logging.getLogger(__name__)


class AdvancedBidAdjustmentAnalyzer(Analyzer):
    """Analyzes complex bid adjustment strategies to identify optimization opportunities."""

    # Business logic thresholds
    HIGH_PERFORMER_THRESHOLD = 80.0
    MODERATE_PERFORMER_THRESHOLD = 60.0
    LOW_PERFORMER_THRESHOLD = 40.0

    # Data quality thresholds
    MIN_IMPRESSIONS_THRESHOLD = 100
    MIN_CONVERSIONS_THRESHOLD = 0.5
    MIN_COVERAGE_PERCENTAGE = 80.0
    MIN_COMPLETENESS_SCORE = 85.0

    # Performance variance thresholds
    SIGNIFICANT_ROI_VARIANCE = 25.0  # 25% ROI difference from baseline
    SIGNIFICANT_COST_VARIANCE = 20.0  # 20% cost difference
    EFFICIENCY_IMPROVEMENT_POTENTIAL = 20.0  # 20% improvement potential
    MIN_ACTIONABLE_RECOMMENDATIONS = 5
    MIN_PERFORMANCE_IMPACT = 15.0  # 15% performance impact

    def __init__(
        self,
        min_impressions: int = 100,
        min_conversions: float = 0.5,
        roi_variance_threshold: float = 0.25,
        cost_variance_threshold: float = 0.20,
        avg_conversion_value: float = 50.0,
    ):
        """Initialize the advanced bid adjustment analyzer.

        Args:
            min_impressions: Minimum impressions required for analysis
            min_conversions: Minimum conversions required for analysis
            roi_variance_threshold: Threshold for significant ROI variance
            cost_variance_threshold: Threshold for significant cost variance
            avg_conversion_value: Average value per conversion (e.g., monthly membership value)
        """
        self.min_impressions = min_impressions
        self.min_conversions = min_conversions
        self.roi_variance_threshold = roi_variance_threshold
        self.cost_variance_threshold = cost_variance_threshold
        self.avg_conversion_value = avg_conversion_value

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Advanced Bid Adjustment Strategy Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes complex bid adjustment strategies across campaigns to identify "
            "optimization opportunities, assess ROI impact, and provide strategic bidding "
            "recommendations for improved campaign performance and cost efficiency."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> BidAdjustmentAnalysisResult:
        """Analyze advanced bid adjustment strategies for a customer.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (bid_adjustment_data)

        Returns:
            Bid adjustment analysis result
        """
        logger.info(
            f"Starting bid adjustment analysis for customer {customer_id}",
            extra={
                "customer_id": customer_id,
                "date_range": f"{start_date} to {end_date}",
                "analyzer": self.get_name(),
            },
        )

        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )

        try:
            # Extract bid adjustment data from kwargs
            bid_data = kwargs.get("bid_adjustment_data")

            if bid_data is None or (
                isinstance(bid_data, pd.DataFrame) and bid_data.empty
            ):
                logger.warning("No bid adjustment data provided for analysis")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Convert raw data to structured models
            bid_adjustments = self._convert_to_bid_adjustments(bid_data)

            if not bid_adjustments:
                logger.warning("No valid bid adjustments found in data")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Analyze bid strategies
            bid_strategies = self._analyze_bid_strategies(bid_adjustments)

            # Generate optimization recommendations
            optimizations = self._generate_optimizations(bid_adjustments)

            # Analyze competitive positioning
            competitive_insights = self._analyze_competitive_position(bid_adjustments)

            # Create summary
            summary = self._create_summary(
                bid_adjustments, bid_strategies, optimizations
            )

            return BidAdjustmentAnalysisResult(
                customer_id=customer_id,
                analysis_date=datetime.now(),
                start_date=start_date,
                end_date=end_date,
                bid_adjustments=bid_adjustments,
                bid_strategies=bid_strategies,
                optimizations=optimizations,
                competitive_insights=competitive_insights,
                summary=summary,
                metadata={
                    "analyzer_version": "1.0.0",
                    "thresholds": {
                        "min_impressions": self.min_impressions,
                        "min_conversions": self.min_conversions,
                        "roi_variance": self.roi_variance_threshold,
                        "cost_variance": self.cost_variance_threshold,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error analyzing bid adjustments: {str(e)}")
            raise

    def _validate_bid_data(self, bid_data: pd.DataFrame) -> None:
        """Validate required columns exist in bid data.

        Args:
            bid_data: Raw bid adjustment DataFrame

        Raises:
            ValueError: If required columns are missing
        """
        required_columns = ["Campaign", "Interaction type", "Cost", "Conversions"]
        missing = set(required_columns) - set(bid_data.columns)
        if missing:
            raise ValueError(f"Missing required columns in bid data: {missing}")

    def _convert_to_bid_adjustments(
        self, bid_data: pd.DataFrame
    ) -> List[BidAdjustment]:
        """Convert raw bid adjustment data to structured models.

        Args:
            bid_data: Raw bid adjustment DataFrame

        Returns:
            List of BidAdjustment objects
        """
        # Validate data first
        self._validate_bid_data(bid_data)

        bid_adjustments = []

        # Ensure column names don't have spaces for itertuples
        bid_data_clean = bid_data.copy()
        bid_data_clean.columns = [
            col.replace(" ", "_").replace(".", "") for col in bid_data_clean.columns
        ]

        for row in bid_data_clean.itertuples(index=False):
            try:
                # Parse interaction type
                interaction_type = self._parse_interaction_type(
                    getattr(row, "Interaction_type", "Unknown")
                )

                # Create performance metrics
                metrics = BidPerformanceMetrics(
                    impressions=self._safe_int(getattr(row, "Impr", 0)),
                    clicks=self._safe_int(getattr(row, "Clicks", 0)),
                    conversions=self._safe_float(getattr(row, "Conversions", 0)),
                    cost=self._safe_float(getattr(row, "Cost", 0)),
                    interaction_rate=self._safe_float(
                        getattr(row, "Interaction_rate", "0%")
                    ),
                    conversion_rate=self._safe_float(getattr(row, "Conv_rate", "0%")),
                    cost_per_conversion=self._safe_float(
                        getattr(row, "Cost_/_conv", 0)
                    ),
                    avg_cpm=self._safe_float(getattr(row, "Avg_CPM", 0)),
                    avg_cpc=self._safe_float(getattr(row, "Avg_cost", 0)),
                    interaction_coverage=self._safe_float(
                        getattr(row, "Inter_coverage", "0%")
                    ),
                )

                # Calculate ROI if possible
                if metrics.conversions > 0 and metrics.cost > 0:
                    # Use configurable average conversion value
                    metrics.revenue = metrics.conversions * self.avg_conversion_value
                    metrics.roi = (
                        (metrics.revenue - metrics.cost) / metrics.cost
                    ) * 100

                # Determine optimization status
                optimization_status = self._determine_optimization_status(metrics)

                # Create bid adjustment object
                campaign_name = getattr(row, "Campaign", "Unknown")
                adjustment = BidAdjustment(
                    adjustment_id=f"{campaign_name}_{interaction_type.value}",
                    campaign_name=campaign_name,
                    interaction_type=interaction_type,
                    dimension=BidAdjustmentDimension.INTERACTION_TYPE,
                    bid_modifier=self._parse_bid_modifier(
                        getattr(row, "Bid_adj", "--")
                    ),
                    performance=metrics,
                    optimization_status=optimization_status,
                    metadata={
                        "currency_code": getattr(row, "Currency_code", "USD"),
                    },
                )

                bid_adjustments.append(adjustment)

            except Exception as e:
                logger.warning(f"Error parsing bid adjustment row: {str(e)}")
                continue

        return bid_adjustments

    def _analyze_bid_strategies(
        self, bid_adjustments: List[BidAdjustment]
    ) -> List[BidStrategy]:
        """Analyze bid strategies across campaigns.

        Args:
            bid_adjustments: List of bid adjustments

        Returns:
            List of BidStrategy objects
        """
        strategies = {}

        for adjustment in bid_adjustments:
            # Group by interaction type as proxy for strategy
            strategy_key = adjustment.interaction_type.value

            if strategy_key not in strategies:
                strategies[strategy_key] = BidStrategy(
                    strategy_id=strategy_key,
                    strategy_type=BidStrategyType.MANUAL_CPC,  # Default assumption
                    campaign_count=0,
                    total_impressions=0,
                    total_clicks=0,
                    total_conversions=0.0,
                    total_cost=0.0,
                    avg_bid_modifier=0.0,
                    effectiveness_score=0.0,
                    optimization_opportunities=[],
                    top_performing_campaigns=[],
                    underperforming_campaigns=[],
                )

            strategy = strategies[strategy_key]
            strategy.campaign_count += 1
            strategy.total_impressions += adjustment.performance.impressions
            strategy.total_clicks += adjustment.performance.clicks
            strategy.total_conversions += adjustment.performance.conversions
            strategy.total_cost += adjustment.performance.cost

            # Track performing campaigns
            if adjustment.optimization_status == OptimizationStatus.OPTIMAL:
                strategy.top_performing_campaigns.append(adjustment.campaign_name)
            elif adjustment.optimization_status in [
                OptimizationStatus.OVER_BIDDING,
                OptimizationStatus.UNDER_BIDDING,
            ]:
                strategy.underperforming_campaigns.append(adjustment.campaign_name)

        # Calculate effectiveness scores
        for strategy in strategies.values():
            if strategy.campaign_count > 0:
                strategy.avg_bid_modifier = 1.0  # Default if not available

                # Calculate effectiveness based on conversion rate and cost efficiency
                if strategy.total_impressions > 0:
                    conv_rate = (
                        strategy.total_conversions / strategy.total_clicks
                        if strategy.total_clicks > 0
                        else 0
                    )
                    cost_per_conv = (
                        strategy.total_cost / strategy.total_conversions
                        if strategy.total_conversions > 0
                        else float("inf")
                    )

                    # Score based on conversion rate (0-50 points) and cost efficiency (0-50 points)
                    conv_score = min(conv_rate * 500, 50)  # Cap at 50
                    # Guard against infinity values
                    if cost_per_conv == float("inf"):
                        cost_score = 0
                    else:
                        cost_score = max(
                            0, 50 - (cost_per_conv / 10)
                        )  # Lower cost is better

                    strategy.effectiveness_score = conv_score + cost_score

            # Add optimization opportunities
            if len(strategy.underperforming_campaigns) > 0:
                strategy.optimization_opportunities.append(
                    f"Review {len(strategy.underperforming_campaigns)} underperforming campaigns"
                )
            if strategy.total_conversions == 0 and strategy.total_cost > 100:
                strategy.optimization_opportunities.append(
                    "Zero conversions despite significant spend - review targeting"
                )

        return list(strategies.values())

    def _generate_optimizations(
        self, bid_adjustments: List[BidAdjustment]
    ) -> List[BidOptimization]:
        """Generate bid optimization recommendations.

        Args:
            bid_adjustments: List of bid adjustments

        Returns:
            List of BidOptimization objects
        """
        optimizations = []

        for adjustment in bid_adjustments:
            if adjustment.optimization_status == OptimizationStatus.OVER_BIDDING:
                # Recommend reducing bid
                current_bid = adjustment.bid_modifier or 1.0
                recommended_bid = max(0.7, current_bid * 0.85)  # Reduce by 15%

                optimization = BidOptimization(
                    adjustment_id=adjustment.adjustment_id,
                    campaign_name=adjustment.campaign_name,
                    current_bid_modifier=current_bid,
                    recommended_bid_modifier=recommended_bid,
                    expected_impact="Reduce cost while maintaining performance",
                    reasoning=f"High cost per conversion (${adjustment.performance.cost_per_conversion:.2f}) suggests over-bidding",
                    priority="High" if adjustment.performance.cost > 500 else "Medium",
                    estimated_cost_savings=adjustment.performance.cost * 0.15,
                    confidence_score=0.75,
                )
                optimizations.append(optimization)

            elif adjustment.optimization_status == OptimizationStatus.UNDER_BIDDING:
                # Recommend increasing bid
                current_bid = adjustment.bid_modifier or 1.0
                recommended_bid = min(1.5, current_bid * 1.2)  # Increase by 20%

                optimization = BidOptimization(
                    adjustment_id=adjustment.adjustment_id,
                    campaign_name=adjustment.campaign_name,
                    current_bid_modifier=current_bid,
                    recommended_bid_modifier=recommended_bid,
                    expected_impact="Increase visibility and conversions",
                    reasoning=f"Low interaction coverage ({adjustment.performance.interaction_coverage:.1f}%) indicates missed opportunities",
                    priority="High"
                    if adjustment.performance.interaction_coverage < 50
                    else "Medium",
                    estimated_conversion_increase=adjustment.performance.conversions
                    * 0.2,
                    confidence_score=0.70,
                )
                optimizations.append(optimization)

            elif (
                adjustment.performance.conversions == 0
                and adjustment.performance.cost > 100
            ):
                # Zero conversion campaigns
                optimization = BidOptimization(
                    adjustment_id=adjustment.adjustment_id,
                    campaign_name=adjustment.campaign_name,
                    current_bid_modifier=adjustment.bid_modifier,
                    recommended_bid_modifier=0.5,  # Significantly reduce bid
                    expected_impact="Test lower bids or pause if no improvement",
                    reasoning="Zero conversions despite spend - needs strategic review",
                    priority="High",
                    estimated_cost_savings=adjustment.performance.cost * 0.5,
                    confidence_score=0.80,
                )
                optimizations.append(optimization)

        # Sort by priority and estimated savings
        optimizations.sort(
            key=lambda x: (
                {"High": 3, "Medium": 2, "Low": 1}.get(x.priority, 0),
                x.estimated_cost_savings or 0,
            ),
            reverse=True,
        )

        return optimizations[:10]  # Return top 10 recommendations

    def _analyze_competitive_position(
        self, bid_adjustments: List[BidAdjustment]
    ) -> CompetitiveInsight:
        """Analyze competitive positioning based on bid performance.

        Args:
            bid_adjustments: List of bid adjustments

        Returns:
            CompetitiveInsight object
        """
        total_impressions = sum(adj.performance.impressions for adj in bid_adjustments)
        total_conversions = sum(adj.performance.conversions for adj in bid_adjustments)
        avg_coverage = (
            sum(adj.performance.interaction_coverage for adj in bid_adjustments)
            / len(bid_adjustments)
            if bid_adjustments
            else 0
        )

        # Determine market position based on coverage and performance
        if avg_coverage > 70 and total_conversions > 10:
            market_position = "Leader"
        elif avg_coverage > 50 and total_conversions > 5:
            market_position = "Competitive"
        else:
            market_position = "Lagging"

        recommendations = []
        if market_position == "Lagging":
            recommendations.append("Consider increasing bids in high-value segments")
            recommendations.append("Review targeting to improve relevance")
        elif market_position == "Competitive":
            recommendations.append("Test bid increases in top-performing campaigns")
            recommendations.append("Optimize underperforming segments")
        else:
            recommendations.append("Maintain current bid strategy")
            recommendations.append("Focus on efficiency improvements")

        # Add specific recommendations based on data
        zero_conv_campaigns = [
            adj.campaign_name
            for adj in bid_adjustments
            if adj.performance.conversions == 0 and adj.performance.cost > 50
        ]
        if zero_conv_campaigns:
            recommendations.append(
                f"Review {len(zero_conv_campaigns)} campaigns with zero conversions"
            )

        return CompetitiveInsight(
            market_position=market_position,
            impression_share=avg_coverage / 100 if avg_coverage > 0 else None,
            competitive_metrics={
                "avg_interaction_coverage": avg_coverage,
                "total_market_impressions": total_impressions,
                "conversion_efficiency": total_conversions / total_impressions * 100
                if total_impressions > 0
                else 0,
            },
            recommendations=recommendations[:5],  # Top 5 recommendations
        )

    def _create_summary(
        self,
        bid_adjustments: List[BidAdjustment],
        bid_strategies: List[BidStrategy],
        optimizations: List[BidOptimization],
    ) -> BidAdjustmentAnalysisSummary:
        """Create analysis summary.

        Args:
            bid_adjustments: List of bid adjustments
            bid_strategies: List of bid strategies
            optimizations: List of optimizations

        Returns:
            BidAdjustmentAnalysisSummary object
        """
        total_impressions = sum(adj.performance.impressions for adj in bid_adjustments)
        total_clicks = sum(adj.performance.clicks for adj in bid_adjustments)
        total_conversions = sum(adj.performance.conversions for adj in bid_adjustments)
        total_cost = sum(adj.performance.cost for adj in bid_adjustments)

        # Calculate average ROI
        adjustments_with_roi = [
            adj for adj in bid_adjustments if adj.performance.roi is not None
        ]
        avg_roi = (
            sum(adj.performance.roi for adj in adjustments_with_roi)
            / len(adjustments_with_roi)
            if adjustments_with_roi
            else 0.0
        )

        # Count optimization statuses
        optimal_count = sum(
            1
            for adj in bid_adjustments
            if adj.optimization_status == OptimizationStatus.OPTIMAL
        )
        over_bidding_count = sum(
            1
            for adj in bid_adjustments
            if adj.optimization_status == OptimizationStatus.OVER_BIDDING
        )
        under_bidding_count = sum(
            1
            for adj in bid_adjustments
            if adj.optimization_status == OptimizationStatus.UNDER_BIDDING
        )

        # Generate key insights
        key_insights = []

        if total_conversions == 0:
            key_insights.append(
                "Critical: No conversions recorded across all campaigns"
            )
        elif total_cost / total_conversions > 100:
            key_insights.append(
                f"High cost per conversion: ${total_cost / total_conversions:.2f}"
            )

        if over_bidding_count > len(bid_adjustments) * 0.3:
            key_insights.append(
                f"{over_bidding_count} campaigns show signs of over-bidding"
            )

        if under_bidding_count > len(bid_adjustments) * 0.3:
            key_insights.append(
                f"{under_bidding_count} campaigns may benefit from bid increases"
            )

        potential_savings = sum(
            opt.estimated_cost_savings
            for opt in optimizations
            if opt.estimated_cost_savings
        )
        if potential_savings > 0:
            key_insights.append(f"Potential cost savings: ${potential_savings:.2f}")

        # Calculate data quality score
        campaigns_with_data = sum(
            1
            for adj in bid_adjustments
            if adj.performance.impressions > self.min_impressions
        )
        data_quality_score = (
            (campaigns_with_data / len(bid_adjustments) * 100) if bid_adjustments else 0
        )

        return BidAdjustmentAnalysisSummary(
            total_campaigns_analyzed=len(
                set(adj.campaign_name for adj in bid_adjustments)
            ),
            total_bid_adjustments=len(bid_adjustments),
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_conversions=total_conversions,
            total_cost=total_cost,
            avg_roi=avg_roi,
            optimal_adjustments_count=optimal_count,
            over_bidding_count=over_bidding_count,
            under_bidding_count=under_bidding_count,
            top_optimization_opportunities=optimizations[:5],
            key_insights=key_insights,
            data_quality_score=data_quality_score,
            analysis_confidence=min(data_quality_score, 90.0),  # Cap at 90%
        )

    def _determine_optimization_status(
        self, metrics: BidPerformanceMetrics
    ) -> OptimizationStatus:
        """Determine optimization status based on performance metrics.

        Args:
            metrics: Performance metrics

        Returns:
            OptimizationStatus
        """
        if metrics.impressions < self.min_impressions:
            return OptimizationStatus.NO_DATA

        # Check for over-bidding (high cost, low conversions)
        if metrics.conversions > 0:
            if metrics.cost_per_conversion > 100:  # High cost per conversion
                return OptimizationStatus.OVER_BIDDING
            elif metrics.cost_per_conversion < 30:  # Efficient conversions
                return OptimizationStatus.OPTIMAL
        else:
            if metrics.cost > 100:  # Spending with no conversions
                return OptimizationStatus.OVER_BIDDING

        # Check for under-bidding (low coverage, low impressions)
        if metrics.interaction_coverage < 50:
            return OptimizationStatus.UNDER_BIDDING

        # Check conversion rate
        if metrics.conversion_rate > 2:  # Good conversion rate
            return OptimizationStatus.OPTIMAL
        elif metrics.conversion_rate < 0.5:  # Poor conversion rate
            return OptimizationStatus.NEEDS_REVIEW

        return OptimizationStatus.NEEDS_REVIEW

    def _parse_interaction_type(self, value: str) -> InteractionType:
        """Parse interaction type from string value.

        Args:
            value: String value

        Returns:
            InteractionType
        """
        if not value or pd.isna(value):
            return InteractionType.UNKNOWN

        value_upper = str(value).upper()
        for interaction_type in InteractionType:
            if interaction_type.value.upper() in value_upper:
                return interaction_type

        return InteractionType.UNKNOWN

    def _parse_bid_modifier(self, value: Any) -> Optional[float]:
        """Parse bid modifier from string value.

        Args:
            value: String value (e.g., "--", "1.2", "+20%")

        Returns:
            Float bid modifier or None
        """
        if not value or value == "--" or pd.isna(value):
            return None

        try:
            # Handle percentage format
            if isinstance(value, str) and "%" in value:
                return 1.0 + (float(value.replace("%", "").replace("+", "")) / 100)
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value or 0.0
        """
        if pd.isna(value):
            return 0.0

        if isinstance(value, str):
            # Remove percentage sign and commas
            value = value.replace("%", "").replace(",", "").strip()
            if value == "--" or not value:
                return 0.0

        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to integer.

        Args:
            value: Value to convert

        Returns:
            Integer value or 0
        """
        if pd.isna(value):
            return 0

        if isinstance(value, str):
            # Remove commas
            value = value.replace(",", "").strip()
            if value == "--" or not value:
                return 0

        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> BidAdjustmentAnalysisResult:
        """Create empty result when no data is available.

        Args:
            customer_id: Customer ID
            start_date: Start date
            end_date: End date

        Returns:
            Empty BidAdjustmentAnalysisResult
        """
        return BidAdjustmentAnalysisResult(
            customer_id=customer_id,
            analysis_date=datetime.now(),
            start_date=start_date,
            end_date=end_date,
            bid_adjustments=[],
            bid_strategies=[],
            optimizations=[],
            competitive_insights=CompetitiveInsight(
                market_position="No Data",
                recommendations=["No bid adjustment data available for analysis"],
            ),
            summary=BidAdjustmentAnalysisSummary(
                total_campaigns_analyzed=0,
                total_bid_adjustments=0,
                total_impressions=0,
                total_clicks=0,
                total_conversions=0.0,
                total_cost=0.0,
                avg_roi=0.0,
                optimal_adjustments_count=0,
                over_bidding_count=0,
                under_bidding_count=0,
                top_optimization_opportunities=[],
                key_insights=["No data available for analysis"],
                data_quality_score=0.0,
                analysis_confidence=0.0,
            ),
            metadata={"error": "No bid adjustment data provided"},
        )
