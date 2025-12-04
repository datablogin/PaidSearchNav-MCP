"""Negative Keyword Conflict Analyzer for PaidSearchNav MCP server.

This analyzer identifies negative keywords blocking positive keywords.
"""

import logging
import re
from typing import Any

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer

logger = logging.getLogger(__name__)


class NegativeConflictAnalyzer(BaseAnalyzer):
    """Identify negative keywords that block positive keywords.

    Returns conflicts causing lost impression share and revenue.
    """

    async def analyze(
        self,
        customer_id: str,
        start_date: str = "",  # Not used for negative analysis
        end_date: str = "",  # Not used for negative analysis
        **kwargs: Any,
    ) -> AnalysisSummary:
        """Identify negative keyword conflicts.

        Args:
            customer_id: Google Ads customer ID
            start_date: Not used (negative keywords are not time-bound)
            end_date: Not used (negative keywords are not time-bound)

        Returns:
            AnalysisSummary with conflict recommendations
        """
        from paidsearchnav_mcp.server import (
            KeywordsRequest,
            NegativeKeywordsRequest,
            get_keywords,
            get_negative_keywords,
        )

        # Extract underlying functions from FastMCP FunctionTool objects
        get_keywords_fn = (
            get_keywords.fn if hasattr(get_keywords, "fn") else get_keywords
        )
        get_negative_keywords_fn = (
            get_negative_keywords.fn
            if hasattr(get_negative_keywords, "fn")
            else get_negative_keywords
        )

        logger.info(
            f"Starting negative keyword conflict analysis for customer {customer_id}"
        )

        # Fetch keywords with recent data for impact assessment
        # Use last 30 days if no dates provided
        if not start_date or not end_date:
            from datetime import datetime, timedelta

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        keywords_request = KeywordsRequest(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )
        keywords_result = await get_keywords_fn(keywords_request)
        keywords = keywords_result.get("data", [])

        # Fetch negative keywords
        negatives_request = NegativeKeywordsRequest(customer_id=customer_id)
        negatives_result = await get_negative_keywords_fn(negatives_request)
        negatives = negatives_result.get("data", [])

        logger.info(
            f"Analyzing {len(keywords)} keywords against {len(negatives)} negative keywords"
        )

        # Find conflicts
        conflicts = []
        for keyword in keywords:
            keyword_text = keyword.get("keyword_text", "").lower()
            if not keyword_text:
                continue

            for negative in negatives:
                negative_text = negative.get("text", "").lower()
                negative_match_type = negative.get("match_type", "BROAD")

                if self._is_conflict(keyword_text, negative_text, negative_match_type):
                    # Estimate revenue loss from blocking
                    # Note: get_keywords returns flat structure with metrics at top level
                    revenue_loss = keyword.get("conversion_value", 0.0)
                    impressions_lost = keyword.get("impressions", 0)

                    conflicts.append(
                        {
                            "positive_keyword": keyword_text,
                            "negative_keyword": negative_text,
                            "negative_match_type": negative_match_type,
                            "negative_level": negative.get("level", "UNKNOWN"),
                            "estimated_savings": revenue_loss,  # Actually revenue LOSS
                            "impressions_lost": impressions_lost,
                            "campaign": keyword.get("campaign_name", ""),
                            "reasoning": f"Negative '{negative_text}' blocks '{keyword_text}' (${revenue_loss:.2f} revenue)",
                        }
                    )

        # Sort by revenue loss descending and take top 10
        conflicts.sort(key=lambda x: x["estimated_savings"], reverse=True)
        top_10 = conflicts[:10]

        # Calculate total revenue loss
        total_revenue_loss = sum(c["estimated_savings"] for c in top_10)

        # Determine primary issue
        if len(conflicts) > 10:
            primary_issue = f"{len(conflicts)} negative keyword conflicts detected"
        elif total_revenue_loss > 1000:
            primary_issue = f"High-impact conflicts: ${total_revenue_loss:,.2f} monthly revenue loss"
        else:
            primary_issue = "Minor negative keyword conflicts detected"

        # Generate implementation steps
        implementation_steps = self._generate_implementation_steps(top_10)

        logger.info(
            f"Analysis complete: {len(top_10)} conflicts identified, "
            f"${total_revenue_loss:,.2f} monthly revenue loss"
        )

        return AnalysisSummary(
            total_records_analyzed=len(keywords),
            estimated_monthly_savings=total_revenue_loss,  # Actually revenue recovery
            primary_issue=primary_issue,
            top_recommendations=top_10,
            implementation_steps=implementation_steps,
            analysis_period=f"{start_date} to {end_date}",
            customer_id=customer_id,
        )

    def _is_conflict(
        self, keyword_text: str, negative_text: str, negative_match_type: str
    ) -> bool:
        """Check if a negative keyword blocks a positive keyword.

        Args:
            keyword_text: Positive keyword text (lowercase)
            negative_text: Negative keyword text (lowercase)
            negative_match_type: Negative match type (EXACT, PHRASE, BROAD)

        Returns:
            True if there's a conflict
        """
        if not keyword_text or not negative_text:
            return False

        if negative_match_type == "EXACT":
            # Exact match negative only blocks exact match
            return keyword_text == negative_text
        elif negative_match_type == "PHRASE":
            # Phrase match negative blocks if negative phrase is in positive
            return negative_text in keyword_text
        else:  # BROAD
            # Broad match negative blocks if all words are present
            negative_words = set(re.findall(r"\b\w+\b", negative_text))
            keyword_words = set(re.findall(r"\b\w+\b", keyword_text))
            return negative_words.issubset(keyword_words) and len(negative_words) > 0

    def _generate_implementation_steps(
        self, top_recommendations: list[dict]
    ) -> list[str]:
        """Generate prioritized action steps."""
        if not top_recommendations:
            return ["No negative keyword conflicts detected - account is clean"]

        return [
            f"Week 1: Review and remove top 3 conflicting negative keywords ({self._format_currency(sum(r['estimated_savings'] for r in top_recommendations[:3]))}/month revenue recovery)",
            f"Week 2: Resolve remaining {min(len(top_recommendations) - 3, 7)} conflicts",
            "Week 3: Monitor impression share to confirm positive keywords are serving",
            "Week 4: Audit negative keyword strategy to prevent future conflicts",
        ]
