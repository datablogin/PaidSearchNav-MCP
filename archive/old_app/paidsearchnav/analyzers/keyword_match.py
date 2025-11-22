"""Keyword Match Type Audit Analyzer.

This analyzer evaluates keyword performance across different match types
(Broad, Phrase, Exact) to identify optimization opportunities and cost
inefficiencies in Google Ads campaigns.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    KeywordMatchType,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.analysis import KeywordMatchAnalysisResult

if TYPE_CHECKING:
    from paidsearchnav.core.models import Keyword
    from paidsearchnav.data_providers.base import DataProvider


class KeywordMatchAnalyzer(Analyzer):
    """Analyzes keyword performance by match type to identify optimization opportunities."""

    def __init__(
        self,
        data_provider: DataProvider,
        min_impressions: int = 100,
        high_cost_threshold: float = 100.0,
        low_roi_threshold: float = 1.5,
        max_broad_cpa_multiplier: float = 2.0,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Data provider for fetching keyword data
            min_impressions: Minimum impressions to include in analysis
            high_cost_threshold: Cost threshold to flag high-cost keywords
            low_roi_threshold: ROAS threshold to identify low ROI keywords
            max_broad_cpa_multiplier: Max acceptable CPA multiplier for broad match
        """
        self.data_provider = data_provider
        self.min_impressions = min_impressions
        self.high_cost_threshold = high_cost_threshold
        self.low_roi_threshold = low_roi_threshold
        self.max_broad_cpa_multiplier = max_broad_cpa_multiplier

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Keyword Match Type Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes keyword performance across match types (Broad, Phrase, Exact) "
            "to identify optimization opportunities and cost inefficiencies."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> KeywordMatchAnalysisResult:
        """Run keyword match type analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional parameters (campaigns, ad_groups)

        Returns:
            Analysis results with recommendations
        """
        # Get optional filters
        campaigns = kwargs.get("campaigns")
        ad_groups = kwargs.get("ad_groups")

        # Fetch keyword data
        keywords = await self.data_provider.get_keywords(
            customer_id=customer_id,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Filter by minimum impressions
        keywords = [k for k in keywords if k.impressions >= self.min_impressions]

        # Analyze by match type
        match_type_stats = self._calculate_match_type_stats(keywords)

        # Identify problematic keywords
        high_cost_broad = self._find_high_cost_broad_keywords(keywords)
        low_quality_keywords = self._find_low_quality_keywords(keywords)
        duplicate_opportunities = self._find_duplicate_opportunities(keywords)

        # Calculate optimization potential
        potential_savings = self._calculate_potential_savings(
            high_cost_broad, match_type_stats
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            match_type_stats,
            high_cost_broad,
            low_quality_keywords,
            duplicate_opportunities,
        )

        return KeywordMatchAnalysisResult(
            customer_id=customer_id,
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            total_keywords=len(keywords),
            match_type_stats=match_type_stats,
            high_cost_broad_keywords=high_cost_broad,
            low_quality_keywords=low_quality_keywords,
            duplicate_opportunities=duplicate_opportunities,
            potential_savings=potential_savings,
            recommendations=recommendations,
        )

    def _calculate_match_type_stats(
        self, keywords: list[Keyword]
    ) -> dict[str, dict[str, Any]]:
        """Calculate aggregate statistics by match type."""
        stats = defaultdict(
            lambda: {
                "count": 0,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
                "keywords": [],
            }
        )

        for keyword in keywords:
            match_type = keyword.match_type
            stats[match_type]["count"] += 1
            stats[match_type]["impressions"] += keyword.impressions
            stats[match_type]["clicks"] += keyword.clicks
            stats[match_type]["cost"] += keyword.cost
            stats[match_type]["conversions"] += keyword.conversions
            stats[match_type]["conversion_value"] += keyword.conversion_value
            stats[match_type]["keywords"].append(keyword)

        # Calculate derived metrics
        for _, data in stats.items():
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

    def _find_high_cost_broad_keywords(self, keywords: list[Keyword]) -> list[Keyword]:
        """Find high-cost, low-ROI broad match keywords."""
        problematic = []

        for keyword in keywords:
            if keyword.match_type != KeywordMatchType.BROAD:
                continue

            # Check for high cost
            if keyword.cost < self.high_cost_threshold:
                continue

            # Calculate ROAS
            roas = keyword.conversion_value / keyword.cost if keyword.cost > 0 else 0.0

            # Check for low ROI or high CPA
            if roas < self.low_roi_threshold or (
                keyword.cpa > 0 and keyword.conversions > 0
            ):
                problematic.append(keyword)

        # Sort by cost descending
        return sorted(problematic, key=lambda k: k.cost, reverse=True)

    def _find_low_quality_keywords(self, keywords: list[Keyword]) -> list[Keyword]:
        """Find keywords with low quality scores."""
        low_quality = [k for k in keywords if k.is_low_quality and k.cost > 0]

        # Sort by cost descending
        return sorted(low_quality, key=lambda k: k.cost, reverse=True)

    def _find_duplicate_opportunities(
        self, keywords: list[Keyword]
    ) -> list[dict[str, Any]]:
        """Find opportunities to consolidate duplicate keywords."""
        # Group by normalized text
        text_groups = defaultdict(list)

        for keyword in keywords:
            normalized_text = keyword.text.lower().strip()
            text_groups[normalized_text].append(keyword)

        opportunities = []

        for text, group in text_groups.items():
            if len(group) <= 1:
                continue

            # Calculate performance by match type
            match_type_perf = {}
            for keyword in group:
                match_type = keyword.match_type
                if match_type not in match_type_perf:
                    match_type_perf[match_type] = {
                        "keywords": [],
                        "total_cost": 0.0,
                        "total_conversions": 0.0,
                        "total_clicks": 0,
                    }

                match_type_perf[match_type]["keywords"].append(keyword)
                match_type_perf[match_type]["total_cost"] += keyword.cost
                match_type_perf[match_type]["total_conversions"] += keyword.conversions
                match_type_perf[match_type]["total_clicks"] += keyword.clicks

            # Determine if consolidation would help
            if len(match_type_perf) > 1:
                # Calculate best performing match type
                best_match_type = None
                best_cpa = float("inf")

                for match_type, data in match_type_perf.items():
                    if data["total_conversions"] > 0:
                        cpa = data["total_cost"] / data["total_conversions"]
                        if cpa < best_cpa:
                            best_cpa = cpa
                            best_match_type = match_type

                if best_match_type:
                    opportunities.append(
                        {
                            "keyword_text": text,
                            "match_types_found": list(match_type_perf.keys()),
                            "recommended_match_type": best_match_type,
                            "potential_savings": sum(
                                data["total_cost"]
                                for mt, data in match_type_perf.items()
                                if mt != best_match_type
                            ),
                            "keywords": group,
                        }
                    )

        # Sort by potential savings
        return sorted(opportunities, key=lambda x: x["potential_savings"], reverse=True)

    def _calculate_potential_savings(
        self,
        high_cost_broad: list[Keyword],
        match_type_stats: dict[str, dict[str, Any]],
    ) -> float:
        """Calculate potential savings from optimizations."""
        savings = 0.0

        # Savings from pausing/restricting high-cost broad keywords
        broad_stats = match_type_stats.get("BROAD", {})
        if broad_stats and broad_stats.get("cpa", 0) > 0:
            # Compare broad CPA to overall account CPA
            total_cost = sum(stats["cost"] for stats in match_type_stats.values())
            total_conversions = sum(
                stats["conversions"] for stats in match_type_stats.values()
            )

            if total_conversions > 0:
                overall_cpa = total_cost / total_conversions
                broad_cpa = broad_stats["cpa"]

                if broad_cpa > overall_cpa * self.max_broad_cpa_multiplier:
                    # Estimate savings from optimizing broad match
                    excess_cost_ratio = (
                        broad_cpa / overall_cpa - 1
                    ) / self.max_broad_cpa_multiplier
                    savings += broad_stats["cost"] * excess_cost_ratio * 0.5

        # Add savings from high-cost keywords
        for keyword in high_cost_broad[:10]:  # Top 10 worst performers
            if keyword.conversions == 0:
                savings += keyword.cost * 0.8  # Assume 80% savings
            elif keyword.cpa > 0:
                # Estimate savings from improving to average CPA
                if total_conversions > 0:
                    overall_cpa = total_cost / total_conversions
                    if keyword.cpa > overall_cpa * 2:
                        savings += (
                            (keyword.cpa - overall_cpa) * keyword.conversions * 0.5
                        )

        return round(savings, 2)

    def _generate_recommendations(
        self,
        match_type_stats: dict[str, dict[str, Any]],
        high_cost_broad: list[Keyword],
        low_quality_keywords: list[Keyword],
        duplicate_opportunities: list[dict[str, Any]],
    ) -> list[Recommendation]:
        """Generate actionable recommendations."""
        recommendations = []

        # Check broad match performance
        broad_stats = match_type_stats.get("BROAD", {})
        if broad_stats and broad_stats.get("count", 0) > 0:
            broad_cost_ratio = broad_stats["cost"] / sum(
                s["cost"] for s in match_type_stats.values()
            )

            if (
                broad_cost_ratio > 0.5
                and broad_stats.get("roas", 0) < self.low_roi_threshold
            ):
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.PAUSE_KEYWORDS,
                        priority=RecommendationPriority.HIGH,
                        title="Reduce broad match usage",
                        description=(
                            f"Broad match keywords account for {broad_cost_ratio:.0%} of spend "
                            f"but have ROAS of {broad_stats.get('roas', 0):.2f}. "
                            f"Consider pausing poor performers or converting to phrase/exact match."
                        ),
                    )
                )

        # High-cost broad keywords
        if high_cost_broad:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.HIGH,
                    title=f"Optimize {len(high_cost_broad)} high-cost broad keywords",
                    description=(
                        f"Found {len(high_cost_broad)} broad match keywords with high cost "
                        f"and low ROI. Top keyword '{high_cost_broad[0].text}' "
                        f"spent ${high_cost_broad[0].cost:.2f} with "
                        f"{high_cost_broad[0].conversions:.1f} conversions."
                    ),
                )
            )

        # Low quality keywords
        if low_quality_keywords:
            total_low_quality_cost = sum(k.cost for k in low_quality_keywords)
            recommendations.append(
                Recommendation(
                    type=RecommendationType.IMPROVE_QUALITY_SCORE,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Improve {len(low_quality_keywords)} low quality keywords",
                    description=(
                        f"Keywords with quality score < 7 spent ${total_low_quality_cost:.2f}. "
                        f"Improve ad relevance, landing pages, and expected CTR."
                    ),
                )
            )

        # Duplicate consolidation
        if duplicate_opportunities:
            total_dup_savings = sum(
                opp["potential_savings"] for opp in duplicate_opportunities
            )
            recommendations.append(
                Recommendation(
                    type=RecommendationType.CONSOLIDATE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Consolidate {len(duplicate_opportunities)} duplicate keywords",
                    description=(
                        f"Found keywords with same text but different match types. "
                        f"Consolidating could save ${total_dup_savings:.2f}."
                    ),
                )
            )

        # Match type distribution
        if len(match_type_stats) > 0:
            exact_ratio = match_type_stats.get("EXACT", {}).get("count", 0) / sum(
                s["count"] for s in match_type_stats.values()
            )

            if exact_ratio < 0.3:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_KEYWORD,
                        priority=RecommendationPriority.LOW,
                        title="Increase exact match coverage",
                        description=(
                            f"Only {exact_ratio:.0%} of keywords are exact match. "
                            f"Consider adding exact match versions of top performing queries."
                        ),
                    )
                )

        return recommendations
