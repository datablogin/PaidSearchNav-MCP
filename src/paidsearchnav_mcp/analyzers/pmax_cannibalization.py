"""Performance Max Cannibalization Analyzer for PaidSearchNav MCP server.

This analyzer detects Performance Max campaigns cannibalizing Search campaigns.
"""

import logging
from typing import Any

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer

logger = logging.getLogger(__name__)


class PMaxCannibalizationAnalyzer(BaseAnalyzer):
    """Detect Performance Max campaigns cannibalizing Search campaigns.

    Returns PMax negative keywords to prevent traffic overlap.
    """

    def __init__(
        self,
        min_overlap_cost: float = 20.0,
        overlap_threshold: float = 0.2,  # 20% overlap is significant
    ):
        """Initialize the analyzer.

        Args:
            min_overlap_cost: Minimum combined cost to flag overlap ($)
            overlap_threshold: Threshold for flagging overlap (0.2 = 20%)
        """
        self.min_overlap_cost = min_overlap_cost
        self.overlap_threshold = overlap_threshold

    async def analyze(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        **kwargs: Any,
    ) -> AnalysisSummary:
        """Detect PMax/Search campaign cannibalization.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)

        Returns:
            AnalysisSummary with PMax negative keyword recommendations
        """
        from paidsearchnav_mcp.server import (
            CampaignsRequest,
            get_campaigns,
            get_search_terms,
        )

        # Extract underlying functions from FastMCP FunctionTool objects
        get_campaigns_fn = (
            get_campaigns.fn if hasattr(get_campaigns, "fn") else get_campaigns
        )
        get_search_terms_fn = (
            get_search_terms.fn if hasattr(get_search_terms, "fn") else get_search_terms
        )

        logger.info(
            f"Starting PMax cannibalization analysis for customer {customer_id}"
        )

        # Fetch campaigns to identify PMax and Search campaigns
        campaigns_request = CampaignsRequest(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )
        campaigns_result = await get_campaigns_fn(campaigns_request)
        campaigns = campaigns_result.get("data", [])

        pmax_campaigns = [c for c in campaigns if c.get("type") == "PERFORMANCE_MAX"]
        search_campaigns = [c for c in campaigns if c.get("type") == "SEARCH"]

        if not pmax_campaigns:
            return AnalysisSummary(
                total_records_analyzed=0,
                estimated_monthly_savings=0.0,
                primary_issue="No Performance Max campaigns found",
                top_recommendations=[],
                implementation_steps=["Create Performance Max campaigns to analyze"],
                analysis_period=f"{start_date} to {end_date}",
                customer_id=customer_id,
            )

        if not search_campaigns:
            return AnalysisSummary(
                total_records_analyzed=0,
                estimated_monthly_savings=0.0,
                primary_issue="No Search campaigns found - no cannibalization possible",
                top_recommendations=[],
                implementation_steps=["No action needed - only PMax campaigns exist"],
                analysis_period=f"{start_date} to {end_date}",
                customer_id=customer_id,
            )

        logger.info(
            f"Analyzing {len(pmax_campaigns)} PMax campaigns vs {len(search_campaigns)} Search campaigns"
        )

        # Fetch search terms for both campaign types IN PARALLEL (performance optimization)
        import asyncio

        pmax_search_terms, search_search_terms = await asyncio.gather(
            self._fetch_search_terms_for_campaigns(
                get_search_terms_fn,
                customer_id,
                start_date,
                end_date,
                [c["campaign_id"] for c in pmax_campaigns],
            ),
            self._fetch_search_terms_for_campaigns(
                get_search_terms_fn,
                customer_id,
                start_date,
                end_date,
                [c["campaign_id"] for c in search_campaigns],
            ),
        )

        # Find overlapping search terms
        pmax_terms_map = {
            st.get("search_term", "").lower(): st for st in pmax_search_terms
        }
        search_terms_map = {
            st.get("search_term", "").lower(): st for st in search_search_terms
        }

        overlapping_terms = set(pmax_terms_map.keys()) & set(search_terms_map.keys())

        logger.info(f"Found {len(overlapping_terms)} overlapping search terms")

        # Analyze overlaps and create recommendations
        recommendations = []

        for term in overlapping_terms:
            pmax_st = pmax_terms_map[term]
            search_st = search_terms_map[term]

            pmax_cost = pmax_st.get("metrics", {}).get("cost", 0.0)
            search_cost = search_st.get("metrics", {}).get("cost", 0.0)
            total_cost = pmax_cost + search_cost

            # Only flag if total cost exceeds threshold
            if total_cost < self.min_overlap_cost:
                continue

            # Calculate performance metrics
            pmax_conversions = pmax_st.get("metrics", {}).get("conversions", 0)
            search_conversions = search_st.get("metrics", {}).get("conversions", 0)

            pmax_cpa = (
                pmax_cost / pmax_conversions if pmax_conversions > 0 else float("inf")
            )
            search_cpa = (
                search_cost / search_conversions
                if search_conversions > 0
                else float("inf")
            )

            # Determine recommendation
            if search_cpa < pmax_cpa:
                # Search performs better - add negative to PMax
                estimated_savings = (
                    pmax_cost * 0.5
                )  # Conservative: save 50% of PMax cost
                action = "Add to PMax negative keywords"
                reasoning = f"Search CPA ${search_cpa:.2f} < PMax CPA ${pmax_cpa:.2f}"
            elif pmax_cpa < search_cpa:
                # PMax performs better - could pause in Search
                estimated_savings = search_cost * 0.5
                action = "Consider pausing in Search campaign"
                reasoning = f"PMax CPA ${pmax_cpa:.2f} < Search CPA ${search_cpa:.2f}"
            else:
                # Similar performance - still wasteful overlap
                estimated_savings = total_cost * 0.3  # Save 30% by optimization
                action = "Add to PMax negatives or adjust Search bids"
                reasoning = f"Similar performance, ${total_cost:.2f} overlap cost"

            recommendations.append(
                {
                    "search_term": term,
                    "action": action,
                    "pmax_cost": pmax_cost,
                    "search_cost": search_cost,
                    "total_cost": total_cost,
                    "estimated_savings": estimated_savings,
                    "reasoning": reasoning,
                    "metric": f"Overlap: ${total_cost:.2f}/month",
                }
            )

        # Sort by total cost descending and take top 10
        recommendations.sort(key=lambda x: x["total_cost"], reverse=True)
        top_10 = recommendations[:10]

        # Calculate total savings
        total_savings = sum(r["estimated_savings"] for r in top_10)
        total_overlap_cost = sum(r["total_cost"] for r in recommendations)

        # Calculate overlap percentage
        total_pmax_cost = sum(
            pmax_st.get("metrics", {}).get("cost", 0.0) for pmax_st in pmax_search_terms
        )
        overlap_percentage = (
            (total_overlap_cost / total_pmax_cost * 100) if total_pmax_cost > 0 else 0.0
        )

        # Determine primary issue
        if overlap_percentage > 50:
            primary_issue = f"Severe cannibalization: {overlap_percentage:.0f}% of PMax traffic overlaps with Search"
        elif overlap_percentage > 20:
            primary_issue = (
                f"Moderate cannibalization: {overlap_percentage:.0f}% overlap detected"
            )
        elif total_overlap_cost > 500:
            primary_issue = f"High-cost overlap: ${total_overlap_cost:,.2f}/month on duplicate traffic"
        else:
            primary_issue = "Minor overlap between PMax and Search campaigns"

        # Generate implementation steps
        implementation_steps = self._generate_implementation_steps(
            top_10, overlap_percentage
        )

        logger.info(
            f"Analysis complete: {len(top_10)} cannibalization recommendations, "
            f"${total_savings:,.2f} monthly savings"
        )

        return AnalysisSummary(
            total_records_analyzed=len(overlapping_terms),
            estimated_monthly_savings=total_savings,
            primary_issue=primary_issue,
            top_recommendations=top_10,
            implementation_steps=implementation_steps,
            analysis_period=f"{start_date} to {end_date}",
            customer_id=customer_id,
        )

    async def _fetch_search_terms_for_campaigns(
        self,
        get_search_terms_fn: Any,
        customer_id: str,
        start_date: str,
        end_date: str,
        campaign_ids: list[str],
    ) -> list[dict]:
        """Fetch search terms for specific campaigns in parallel.

        Performance optimizations:
        - Larger page size (2000 vs 500) reduces API calls by 75%
        - Parallel fetching across campaigns reduces wall-clock time
        """
        import asyncio

        from paidsearchnav_mcp.server import SearchTermsRequest

        async def fetch_campaign_terms(campaign_id: str) -> list[dict]:
            """Fetch all search terms for a single campaign."""
            all_terms = []
            offset = 0
            limit = 2000  # Increased from 500 (75% fewer API calls)

            while True:
                request = SearchTermsRequest(
                    customer_id=customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    campaign_id=campaign_id,
                    limit=limit,
                    offset=offset,
                )
                result = await get_search_terms_fn(request)

                if result["status"] != "success":
                    break

                all_terms.extend(result["data"])

                if not result["metadata"]["pagination"]["has_more"]:
                    break

                offset += limit

            return all_terms

        # Fetch all campaigns in parallel
        campaign_results = await asyncio.gather(
            *[fetch_campaign_terms(campaign_id) for campaign_id in campaign_ids]
        )

        # Flatten results
        all_terms = []
        for terms in campaign_results:
            all_terms.extend(terms)

        return all_terms

    def _generate_implementation_steps(
        self, top_recommendations: list[dict], overlap_percentage: float
    ) -> list[str]:
        """Generate prioritized action steps."""
        if not top_recommendations:
            return [
                "No PMax/Search cannibalization detected - campaigns are well-separated"
            ]

        if overlap_percentage > 50:
            urgency = "CRITICAL"
        elif overlap_percentage > 20:
            urgency = "HIGH"
        else:
            urgency = "MEDIUM"

        top_3_savings = sum(r["estimated_savings"] for r in top_recommendations[:3])

        return [
            f"{urgency} PRIORITY: Week 1: Add top 3 overlapping terms to PMax negative keyword list ({self._format_currency(top_3_savings)}/month savings)",
            f"Week 2: Add remaining {min(len(top_recommendations) - 3, 7)} terms to PMax negatives",
            "Week 3: Monitor Search campaign impression share and performance improvements",
            "Week 4: Review overall PMax/Search strategy and consider campaign restructuring",
        ]
