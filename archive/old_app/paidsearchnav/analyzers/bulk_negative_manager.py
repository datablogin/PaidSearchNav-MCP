"""Bulk negative keyword management analyzer.

This module provides advanced bulk negative keyword management capabilities including
performance-based automation, smart templates, and ROI-driven recommendations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.campaign import Campaign
from paidsearchnav.core.models.search_term import SearchTerm

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


class BulkNegativeManagerAnalyzer(Analyzer):
    """Advanced bulk negative keyword management with automation and ROI prioritization."""

    def __init__(
        self,
        data_provider: DataProvider,
        cpa_threshold: float = 100.0,
        ctr_threshold: float = 0.02,
        roas_threshold: float = 2.0,
        min_cost_threshold: float = 50.0,
        conversion_value_per_conversion: float = 50.0,
    ) -> None:
        """Initialize the analyzer.

        Args:
            data_provider: Provider for fetching Google Ads data
            cpa_threshold: Maximum acceptable CPA for keywords
            ctr_threshold: Minimum acceptable CTR for keywords
            roas_threshold: Minimum acceptable ROAS for keywords
            min_cost_threshold: Minimum cost to consider for negative keyword suggestions
            conversion_value_per_conversion: Average conversion value for ROI calculations
        """
        self.data_provider = data_provider
        self.cpa_threshold = cpa_threshold
        self.ctr_threshold = ctr_threshold
        self.roas_threshold = roas_threshold
        self.min_cost_threshold = min_cost_threshold
        self.conversion_value_per_conversion = conversion_value_per_conversion

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Bulk Negative Keyword Manager"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Advanced bulk negative keyword management with performance-based automation, "
            "smart industry templates, ROI prioritization, and automated application capabilities."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run bulk negative keyword management analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis period start
            end_date: Analysis period end
            **kwargs: Additional parameters including:
                - auto_apply: Whether to automatically apply suggestions
                - industry: Industry type for template selection
                - campaign_types: Campaign types to analyze

        Returns:
            Analysis result with negative keyword suggestions and bulk management recommendations
        """
        logger.info(
            f"Starting bulk negative keyword analysis for customer {customer_id}"
        )

        # Extract parameters
        auto_apply = kwargs.get("auto_apply", False)
        industry = kwargs.get("industry", "general")
        campaign_types = kwargs.get("campaign_types", [])

        # Fetch data
        campaigns = await self.data_provider.get_campaigns(
            customer_id, start_date, end_date
        )
        search_terms = await self.data_provider.get_search_terms(
            customer_id, start_date, end_date
        )
        existing_negatives = await self.data_provider.get_negative_keywords(
            customer_id, include_shared_sets=True
        )

        # Filter campaigns if specified
        if campaign_types:
            campaigns = [c for c in campaigns if c.type in campaign_types]

        # 1. Performance-based negative keyword suggestions
        performance_suggestions = self._analyze_performance_based_negatives(
            search_terms, existing_negatives
        )

        # 2. Smart negative keyword templates (only if there are campaigns)
        template_suggestions = (
            self._get_industry_template_suggestions(
                industry, campaigns, existing_negatives
            )
            if campaigns
            else []
        )

        # 3. N-gram analysis for pattern recognition
        ngram_suggestions = self._analyze_search_term_patterns(
            search_terms, existing_negatives
        )

        # 4. Competitor term analysis
        competitor_suggestions = self._analyze_competitor_terms(
            search_terms, existing_negatives
        )

        # Combine and prioritize all suggestions
        all_suggestions = (
            performance_suggestions
            + template_suggestions
            + ngram_suggestions
            + competitor_suggestions
        )

        # Calculate ROI-based priorities
        prioritized_suggestions = self._prioritize_by_roi(all_suggestions)

        # Generate bulk application recommendations
        bulk_recommendations = self._generate_bulk_recommendations(
            prioritized_suggestions, campaigns, auto_apply
        )

        # Calculate metrics
        total_potential_savings = sum(
            s.get("potential_savings", 0) for s in prioritized_suggestions
        )

        metrics = AnalysisMetrics(
            total_keywords_analyzed=len(search_terms),
            total_campaigns_analyzed=len(campaigns),
            issues_found=len(prioritized_suggestions),
            critical_issues=len(
                [s for s in prioritized_suggestions if s.get("priority") == "critical"]
            ),
            potential_cost_savings=total_potential_savings,
            custom_metrics={
                "negative_suggestions_found": len(prioritized_suggestions),
                "performance_based_suggestions": len(performance_suggestions),
                "template_suggestions": len(template_suggestions),
                "ngram_suggestions": len(ngram_suggestions),
                "competitor_suggestions": len(competitor_suggestions),
                "total_search_terms_analyzed": len(search_terms),
                "existing_negatives_count": len(existing_negatives),
                "estimated_conversion_loss_prevented": self._calculate_conversion_loss_prevented(
                    prioritized_suggestions
                ),
            },
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="bulk_negative_management",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            recommendations=bulk_recommendations,
            raw_data={
                "negative_keyword_suggestions": prioritized_suggestions[
                    :50
                ],  # Top 50 for performance
                "performance_analysis": {
                    "total_suggestions": len(prioritized_suggestions),
                    "by_type": {
                        "performance_based": len(performance_suggestions),
                        "industry_template": len(template_suggestions),
                        "ngram_pattern": len(ngram_suggestions),
                        "competitor_terms": len(competitor_suggestions),
                    },
                    "by_priority": {
                        "critical": len(
                            [
                                s
                                for s in prioritized_suggestions
                                if s.get("priority") == "critical"
                            ]
                        ),
                        "high": len(
                            [
                                s
                                for s in prioritized_suggestions
                                if s.get("priority") == "high"
                            ]
                        ),
                        "medium": len(
                            [
                                s
                                for s in prioritized_suggestions
                                if s.get("priority") == "medium"
                            ]
                        ),
                        "low": len(
                            [
                                s
                                for s in prioritized_suggestions
                                if s.get("priority") == "low"
                            ]
                        ),
                    },
                },
                "industry_insights": {
                    "industry": industry,
                    "template_keywords_suggested": len(template_suggestions),
                    "custom_patterns_found": len(ngram_suggestions),
                },
            },
        )

    def _analyze_performance_based_negatives(
        self, search_terms: list[SearchTerm], existing_negatives: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Analyze search terms for performance-based negative keyword suggestions."""
        suggestions = []
        existing_negative_texts = {
            neg.get("text", "").lower() for neg in existing_negatives
        }

        for term in search_terms:
            search_term = term.search_term.lower()
            cost = term.cost
            conversions = int(term.conversions)
            clicks = term.clicks
            impressions = term.impressions
            conversion_value = term.conversion_value

            # Skip if already exists as negative
            if search_term in existing_negative_texts:
                continue

            # Skip if below minimum cost threshold
            if cost < self.min_cost_threshold:
                continue

            # Calculate performance metrics
            ctr = clicks / impressions if impressions > 0 else 0
            cpa = cost / conversions if conversions > 0 else float("inf")
            roas = conversion_value / cost if cost > 0 else 0

            # Check if term meets negative criteria
            is_poor_performer = (
                (conversions == 0 and cost > self.min_cost_threshold)
                or (cpa > self.cpa_threshold and conversions > 0)
                or (ctr < self.ctr_threshold and clicks > 10)
                or (roas < self.roas_threshold and conversion_value > 0)
            )

            if is_poor_performer:
                # Calculate potential savings and priority
                potential_savings = cost  # Full cost savings if term is negated

                # Determine priority based on cost and poor performance severity
                if cost > 500 or (conversions == 0 and cost > 200):
                    priority = "critical"
                elif cost > 200 or cpa > self.cpa_threshold * 2:
                    priority = "high"
                elif cost > 100 or ctr < self.ctr_threshold * 0.5:
                    priority = "medium"
                else:
                    priority = "low"

                # Determine confidence based on data quality
                confidence = self._calculate_confidence(clicks, impressions, cost)

                suggestions.append(
                    {
                        "keyword": search_term,
                        "type": "performance_based",
                        "reason": self._get_performance_reason(
                            cpa, ctr, roas, conversions, cost
                        ),
                        "priority": priority,
                        "confidence": confidence,
                        "potential_savings": potential_savings,
                        "match_type": "phrase",  # Default to phrase match for safety
                        "campaign_applicability": "all",  # Apply to all campaigns by default
                        "performance_data": {
                            "cost": cost,
                            "conversions": conversions,
                            "clicks": clicks,
                            "impressions": impressions,
                            "ctr": ctr,
                            "cpa": cpa if conversions > 0 else None,
                            "roas": roas if cost > 0 else None,
                            "conversion_value": conversion_value,
                        },
                    }
                )

        return sorted(suggestions, key=lambda x: x["potential_savings"], reverse=True)

    def _get_industry_template_suggestions(
        self,
        industry: str,
        campaigns: list[Campaign],
        existing_negatives: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Get industry-specific negative keyword template suggestions."""
        suggestions = []
        existing_negative_texts = {
            neg.get("text", "").lower() for neg in existing_negatives
        }

        # Industry-specific negative keyword templates
        industry_templates = {
            "retail": [
                "free",
                "cheap",
                "wholesale",
                "bulk",
                "discount",
                "coupon",
                "sale",
                "used",
                "second hand",
                "refurbished",
                "broken",
                "repair",
                "fix",
                "diy",
                "how to make",
                "homemade",
                "tutorial",
                "instructions",
                "jobs",
                "career",
                "hiring",
                "employment",
                "work",
            ],
            "healthcare": [
                "free",
                "cheap",
                "alternative",
                "home remedy",
                "natural cure",
                "diy",
                "without prescription",
                "illegal",
                "fake",
                "counterfeit",
                "jobs",
                "career",
                "training",
                "school",
                "certification",
                "insurance",
                "coverage",
                "claim",
                "lawsuit",
                "legal",
            ],
            "automotive": [
                "free",
                "cheap",
                "used",
                "junk",
                "scrap",
                "parts",
                "salvage",
                "diy",
                "repair",
                "fix",
                "broken",
                "problem",
                "issue",
                "rental",
                "lease",
                "finance",
                "loan",
                "credit",
                "jobs",
                "career",
                "mechanic",
                "training",
                "school",
            ],
            "real_estate": [
                "free",
                "rent",
                "rental",
                "lease",
                "foreclosure",
                "auction",
                "cheap",
                "affordable",
                "government",
                "subsidized",
                "section 8",
                "mobile home",
                "trailer",
                "rv",
                "temporary",
                "short term",
                "jobs",
                "career",
                "agent",
                "license",
                "training",
                "school",
            ],
            "financial": [
                "free",
                "no fee",
                "scam",
                "fraud",
                "illegal",
                "fake",
                "guaranteed",
                "instant",
                "fast cash",
                "easy money",
                "bankruptcy",
                "debt",
                "collection",
                "lawsuit",
                "legal",
                "jobs",
                "career",
                "training",
                "certification",
                "license",
            ],
            "education": [
                "free",
                "cheap",
                "pirated",
                "torrent",
                "download",
                "crack",
                "fake",
                "diploma mill",
                "scam",
                "fraud",
                "unaccredited",
                "jobs",
                "career",
                "salary",
                "employment",
                "hiring",
                "test answers",
                "cheat",
                "plagiarism",
                "homework help",
            ],
            "general": [
                "free",
                "cheap",
                "jobs",
                "career",
                "hiring",
                "employment",
                "diy",
                "how to",
                "tutorial",
                "instructions",
                "manual",
                "used",
                "second hand",
                "broken",
                "repair",
                "fix",
                "problem",
                "scam",
                "fraud",
                "fake",
                "illegal",
                "pirated",
                "torrent",
            ],
        }

        # Get relevant templates for the industry
        template_keywords = industry_templates.get(
            industry, industry_templates["general"]
        )

        for keyword in template_keywords:
            if keyword.lower() not in existing_negative_texts:
                # Estimate potential savings based on industry and keyword type
                estimated_savings = self._estimate_template_savings(
                    keyword, industry, campaigns
                )

                suggestions.append(
                    {
                        "keyword": keyword,
                        "type": "industry_template",
                        "reason": f"Industry best practice for {industry} - commonly irrelevant search term",
                        "priority": "medium",
                        "confidence": 0.7,  # Medium confidence for templates
                        "potential_savings": estimated_savings,
                        "match_type": "broad",  # Broad match for template keywords
                        "campaign_applicability": "all",
                        "industry": industry,
                        "template_category": self._categorize_template_keyword(keyword),
                    }
                )

        return suggestions

    def _analyze_search_term_patterns(
        self, search_terms: list[SearchTerm], existing_negatives: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Analyze search terms for patterns that suggest negative keywords."""
        suggestions = []
        existing_negative_texts = {
            neg.get("text", "").lower() for neg in existing_negatives
        }

        # Analyze 2-gram and 3-gram patterns
        for n in [2, 3]:
            ngram_stats = self._extract_ngram_stats(search_terms, n)

            for ngram, stats in ngram_stats.items():
                if ngram.lower() in existing_negative_texts:
                    continue

                # Consider n-gram for negative if it has poor performance
                if (
                    stats["occurrences"] >= 3  # Appears multiple times (lowered from 5)
                    and stats["total_cost"] >= 50  # Significant cost (lowered from 100)
                    and stats["conversion_rate"] < 0.01  # Very low conversion rate
                ):
                    suggestions.append(
                        {
                            "keyword": ngram,
                            "type": "ngram_pattern",
                            "reason": f"N-gram pattern with {stats['occurrences']} occurrences, ${stats['total_cost']:.2f} cost, {stats['conversion_rate']:.1%} conversion rate",
                            "priority": "medium"
                            if stats["total_cost"] > 200
                            else "low",
                            "confidence": min(
                                0.9, stats["occurrences"] / 10
                            ),  # Higher confidence with more occurrences
                            "potential_savings": stats["total_cost"],
                            "match_type": "phrase",
                            "campaign_applicability": "all",
                            "pattern_stats": stats,
                            "ngram_length": n,
                        }
                    )

        return sorted(suggestions, key=lambda x: x["potential_savings"], reverse=True)

    def _analyze_competitor_terms(
        self, search_terms: list[SearchTerm], existing_negatives: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Analyze search terms for competitor brand names and suggest as negatives."""
        suggestions = []
        existing_negative_texts = {
            neg.get("text", "").lower() for neg in existing_negatives
        }

        # Common competitor indicators
        competitor_indicators = [
            "vs",
            "versus",
            "compared to",
            "alternative to",
            "instead of",
            "better than",
            "competitor",
            "competition",
            "rival",
        ]

        # Brand name patterns (simplified - would need industry-specific logic)
        potential_brand_patterns = [
            r"\b[A-Z][a-z]+\s+(brand|company|inc|corp|llc)\b",
            r"\b[A-Z]{2,}\b",  # All caps words (often brands)
        ]

        for term in search_terms:
            search_term = term.search_term.lower()
            cost = term.cost
            conversions = int(term.conversions)

            # Skip if already exists as negative
            if search_term in existing_negative_texts:
                continue

            # Check for competitor indicators
            has_competitor_indicator = any(
                indicator in search_term for indicator in competitor_indicators
            )

            # Simple competitor detection (would be enhanced with brand databases)
            if has_competitor_indicator and cost > 50 and conversions == 0:
                suggestions.append(
                    {
                        "keyword": search_term,
                        "type": "competitor_terms",
                        "reason": f"Contains competitor indicators and no conversions with ${cost:.2f} cost",
                        "priority": "high" if cost > 200 else "medium",
                        "confidence": 0.8,
                        "potential_savings": cost,
                        "match_type": "phrase",
                        "campaign_applicability": "all",
                        "competitor_indicators": [
                            ind for ind in competitor_indicators if ind in search_term
                        ],
                    }
                )

        return sorted(suggestions, key=lambda x: x["potential_savings"], reverse=True)

    def _prioritize_by_roi(
        self, suggestions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Prioritize suggestions by ROI potential."""
        for suggestion in suggestions:
            # Calculate ROI score based on potential savings, confidence, and priority
            potential_savings = suggestion.get("potential_savings", 0)
            confidence = suggestion.get("confidence", 0.5)
            priority_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            priority_weight = priority_weights.get(suggestion.get("priority", "low"), 1)

            # ROI score formula
            roi_score = (potential_savings * confidence * priority_weight) / 100
            suggestion["roi_score"] = roi_score

        return sorted(suggestions, key=lambda x: x["roi_score"], reverse=True)

    def _generate_bulk_recommendations(
        self,
        suggestions: list[dict[str, Any]],
        campaigns: list[Campaign],
        auto_apply: bool,
    ) -> list[Recommendation]:
        """Generate bulk application recommendations."""
        recommendations = []

        if not suggestions:
            return recommendations

        # High-priority bulk recommendation
        high_priority_suggestions = [
            s for s in suggestions[:20] if s.get("priority") in ["critical", "high"]
        ]

        if high_priority_suggestions:
            total_savings = sum(
                s.get("potential_savings", 0) for s in high_priority_suggestions
            )

            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.HIGH,
                    title=f"Apply {len(high_priority_suggestions)} high-priority negative keywords",
                    description=(
                        f"Implement {len(high_priority_suggestions)} negative keywords with high ROI potential. "
                        f"These keywords are currently wasting approximately ${total_savings:.2f} in spend "
                        f"with minimal or no conversion value. Applying these negatives could significantly "
                        f"improve campaign efficiency and reduce wasted spend."
                    ),
                    estimated_cost_savings=total_savings,
                    action_data={
                        "bulk_apply": True,
                        "auto_apply": auto_apply,
                        "negative_keywords": high_priority_suggestions,
                        "application_method": "shared_list",
                        "shared_list_name": "High-Priority Automated Negatives",
                    },
                )
            )

        # Industry template recommendation
        template_suggestions = [
            s for s in suggestions if s.get("type") == "industry_template"
        ]
        if template_suggestions:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.MEDIUM,
                    title="Apply industry-specific negative keyword template",
                    description=(
                        f"Implement {len(template_suggestions)} industry best-practice negative keywords. "
                        f"These keywords are commonly irrelevant for your industry and can prevent "
                        f"wasted impressions and clicks on non-converting traffic."
                    ),
                    estimated_cost_savings=sum(
                        s.get("potential_savings", 0) for s in template_suggestions
                    ),
                    action_data={
                        "bulk_apply": True,
                        "auto_apply": auto_apply,
                        "negative_keywords": template_suggestions,
                        "application_method": "shared_list",
                        "shared_list_name": f"Industry Template - {template_suggestions[0].get('industry', 'General')}",
                    },
                )
            )

        # Pattern-based recommendation
        pattern_suggestions = [
            s for s in suggestions if s.get("type") == "ngram_pattern"
        ]
        if pattern_suggestions:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.MEDIUM,
                    title="Apply pattern-based negative keywords",
                    description=(
                        f"Implement {len(pattern_suggestions)} negative keywords identified through "
                        f"search term pattern analysis. These patterns show poor performance across "
                        f"multiple search terms and can be safely negated."
                    ),
                    estimated_cost_savings=sum(
                        s.get("potential_savings", 0) for s in pattern_suggestions
                    ),
                    action_data={
                        "bulk_apply": True,
                        "auto_apply": auto_apply,
                        "negative_keywords": pattern_suggestions,
                        "application_method": "shared_list",
                        "shared_list_name": "Pattern-Based Negatives",
                    },
                )
            )

        return recommendations

    def _calculate_confidence(
        self, clicks: int, impressions: int, cost: float
    ) -> float:
        """Calculate confidence score based on data volume."""
        # More clicks and impressions = higher confidence
        data_volume_score = min(1.0, (clicks + impressions / 10) / 100)

        # Higher cost = higher confidence in the decision
        cost_score = min(1.0, cost / 500)

        return (data_volume_score + cost_score) / 2

    def _get_performance_reason(
        self, cpa: float, ctr: float, roas: float, conversions: int, cost: float
    ) -> str:
        """Generate human-readable reason for negative keyword suggestion."""
        reasons = []

        if conversions == 0 and cost > self.min_cost_threshold:
            reasons.append(f"No conversions with ${cost:.2f} spend")

        if cpa > self.cpa_threshold and conversions > 0:
            reasons.append(f"High CPA of ${cpa:.2f} (threshold: ${self.cpa_threshold})")

        if ctr < self.ctr_threshold:
            reasons.append(
                f"Low CTR of {ctr:.2%} (threshold: {self.ctr_threshold:.2%})"
            )

        if roas < self.roas_threshold and roas > 0:
            reasons.append(f"Low ROAS of {roas:.2f} (threshold: {self.roas_threshold})")

        return "; ".join(reasons) if reasons else "Poor overall performance metrics"

    def _estimate_template_savings(
        self, keyword: str, industry: str, campaigns: list[Campaign]
    ) -> float:
        """Estimate potential savings from template keywords."""
        # Base estimate on industry and campaign spend
        total_campaign_cost = sum(c.cost for c in campaigns)

        # Estimate that template keywords typically save 1-3% of total spend
        keyword_risk_factors = {
            "free": 0.03,
            "cheap": 0.02,
            "jobs": 0.015,
            "career": 0.015,
            "diy": 0.01,
            "used": 0.01,
            "scam": 0.005,
            "fraud": 0.005,
        }

        risk_factor = keyword_risk_factors.get(keyword.lower(), 0.01)
        return total_campaign_cost * risk_factor

    def _categorize_template_keyword(self, keyword: str) -> str:
        """Categorize template keywords by type."""
        categories = {
            "price_sensitive": ["free", "cheap", "discount", "sale", "coupon"],
            "employment": ["jobs", "career", "hiring", "employment", "work"],
            "quality_concerns": ["used", "broken", "repair", "fix", "problem"],
            "fraud_related": ["scam", "fraud", "fake", "illegal", "pirated"],
            "diy_related": ["diy", "how to", "tutorial", "instructions", "manual"],
            "general": [],
        }

        for category, keywords in categories.items():
            if keyword.lower() in keywords:
                return category
        return "general"

    def _extract_ngram_stats(
        self, search_terms: list[SearchTerm], n: int
    ) -> dict[str, dict[str, Any]]:
        """Extract n-gram statistics from search terms."""
        ngram_stats = {}

        for term in search_terms:
            search_term = term.search_term.lower()
            cost = term.cost
            conversions = int(term.conversions)
            clicks = term.clicks

            words = search_term.split()
            for i in range(len(words) - n + 1):
                ngram = " ".join(words[i : i + n])

                if ngram not in ngram_stats:
                    ngram_stats[ngram] = {
                        "occurrences": 0,
                        "total_cost": 0,
                        "total_conversions": 0,
                        "total_clicks": 0,
                    }

                ngram_stats[ngram]["occurrences"] += 1
                ngram_stats[ngram]["total_cost"] += cost
                ngram_stats[ngram]["total_conversions"] += conversions
                ngram_stats[ngram]["total_clicks"] += clicks

        # Calculate conversion rates
        for ngram, stats in ngram_stats.items():
            stats["conversion_rate"] = (
                stats["total_conversions"] / stats["total_clicks"]
                if stats["total_clicks"] > 0
                else 0
            )

        return ngram_stats

    def _calculate_conversion_loss_prevented(
        self, suggestions: list[dict[str, Any]]
    ) -> float:
        """Calculate potential conversion loss prevented by implementing suggestions."""
        # Estimate that for every dollar saved, we prevent loss of low-value conversions
        total_savings = sum(s.get("potential_savings", 0) for s in suggestions)

        # Assume prevented conversions at 1/10th the value of normal conversions
        prevented_conversion_value = total_savings / (
            self.conversion_value_per_conversion * 10
        )

        return prevented_conversion_value
