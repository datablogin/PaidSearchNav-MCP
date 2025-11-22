"""Campaign Overlap Analyzer.

This analyzer detects campaign overlap and conflicts across all campaign types,
providing comprehensive channel-level reporting and optimization recommendations.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    CampaignOverlapAnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.platforms.ga4.bigquery_client import GA4BigQueryClient

if TYPE_CHECKING:
    from paidsearchnav.core.models.campaign import Campaign
    from paidsearchnav.core.models.search_term import SearchTerm
    from paidsearchnav.data_providers.base import DataProvider


logger = logging.getLogger(__name__)


class CampaignOverlapAnalyzer(Analyzer):
    """Analyzes campaign overlap and provides channel-level reporting."""

    # Constants for analysis thresholds and percentages
    DEFAULT_CHANNEL_DOMINANCE_THRESHOLD = 0.7
    DEFAULT_EFFICIENCY_GAP_MULTIPLIER = 3.0
    DEFAULT_LOW_ROAS_THRESHOLD = 2.0
    DEFAULT_HIGH_CPA_THRESHOLD = 100.0
    DEFAULT_BUDGET_REALLOCATION_PERCENTAGE = 0.25
    DEFAULT_CAMPAIGN_OPTIMIZATION_PERCENTAGE = 0.15

    # Default brand terms for conflict detection
    DEFAULT_BRAND_TERMS = [
        "brand",
        "company",
        "store",
        "shop",
        "business",
        "inc",
        "ltd",
        "corp",
    ]

    def __init__(
        self,
        data_provider: DataProvider,
        min_impressions: int = 100,
        min_spend_threshold: float = 25.0,
        overlap_threshold: float = 0.7,
        conflict_threshold: float = 0.8,
        ga4_client: Optional[GA4BigQueryClient] = None,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Data provider for fetching campaign data
            min_impressions: Minimum impressions to include in analysis
            min_spend_threshold: Minimum spend to include campaigns
            overlap_threshold: Threshold for detecting significant overlap
            conflict_threshold: Threshold for detecting conflicts
        """
        self.data_provider = data_provider
        self.min_impressions = min_impressions
        self.min_spend_threshold = min_spend_threshold
        self.overlap_threshold = overlap_threshold
        self.conflict_threshold = conflict_threshold
        self.ga4_client = ga4_client

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Campaign Overlap Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes campaign overlap and conflicts across all campaign types, "
            "providing channel-level reporting and optimization recommendations."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> CampaignOverlapAnalysisResult:
        """Run campaign overlap analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional parameters

        Returns:
            Analysis results with overlap insights and recommendations
        """
        # Fetch all campaigns
        all_campaigns = await self.data_provider.get_campaigns(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Filter campaigns by minimum thresholds
        active_campaigns = [
            c
            for c in all_campaigns
            if c.cost >= self.min_spend_threshold
            and c.impressions >= self.min_impressions
        ]

        # Analyze channel-level performance
        channel_performance = await self._analyze_channel_performance(
            customer_id, active_campaigns, start_date, end_date
        )

        # Enhance with GA4 revenue attribution if available
        if self.ga4_client:
            channel_performance = await self._enhance_with_ga4_attribution(
                channel_performance, start_date, end_date
            )

        # Detect campaign overlaps
        overlap_analysis = await self._detect_campaign_overlaps(
            customer_id, active_campaigns, start_date, end_date
        )

        # Analyze brand exclusion conflicts
        brand_conflicts = await self._analyze_brand_conflicts(
            customer_id, active_campaigns, start_date, end_date
        )

        # Generate budget optimization recommendations
        budget_optimization = await self._analyze_budget_optimization(
            customer_id, active_campaigns, channel_performance
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            channel_performance, overlap_analysis, brand_conflicts, budget_optimization
        )

        # Calculate key metrics
        total_spend = sum(c.cost for c in active_campaigns)
        total_conversions = sum(c.conversions for c in active_campaigns)
        total_conversion_value = sum(c.conversion_value for c in active_campaigns)

        # Calculate overall ROAS (not average ROAS)
        overall_roas = total_conversion_value / total_spend if total_spend > 0 else 0.0

        return CampaignOverlapAnalysisResult(
            customer_id=customer_id,
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            channel_performance=channel_performance,
            overlap_analysis=overlap_analysis,
            brand_conflicts=brand_conflicts,
            budget_optimization=budget_optimization,
            total_campaigns=len(active_campaigns),
            total_spend=total_spend,
            total_conversions=total_conversions,
            avg_roas=overall_roas,
            overlap_count=overlap_analysis.get("overlap_count", 0),
            total_overlap_cost=overlap_analysis.get("total_overlap_cost", 0.0),
        )

    async def _analyze_channel_performance(
        self,
        customer_id: str,
        campaigns: list[Campaign],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Analyze performance by channel across all campaign types."""
        if not campaigns:
            return {"channels": [], "insights": []}

        # Group campaigns by type/channel
        channel_data = defaultdict(
            lambda: {
                "campaigns": [],
                "total_spend": 0.0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_conversions": 0.0,
                "total_conversion_value": 0.0,
            }
        )

        for campaign in campaigns:
            channel = self._get_channel_name(campaign.type)
            channel_data[channel]["campaigns"].append(campaign)
            channel_data[channel]["total_spend"] += campaign.cost
            channel_data[channel]["total_impressions"] += campaign.impressions
            channel_data[channel]["total_clicks"] += campaign.clicks
            channel_data[channel]["total_conversions"] += campaign.conversions
            channel_data[channel]["total_conversion_value"] += campaign.conversion_value

        # Calculate performance metrics by channel
        channels = []
        for channel, data in channel_data.items():
            channel_metrics = {
                "channel": channel,
                "campaign_count": len(data["campaigns"]),
                "spend": data["total_spend"],
                "impressions": data["total_impressions"],
                "clicks": data["total_clicks"],
                "conversions": data["total_conversions"],
                "conversion_value": data["total_conversion_value"],
                "cpa": self._calculate_cpa(
                    data["total_spend"], data["total_conversions"]
                ),
                "ctr": self._calculate_ctr(
                    data["total_clicks"], data["total_impressions"]
                ),
                "roas": self._calculate_roas(
                    data["total_conversion_value"], data["total_spend"]
                ),
                "conversion_rate": (
                    data["total_conversions"] / data["total_clicks"] * 100
                    if data["total_clicks"] > 0
                    else 0.0
                ),
            }
            channels.append(channel_metrics)

        # Sort channels by spend
        channels.sort(key=lambda x: x["spend"], reverse=True)

        # Generate insights
        insights = self._generate_channel_insights(channels)

        return {
            "channels": channels,
            "insights": insights,
            "total_spend": sum(c["spend"] for c in channels),
            "channel_count": len(channels),
        }

    async def _detect_campaign_overlaps(
        self,
        customer_id: str,
        campaigns: list[Campaign],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Detect overlaps between campaigns."""
        if len(campaigns) < 2:
            return {"overlaps": [], "overlap_count": 0, "total_overlap_cost": 0.0}

        # Get search terms for all campaigns in parallel
        async def get_campaign_search_terms(campaign):
            try:
                return campaign.campaign_id, await self.data_provider.get_search_terms(
                    customer_id=customer_id,
                    campaign_id=campaign.campaign_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception:
                return campaign.campaign_id, []

        # Execute API calls in parallel
        search_terms_tasks = [
            get_campaign_search_terms(campaign) for campaign in campaigns
        ]
        search_terms_results = await asyncio.gather(
            *search_terms_tasks, return_exceptions=True
        )

        # Process results
        search_terms_by_campaign = {}
        for result in search_terms_results:
            if isinstance(result, Exception):
                continue
            campaign_id, search_terms = result
            search_terms_by_campaign[campaign_id] = search_terms

        # Detect overlaps
        overlaps = []
        total_overlap_cost = 0.0

        for i, campaign1 in enumerate(campaigns):
            for campaign2 in campaigns[i + 1 :]:
                if campaign1.campaign_id == campaign2.campaign_id:
                    continue

                overlap_data = self._calculate_overlap(
                    campaign1,
                    campaign2,
                    search_terms_by_campaign.get(campaign1.campaign_id, []),
                    search_terms_by_campaign.get(campaign2.campaign_id, []),
                )

                if overlap_data["overlap_percentage"] > self.overlap_threshold:
                    overlaps.append(overlap_data)
                    total_overlap_cost += overlap_data["overlap_cost"]

        return {
            "overlaps": overlaps,
            "overlap_count": len(overlaps),
            "total_overlap_cost": total_overlap_cost,
            "high_conflict_overlaps": [
                o for o in overlaps if o["overlap_percentage"] > self.conflict_threshold
            ],
        }

    async def _analyze_brand_conflicts(
        self,
        customer_id: str,
        campaigns: list[Campaign],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Analyze brand exclusion conflicts."""
        if not campaigns:
            return {"conflicts": [], "conflict_count": 0}

        # Get negative keywords for all campaigns in parallel
        async def get_campaign_negative_keywords(campaign):
            try:
                return (
                    campaign.campaign_id,
                    await self.data_provider.get_negative_keywords(
                        customer_id=customer_id,
                        campaign_id=campaign.campaign_id,
                    ),
                )
            except Exception:
                return campaign.campaign_id, []

        # Execute API calls in parallel
        negative_keywords_tasks = [
            get_campaign_negative_keywords(campaign) for campaign in campaigns
        ]
        negative_keywords_results = await asyncio.gather(
            *negative_keywords_tasks, return_exceptions=True
        )

        # Process results
        negative_keywords_by_campaign = {}
        for result in negative_keywords_results:
            if isinstance(result, Exception):
                continue
            campaign_id, negative_keywords = result
            negative_keywords_by_campaign[campaign_id] = negative_keywords

        # Detect brand conflicts
        conflicts = []
        brand_terms = self.DEFAULT_BRAND_TERMS

        for campaign in campaigns:
            if campaign.type == "PERFORMANCE_MAX":
                # Check if PMax might be showing for brand terms that are excluded elsewhere
                negative_keywords = negative_keywords_by_campaign.get(
                    campaign.campaign_id, []
                )
                brand_negatives = [
                    nk
                    for nk in negative_keywords
                    if any(brand_term in nk.text.lower() for brand_term in brand_terms)
                ]

                if brand_negatives:
                    conflicts.append(
                        {
                            "campaign_id": campaign.campaign_id,
                            "campaign_name": getattr(
                                campaign, "name", f"Campaign {campaign.campaign_id}"
                            ),
                            "conflict_type": "brand_exclusion",
                            "details": "Performance Max campaign may conflict with brand exclusions",
                            "negative_keywords": [nk.text for nk in brand_negatives],
                            "severity": "HIGH",
                        }
                    )

        return {
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }

    async def _analyze_budget_optimization(
        self,
        customer_id: str,
        campaigns: list[Campaign],
        channel_performance: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze budget optimization opportunities."""
        if not campaigns or not channel_performance.get("channels"):
            return {"opportunities": [], "total_potential_savings": 0.0}

        channels = channel_performance["channels"]
        opportunities = []
        total_potential_savings = 0.0

        # Find best and worst performing channels
        channels_with_conversions = [c for c in channels if c["conversions"] > 0]
        if len(channels_with_conversions) >= 2:
            best_channel = min(channels_with_conversions, key=lambda x: x["cpa"])
            worst_channel = max(channels_with_conversions, key=lambda x: x["cpa"])

            # If performance gap is significant, recommend budget reallocation
            if worst_channel["cpa"] > best_channel["cpa"] * 2:
                reallocation_amount = (
                    worst_channel["spend"] * self.DEFAULT_BUDGET_REALLOCATION_PERCENTAGE
                )
                potential_savings = (worst_channel["cpa"] - best_channel["cpa"]) * (
                    reallocation_amount / best_channel["cpa"]
                )

                opportunities.append(
                    {
                        "type": "budget_reallocation",
                        "from_channel": worst_channel["channel"],
                        "to_channel": best_channel["channel"],
                        "amount": reallocation_amount,
                        "potential_savings": potential_savings,
                        "impact": f"Reduce overall CPA by approximately ${potential_savings:.2f}",
                    }
                )

                total_potential_savings += potential_savings

        # Look for underperforming campaigns within channels
        for channel in channels:
            if (
                channel["conversions"] > 0
                and channel["cpa"] > self.DEFAULT_HIGH_CPA_THRESHOLD
            ):
                campaign_optimization = (
                    channel["spend"] * self.DEFAULT_CAMPAIGN_OPTIMIZATION_PERCENTAGE
                )
                opportunities.append(
                    {
                        "type": "campaign_optimization",
                        "channel": channel["channel"],
                        "current_cpa": channel["cpa"],
                        "potential_savings": campaign_optimization,
                        "impact": f"Optimize {channel['channel']} campaigns to reduce spend by ${campaign_optimization:.2f}",
                    }
                )

                total_potential_savings += campaign_optimization

        return {
            "opportunities": opportunities,
            "total_potential_savings": total_potential_savings,
            "optimization_score": min(
                100, (total_potential_savings / sum(c["spend"] for c in channels)) * 100
            )
            if channels
            else 0,
        }

    def _calculate_overlap(
        self,
        campaign1: Campaign,
        campaign2: Campaign,
        search_terms1: list[SearchTerm],
        search_terms2: list[SearchTerm],
    ) -> dict[str, Any]:
        """Calculate overlap between two campaigns."""
        if not search_terms1 or not search_terms2:
            return {
                "campaign1_id": campaign1.campaign_id,
                "campaign2_id": campaign2.campaign_id,
                "campaign1_type": campaign1.type,
                "campaign2_type": campaign2.type,
                "overlap_percentage": 0.0,
                "overlap_cost": 0.0,
                "overlapping_terms": [],
            }

        # Normalize search terms
        terms1 = {self._normalize_query(st.search_term) for st in search_terms1}
        terms2 = {self._normalize_query(st.search_term) for st in search_terms2}

        # Find overlapping terms
        overlapping_terms = terms1.intersection(terms2)

        # Calculate symmetric overlap percentage using Jaccard index
        union_terms = terms1.union(terms2)
        overlap_percentage = (
            len(overlapping_terms) / len(union_terms) * 100 if union_terms else 0.0
        )

        # Calculate overlap cost
        overlap_cost = 0.0
        overlapping_details = []

        for term in overlapping_terms:
            term1_data = next(
                (
                    st
                    for st in search_terms1
                    if self._normalize_query(st.search_term) == term
                ),
                None,
            )
            term2_data = next(
                (
                    st
                    for st in search_terms2
                    if self._normalize_query(st.search_term) == term
                ),
                None,
            )

            if term1_data and term2_data:
                term_overlap_cost = term1_data.metrics.cost + term2_data.metrics.cost
                overlap_cost += term_overlap_cost

                overlapping_details.append(
                    {
                        "term": term,
                        "campaign1_cost": term1_data.metrics.cost,
                        "campaign2_cost": term2_data.metrics.cost,
                        "total_cost": term_overlap_cost,
                    }
                )

        return {
            "campaign1_id": campaign1.campaign_id,
            "campaign2_id": campaign2.campaign_id,
            "campaign1_type": campaign1.type,
            "campaign2_type": campaign2.type,
            "overlap_percentage": overlap_percentage,
            "overlap_cost": overlap_cost,
            "overlapping_terms": overlapping_details[:10],  # Limit to top 10
            "total_overlapping_terms": len(overlapping_terms),
        }

    def _generate_channel_insights(
        self, channels: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate insights about channel performance."""
        insights = []

        if not channels:
            return insights

        # Channel dominance insight
        total_spend = sum(c["spend"] for c in channels)
        if total_spend > 0:
            dominant_channel = max(channels, key=lambda x: x["spend"])

            if (
                dominant_channel["spend"] / total_spend
                > self.DEFAULT_CHANNEL_DOMINANCE_THRESHOLD
            ):
                insights.append(
                    {
                        "type": "channel_dominance",
                        "severity": "MEDIUM",
                        "message": f"{dominant_channel['channel']} accounts for {dominant_channel['spend'] / total_spend * 100:.1f}% of total spend",
                        "recommendation": "Consider diversifying spend across multiple channels",
                    }
                )

        # Performance efficiency insight
        channels_with_conversions = [c for c in channels if c["conversions"] > 0]
        if len(channels_with_conversions) >= 2:
            best_channel = min(channels_with_conversions, key=lambda x: x["cpa"])
            worst_channel = max(channels_with_conversions, key=lambda x: x["cpa"])

            if (
                worst_channel["cpa"]
                > best_channel["cpa"] * self.DEFAULT_EFFICIENCY_GAP_MULTIPLIER
            ):
                insights.append(
                    {
                        "type": "efficiency_gap",
                        "severity": "HIGH",
                        "message": f"Large efficiency gap between {best_channel['channel']} (${best_channel['cpa']:.2f} CPA) and {worst_channel['channel']} (${worst_channel['cpa']:.2f} CPA)",
                        "recommendation": f"Consider reallocating budget from {worst_channel['channel']} to {best_channel['channel']}",
                    }
                )

        # Underperforming channels
        for channel in channels:
            if (
                channel["conversions"] > 0
                and channel["roas"] < self.DEFAULT_LOW_ROAS_THRESHOLD
            ):
                insights.append(
                    {
                        "type": "low_roas",
                        "severity": "MEDIUM",
                        "message": f"{channel['channel']} has low ROAS of {channel['roas']:.2f}",
                        "recommendation": f"Review and optimize {channel['channel']} campaigns",
                    }
                )

        return insights

    def _generate_recommendations(
        self,
        channel_performance: dict[str, Any],
        overlap_analysis: dict[str, Any],
        brand_conflicts: dict[str, Any],
        budget_optimization: dict[str, Any],
    ) -> list[Recommendation]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Channel performance recommendations
        for insight in channel_performance.get("insights", []):
            if insight["severity"] == "HIGH":
                priority = RecommendationPriority.HIGH
            elif insight["severity"] == "MEDIUM":
                priority = RecommendationPriority.MEDIUM
            else:
                priority = RecommendationPriority.LOW

            recommendations.append(
                Recommendation(
                    title=insight["message"],
                    description=insight["recommendation"],
                    priority=priority,
                    type=RecommendationType.BUDGET_OPTIMIZATION,
                    impact=insight.get("impact", ""),
                )
            )

        # Overlap recommendations
        for overlap in overlap_analysis.get("high_conflict_overlaps", []):
            recommendations.append(
                Recommendation(
                    title=f"Resolve campaign overlap between {overlap['campaign1_type']} and {overlap['campaign2_type']}",
                    description=f"Campaigns have {overlap['overlap_percentage']:.1f}% overlap costing ${overlap['overlap_cost']:.2f}",
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.RESOLVE_CONFLICTS,
                    impact=f"Potential savings: ${overlap['overlap_cost'] * 0.3:.2f}",
                )
            )

        # Brand conflict recommendations
        for conflict in brand_conflicts.get("conflicts", []):
            recommendations.append(
                Recommendation(
                    title=f"Resolve brand exclusion conflict in {conflict['campaign_name']}",
                    description=conflict["details"],
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.RESOLVE_CONFLICTS,
                    impact="Prevent brand term conflicts",
                )
            )

        # Budget optimization recommendations
        for opportunity in budget_optimization.get("opportunities", []):
            recommendations.append(
                Recommendation(
                    title=f"Budget optimization opportunity: {opportunity['type']}",
                    description=opportunity["impact"],
                    priority=RecommendationPriority.MEDIUM,
                    type=RecommendationType.BUDGET_OPTIMIZATION,
                    impact=f"Potential savings: ${opportunity['potential_savings']:.2f}",
                )
            )

        return recommendations

    def _get_channel_name(self, campaign_type: str) -> str:
        """Get channel name from campaign type."""
        channel_mapping = {
            "SEARCH": "Search",
            "DISPLAY": "Display",
            "SHOPPING": "Shopping",
            "PERFORMANCE_MAX": "Performance Max",
            "VIDEO": "Video",
            "DISCOVERY": "Discovery",
            "APP": "App",
            "SMART": "Smart",
            "LOCAL": "Local",
        }
        return channel_mapping.get(campaign_type, campaign_type.title())

    def _normalize_query(self, query: str) -> str:
        """Normalize search query for comparison."""
        # Replace hyphens and other punctuation with spaces, then normalize whitespace
        normalized = re.sub(r"[^\w\s]", " ", query.lower().strip())
        return re.sub(r"\s+", " ", normalized).strip()

    def _calculate_cpa(self, cost: float, conversions: float) -> float:
        """Calculate CPA safely."""
        return cost / conversions if conversions > 0 else float("inf")

    def _calculate_ctr(self, clicks: int, impressions: int) -> float:
        """Calculate CTR percentage safely."""
        return (clicks / impressions * 100) if impressions > 0 else 0.0

    def _calculate_roas(self, conversion_value: float, cost: float) -> float:
        """Calculate ROAS safely."""
        return conversion_value / cost if cost > 0 else 0.0

    async def _enhance_with_ga4_attribution(
        self,
        channel_performance: dict[str, Any],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Enhance channel performance with GA4 revenue attribution data.

        Args:
            channel_performance: Current channel performance data
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Enhanced channel performance with GA4 attribution
        """
        if not self.ga4_client:
            logger.warning("GA4 client not available, skipping GA4 enhancement")
            return channel_performance

        try:
            # Get GA4 revenue attribution data for all models in single optimized query
            attribution_data = self.ga4_client.get_ga4_revenue_attribution_multi_model(
                start_date, end_date
            )
            attribution_models = list(attribution_data.keys())

            if not any(attribution_data.values()):
                logger.info("No GA4 revenue attribution data found")
                return channel_performance

            # Enhance channel data with GA4 attribution
            enhanced_channels = []
            for channel in channel_performance.get("channels", []):
                enhanced_channel = channel.copy()

                # Match GA4 data by campaign name
                for model, ga4_data in attribution_data.items():
                    matching_revenue = [
                        record
                        for record in ga4_data
                        if record.get("campaign_name", "").lower()
                        in [
                            camp.get("name", "").lower()
                            for camp in channel_performance.get("campaigns", [])
                        ]
                    ]

                    if matching_revenue:
                        total_ga4_revenue = sum(
                            record.get("attributed_revenue", 0)
                            for record in matching_revenue
                        )
                        total_ga4_transactions = len(
                            set(
                                record.get("transaction_id")
                                for record in matching_revenue
                                if record.get("transaction_id")
                            )
                        )

                        # Add GA4 attribution metrics
                        enhanced_channel[f"ga4_{model}_revenue"] = total_ga4_revenue
                        enhanced_channel[f"ga4_{model}_transactions"] = (
                            total_ga4_transactions
                        )
                        enhanced_channel[f"ga4_{model}_roas"] = (
                            (total_ga4_revenue / enhanced_channel["spend"])
                            if enhanced_channel["spend"] > 0
                            else 0.0
                        )

                # Calculate blended attribution metrics
                if any(
                    f"ga4_{model}_revenue" in enhanced_channel
                    for model in attribution_models
                ):
                    total_attributed_revenue = sum(
                        enhanced_channel.get(f"ga4_{model}_revenue", 0)
                        for model in attribution_models
                    )
                    avg_attributed_revenue = total_attributed_revenue / len(
                        attribution_models
                    )

                    enhanced_channel["ga4_blended_revenue"] = avg_attributed_revenue
                    enhanced_channel["ga4_blended_roas"] = (
                        (avg_attributed_revenue / enhanced_channel["spend"])
                        if enhanced_channel["spend"] > 0
                        else 0.0
                    )
                    enhanced_channel["ga4_enhanced"] = True

                    logger.info(
                        f"Enhanced {channel['channel']} with GA4 attribution: "
                        f"${avg_attributed_revenue:.2f} blended revenue, "
                        f"{enhanced_channel['ga4_blended_roas']:.2f} ROAS"
                    )

                enhanced_channels.append(enhanced_channel)

            # Update channel performance data
            enhanced_performance = channel_performance.copy()
            enhanced_performance["channels"] = enhanced_channels
            enhanced_performance["ga4_attribution_models"] = attribution_models
            enhanced_performance["ga4_enhanced"] = True

            logger.info(
                f"Enhanced {len(enhanced_channels)} channels with GA4 attribution data"
            )
            return enhanced_performance

        except Exception as e:
            logger.error(f"Failed to enhance channels with GA4 attribution: {e}")
            # Return original data if GA4 enhancement fails
            return channel_performance
