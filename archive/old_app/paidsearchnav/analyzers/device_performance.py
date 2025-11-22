"""Device performance analyzer for mobile/desktop optimization opportunities."""

import logging
import statistics
from datetime import datetime
from typing import Any

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    DeviceInsight,
    DevicePerformanceAnalysisResult,
    DevicePerformanceData,
    DevicePerformanceSummary,
    DeviceShareMetrics,
    DeviceType,
)

logger = logging.getLogger(__name__)


class DevicePerformanceAnalyzer(Analyzer):
    """Analyzes device performance to identify mobile/desktop optimization opportunities."""

    # Business logic thresholds - extracted as constants for maintainability
    MOBILE_CPC_THRESHOLD = 1.4  # Mobile CPC 40% higher than desktop
    DESKTOP_OPPORTUNITY_THRESHOLD = (
        1.2  # Desktop conversion rate 20% higher than mobile
    )
    TABLET_UNDERPERFORMANCE_THRESHOLD = 0.7  # Tablet conversion rate 30% below average
    HIGH_PERFORMER_SCORE = 80.0  # Performance score threshold for high performers
    LOW_PERFORMER_SCORE = 40.0  # Performance score threshold for low performers
    MODERATE_PERFORMER_SCORE = (
        60.0  # Performance score threshold for moderate performers
    )

    def __init__(
        self,
        min_impressions: int = 100,
        min_clicks: int = 10,
        cpc_variance_threshold: float = 0.15,  # 15% CPC variance threshold
        conversion_rate_threshold: float = 0.20,  # 20% conversion rate threshold
    ):
        """Initialize the device performance analyzer.

        Args:
            min_impressions: Minimum impressions required for analysis
            min_clicks: Minimum clicks required for analysis
            cpc_variance_threshold: Threshold for significant CPC variance
            conversion_rate_threshold: Threshold for significant conversion rate variance
        """
        self.min_impressions = min_impressions
        self.min_clicks = min_clicks
        self.cpc_variance_threshold = cpc_variance_threshold
        self.conversion_rate_threshold = conversion_rate_threshold

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> DevicePerformanceAnalysisResult:
        """Analyze device performance for a customer.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (device_data)

        Returns:
            Device performance analysis result
        """
        logger.info(f"Starting device performance analysis for customer {customer_id}")

        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )

        try:
            # Get device data - this should be provided via kwargs in a real implementation
            # For now, we'll work with the data structure provided
            device_data_raw = kwargs.get("device_data", [])

            if not device_data_raw:
                logger.warning("No device data provided for analysis")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Convert raw data to structured models
            performance_data = self._convert_to_performance_data(
                device_data_raw, start_date, end_date
            )

            # Filter data by minimum thresholds
            filtered_data = self._filter_performance_data(performance_data)

            if not filtered_data:
                logger.warning("No device data meets minimum thresholds")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Calculate device shares
            device_shares = self._calculate_device_shares(filtered_data)

            # Analyze performance summary
            summary = self._analyze_performance_summary(
                customer_id, filtered_data, start_date, end_date
            )

            # Generate insights
            insights = self._generate_device_insights(filtered_data, summary)

            # Generate recommendations
            recommendations = self._generate_recommendations(insights, summary)

            # Calculate bid adjustment recommendations
            bid_adjustments = self._calculate_bid_adjustments(insights)

            # Create dashboard metrics
            dashboard_metrics = self._create_dashboard_metrics(summary, insights)

            result = DevicePerformanceAnalysisResult(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                performance_data=filtered_data,
                summary=summary,
                device_shares=device_shares,
                insights=insights,
                device_recommendations=recommendations,
                bid_adjustment_recommendations=bid_adjustments,
                dashboard_metrics=dashboard_metrics,
            )

            logger.info(f"Device analysis completed with {len(insights)} insights")
            return result

        except Exception as ex:
            logger.error(f"Device performance analysis failed: {ex}")
            raise

    def _convert_to_performance_data(
        self,
        raw_data: list[dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> list[DevicePerformanceData]:
        """Convert raw CSV data to structured performance data."""
        performance_data = []

        for row in raw_data:
            try:
                # Map device type from string to enum
                device_str = row.get("device", "Unknown")
                device_type = self._map_device_type(device_str)

                device_data = DevicePerformanceData(
                    customer_id=row.get("customer_id", "unknown"),
                    campaign_id=row.get("campaign_id", ""),
                    campaign_name=row.get("campaign_name", row.get("campaign", "")),
                    ad_group_id=row.get("ad_group_id"),
                    ad_group_name=row.get("ad_group_name", row.get("ad_group")),
                    device_type=device_type,
                    level=row.get("level", "Campaign"),
                    bid_adjustment=float(row.get("bid_adjustment", 0.0)),
                    ad_group_bid_adjustment=float(
                        row.get("ad_group_bid_adjustment", 0.0)
                    )
                    if row.get("ad_group_bid_adjustment")
                    else None,
                    impressions=int(row.get("impressions", 0)),
                    clicks=int(row.get("clicks", 0)),
                    conversions=float(row.get("conversions", 0.0)),
                    cost_micros=int(max(0.0, float(row.get("cost", 0.0))) * 1_000_000),
                    conversion_value_micros=int(
                        max(0.0, float(row.get("conversion_value", 0.0))) * 1_000_000
                    ),
                    start_date=start_date,
                    end_date=end_date,
                )

                performance_data.append(device_data)

            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid device data row: {e}")
                continue

        return performance_data

    def _map_device_type(self, device_str: str) -> DeviceType:
        """Map device string to DeviceType enum."""
        device_mapping = {
            "Mobile phones": DeviceType.MOBILE,
            "Computers": DeviceType.DESKTOP,
            "Tablets": DeviceType.TABLET,
            "Mobile": DeviceType.MOBILE,
            "Desktop": DeviceType.DESKTOP,
            "Tablet": DeviceType.TABLET,
        }
        return device_mapping.get(device_str, DeviceType.UNKNOWN)

    def _filter_performance_data(
        self, data: list[DevicePerformanceData]
    ) -> list[DevicePerformanceData]:
        """Filter performance data by minimum thresholds."""
        return [
            d
            for d in data
            if d.impressions >= self.min_impressions and d.clicks >= self.min_clicks
        ]

    def _calculate_device_shares(
        self, data: list[DevicePerformanceData]
    ) -> list[DeviceShareMetrics]:
        """Calculate share metrics for each device type."""
        if not data:
            return []

        # Aggregate by device type
        device_totals = {}
        for d in data:
            if d.device_type not in device_totals:
                device_totals[d.device_type] = {
                    "clicks": 0,
                    "impressions": 0,
                    "cost": 0.0,
                    "conversions": 0.0,
                    "conversion_value": 0.0,
                }

            device_totals[d.device_type]["clicks"] += d.clicks
            device_totals[d.device_type]["impressions"] += d.impressions
            device_totals[d.device_type]["cost"] += d.cost
            device_totals[d.device_type]["conversions"] += d.conversions
            device_totals[d.device_type]["conversion_value"] += d.conversion_value

        # Calculate totals across all devices
        total_clicks = sum(d.clicks for d in data)
        total_impressions = sum(d.impressions for d in data)
        total_cost = sum(d.cost for d in data)
        total_conversions = sum(d.conversions for d in data)
        total_conversion_value = sum(d.conversion_value for d in data)

        # Calculate shares
        shares = []
        for device_type, totals in device_totals.items():
            share = DeviceShareMetrics(
                device_type=device_type,
                click_share=totals["clicks"] / total_clicks
                if total_clicks > 0
                else 0.0,
                impression_share=totals["impressions"] / total_impressions
                if total_impressions > 0
                else 0.0,
                cost_share=totals["cost"] / total_cost if total_cost > 0 else 0.0,
                conversion_share=totals["conversions"] / total_conversions
                if total_conversions > 0
                else 0.0,
                conversion_value_share=totals["conversion_value"]
                / total_conversion_value
                if total_conversion_value > 0
                else 0.0,
            )
            shares.append(share)

        return shares

    def _analyze_performance_summary(
        self,
        customer_id: str,
        data: list[DevicePerformanceData],
        start_date: datetime,
        end_date: datetime,
    ) -> DevicePerformanceSummary:
        """Analyze overall device performance summary."""
        if not data:
            return self._create_empty_summary(customer_id, start_date, end_date)

        total_cost = sum(d.cost for d in data)
        total_conversions = sum(d.conversions for d in data)
        total_clicks = sum(d.clicks for d in data)
        total_impressions = sum(d.impressions for d in data)

        # Calculate averages
        cpc_values = [d.avg_cpc for d in data if d.avg_cpc > 0]
        conversion_rate_values = [
            d.conversion_rate for d in data if d.conversion_rate > 0
        ]
        roas_values = [d.roas for d in data if d.roas > 0]

        average_cpc = statistics.mean(cpc_values) if cpc_values else 0.0
        average_conversion_rate = (
            statistics.mean(conversion_rate_values) if conversion_rate_values else 0.0
        )
        average_roas = statistics.mean(roas_values) if roas_values else 0.0

        # Calculate device distribution
        device_distribution: dict[str, int] = {}
        for d in data:
            device_str = (
                d.device_type.value
                if hasattr(d.device_type, "value")
                else str(d.device_type)
            )
            device_distribution[device_str] = device_distribution.get(device_str, 0) + 1

        # Calculate variance metrics
        cpc_variance = self._calculate_cpc_variance(data)
        conversion_rate_variance = self._calculate_conversion_rate_variance(data)

        # Group data by device type once to avoid multiple iterations
        device_groups = self._group_data_by_device_type(data)
        mobile_data = device_groups.get(DeviceType.MOBILE, [])
        desktop_data = device_groups.get(DeviceType.DESKTOP, [])
        tablet_data = device_groups.get(DeviceType.TABLET, [])

        mobile_optimization_needed = self._needs_mobile_optimization(
            mobile_data, desktop_data
        )
        desktop_opportunity = self._has_desktop_opportunity(desktop_data, mobile_data)
        tablet_underperformance = self._has_tablet_underperformance(
            tablet_data, average_conversion_rate
        )

        return DevicePerformanceSummary(
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
            total_devices=len(set(d.device_type for d in data)),
            total_cost=total_cost,
            total_conversions=total_conversions,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            average_cpc=average_cpc,
            average_conversion_rate=average_conversion_rate,
            average_roas=average_roas,
            device_distribution=device_distribution,
            cpc_variance_percentage=cpc_variance,
            conversion_rate_variance_percentage=conversion_rate_variance,
            optimization_potential=max(cpc_variance, conversion_rate_variance),
            mobile_optimization_needed=mobile_optimization_needed,
            desktop_opportunity=desktop_opportunity,
            tablet_underperformance=tablet_underperformance,
        )

    def _calculate_cpc_variance(self, data: list[DevicePerformanceData]) -> float:
        """Calculate CPC variance percentage across devices."""
        cpc_values = [d.avg_cpc for d in data if d.avg_cpc > 0]
        if len(cpc_values) < 2:
            return 0.0

        min_cpc = min(cpc_values)
        max_cpc = max(cpc_values)

        return ((max_cpc - min_cpc) / min_cpc * 100) if min_cpc > 0 else 0.0

    def _calculate_conversion_rate_variance(
        self, data: list[DevicePerformanceData]
    ) -> float:
        """Calculate conversion rate variance percentage across devices."""
        conv_rate_values = [d.conversion_rate for d in data if d.conversion_rate > 0]
        if len(conv_rate_values) < 2:
            return 0.0

        min_rate = min(conv_rate_values)
        max_rate = max(conv_rate_values)

        return ((max_rate - min_rate) / min_rate * 100) if min_rate > 0 else 0.0

    def _group_data_by_device_type(
        self, data: list[DevicePerformanceData]
    ) -> dict[DeviceType, list[DevicePerformanceData]]:
        """Group performance data by device type to avoid multiple iterations.

        Args:
            data: List of device performance data

        Returns:
            Dictionary mapping device types to their respective data lists
        """
        from collections import defaultdict

        device_groups: dict[DeviceType, list[DevicePerformanceData]] = defaultdict(list)
        for d in data:
            device_groups[d.device_type].append(d)
        return dict(device_groups)

    def _needs_mobile_optimization(
        self,
        mobile_data: list[DevicePerformanceData],
        desktop_data: list[DevicePerformanceData],
    ) -> bool:
        """Check if mobile optimization is needed.

        Returns True if mobile CPC is significantly higher than desktop CPC.
        Uses MOBILE_CPC_THRESHOLD (40% higher) as the benchmark.

        Args:
            mobile_data: Performance data for mobile devices
            desktop_data: Performance data for desktop devices

        Returns:
            bool: True if mobile optimization is needed
        """
        if not mobile_data or not desktop_data:
            return False

        # Get CPC values with safety checks for empty lists
        mobile_cpc_values = [d.avg_cpc for d in mobile_data if d.avg_cpc > 0]
        desktop_cpc_values = [d.avg_cpc for d in desktop_data if d.avg_cpc > 0]

        if not mobile_cpc_values or not desktop_cpc_values:
            return False

        mobile_avg_cpc = statistics.mean(mobile_cpc_values)
        desktop_avg_cpc = statistics.mean(desktop_cpc_values)

        # Mobile optimization needed if mobile CPC exceeds threshold vs desktop
        return mobile_avg_cpc > desktop_avg_cpc * self.MOBILE_CPC_THRESHOLD

    def _has_desktop_opportunity(
        self,
        desktop_data: list[DevicePerformanceData],
        mobile_data: list[DevicePerformanceData],
    ) -> bool:
        """Check if desktop has untapped opportunity.

        Returns True if desktop conversion rate is significantly higher than mobile.
        Uses DESKTOP_OPPORTUNITY_THRESHOLD (20% higher) as the benchmark.

        Args:
            desktop_data: Performance data for desktop devices
            mobile_data: Performance data for mobile devices

        Returns:
            bool: True if desktop has expansion opportunity
        """
        if not desktop_data or not mobile_data:
            return False

        # Get conversion rate values with safety checks for empty lists
        desktop_conversion_values = [
            d.conversion_rate for d in desktop_data if d.conversion_rate > 0
        ]
        mobile_conversion_values = [
            d.conversion_rate for d in mobile_data if d.conversion_rate > 0
        ]

        if not desktop_conversion_values or not mobile_conversion_values:
            return False

        desktop_conversion_rate = statistics.mean(desktop_conversion_values)
        mobile_conversion_rate = statistics.mean(mobile_conversion_values)

        # Desktop opportunity if conversion rate exceeds threshold vs mobile
        return (
            desktop_conversion_rate
            > mobile_conversion_rate * self.DESKTOP_OPPORTUNITY_THRESHOLD
        )

    def _has_tablet_underperformance(
        self, tablet_data: list[DevicePerformanceData], average_conversion_rate: float
    ) -> bool:
        """Check if tablet is underperforming.

        Returns True if tablet conversion rate is significantly below average.
        Uses TABLET_UNDERPERFORMANCE_THRESHOLD (30% below) as the benchmark.

        Args:
            tablet_data: Performance data for tablet devices
            average_conversion_rate: Overall average conversion rate across all devices

        Returns:
            bool: True if tablet is underperforming
        """
        if not tablet_data or average_conversion_rate == 0:
            return False

        # Get conversion rate values with safety check for empty list
        tablet_conversion_values = [
            d.conversion_rate for d in tablet_data if d.conversion_rate > 0
        ]

        if not tablet_conversion_values:
            return False

        tablet_conversion_rate = statistics.mean(tablet_conversion_values)

        # Tablet underperforming if below threshold vs average
        return (
            tablet_conversion_rate
            < average_conversion_rate * self.TABLET_UNDERPERFORMANCE_THRESHOLD
        )

    def _generate_device_insights(
        self, data: list[DevicePerformanceData], summary: DevicePerformanceSummary
    ) -> list[DeviceInsight]:
        """Generate insights for each device type."""
        insights = []

        # Group data by device type (reuse the helper method)
        device_groups = self._group_data_by_device_type(data)

        for device_type, device_data in device_groups.items():
            # Aggregate metrics for this device type
            total_clicks = sum(d.clicks for d in device_data)
            total_cost = sum(d.cost for d in device_data)
            total_conversions = sum(d.conversions for d in device_data)

            avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0.0
            conversion_rate = (
                total_conversions / total_clicks if total_clicks > 0 else 0.0
            )
            total_conversion_value = sum(d.conversion_value for d in device_data)
            roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

            # Calculate vs average
            cpc_vs_avg = (
                avg_cpc / summary.average_cpc if summary.average_cpc > 0 else 1.0
            )
            conversion_rate_vs_avg = (
                conversion_rate / summary.average_conversion_rate
                if summary.average_conversion_rate > 0
                else 1.0
            )
            roas_vs_avg = (
                roas / summary.average_roas if summary.average_roas > 0 else 1.0
            )

            # Calculate shares
            click_share = (
                total_clicks / summary.total_clicks if summary.total_clicks > 0 else 0.0
            )
            cost_share = (
                total_cost / summary.total_cost if summary.total_cost > 0 else 0.0
            )
            conversion_share = (
                total_conversions / summary.total_conversions
                if summary.total_conversions > 0
                else 0.0
            )

            # Calculate performance score
            performance_score = self._calculate_performance_score(
                cpc_vs_avg, conversion_rate_vs_avg, roas_vs_avg
            )

            # Generate recommendations
            recommended_action = self._get_recommended_action(
                device_type, performance_score, cpc_vs_avg
            )
            bid_adjustment_rec = self._get_bid_adjustment_recommendation(
                device_type, cpc_vs_avg, conversion_rate_vs_avg
            )
            budget_rec = self._get_budget_recommendation(
                device_type, performance_score, cost_share
            )
            optimization_opportunity = self._get_optimization_opportunity(
                device_type, cpc_vs_avg, conversion_rate_vs_avg
            )

            insight = DeviceInsight(
                device_type=device_type,
                performance_score=performance_score,
                cpc_vs_average=cpc_vs_avg,
                conversion_rate_vs_average=conversion_rate_vs_avg,
                roas_vs_average=roas_vs_avg,
                click_share=click_share,
                cost_share=cost_share,
                conversion_share=conversion_share,
                recommended_action=recommended_action,
                bid_adjustment_recommendation=bid_adjustment_rec,
                budget_recommendation=budget_rec,
                optimization_opportunity=optimization_opportunity,
            )

            insights.append(insight)

        # Sort by performance score
        insights.sort(key=lambda x: x.performance_score, reverse=True)
        return insights

    def _calculate_performance_score(
        self, cpc_vs_avg: float, conversion_rate_vs_avg: float, roas_vs_avg: float
    ) -> float:
        """Calculate overall performance score (0-100) for a device type."""
        # Lower CPC is better, higher conversion rate and ROAS are better
        cpc_score = max(0, min(100, 100 - (cpc_vs_avg - 1) * 50))
        conversion_score = max(0, min(100, (conversion_rate_vs_avg - 1) * 25 + 50))
        roas_score = (
            max(0, min(100, (roas_vs_avg - 1) * 25 + 50)) if roas_vs_avg > 0 else 0
        )

        # Weighted average (CPC 40%, conversion rate 40%, ROAS 20%)
        return cpc_score * 0.4 + conversion_score * 0.4 + roas_score * 0.2

    def _get_recommended_action(
        self, device_type: DeviceType, score: float, cpc_vs_avg: float
    ) -> str:
        """Get recommended action for a device type."""
        if score >= self.HIGH_PERFORMER_SCORE:
            return "INCREASE_INVESTMENT"
        elif score >= self.MODERATE_PERFORMER_SCORE:
            return "MAINTAIN_CURRENT"
        elif score >= self.LOW_PERFORMER_SCORE:
            return "OPTIMIZE_TARGETING"
        else:
            return "REDUCE_INVESTMENT"

    def _get_bid_adjustment_recommendation(
        self, device_type: DeviceType, cpc_vs_avg: float, conversion_rate_vs_avg: float
    ) -> str:
        """Get bid adjustment recommendation for a device type."""
        if device_type == DeviceType.MOBILE:
            if cpc_vs_avg > 1.3:  # Mobile CPC 30% higher than average
                return "Decrease mobile bid adjustments by 15-25%"
            elif conversion_rate_vs_avg > 1.2:  # Mobile conversion rate 20% higher
                return "Increase mobile bid adjustments by 10-20%"
        elif device_type == DeviceType.DESKTOP:
            if conversion_rate_vs_avg > 1.3:  # Desktop conversion rate 30% higher
                return "Increase desktop bid adjustments by 15-25%"
            elif cpc_vs_avg < 0.8:  # Desktop CPC 20% lower
                return "Consider increasing desktop bid adjustments by 10-15%"
        elif device_type == DeviceType.TABLET:
            if conversion_rate_vs_avg < 0.7:  # Tablet conversion rate 30% lower
                return "Decrease tablet bid adjustments by 20-30% or exclude"

        return "Monitor current bid adjustments"

    def _get_budget_recommendation(
        self, device_type: DeviceType, score: float, cost_share: float
    ) -> str:
        """Get budget recommendation for a device type."""
        if score >= self.HIGH_PERFORMER_SCORE and cost_share < 0.3:
            return f"Increase {device_type.value} budget allocation by 15-25%"
        elif score <= self.LOW_PERFORMER_SCORE and cost_share > 0.2:
            return f"Decrease {device_type.value} budget allocation by 20-30%"
        elif score >= self.MODERATE_PERFORMER_SCORE:
            return f"Maintain current {device_type.value} budget allocation"
        else:
            return f"Consider redistributing {device_type.value} budget to higher-performing devices"

    def _get_optimization_opportunity(
        self, device_type: DeviceType, cpc_vs_avg: float, conversion_rate_vs_avg: float
    ) -> str:
        """Get optimization opportunity for a device type."""
        opportunities = []

        if device_type == DeviceType.MOBILE and cpc_vs_avg > 1.2:
            opportunities.append("Mobile CPC optimization needed")

        if conversion_rate_vs_avg < 0.8:
            opportunities.append(f"{device_type.value} landing page optimization")

        if device_type == DeviceType.DESKTOP and conversion_rate_vs_avg > 1.2:
            opportunities.append("Desktop expansion opportunity")

        if device_type == DeviceType.TABLET and conversion_rate_vs_avg < 0.6:
            opportunities.append("Consider tablet exclusion")

        return (
            "; ".join(opportunities)
            if opportunities
            else "No major optimization opportunities identified"
        )

    def _generate_recommendations(
        self, insights: list[DeviceInsight], summary: DevicePerformanceSummary
    ) -> list[str]:
        """Generate actionable recommendations based on insights."""
        recommendations = []

        # Mobile optimization
        if summary.mobile_optimization_needed:
            recommendations.append(
                "Mobile CPC is significantly higher than desktop - implement mobile bid adjustments or landing page optimization"
            )

        # Desktop opportunity
        if summary.desktop_opportunity:
            recommendations.append(
                "Desktop shows higher conversion rates - consider increasing desktop bid adjustments and budget allocation"
            )

        # Tablet underperformance
        if summary.tablet_underperformance:
            recommendations.append(
                "Tablet performance is significantly below average - consider reducing tablet bid adjustments or excluding tablets"
            )

        # CPC variance
        if summary.cpc_variance_percentage > 30:
            recommendations.append(
                f"High CPC variance ({summary.cpc_variance_percentage:.1f}%) across devices - implement device-specific bid adjustments"
            )

        # Top performing device
        top_device = (
            max(insights, key=lambda x: x.performance_score) if insights else None
        )
        if top_device and top_device.performance_score >= self.HIGH_PERFORMER_SCORE:
            recommendations.append(
                f"Increase investment in {top_device.device_type.value} - highest performing device type"
            )

        # Underperforming device
        worst_device = (
            min(insights, key=lambda x: x.performance_score) if insights else None
        )
        if worst_device and worst_device.performance_score <= self.LOW_PERFORMER_SCORE:
            recommendations.append(
                f"Review {worst_device.device_type.value} strategy - lowest performing device type"
            )

        return recommendations

    def _calculate_bid_adjustments(
        self, insights: list[DeviceInsight]
    ) -> dict[str, float]:
        """Calculate recommended bid adjustments for each device type."""
        bid_adjustments = {}

        for insight in insights:
            device_str = insight.device_type.value

            # Calculate bid adjustment based on performance vs average
            if insight.performance_score >= self.HIGH_PERFORMER_SCORE:
                # High performers get positive adjustments
                bid_adjustments[device_str] = min(
                    0.50, (insight.performance_score - 50) / 100
                )
            elif insight.performance_score <= self.LOW_PERFORMER_SCORE:
                # Low performers get negative adjustments
                bid_adjustments[device_str] = max(
                    -0.50, (insight.performance_score - 50) / 100
                )
            else:
                # Average performers maintain current adjustments
                bid_adjustments[device_str] = 0.0

        return bid_adjustments

    def _create_dashboard_metrics(
        self, summary: DevicePerformanceSummary, insights: list[DeviceInsight]
    ) -> dict[str, float]:
        """Create key metrics for dashboard display."""
        top_performer_score = insights[0].performance_score if insights else 0.0
        bottom_performer_score = insights[-1].performance_score if insights else 0.0

        return {
            "total_devices": float(summary.total_devices),
            "average_cpc": summary.average_cpc,
            "average_conversion_rate": summary.average_conversion_rate
            * 100,  # Convert to percentage
            "average_roas": summary.average_roas,
            "cpc_variance_percentage": summary.cpc_variance_percentage,
            "conversion_rate_variance_percentage": summary.conversion_rate_variance_percentage,
            "optimization_potential": summary.optimization_potential,
            "top_performer_score": top_performer_score,
            "bottom_performer_score": bottom_performer_score,
            "performance_spread": top_performer_score - bottom_performer_score,
            "mobile_optimization_needed": float(summary.mobile_optimization_needed),
            "desktop_opportunity": float(summary.desktop_opportunity),
            "tablet_underperformance": float(summary.tablet_underperformance),
        }

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> DevicePerformanceAnalysisResult:
        """Create empty result when no data is available."""
        return DevicePerformanceAnalysisResult(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            performance_data=[],
            summary=self._create_empty_summary(customer_id, start_date, end_date),
            device_shares=[],
            insights=[],
            device_recommendations=["No device data available for analysis"],
            bid_adjustment_recommendations={},
            dashboard_metrics={},
        )

    def _create_empty_summary(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> DevicePerformanceSummary:
        """Create empty summary when no data is available."""
        return DevicePerformanceSummary(
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
            total_devices=0,
            total_cost=0.0,
            total_conversions=0.0,
            total_clicks=0,
            total_impressions=0,
            average_cpc=0.0,
            average_conversion_rate=0.0,
            average_roas=0.0,
            device_distribution={},
            cpc_variance_percentage=0.0,
            conversion_rate_variance_percentage=0.0,
            optimization_potential=0.0,
        )

    def get_name(self) -> str:
        """Return analyzer name."""
        return "device_performance"

    def get_description(self) -> str:
        """Return analyzer description."""
        return "Analyzes device performance to identify mobile/desktop optimization opportunities"
