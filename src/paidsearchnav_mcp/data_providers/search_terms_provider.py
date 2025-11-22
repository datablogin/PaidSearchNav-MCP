"""Specialized provider for search terms data with advanced filtering and analysis."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.data_providers.base import DataProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SearchTermsProvider:
    """Specialized provider for search terms data with enhanced capabilities.

    This provider wraps a base DataProvider and adds specialized functionality
    for working with search terms data, including:
    - Advanced filtering and segmentation
    - Local intent detection
    - Performance categorization
    - Search term analysis utilities
    """

    def __init__(self, data_provider: DataProvider):
        """Initialize the search terms provider.

        Args:
            data_provider: Base data provider to use for fetching data
        """
        self.data_provider = data_provider

    async def get_search_terms_with_local_intent(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[SearchTerm]:
        """Get search terms that have local intent indicators.

        Local intent indicators include:
        - "near me" phrases
        - City/location names
        - "nearby", "local", "closest" keywords
        - ZIP codes
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        local_indicators = [
            "near me",
            "nearby",
            "closest",
            "local",
            "in my area",
            "around me",
            "close to me",
            "near my location",
        ]

        local_terms = []
        for term in all_terms:
            term_lower = term.search_term.lower()

            # Check for local indicators
            has_local_intent = any(
                indicator in term_lower for indicator in local_indicators
            )

            # Check for ZIP code pattern (5 digits)
            import re

            has_zip = bool(re.search(r"\b\d{5}\b", term.search_term))

            if has_local_intent or has_zip:
                local_terms.append(term)

        logger.info(
            f"Found {len(local_terms)} search terms with local intent out of {len(all_terms)}"
        )
        return local_terms

    async def get_high_cost_low_conversion_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        min_cost: float = 100.0,
        max_conversion_rate: float = 0.01,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[SearchTerm]:
        """Get search terms with high cost but low conversion rate.

        These are prime candidates for negative keywords.
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        wasteful_terms = []
        for term in all_terms:
            if term.metrics.cost >= min_cost:
                conversion_rate = (
                    term.metrics.conversions / term.metrics.clicks
                    if term.metrics.clicks > 0
                    else 0
                )
                if conversion_rate <= max_conversion_rate:
                    wasteful_terms.append(term)

        # Sort by cost descending to prioritize biggest waste
        wasteful_terms.sort(key=lambda t: t.metrics.cost, reverse=True)

        total_waste = sum(t.metrics.cost for t in wasteful_terms)
        logger.info(
            f"Found {len(wasteful_terms)} high-cost low-conversion terms "
            f"totaling ${total_waste:.2f} in spend"
        )

        return wasteful_terms

    async def get_brand_vs_non_brand_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        brand_keywords: list[str],
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> tuple[list[SearchTerm], list[SearchTerm]]:
        """Segment search terms into brand and non-brand categories.

        Args:
            brand_keywords: List of brand-related keywords to identify brand terms

        Returns:
            Tuple of (brand_terms, non_brand_terms)
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        brand_terms = []
        non_brand_terms = []

        # Normalize brand keywords for comparison
        brand_keywords_lower = [kw.lower() for kw in brand_keywords]

        for term in all_terms:
            term_lower = term.search_term.lower()
            is_brand = any(brand_kw in term_lower for brand_kw in brand_keywords_lower)

            if is_brand:
                brand_terms.append(term)
            else:
                non_brand_terms.append(term)

        logger.info(
            f"Segmented {len(all_terms)} terms into "
            f"{len(brand_terms)} brand and {len(non_brand_terms)} non-brand"
        )

        return brand_terms, non_brand_terms

    async def get_search_terms_by_performance_tier(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> dict[str, list[SearchTerm]]:
        """Categorize search terms by performance tiers.

        Tiers:
        - top_performers: High ROAS (>300%), good volume
        - good_performers: Positive ROAS (100-300%)
        - break_even: Near break-even (50-100% ROAS)
        - poor_performers: Low ROAS (<50%)
        - no_conversions: Zero conversions with significant spend
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        tiers = {
            "top_performers": [],
            "good_performers": [],
            "break_even": [],
            "poor_performers": [],
            "no_conversions": [],
        }

        for term in all_terms:
            if term.metrics.cost == 0:
                continue  # Skip terms with no spend

            roas = (
                (term.metrics.conversion_value / term.metrics.cost * 100)
                if term.metrics.cost > 0
                else 0
            )

            if (
                term.metrics.conversions == 0 and term.metrics.cost >= 50
            ):  # Significant spend threshold
                tiers["no_conversions"].append(term)
            elif roas >= 300:
                tiers["top_performers"].append(term)
            elif roas >= 100:
                tiers["good_performers"].append(term)
            elif roas >= 50:
                tiers["break_even"].append(term)
            else:
                tiers["poor_performers"].append(term)

        # Sort each tier by cost descending
        for tier_name, terms in tiers.items():
            terms.sort(key=lambda t: t.metrics.cost, reverse=True)
            logger.info(f"{tier_name}: {len(terms)} terms")

        return tiers

    async def get_question_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[SearchTerm]:
        """Get search terms that are questions.

        Identifies terms starting with question words like:
        what, where, when, why, how, who, which, etc.
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        question_words = [
            "what",
            "where",
            "when",
            "why",
            "how",
            "who",
            "which",
            "is",
            "are",
            "can",
            "does",
            "do",
            "will",
            "should",
        ]

        question_terms = []
        for term in all_terms:
            first_word = term.search_term.lower().split()[0] if term.search_term else ""
            if first_word in question_words:
                question_terms.append(term)

        logger.info(f"Found {len(question_terms)} question search terms")
        return question_terms

    async def get_competitor_related_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        competitor_names: list[str],
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[SearchTerm]:
        """Get search terms that mention competitor names.

        Args:
            competitor_names: List of competitor brand names to check
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        competitor_names_lower = [name.lower() for name in competitor_names]

        competitor_terms = []
        for term in all_terms:
            term_lower = term.search_term.lower()
            if any(comp in term_lower for comp in competitor_names_lower):
                competitor_terms.append(term)

        logger.info(f"Found {len(competitor_terms)} competitor-related search terms")
        return competitor_terms

    async def get_search_term_summary_stats(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics for search terms.

        Returns comprehensive metrics including:
        - Total terms, impressions, clicks, cost, conversions
        - Average CTR, CPC, conversion rate, ROAS
        - Top performing terms
        - Worst performing terms
        """
        all_terms = await self.data_provider.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        if not all_terms:
            return {
                "total_terms": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_cost": 0.0,
                "total_conversions": 0.0,
                "total_conversion_value": 0.0,
                "avg_ctr": 0.0,
                "avg_cpc": 0.0,
                "avg_conversion_rate": 0.0,
                "avg_roas": 0.0,
                "top_terms_by_conversions": [],
                "top_terms_by_cost": [],
                "worst_terms_by_waste": [],
            }

        # Calculate totals
        total_impressions = sum(t.metrics.impressions for t in all_terms)
        total_clicks = sum(t.metrics.clicks for t in all_terms)
        total_cost = sum(t.metrics.cost for t in all_terms)
        total_conversions = sum(t.metrics.conversions for t in all_terms)
        total_conversion_value = sum(t.metrics.conversion_value for t in all_terms)

        # Calculate averages
        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )
        avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0
        avg_conversion_rate = (
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        )
        avg_roas = (total_conversion_value / total_cost * 100) if total_cost > 0 else 0

        # Get top performers
        terms_with_conversions = [t for t in all_terms if t.metrics.conversions > 0]
        top_by_conversions = sorted(
            terms_with_conversions, key=lambda t: t.metrics.conversions, reverse=True
        )[:10]

        # Get highest cost terms
        top_by_cost = sorted(all_terms, key=lambda t: t.metrics.cost, reverse=True)[:10]

        # Get worst performers (high cost, no conversions)
        no_conversion_terms = [
            t for t in all_terms if t.metrics.conversions == 0 and t.metrics.cost > 0
        ]
        worst_by_waste = sorted(
            no_conversion_terms, key=lambda t: t.metrics.cost, reverse=True
        )[:10]

        return {
            "total_terms": len(all_terms),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_cost": round(total_cost, 2),
            "total_conversions": round(total_conversions, 2),
            "total_conversion_value": round(total_conversion_value, 2),
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpc": round(avg_cpc, 2),
            "avg_conversion_rate": round(avg_conversion_rate, 2),
            "avg_roas": round(avg_roas, 2),
            "top_terms_by_conversions": [
                {
                    "term": t.search_term,
                    "conversions": t.metrics.conversions,
                    "cost": t.metrics.cost,
                    "roas": round(
                        (t.metrics.conversion_value / t.metrics.cost * 100)
                        if t.metrics.cost > 0
                        else 0,
                        2,
                    ),
                }
                for t in top_by_conversions
            ],
            "top_terms_by_cost": [
                {
                    "term": t.search_term,
                    "cost": t.metrics.cost,
                    "conversions": t.metrics.conversions,
                    "roas": round(
                        (t.metrics.conversion_value / t.metrics.cost * 100)
                        if t.metrics.cost > 0
                        else 0,
                        2,
                    ),
                }
                for t in top_by_cost
            ],
            "worst_terms_by_waste": [
                {
                    "term": t.search_term,
                    "cost": t.metrics.cost,
                    "clicks": t.metrics.clicks,
                    "impressions": t.metrics.impressions,
                }
                for t in worst_by_waste
            ],
        }
