"""Search Term Waste Analyzer for PaidSearchNav MCP server.

This analyzer identifies search terms generating spend with no conversion value.
"""

import logging
from typing import Any

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer

logger = logging.getLogger(__name__)


class SearchTermWasteAnalyzer(BaseAnalyzer):
    """Identify search terms generating spend with no conversion value.

    Returns top negative keyword recommendations to eliminate wasted budget.
    """

    def __init__(
        self,
        min_cost: float = 10.0,
        min_clicks: int = 5,
        min_impressions: int = 100,
    ):
        """Initialize the analyzer.

        Args:
            min_cost: Minimum cost to consider wasteful ($)
            min_clicks: Minimum clicks to establish pattern
            min_impressions: Minimum impressions for statistical significance
        """
        self.min_cost = min_cost
        self.min_clicks = min_clicks
        self.min_impressions = min_impressions

    async def analyze(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        **kwargs: Any,
    ) -> AnalysisSummary:
        """Identify search terms generating waste.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)

        Returns:
            AnalysisSummary with top negative keyword recommendations
        """
        from paidsearchnav_mcp.server import get_search_terms

        # Extract underlying function from FastMCP FunctionTool object
        get_search_terms_fn = (
            get_search_terms.fn if hasattr(get_search_terms, "fn") else get_search_terms
        )

        logger.info(f"Starting search term waste analysis for customer {customer_id}")

        # Fetch all search terms with automatic pagination
        all_search_terms = await self._fetch_all_search_terms(
            get_search_terms_fn, customer_id, start_date, end_date
        )

        logger.info(f"Analyzing {len(all_search_terms)} search terms")

        # Find wasteful search terms (no conversions with significant spend)
        wasteful_terms = []
        for st in all_search_terms:
            metrics = st.get("metrics", {})
            conversions = metrics.get("conversions", 0)
            cost = metrics.get("cost", 0.0)
            clicks = metrics.get("clicks", 0)
            impressions = metrics.get("impressions", 0)

            # Wasteful if: no conversions + significant spend/clicks
            if (
                conversions == 0
                and cost >= self.min_cost
                and clicks >= self.min_clicks
                and impressions >= self.min_impressions
            ):
                wasteful_terms.append(
                    {
                        "search_term": st.get("search_term", ""),
                        "cost": cost,
                        "clicks": clicks,
                        "impressions": impressions,
                        "estimated_savings": cost,  # Full cost saved by blocking
                        "campaign": st.get("campaign_name", ""),
                        "match_type": st.get("match_type", ""),
                        "reasoning": f"${cost:.2f} spent, {clicks} clicks, 0 conversions",
                    }
                )

        # Sort by cost descending and take top 10
        wasteful_terms.sort(key=lambda x: x["cost"], reverse=True)
        top_10 = wasteful_terms[:10]

        # Calculate total potential savings
        total_savings = sum(t["estimated_savings"] for t in top_10)

        # Determine primary issue
        if len(wasteful_terms) > 20:
            primary_issue = f"Significant waste: {len(wasteful_terms)} search terms with no conversions"
        elif total_savings > 500:
            primary_issue = (
                f"High-cost waste: ${total_savings:,.2f}/month on non-converting terms"
            )
        else:
            primary_issue = "Moderate waste detected in search terms"

        # Generate implementation steps
        implementation_steps = self._generate_implementation_steps(top_10)

        logger.info(
            f"Analysis complete: {len(top_10)} negative keyword recommendations, "
            f"${total_savings:,.2f} monthly savings"
        )

        return AnalysisSummary(
            total_records_analyzed=len(all_search_terms),
            estimated_monthly_savings=total_savings,
            primary_issue=primary_issue,
            top_recommendations=top_10,
            implementation_steps=implementation_steps,
            analysis_period=f"{start_date} to {end_date}",
            customer_id=customer_id,
        )

    async def _fetch_all_search_terms(
        self,
        get_search_terms_fn: Any,
        customer_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Fetch all search terms with automatic pagination."""
        from paidsearchnav_mcp.server import SearchTermsRequest

        all_search_terms = []
        offset = 0
        limit = 500

        while True:
            request = SearchTermsRequest(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            )
            result = await get_search_terms_fn(request)

            if result["status"] != "success":
                logger.warning(f"Failed to fetch search terms at offset {offset}")
                break

            all_search_terms.extend(result["data"])

            if not result["metadata"]["pagination"]["has_more"]:
                break

            offset += limit

        return all_search_terms

    def _generate_implementation_steps(
        self, top_recommendations: list[dict]
    ) -> list[str]:
        """Generate prioritized action steps."""
        if not top_recommendations:
            return [
                "No wasteful search terms identified - campaigns are well-optimized"
            ]

        top_3_savings = sum(r["estimated_savings"] for r in top_recommendations[:3])

        return [
            f"Week 1: Add top 3 wasteful terms as account-level negatives ({self._format_currency(top_3_savings)}/month savings)",
            f"Week 2: Add remaining {min(len(top_recommendations) - 3, 7)} terms to negative list",
            "Week 3: Monitor impression share and ensure no positive keywords are blocked",
            "Week 4: Review and refine negative keyword list based on new data",
        ]
