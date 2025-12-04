"""Geographic Performance Analyzer for PaidSearchNav MCP server.

This analyzer analyzes location performance and recommends bid adjustments.
"""

import logging
import statistics
from typing import Any

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer

logger = logging.getLogger(__name__)


class GeoPerformanceAnalyzer(BaseAnalyzer):
    """Analyze location performance and recommend bid adjustments.

    Returns locations to bid up, bid down, or exclude.
    """

    def __init__(
        self,
        min_impressions: int = 100,
        performance_threshold: float = 0.2,  # 20% deviation
    ):
        """Initialize the analyzer.

        Args:
            min_impressions: Minimum impressions required for analysis
            performance_threshold: Threshold for identifying outliers (0.2 = 20%)
        """
        self.min_impressions = min_impressions
        self.performance_threshold = performance_threshold

    async def analyze(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        **kwargs: Any,
    ) -> AnalysisSummary:
        """Analyze geographic performance.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)

        Returns:
            AnalysisSummary with geo performance recommendations
        """
        from paidsearchnav_mcp.server import CampaignsRequest, get_geo_performance

        # Extract underlying function from FastMCP FunctionTool object
        get_geo_performance_fn = (
            get_geo_performance.fn
            if hasattr(get_geo_performance, "fn")
            else get_geo_performance
        )

        logger.info(
            f"Starting geographic performance analysis for customer {customer_id}"
        )

        # Fetch geographic performance data
        request = CampaignsRequest(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )
        result = await get_geo_performance_fn(request)
        geo_data = result.get("data", [])

        logger.info(f"Analyzing {len(geo_data)} geographic locations")

        # Filter by minimum impressions
        filtered_data = [
            loc for loc in geo_data if loc.get("impressions", 0) >= self.min_impressions
        ]

        if not filtered_data:
            return AnalysisSummary(
                total_records_analyzed=len(geo_data),
                estimated_monthly_savings=0.0,
                primary_issue="Insufficient data for geo performance analysis",
                top_recommendations=[],
                implementation_steps=[
                    "Collect more data before analyzing geo performance"
                ],
                analysis_period=f"{start_date} to {end_date}",
                customer_id=customer_id,
            )

        # Calculate average CPA and ROAS
        locations_with_conversions = [
            loc for loc in filtered_data if loc.get("conversions", 0) > 0
        ]

        if locations_with_conversions:
            avg_cpa = statistics.mean(
                loc.get("cost_micros", 0) / 1_000_000 / loc.get("conversions", 1)
                for loc in locations_with_conversions
                if loc.get("conversions", 0) > 0
            )
            avg_roas = statistics.mean(
                loc.get("conversion_value_micros", 0)
                / 1_000_000
                / max(loc.get("cost_micros", 0) / 1_000_000, 0.001)
                for loc in locations_with_conversions
                if loc.get("cost_micros", 0) > 0
            )
        else:
            avg_cpa = 0.0
            avg_roas = 0.0

        # Identify locations for bid adjustments
        recommendations = []

        for loc in filtered_data:
            location_name = loc.get("location_name", "Unknown")
            cost = loc.get("cost_micros", 0) / 1_000_000
            conversions = loc.get("conversions", 0)
            revenue = loc.get("conversion_value_micros", 0) / 1_000_000

            if conversions == 0:
                # No conversions - consider excluding or bid down
                recommendations.append(
                    {
                        "location": location_name,
                        "action": "BID_DOWN or EXCLUDE",
                        "current_cost": cost,
                        "estimated_savings": cost
                        * 0.5,  # Save 50% by bid down or 100% by exclude
                        "reasoning": f"${cost:.2f} spent with 0 conversions",
                        "metric": "No conversions",
                    }
                )
            else:
                cpa = cost / max(conversions, 0.001)  # Protect against division by zero
                roas = revenue / max(cost, 0.001)  # Protect against division by zero

                # High performers (low CPA or high ROAS)
                if cpa < avg_cpa * (
                    1 - self.performance_threshold
                ) or roas > avg_roas * (1 + self.performance_threshold):
                    # Negative savings = opportunity cost of NOT increasing bids
                    potential_gain = cost * 0.3  # Could gain 30% more with bid increase
                    recommendations.append(
                        {
                            "location": location_name,
                            "action": "BID_UP",
                            "current_cost": cost,
                            "estimated_savings": -potential_gain,  # Negative = investment
                            "reasoning": f"CPA ${cpa:.2f} vs avg ${avg_cpa:.2f}, ROAS {roas:.2f} vs avg {avg_roas:.2f}",
                            "metric": f"High performer: {cpa / avg_cpa:.1%} of avg CPA",
                        }
                    )

                # Low performers (high CPA or low ROAS)
                elif cpa > avg_cpa * (
                    1 + self.performance_threshold
                ) or roas < avg_roas * (1 - self.performance_threshold):
                    savings = cost * 0.3  # Save 30% by bid down
                    recommendations.append(
                        {
                            "location": location_name,
                            "action": "BID_DOWN",
                            "current_cost": cost,
                            "estimated_savings": savings,
                            "reasoning": f"CPA ${cpa:.2f} vs avg ${avg_cpa:.2f}, ROAS {roas:.2f} vs avg {avg_roas:.2f}",
                            "metric": f"Low performer: {cpa / avg_cpa:.1%} of avg CPA",
                        }
                    )

        # Sort by absolute savings/impact and take top 10
        recommendations.sort(key=lambda x: abs(x["estimated_savings"]), reverse=True)
        top_10 = recommendations[:10]

        # Calculate total savings (exclude bid-up recommendations from savings)
        total_savings = sum(
            r["estimated_savings"] for r in top_10 if r["estimated_savings"] > 0
        )

        # Determine primary issue
        bid_down_count = sum(1 for r in recommendations if "DOWN" in r["action"])
        exclude_count = sum(1 for r in recommendations if "EXCLUDE" in r["action"])

        if bid_down_count + exclude_count > 10:
            primary_issue = f"{bid_down_count + exclude_count} underperforming locations wasting budget"
        elif total_savings > 500:
            primary_issue = (
                f"Geographic inefficiencies: ${total_savings:,.2f}/month wasted"
            )
        else:
            primary_issue = "Minor geographic performance variations detected"

        # Generate implementation steps
        implementation_steps = self._generate_implementation_steps(top_10)

        logger.info(
            f"Analysis complete: {len(top_10)} geo recommendations, "
            f"${total_savings:,.2f} monthly savings"
        )

        return AnalysisSummary(
            total_records_analyzed=len(filtered_data),
            estimated_monthly_savings=total_savings,
            primary_issue=primary_issue,
            top_recommendations=top_10,
            implementation_steps=implementation_steps,
            analysis_period=f"{start_date} to {end_date}",
            customer_id=customer_id,
        )

    def _generate_implementation_steps(
        self, top_recommendations: list[dict]
    ) -> list[str]:
        """Generate prioritized action steps."""
        if not top_recommendations:
            return ["No geographic adjustments needed - performance is balanced"]

        bid_up = [r for r in top_recommendations if r["action"] == "BID_UP"]
        bid_down = [r for r in top_recommendations if r["action"] == "BID_DOWN"]
        exclude = [r for r in top_recommendations if "EXCLUDE" in r["action"]]

        return [
            f"Week 1: Exclude or bid down {len(exclude) + len(bid_down)} underperforming locations",
            f"Week 2: Increase bids by 20-30% for {len(bid_up)} high-performing locations",
            "Week 3: Monitor performance changes and adjust as needed",
            "Week 4: Review location targeting radius and DMA settings",
        ]
