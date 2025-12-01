"""Keyword Match Type Analyzer for PaidSearchNav MCP server.

This analyzer evaluates keyword performance across different match types
(Broad, Phrase, Exact) to identify optimization opportunities.
"""

import logging
from collections import defaultdict
from typing import Any

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer

logger = logging.getLogger(__name__)


class KeywordMatchAnalyzer(BaseAnalyzer):
    """Analyzes keyword match types and identifies exact match opportunities.

    This analyzer:
    1. Fetches all keywords and search terms with automatic pagination
    2. Analyzes match type performance (BROAD, PHRASE, EXACT)
    3. Identifies exact match opportunities
    4. Returns only top 10 recommendations (not raw data)
    """

    def __init__(
        self,
        min_impressions: int = 50,
        high_cost_threshold: float = 100.0,
        low_roas_threshold: float = 1.5,
        max_broad_cpa_multiplier: float = 2.0,
        exact_match_ratio_threshold: float = 0.6,
    ):
        """Initialize the analyzer.

        Args:
            min_impressions: Minimum impressions to include in analysis (default: 50, balances data quality and coverage)
            high_cost_threshold: Cost threshold to flag high-cost keywords ($)
            low_roas_threshold: ROAS threshold to identify low ROI keywords
            max_broad_cpa_multiplier: Max acceptable CPA multiplier for broad match
            exact_match_ratio_threshold: Ratio of exact search terms to recommend conversion (0.6 = 60%)
        """
        self.min_impressions = min_impressions
        self.high_cost_threshold = high_cost_threshold
        self.low_roas_threshold = low_roas_threshold
        self.max_broad_cpa_multiplier = max_broad_cpa_multiplier
        self.exact_match_ratio_threshold = exact_match_ratio_threshold

    async def analyze(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        campaign_id: str | None = None,
    ) -> AnalysisSummary:
        """Analyze keyword match types and recommend exact match opportunities.

        Args:
            customer_id: Google Ads customer ID (10 digits, no dashes)
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)
            campaign_id: Optional campaign ID to limit scope

        Returns:
            AnalysisSummary with top 10 recommendations only (not raw data)
        """
        from paidsearchnav_mcp.server import (
            get_keywords,
            get_search_terms,
        )

        # Extract underlying functions from FastMCP FunctionTool objects
        get_keywords_fn = (
            get_keywords.fn if hasattr(get_keywords, "fn") else get_keywords
        )
        get_search_terms_fn = (
            get_search_terms.fn if hasattr(get_search_terms, "fn") else get_search_terms
        )

        logger.info(
            f"Starting keyword match analysis for customer {customer_id}, "
            f"date range {start_date} to {end_date}"
        )

        # Fetch all keywords with automatic pagination
        keywords = await self._fetch_all_keywords(
            get_keywords_fn, customer_id, start_date, end_date, campaign_id
        )

        # Fetch all search terms with automatic pagination
        search_terms = await self._fetch_all_search_terms(
            get_search_terms_fn, customer_id, start_date, end_date, campaign_id
        )

        logger.info(
            f"Fetched {len(keywords)} keywords and {len(search_terms)} search terms"
        )

        # Filter to active keywords with minimum impressions
        # Note: get_keywords returns flat structure with metrics at top level
        active_keywords = [
            k for k in keywords if k.get("impressions", 0) >= self.min_impressions
        ]

        logger.info(f"Analyzing {len(active_keywords)} active keywords")

        # Handle no-data scenario with helpful guidance
        if len(active_keywords) == 0:
            if len(keywords) == 0:
                # No keywords at all
                primary_issue = (
                    "No keywords found in this account. "
                    "This account may only have Performance Max or Display campaigns."
                )
            else:
                # Keywords exist but all filtered out
                max_impressions = max(
                    (k.get("impressions", 0) for k in keywords), default=0
                )
                suggested_threshold = max(10, max_impressions // 2)
                primary_issue = (
                    f"No keywords found with ≥{self.min_impressions} impressions. "
                    f"Found {len(keywords)} keywords with max {max_impressions} impressions. "
                    f"Try reducing min_impressions to {suggested_threshold} or extending the date range."
                )

            logger.warning(primary_issue)
            return AnalysisSummary(
                total_records_analyzed=0,
                estimated_monthly_savings=0.0,
                primary_issue=primary_issue,
                top_recommendations=[],
                implementation_steps=[
                    "Review account settings and ensure search campaigns are active",
                    "Consider extending the date range to capture more data",
                    f"Try reducing min_impressions threshold (currently {self.min_impressions})",
                ],
                analysis_period=f"{start_date} to {end_date}",
                customer_id=customer_id,
            )

        # Calculate match type performance
        match_type_stats = self._calculate_match_type_performance(active_keywords)

        # Find exact match opportunities
        exact_opportunities = self._find_exact_match_opportunities(
            active_keywords, search_terms
        )

        # Find high-cost broad match keywords to optimize
        high_cost_broad = self._find_high_cost_broad_keywords(
            active_keywords, match_type_stats
        )

        # Combine and rank all recommendations
        all_recommendations = exact_opportunities + high_cost_broad
        all_recommendations.sort(key=lambda x: x["estimated_savings"], reverse=True)
        top_10 = all_recommendations[:10]

        # Calculate total savings
        total_savings = sum(r["estimated_savings"] for r in top_10)

        # Determine primary issue
        primary_issue = self._identify_primary_issue(
            match_type_stats, exact_opportunities, high_cost_broad
        )

        # Generate implementation steps
        implementation_steps = self._generate_implementation_steps(top_10)

        logger.info(
            f"Analysis complete: {len(top_10)} recommendations, "
            f"${total_savings:,.2f} monthly savings"
        )

        return AnalysisSummary(
            total_records_analyzed=len(active_keywords),
            estimated_monthly_savings=total_savings,
            primary_issue=primary_issue,
            top_recommendations=top_10,
            implementation_steps=implementation_steps,
            analysis_period=f"{start_date} to {end_date}",
            customer_id=customer_id,
        )

    async def _fetch_all_keywords(
        self,
        get_keywords_fn: Any,
        customer_id: str,
        start_date: str,
        end_date: str,
        campaign_id: str | None,
    ) -> list[dict]:
        """Fetch all keywords with automatic pagination.

        Args:
            get_keywords_fn: get_keywords function from server
            customer_id: Google Ads customer ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            campaign_id: Optional campaign ID filter

        Returns:
            List of all keywords (all pages combined)
        """
        from paidsearchnav_mcp.server import KeywordsRequest

        all_keywords = []
        offset = 0
        limit = 500

        while True:
            request = KeywordsRequest(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                campaign_id=campaign_id,
                limit=limit,
                offset=offset,
            )
            result = await get_keywords_fn(request)

            if result["status"] != "success":
                logger.warning(
                    f"Failed to fetch keywords at offset {offset}: {result.get('message')}"
                )
                break

            all_keywords.extend(result["data"])

            if not result["metadata"]["pagination"]["has_more"]:
                break

            offset += limit

        return all_keywords

    async def _fetch_all_search_terms(
        self,
        get_search_terms_fn: Any,
        customer_id: str,
        start_date: str,
        end_date: str,
        campaign_id: str | None,
    ) -> list[dict]:
        """Fetch all search terms with automatic pagination.

        Args:
            get_search_terms_fn: get_search_terms function from server
            customer_id: Google Ads customer ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            campaign_id: Optional campaign ID filter

        Returns:
            List of all search terms (all pages combined)
        """
        from paidsearchnav_mcp.server import SearchTermsRequest

        all_search_terms = []
        offset = 0
        limit = 500

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
                logger.warning(
                    f"Failed to fetch search terms at offset {offset}: {result.get('message')}"
                )
                break

            all_search_terms.extend(result["data"])

            if not result["metadata"]["pagination"]["has_more"]:
                break

            offset += limit

        return all_search_terms

    def _calculate_match_type_performance(
        self, keywords: list[dict]
    ) -> dict[str, dict[str, Any]]:
        """Calculate aggregate statistics by match type.

        Args:
            keywords: List of keyword dictionaries

        Returns:
            Statistics by match type (BROAD, PHRASE, EXACT)
        """
        stats = defaultdict(
            lambda: {
                "count": 0,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
            }
        )

        for keyword in keywords:
            match_type = keyword.get("match_type", "BROAD")
            # Note: metrics are at top level, not nested under "metrics" key

            stats[match_type]["count"] += 1
            stats[match_type]["impressions"] += keyword.get("impressions", 0)
            stats[match_type]["clicks"] += keyword.get("clicks", 0)
            stats[match_type]["cost"] += keyword.get("cost", 0.0)
            stats[match_type]["conversions"] += keyword.get("conversions", 0.0)
            stats[match_type]["conversion_value"] += keyword.get(
                "conversion_value", 0.0
            )

        # Calculate derived metrics
        for match_type, data in stats.items():
            data["ctr"] = (
                (data["clicks"] / data["impressions"] * 100)
                if data["impressions"] > 0
                else 0.0
            )
            data["avg_cpc"] = (
                data["cost"] / data["clicks"] if data["clicks"] > 0 else 0.0
            )
            data["cpa"] = (
                data["cost"] / data["conversions"] if data["conversions"] > 0 else 0.0
            )
            data["roas"] = (
                data["conversion_value"] / data["cost"] if data["cost"] > 0 else 0.0
            )
            data["conversion_rate"] = (
                (data["conversions"] / data["clicks"] * 100)
                if data["clicks"] > 0
                else 0.0
            )

        return dict(stats)

    def _find_exact_match_opportunities(
        self, keywords: list[dict], search_terms: list[dict]
    ) -> list[dict]:
        """Find broad/phrase keywords where ≥60% of search terms are exact matches.

        Args:
            keywords: List of keywords
            search_terms: List of search terms

        Returns:
            List of recommendations with estimated savings
        """
        opportunities = []

        # Group search terms by keyword
        search_terms_by_keyword = defaultdict(list)
        for st in search_terms:
            keyword_text = st.get("keyword_text", "").lower().strip()
            if keyword_text:
                search_terms_by_keyword[keyword_text].append(st)

        # Check each broad/phrase keyword
        for keyword in keywords:
            match_type = keyword.get("match_type", "")
            if match_type not in ["BROAD", "PHRASE"]:
                continue

            keyword_text = keyword.get("keyword_text", "").lower().strip()
            if not keyword_text:
                continue

            keyword_search_terms = search_terms_by_keyword.get(keyword_text, [])
            if not keyword_search_terms:
                continue

            # Calculate what percentage are exact matches
            exact_matches = sum(
                1
                for st in keyword_search_terms
                if st.get("search_term", "").lower().strip() == keyword_text
            )

            total_terms = len(keyword_search_terms)
            exact_ratio = exact_matches / total_terms if total_terms > 0 else 0

            # If ≥60% are exact matches, recommend conversion
            if exact_ratio >= self.exact_match_ratio_threshold:
                # Note: metrics are at top level, not nested
                current_cost = keyword.get("cost", 0.0)

                # Estimate savings: exact match typically 20-30% cheaper than broad/phrase
                estimated_savings = current_cost * 0.25

                opportunities.append(
                    {
                        "keyword": keyword_text,
                        "current_match_type": match_type,
                        "recommended_match_type": "EXACT",
                        "current_cost": current_cost,
                        "estimated_savings": estimated_savings,
                        "exact_match_ratio": exact_ratio,
                        "reasoning": f"{exact_ratio:.0%} of search terms are exact matches",
                        "campaign": keyword.get("campaign_name", ""),
                        "ad_group": keyword.get("ad_group_name", ""),
                    }
                )

        return opportunities

    def _find_high_cost_broad_keywords(
        self, keywords: list[dict], match_type_stats: dict[str, dict[str, Any]]
    ) -> list[dict]:
        """Find broad match keywords with cost >$100 AND (ROAS <1.5 OR CPA >2× avg).

        Args:
            keywords: List of keywords
            match_type_stats: Match type statistics

        Returns:
            List of recommendations with estimated savings
        """
        recommendations = []

        # Calculate overall average CPA for comparison
        total_cost = sum(stats["cost"] for stats in match_type_stats.values())
        total_conversions = sum(
            stats["conversions"] for stats in match_type_stats.values()
        )
        overall_cpa = total_cost / total_conversions if total_conversions > 0 else 0.0

        for keyword in keywords:
            if keyword.get("match_type") != "BROAD":
                continue

            # Note: metrics are at top level, not nested
            cost = keyword.get("cost", 0.0)
            conversions = keyword.get("conversions", 0.0)
            conversion_value = keyword.get("conversion_value", 0.0)

            # Check for high cost
            if cost < self.high_cost_threshold:
                continue

            # Calculate ROAS and CPA
            roas = conversion_value / cost if cost > 0 else 0.0
            cpa = cost / conversions if conversions > 0 else float("inf")

            # Check for low ROI or high CPA
            is_low_roas = roas < self.low_roas_threshold
            is_high_cpa = cpa > (overall_cpa * self.max_broad_cpa_multiplier)

            if is_low_roas or is_high_cpa:
                # Estimate savings by assuming we pause or convert to phrase match
                # Conservative estimate: save 50% of current cost
                estimated_savings = cost * 0.5

                issue = []
                if is_low_roas:
                    issue.append(f"ROAS {roas:.2f} < target {self.low_roas_threshold}")
                if is_high_cpa:
                    issue.append(
                        f"CPA ${cpa:.2f} > {self.max_broad_cpa_multiplier}× avg ${overall_cpa:.2f}"
                    )

                recommendations.append(
                    {
                        "keyword": keyword.get("keyword_text", ""),
                        "current_match_type": "BROAD",
                        "recommended_match_type": "PHRASE or PAUSE",
                        "current_cost": cost,
                        "estimated_savings": estimated_savings,
                        "exact_match_ratio": 0.0,
                        "reasoning": "; ".join(issue),
                        "campaign": keyword.get("campaign_name", ""),
                        "ad_group": keyword.get("ad_group_name", ""),
                    }
                )

        # Sort by cost descending (prioritize high-cost issues)
        recommendations.sort(key=lambda x: x["current_cost"], reverse=True)

        return recommendations

    def _identify_primary_issue(
        self,
        match_type_stats: dict[str, dict[str, Any]],
        opportunities: list[dict],
        high_cost_broad: list[dict],
    ) -> str:
        """Determine the single most important issue.

        Args:
            match_type_stats: Match type statistics
            opportunities: Exact match opportunities
            high_cost_broad: High-cost broad keywords

        Returns:
            Description of the primary issue
        """
        # Calculate broad match spend ratio
        total_cost = sum(stats["cost"] for stats in match_type_stats.values())
        broad_cost = match_type_stats.get("BROAD", {}).get("cost", 0.0)
        broad_ratio = broad_cost / total_cost if total_cost > 0 else 0.0

        broad_roas = match_type_stats.get("BROAD", {}).get("roas", 0.0)

        # Determine primary issue based on severity
        if broad_ratio > 0.5 and broad_roas < self.low_roas_threshold:
            return f"Excessive broad match spend ({broad_ratio:.0%}) with low ROAS ({broad_roas:.2f})"
        elif len(high_cost_broad) > 5:
            return f"{len(high_cost_broad)} high-cost broad keywords wasting budget"
        elif len(opportunities) > 10:
            return f"{len(opportunities)} keywords ready for exact match conversion"
        elif broad_ratio > 0.6:
            return f"High broad match dependency ({broad_ratio:.0%}) increases CPA volatility"
        else:
            return "Match type distribution is relatively balanced"

    def _generate_implementation_steps(
        self, top_recommendations: list[dict]
    ) -> list[str]:
        """Generate prioritized action steps.

        Args:
            top_recommendations: Top 10 recommendations

        Returns:
            List of implementation steps
        """
        if not top_recommendations:
            return ["No immediate action required - match types are optimized"]

        # Handle 1-2 recommendations differently than 3+
        num_recs = len(top_recommendations)
        if num_recs <= 2:
            total_savings = sum(r["estimated_savings"] for r in top_recommendations)
            keyword_word = "keyword" if num_recs == 1 else "keywords"
            return [
                f"Week 1: Convert {num_recs} {keyword_word} to exact match ({self._format_currency(total_savings)}/month savings)",
                "Week 2: Monitor CPA/ROAS improvements and adjust bids accordingly",
                f"Note: Account is well-optimized - only {num_recs} minor optimization(s) found",
            ]

        # Handle 3+ recommendations (standard case)
        top_3_savings = sum(r["estimated_savings"] for r in top_recommendations[:3])
        remaining = num_recs - 3

        steps = [
            f"Week 1: Convert top 3 keywords to exact match ({self._format_currency(top_3_savings)}/month savings)",
            f"Week 2-3: Optimize remaining {remaining} keywords from recommendations",
            "Week 4: Monitor CPA/ROAS improvements and adjust bids accordingly",
        ]

        # Add note about broad match if relevant
        broad_count = sum(
            1 for r in top_recommendations if r["current_match_type"] == "BROAD"
        )
        if broad_count >= 7:
            steps.append(
                f"Note: Consider overall broad match strategy - {broad_count}/{len(top_recommendations)} recommendations involve broad match"
            )

        return steps
