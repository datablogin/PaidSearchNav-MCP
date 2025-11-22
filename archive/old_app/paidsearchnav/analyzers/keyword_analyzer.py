"""Keyword Performance Analyzer.

This analyzer provides comprehensive keyword-level analysis functionality,
including performance metrics, quality score analysis, cost efficiency,
and optimization opportunities beyond basic match type analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    AnalysisMetrics,
    AnalysisResult,
    Keyword,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.search_term import SearchTerm

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


class KeywordAnalysisResult(AnalysisResult):
    """Result of comprehensive keyword analysis."""

    analysis_type: str = "keyword_analysis"

    # Performance analysis
    top_performers: list[Keyword] = []
    bottom_performers: list[Keyword] = []
    deteriorating_keywords: list[dict[str, Any]] = []
    seasonal_patterns: dict[str, Any] = {}

    # Quality score analysis
    quality_score_distribution: dict[int, int] = {}
    low_quality_keywords: list[Keyword] = []
    quality_correlations: dict[str, float] = {}

    # Cost efficiency analysis
    high_cost_low_conversion: list[Keyword] = []
    budget_wasters: list[Keyword] = []
    cpa_outliers: list[Keyword] = []

    # Opportunity identification
    high_impression_low_ctr: list[Keyword] = []
    good_ctr_low_impression: list[Keyword] = []
    negative_candidates: list[str] = []
    no_impression_keywords: list[Keyword] = []

    # Search term integration
    search_term_gaps: list[dict[str, Any]] = []
    high_performing_search_terms: list[dict[str, Any]] = []
    keyword_coverage_analysis: dict[str, Any] = {}

    # Local intent analysis
    local_intent_keywords: list[dict[str, Any]] = []
    local_performance_summary: dict[str, Any] = {}

    # Summary metrics
    total_keywords_analyzed: int = 0
    avg_quality_score: float = 0.0
    median_cpc: float = 0.0
    median_cpa: float = 0.0
    cost_efficiency_score: float = 0.0
    optimization_opportunities: int = 0


class KeywordAnalyzer(Analyzer):
    """Analyzes keyword performance and opportunities."""

    def __init__(
        self,
        data_provider: DataProvider,
        min_impressions: int = 10,
        high_cost_threshold: float = 100.0,
        low_ctr_threshold: float = 1.0,
        high_ctr_threshold: float = 5.0,
        low_impression_threshold: int = 100,
        high_impression_threshold: int = 10000,
        quality_score_threshold: int = 5,
        cpa_outlier_multiplier: float = 3.0,
        cost_percentile_threshold: float = 90.0,
        local_patterns: list[str] | None = None,
        match_type_conversion_threshold: int = 2,
        match_type_ctr_threshold: float = 0.05,
        match_type_clicks_threshold: int = 10,
    ):
        """Initialize the keyword analyzer.

        Args:
            data_provider: Data provider for fetching keyword data
            min_impressions: Minimum impressions to include in main analysis
            high_cost_threshold: Cost threshold for high-cost keyword flagging
            low_ctr_threshold: CTR threshold for low-performing keywords
            high_ctr_threshold: CTR threshold for high-performing keywords
            low_impression_threshold: Impression threshold for bid opportunities
            high_impression_threshold: Impression threshold for high-volume analysis
            quality_score_threshold: Quality score threshold for improvement
            cpa_outlier_multiplier: Multiplier for CPA outlier detection
            cost_percentile_threshold: Percentile threshold for cost analysis
        """
        self.data_provider = data_provider
        self.min_impressions = min_impressions
        self.high_cost_threshold = high_cost_threshold
        self.low_ctr_threshold = low_ctr_threshold
        self.high_ctr_threshold = high_ctr_threshold
        self.low_impression_threshold = low_impression_threshold
        self.high_impression_threshold = high_impression_threshold
        self.quality_score_threshold = quality_score_threshold
        self.cpa_outlier_multiplier = cpa_outlier_multiplier
        self.cost_percentile_threshold = cost_percentile_threshold

        # Local intent patterns - configurable for different businesses
        self.local_patterns = local_patterns or [
            "near me",
            "nearby",
            "near my location",
            "close to me",
            "in my area",
            "local",
            "around me",
            "directions to",
            "how to get to",
            "closest",
            "nearest",
        ]

        # Match type suggestion thresholds
        self.match_type_conversion_threshold = match_type_conversion_threshold
        self.match_type_ctr_threshold = match_type_ctr_threshold
        self.match_type_clicks_threshold = match_type_clicks_threshold

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Keyword Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes keyword performance and optimization opportunities beyond "
            "basic match type analysis, including quality scores, cost efficiency, "
            "and performance patterns."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> KeywordAnalysisResult:
        """Perform comprehensive keyword analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional parameters (campaigns, ad_groups)

        Returns:
            Comprehensive keyword analysis results
        """
        logger.info(f"Starting keyword analysis for customer {customer_id}")

        # Get optional filters
        campaigns = kwargs.get("campaigns")
        ad_groups = kwargs.get("ad_groups")

        # Fetch keyword data
        keywords = await self.data_provider.get_keywords(
            customer_id=customer_id,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        if not keywords:
            logger.warning("No keywords found for analysis")
            return self._create_empty_result(customer_id, start_date, end_date)

        logger.info(f"Analyzing {len(keywords)} keywords")

        # Filter keywords for main analysis (exclude very low impression keywords)
        analysis_keywords = [
            k for k in keywords if k.impressions >= self.min_impressions
        ]

        # Create DataFrame for efficient analysis
        df = self._create_keyword_dataframe(analysis_keywords)

        # Perform analysis
        performance_analysis = self._analyze_performance(df, keywords)
        quality_analysis = self._analyze_quality_scores(df, keywords)
        cost_efficiency = self._analyze_cost_efficiency(df, keywords)
        opportunities = self._identify_opportunities(df, keywords)

        # Analyze search term integration if available
        search_term_analysis = await self._analyze_search_term_integration(
            keywords, customer_id, campaigns, ad_groups
        )

        # Perform local intent analysis for retail businesses
        local_intent_analysis = self._analyze_local_intent(keywords)

        # Calculate summary metrics
        summary_metrics = self._calculate_summary_metrics(df, keywords)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            performance_analysis,
            quality_analysis,
            cost_efficiency,
            opportunities,
            search_term_analysis,
            local_intent_analysis,
        )

        # Calculate optimization opportunities count
        optimization_count = (
            len(opportunities["high_impression_low_ctr"])
            + len(opportunities["good_ctr_low_impression"])
            + len(cost_efficiency["high_cost_low_conversion"])
            + len(quality_analysis["low_quality_keywords"])
        )

        # Create analysis metrics
        metrics = AnalysisMetrics(
            total_keywords_analyzed=len(analysis_keywords),
            issues_found=optimization_count,
            critical_issues=len(
                [
                    r
                    for r in recommendations
                    if r.priority == RecommendationPriority.CRITICAL
                ]
            ),
            potential_cost_savings=self._calculate_potential_savings(
                cost_efficiency, opportunities
            ),
            custom_metrics={
                "avg_quality_score": summary_metrics["avg_quality_score"],
                "median_cpc": summary_metrics["median_cpc"],
                "median_cpa": summary_metrics["median_cpa"],
                "cost_efficiency_score": summary_metrics["cost_efficiency_score"],
            },
        )

        return KeywordAnalysisResult(
            customer_id=customer_id,
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            recommendations=recommendations,
            # Performance analysis
            top_performers=performance_analysis["top_performers"],
            bottom_performers=performance_analysis["bottom_performers"],
            deteriorating_keywords=performance_analysis["deteriorating_keywords"],
            seasonal_patterns=performance_analysis["seasonal_patterns"],
            # Quality score analysis
            quality_score_distribution=quality_analysis["distribution"],
            low_quality_keywords=quality_analysis["low_quality_keywords"],
            quality_correlations=quality_analysis["correlations"],
            # Cost efficiency analysis
            high_cost_low_conversion=cost_efficiency["high_cost_low_conversion"],
            budget_wasters=cost_efficiency["budget_wasters"],
            cpa_outliers=cost_efficiency["cpa_outliers"],
            # Opportunities
            high_impression_low_ctr=opportunities["high_impression_low_ctr"],
            good_ctr_low_impression=opportunities["good_ctr_low_impression"],
            negative_candidates=opportunities["negative_candidates"],
            no_impression_keywords=opportunities["no_impression_keywords"],
            # Search term integration
            search_term_gaps=search_term_analysis.get("gaps", []),
            high_performing_search_terms=search_term_analysis.get(
                "high_performers", []
            ),
            keyword_coverage_analysis=search_term_analysis.get("coverage", {}),
            # Local intent analysis
            local_intent_keywords=local_intent_analysis.get("local_keywords", []),
            local_performance_summary=local_intent_analysis.get("summary", {}),
            # Summary
            total_keywords_analyzed=len(analysis_keywords),
            avg_quality_score=summary_metrics["avg_quality_score"],
            median_cpc=summary_metrics["median_cpc"],
            median_cpa=summary_metrics["median_cpa"],
            cost_efficiency_score=summary_metrics["cost_efficiency_score"],
            optimization_opportunities=optimization_count,
            raw_data={
                "keyword_dataframe": df.to_dict("records") if not df.empty else [],
                "total_keywords": len(keywords),
                "filtered_keywords": len(analysis_keywords),
                "analysis_parameters": {
                    "min_impressions": self.min_impressions,
                    "high_cost_threshold": self.high_cost_threshold,
                    "quality_score_threshold": self.quality_score_threshold,
                },
            },
        )

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> KeywordAnalysisResult:
        """Create empty result when no keywords are found."""
        return KeywordAnalysisResult(
            customer_id=customer_id,
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            metrics=AnalysisMetrics(),
            recommendations=[],
            raw_data={
                "keyword_dataframe": [],
                "total_keywords": 0,
                "filtered_keywords": 0,
                "analysis_parameters": {
                    "min_impressions": self.min_impressions,
                    "high_cost_threshold": self.high_cost_threshold,
                    "quality_score_threshold": self.quality_score_threshold,
                },
            },
        )

    def _create_keyword_dataframe(self, keywords: list[Keyword]) -> pd.DataFrame:
        """Create pandas DataFrame from keywords for efficient analysis."""
        if not keywords:
            return pd.DataFrame()

        data = []
        for keyword in keywords:
            data.append(
                {
                    "keyword_id": keyword.keyword_id,
                    "text": keyword.text,
                    "match_type": keyword.match_type,
                    "campaign_id": keyword.campaign_id,
                    "campaign_name": keyword.campaign_name,
                    "ad_group_id": keyword.ad_group_id,
                    "ad_group_name": keyword.ad_group_name,
                    "status": keyword.status,
                    "quality_score": keyword.quality_score,
                    "cpc_bid": keyword.cpc_bid or 0.0,
                    "impressions": keyword.impressions,
                    "clicks": keyword.clicks,
                    "cost": keyword.cost,
                    "conversions": keyword.conversions,
                    "conversion_value": keyword.conversion_value,
                    "ctr": keyword.ctr,
                    "avg_cpc": keyword.avg_cpc,
                    "conversion_rate": keyword.conversion_rate,
                    "cpa": keyword.cpa,
                    "keyword_obj": keyword,  # Keep reference to original object
                }
            )

        df = pd.DataFrame(data)

        # Add calculated fields
        if not df.empty:
            df["roas"] = df.apply(
                lambda row: row["conversion_value"] / row["cost"]
                if row["cost"] > 0
                else 0.0,
                axis=1,
            )
            df["keyword_length"] = df["text"].str.len()
            df["word_count"] = df["text"].str.split().str.len()

        return df

    def _analyze_performance(
        self, df: pd.DataFrame, all_keywords: list[Keyword]
    ) -> dict[str, Any]:
        """Analyze keyword performance patterns."""
        if df.empty:
            return {
                "top_performers": [],
                "bottom_performers": [],
                "deteriorating_keywords": [],
                "seasonal_patterns": {},
            }

        # Top performers (by conversion value, then CTR)
        top_performers_df = df[
            (df["conversions"] > 0) & (df["conversion_value"] > 0)
        ].nlargest(10, "conversion_value")

        # Bottom performers (high cost, no conversions or very low CTR)
        bottom_performers_df = df[
            (df["cost"] > self.high_cost_threshold / 2)
            & ((df["conversions"] == 0) | (df["ctr"] < self.low_ctr_threshold))
        ].nlargest(10, "cost")

        # Deteriorating keywords (keywords with declining performance)
        # Note: This would require historical data comparison in a real implementation
        deteriorating_keywords = self._identify_deteriorating_keywords(df)

        # Seasonal patterns analysis
        seasonal_patterns = self._analyze_seasonal_patterns(df)

        return {
            "top_performers": [
                row["keyword_obj"] for _, row in top_performers_df.iterrows()
            ],
            "bottom_performers": [
                row["keyword_obj"] for _, row in bottom_performers_df.iterrows()
            ],
            "deteriorating_keywords": deteriorating_keywords,
            "seasonal_patterns": seasonal_patterns,
        }

    def _analyze_quality_scores(
        self, df: pd.DataFrame, all_keywords: list[Keyword]
    ) -> dict[str, Any]:
        """Analyze quality score distribution and correlations."""
        if df.empty:
            return {
                "distribution": {},
                "low_quality_keywords": [],
                "correlations": {},
            }

        # Quality score distribution
        qs_df = df.dropna(subset=["quality_score"])
        distribution = {}
        if not qs_df.empty:
            distribution = qs_df["quality_score"].value_counts().to_dict()

        # Low quality keywords
        low_quality_df = df[
            (df["quality_score"].notna())
            & (df["quality_score"] < self.quality_score_threshold)
            & (df["cost"] > 0)
        ].nlargest(20, "cost")

        # Quality score correlations with performance metrics
        correlations = {}
        if not qs_df.empty and len(qs_df) > 1:
            try:
                correlations = {
                    "quality_vs_ctr": qs_df["quality_score"].corr(qs_df["ctr"]),
                    "quality_vs_cpc": qs_df["quality_score"].corr(qs_df["avg_cpc"]),
                    "quality_vs_cpa": qs_df["quality_score"].corr(qs_df["cpa"]),
                    "quality_vs_conversion_rate": qs_df["quality_score"].corr(
                        qs_df["conversion_rate"]
                    ),
                }
                # Remove NaN correlations
                correlations = {k: v for k, v in correlations.items() if pd.notna(v)}
            except Exception as e:
                logger.warning(f"Could not calculate quality score correlations: {e}")

        return {
            "distribution": distribution,
            "low_quality_keywords": [
                row["keyword_obj"] for _, row in low_quality_df.iterrows()
            ],
            "correlations": correlations,
        }

    def _analyze_cost_efficiency(
        self, df: pd.DataFrame, all_keywords: list[Keyword]
    ) -> dict[str, Any]:
        """Analyze cost efficiency and identify budget wasters."""
        if df.empty:
            return {
                "high_cost_low_conversion": [],
                "budget_wasters": [],
                "cpa_outliers": [],
            }

        # High cost, low conversion keywords
        high_cost_low_conv = df[
            (df["cost"] > self.high_cost_threshold) & (df["conversions"] <= 1)
        ].nlargest(15, "cost")

        # Budget wasters (high cost, no conversions)
        budget_wasters = df[
            (df["cost"] > self.high_cost_threshold / 2) & (df["conversions"] == 0)
        ].nlargest(15, "cost")

        # CPA outliers
        cpa_outliers = []
        converting_df = df[(df["conversions"] > 0) & (df["cpa"] > 0)]
        if not converting_df.empty and len(converting_df) > 1:
            try:
                median_cpa = converting_df["cpa"].median()
                outlier_threshold = median_cpa * self.cpa_outlier_multiplier
                cpa_outliers_df = converting_df[
                    converting_df["cpa"] > outlier_threshold
                ].nlargest(10, "cpa")
                cpa_outliers = [
                    row["keyword_obj"] for _, row in cpa_outliers_df.iterrows()
                ]
            except Exception as e:
                logger.warning(f"Could not identify CPA outliers: {e}")

        return {
            "high_cost_low_conversion": [
                row["keyword_obj"] for _, row in high_cost_low_conv.iterrows()
            ],
            "budget_wasters": [
                row["keyword_obj"] for _, row in budget_wasters.iterrows()
            ],
            "cpa_outliers": cpa_outliers,
        }

    def _identify_opportunities(
        self, df: pd.DataFrame, all_keywords: list[Keyword]
    ) -> dict[str, Any]:
        """Identify optimization opportunities."""
        if df.empty:
            return {
                "high_impression_low_ctr": [],
                "good_ctr_low_impression": [],
                "negative_candidates": [],
                "no_impression_keywords": [],
            }

        # High impressions but low CTR (bid/ad optimization opportunity)
        high_imp_low_ctr = df[
            (df["impressions"] > self.high_impression_threshold)
            & (df["ctr"] < self.low_ctr_threshold)
        ].nlargest(15, "impressions")

        # Good CTR but low impressions (bid increase opportunity)
        good_ctr_low_imp = df[
            (df["ctr"] > self.high_ctr_threshold)
            & (df["impressions"] < self.low_impression_threshold)
            & (df["impressions"] > 0)
        ].nlargest(15, "ctr")

        # Potential negative keyword candidates
        negative_candidates = self._identify_negative_candidates(df)

        # No impression keywords
        no_impression_keywords = [k for k in all_keywords if k.impressions == 0]

        return {
            "high_impression_low_ctr": [
                row["keyword_obj"] for _, row in high_imp_low_ctr.iterrows()
            ],
            "good_ctr_low_impression": [
                row["keyword_obj"] for _, row in good_ctr_low_imp.iterrows()
            ],
            "negative_candidates": negative_candidates,
            "no_impression_keywords": no_impression_keywords[:20],  # Limit to top 20
        }

    def _identify_deteriorating_keywords(
        self, df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        """Identify keywords with deteriorating performance.

        Note: This is a placeholder implementation. In practice, this would
        require historical performance data to compare trends.
        """
        # Placeholder implementation - in practice would compare historical performance
        deteriorating = []

        # Simple heuristic: high cost keywords with poor recent performance
        poor_performers = df[
            (df["cost"] > self.high_cost_threshold)
            & (df["ctr"] < self.low_ctr_threshold)
            & (df["conversions"] == 0)
        ]

        for _, row in poor_performers.head(10).iterrows():
            deteriorating.append(
                {
                    "keyword": row["keyword_obj"],
                    "trend": "declining",
                    "reason": "High cost with poor CTR and no conversions",
                    "recommended_action": "Pause or reduce bid",
                }
            )

        return deteriorating

    def _analyze_seasonal_patterns(self, df: pd.DataFrame) -> dict[str, Any]:
        """Analyze seasonal performance patterns.

        Note: This is a placeholder implementation. In practice, this would
        require time-series data to identify seasonal trends.
        """
        # Placeholder implementation - would require historical time-series data
        return {
            "patterns_detected": False,
            "reason": "Requires historical time-series data for pattern analysis",
            "recommendations": "Implement time-series analysis with historical data",
        }

    def _identify_negative_candidates(self, df: pd.DataFrame) -> list[str]:
        """Identify potential negative keyword candidates."""
        negative_candidates = []

        # Keywords with high cost, low/no conversions, and poor CTR
        poor_performers = df[
            (df["cost"] > self.high_cost_threshold / 3)
            & (df["conversions"] == 0)
            & (df["ctr"] < self.low_ctr_threshold / 2)
        ]

        # Extract common terms that might be good negative candidates
        for _, row in poor_performers.iterrows():
            words = row["text"].lower().split()
            for word in words:
                if len(word) > 3 and word not in negative_candidates:
                    negative_candidates.append(word)

        return negative_candidates[:10]  # Return top 10 candidates

    def _calculate_summary_metrics(
        self, df: pd.DataFrame, all_keywords: list[Keyword]
    ) -> dict[str, float]:
        """Calculate summary metrics for the analysis."""
        if df.empty:
            return {
                "avg_quality_score": 0.0,
                "median_cpc": 0.0,
                "median_cpa": 0.0,
                "cost_efficiency_score": 0.0,
            }

        # Average quality score
        qs_keywords = df.dropna(subset=["quality_score"])
        avg_quality_score = (
            qs_keywords["quality_score"].mean() if not qs_keywords.empty else 0.0
        )

        # Median CPC
        cpc_keywords = df[df["avg_cpc"] > 0]
        median_cpc = cpc_keywords["avg_cpc"].median() if not cpc_keywords.empty else 0.0

        # Median CPA
        cpa_keywords = df[df["cpa"] > 0]
        median_cpa = cpa_keywords["cpa"].median() if not cpa_keywords.empty else 0.0

        # Cost efficiency score (0-100)
        cost_efficiency_score = self._calculate_cost_efficiency_score(df)

        return {
            "avg_quality_score": round(avg_quality_score, 2),
            "median_cpc": round(median_cpc, 2),
            "median_cpa": round(median_cpa, 2),
            "cost_efficiency_score": round(cost_efficiency_score, 2),
        }

    def _calculate_cost_efficiency_score(self, df: pd.DataFrame) -> float:
        """Calculate overall cost efficiency score (0-100)."""
        if df.empty:
            return 0.0

        score = 50.0  # Start with neutral score

        # Factor 1: Conversion rate
        total_clicks = df["clicks"].sum()
        total_conversions = df["conversions"].sum()
        if total_clicks > 0:
            conversion_rate = (total_conversions / total_clicks) * 100
            if conversion_rate > 5.0:  # Excellent
                score += 20
            elif conversion_rate > 2.0:  # Good
                score += 10
            elif conversion_rate < 0.5:  # Poor
                score -= 20

        # Factor 2: ROAS distribution
        roas_keywords = df[df["roas"] > 0]
        if not roas_keywords.empty:
            avg_roas = roas_keywords["roas"].mean()
            if avg_roas > 4.0:  # Excellent ROAS
                score += 15
            elif avg_roas > 2.0:  # Good ROAS
                score += 10
            elif avg_roas < 1.0:  # Poor ROAS
                score -= 20

        # Factor 3: Quality score distribution
        qs_keywords = df.dropna(subset=["quality_score"])
        if not qs_keywords.empty:
            avg_qs = qs_keywords["quality_score"].mean()
            if avg_qs >= 8:  # Excellent
                score += 10
            elif avg_qs >= 6:  # Good
                score += 5
            elif avg_qs < 5:  # Poor
                score -= 15

        # Factor 4: Cost concentration (avoid too much spend on few keywords)
        if len(df) > 0:
            cost_sorted = df.sort_values("cost", ascending=False)
            top_10_percent = max(1, len(cost_sorted) // 10)
            top_10_cost = cost_sorted.head(top_10_percent)["cost"].sum()
            total_cost = df["cost"].sum()

            if total_cost > 0:
                concentration = top_10_cost / total_cost
                if concentration > 0.8:  # Too concentrated
                    score -= 10
                elif concentration < 0.5:  # Well distributed
                    score += 5

        return max(0.0, min(100.0, score))

    def _calculate_potential_savings(
        self, cost_efficiency: dict[str, Any], opportunities: dict[str, Any]
    ) -> float:
        """Calculate potential monthly cost savings."""
        savings = 0.0

        # Savings from budget wasters (assume 80% can be saved)
        budget_wasters = cost_efficiency.get("budget_wasters", [])
        for keyword in budget_wasters:
            savings += keyword.cost * 0.8

        # Savings from high cost, low conversion keywords (assume 50% can be saved)
        high_cost_low_conv = cost_efficiency.get("high_cost_low_conversion", [])
        for keyword in high_cost_low_conv:
            savings += keyword.cost * 0.5

        # Savings from CPA outliers (assume 30% improvement)
        cpa_outliers = cost_efficiency.get("cpa_outliers", [])
        for keyword in cpa_outliers:
            if keyword.conversions > 0:
                current_cost = keyword.cost
                improved_cost = current_cost * 0.7  # 30% improvement
                savings += current_cost - improved_cost

        return round(savings, 2)

    def _generate_recommendations(
        self,
        performance_analysis: dict[str, Any],
        quality_analysis: dict[str, Any],
        cost_efficiency: dict[str, Any],
        opportunities: dict[str, Any],
        search_term_analysis: dict[str, Any] | None = None,
        local_intent_analysis: dict[str, Any] | None = None,
    ) -> list[Recommendation]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # High priority: Budget wasters
        budget_wasters = cost_efficiency.get("budget_wasters", [])
        if budget_wasters:
            total_waste = sum(k.cost for k in budget_wasters)
            recommendations.append(
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORDS,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"Pause {len(budget_wasters)} budget-wasting keywords",
                    description=(
                        f"Found {len(budget_wasters)} keywords with ${total_waste:.2f} "
                        f"in spend but zero conversions. Top waster: '{budget_wasters[0].text}' "
                        f"(${budget_wasters[0].cost:.2f})."
                    ),
                    estimated_cost_savings=total_waste * 0.8,
                    action_data={
                        "keyword_ids": [k.keyword_id for k in budget_wasters[:10]]
                    },
                )
            )

        # High priority: Low quality keywords
        low_quality = quality_analysis.get("low_quality_keywords", [])
        if low_quality:
            total_low_quality_cost = sum(k.cost for k in low_quality)
            recommendations.append(
                Recommendation(
                    type=RecommendationType.IMPROVE_QUALITY_SCORE,
                    priority=RecommendationPriority.HIGH,
                    title=f"Improve {len(low_quality)} low quality score keywords",
                    description=(
                        f"Keywords with quality score < {self.quality_score_threshold} "
                        f"spent ${total_low_quality_cost:.2f}. Improve ad relevance, "
                        f"landing pages, and expected CTR."
                    ),
                    estimated_conversion_increase=15.0,
                    action_data={
                        "keyword_ids": [k.keyword_id for k in low_quality[:10]]
                    },
                )
            )

        # Medium priority: Bid optimization opportunities
        good_ctr_low_imp = opportunities.get("good_ctr_low_impression", [])
        if good_ctr_low_imp:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADJUST_BID,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Increase bids for {len(good_ctr_low_imp)} high-CTR keywords",
                    description=(
                        f"Found {len(good_ctr_low_imp)} keywords with good CTR "
                        f"(>{self.high_ctr_threshold}%) but low impressions. "
                        f"Consider increasing bids for more visibility."
                    ),
                    estimated_conversion_increase=10.0,
                    action_data={
                        "keyword_ids": [k.keyword_id for k in good_ctr_low_imp[:10]]
                    },
                )
            )

        # Medium priority: Ad optimization opportunities
        high_imp_low_ctr = opportunities.get("high_impression_low_ctr", [])
        if high_imp_low_ctr:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Optimize ads for {len(high_imp_low_ctr)} high-volume keywords",
                    description=(
                        f"Keywords with high impressions but low CTR "
                        f"(<{self.low_ctr_threshold}%). Improve ad copy and relevance."
                    ),
                    estimated_conversion_increase=20.0,
                    action_data={
                        "keyword_ids": [k.keyword_id for k in high_imp_low_ctr[:10]]
                    },
                )
            )

        # Medium priority: Negative keyword opportunities
        negative_candidates = opportunities.get("negative_candidates", [])
        if negative_candidates:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Add {len(negative_candidates)} negative keywords",
                    description=(
                        f"Identified {len(negative_candidates)} terms from poor-performing "
                        f"keywords that could be added as negatives: "
                        f"{', '.join(negative_candidates[:5])}"
                    ),
                    estimated_cost_savings=50.0,
                    action_data={"negative_keywords": negative_candidates},
                )
            )

        # Low priority: No impression keywords
        no_impression = opportunities.get("no_impression_keywords", [])
        if no_impression:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.LOW,
                    title=f"Review {len(no_impression)} keywords with no impressions",
                    description=(
                        f"Found {len(no_impression)} keywords with zero impressions. "
                        f"Check search volume, bids, and keyword relevance."
                    ),
                    action_data={
                        "keyword_ids": [k.keyword_id for k in no_impression[:20]]
                    },
                )
            )

        # High priority: CPA outliers
        cpa_outliers = cost_efficiency.get("cpa_outliers", [])
        if cpa_outliers:
            avg_cpa = sum(k.cpa for k in cpa_outliers) / len(cpa_outliers)
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_BIDDING,
                    priority=RecommendationPriority.HIGH,
                    title=f"Optimize {len(cpa_outliers)} high-CPA keywords",
                    description=(
                        f"Found {len(cpa_outliers)} keywords with CPA significantly "
                        f"above account average (avg: ${avg_cpa:.2f}). "
                        f"Consider bid adjustments or pausing."
                    ),
                    estimated_cost_savings=sum(k.cost * 0.3 for k in cpa_outliers),
                    action_data={"keyword_ids": [k.keyword_id for k in cpa_outliers]},
                )
            )

        # Search term integration recommendations
        if search_term_analysis:
            # High-performing search terms not yet keywords
            high_performers = search_term_analysis.get("high_performers", [])
            if high_performers:
                total_conversions = sum(hp["conversions"] for hp in high_performers)
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_KEYWORD,
                        priority=RecommendationPriority.CRITICAL,
                        title=f"Add {len(high_performers)} high-converting search terms as keywords",
                        description=(
                            f"Found {len(high_performers)} search terms with {total_conversions} total conversions "
                            f"that aren't keywords yet. Top performer: '{high_performers[0]['search_term']}' "
                            f"with {high_performers[0]['conversions']} conversions."
                        ),
                        estimated_revenue_increase=total_conversions
                        * 50.0,  # Estimate $50 per conversion
                        action_data={
                            "search_terms_to_add": [
                                {
                                    "term": hp["search_term"],
                                    "match_type": hp["suggested_match_type"],
                                    "reason": hp["reason"],
                                }
                                for hp in high_performers[:10]
                            ]
                        },
                    )
                )

            # Coverage analysis
            coverage = search_term_analysis.get("coverage", {})
            if coverage.get("coverage_percentage", 100) < 70:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.OPTIMIZE_KEYWORDS,
                        priority=RecommendationPriority.HIGH,
                        title="Improve keyword coverage of search terms",
                        description=(
                            f"Only {coverage.get('coverage_percentage', 0):.1f}% of search terms match existing keywords. "
                            f"This indicates potential missed opportunities. Review {coverage.get('gaps_count', 0)} "
                            f"unmatched search terms for keyword expansion."
                        ),
                        action_data={"coverage_metrics": coverage},
                    )
                )

        # Local intent recommendations for retail businesses
        if local_intent_analysis:
            local_summary = local_intent_analysis.get("summary", {})
            local_keywords = local_intent_analysis.get("local_keywords", [])

            if local_keywords and local_summary.get("local_conversion_rate", 0) > 5:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.OPTIMIZE_LOCATION,
                        priority=RecommendationPriority.HIGH,
                        title="Optimize high-performing local intent keywords",
                        description=(
                            f"Local intent keywords ({local_summary.get('total_local_keywords', 0)} keywords) "
                            f"are performing well with {local_summary.get('local_conversion_rate', 0):.1f}% "
                            f"conversion rate. Consider increasing bids on top performers and ensuring "
                            f"location extensions are active."
                        ),
                        estimated_revenue_increase=local_summary.get(
                            "local_conversions", 0
                        )
                        * 20,  # Conservative estimate
                        action_data={
                            "top_local_keywords": [
                                {
                                    "keyword": lk["keyword"],
                                    "conversions": lk["conversions"],
                                    "patterns": lk["detected_patterns"],
                                }
                                for lk in local_keywords[:5]
                            ],
                            "local_metrics": local_summary,
                        },
                    )
                )

            # Recommend adding more local keywords if percentage is low
            if local_summary.get("local_percentage", 0) < 15:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_KEYWORD,
                        priority=RecommendationPriority.MEDIUM,
                        title="Expand local intent keyword coverage",
                        description=(
                            f"Only {local_summary.get('local_percentage', 0):.1f}% of keywords have local intent. "
                            f"For retail businesses, consider adding more 'near me' and location-based keywords "
                            f"to capture local search traffic."
                        ),
                        action_data={
                            "suggested_patterns": [
                                "near me",
                                "nearby",
                                "closest",
                                "in [city]",
                            ],
                            "current_coverage": local_summary,
                        },
                    )
                )

        return recommendations

    async def _analyze_search_term_integration(
        self,
        keywords: list[Keyword],
        customer_id: str,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze search terms in relation to existing keywords.

        Returns:
            Dictionary containing:
            - gaps: Search terms that should be keywords but aren't
            - high_performers: High-performing search terms not yet keywords
            - coverage: Analysis of keyword coverage vs search terms
        """
        try:
            # Get search terms from data provider
            if hasattr(self.data_provider, "get_search_terms"):
                try:
                    search_terms = await self.data_provider.get_search_terms(
                        customer_id=customer_id,
                        campaigns=campaigns,
                        ad_groups=ad_groups,
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch search terms: {e}")
                    search_terms = []
            else:
                # Data provider doesn't support search terms
                logger.info("Data provider does not support search terms")
                search_terms = []

            if not search_terms:
                logger.info("No search terms available for integration analysis")
                return {"gaps": [], "high_performers": [], "coverage": {}}

            # Create sets for efficient lookup
            keyword_texts = {k.text.lower() for k in keywords}
            keyword_map = {k.text.lower(): k for k in keywords}

            # Analyze search terms
            gaps = []
            high_performers = []
            total_search_term_cost = 0.0
            total_search_term_conversions = 0.0
            matched_cost = 0.0
            matched_conversions = 0.0

            for term in search_terms:
                search_text = term.search_term.lower()
                total_search_term_cost += term.metrics.cost
                total_search_term_conversions += term.metrics.conversions

                # Check if search term exists as keyword
                if search_text not in keyword_texts:
                    # This is a gap - search term not in keywords
                    if term.metrics.conversions > 0:
                        # High-performing search term not yet a keyword
                        high_performers.append(
                            {
                                "search_term": term.search_term,
                                "conversions": term.metrics.conversions,
                                "cost": term.metrics.cost,
                                "cpa": term.metrics.cpa,
                                "impressions": term.metrics.impressions,
                                "clicks": term.metrics.clicks,
                                "suggested_match_type": self._suggest_match_type(term),
                                "reason": f"{term.metrics.conversions} conversions at ${term.metrics.cpa:.2f} CPA",
                            }
                        )

                    gaps.append(
                        {
                            "search_term": term.search_term,
                            "impressions": term.metrics.impressions,
                            "clicks": term.metrics.clicks,
                            "cost": term.metrics.cost,
                            "conversions": term.metrics.conversions,
                        }
                    )
                else:
                    # Search term matches an existing keyword
                    matched_cost += term.metrics.cost
                    matched_conversions += term.metrics.conversions

            # Calculate coverage metrics
            coverage = {
                "total_search_terms": len(search_terms),
                "matched_search_terms": len(search_terms) - len(gaps),
                "coverage_percentage": (
                    (len(search_terms) - len(gaps)) / len(search_terms) * 100
                )
                if search_terms
                else 0,
                "cost_coverage": (matched_cost / total_search_term_cost * 100)
                if total_search_term_cost > 0
                else 0,
                "conversion_coverage": (
                    matched_conversions / total_search_term_conversions * 100
                )
                if total_search_term_conversions > 0
                else 0,
                "gaps_count": len(gaps),
                "high_performers_count": len(high_performers),
            }

            # Sort high performers by conversions
            high_performers.sort(key=lambda x: x["conversions"], reverse=True)

            return {
                "gaps": gaps[:50],  # Limit to top 50 gaps
                "high_performers": high_performers[:20],  # Top 20 high performers
                "coverage": coverage,
            }

        except Exception as e:
            logger.error(f"Error in search term integration analysis: {e}")
            return {"gaps": [], "high_performers": [], "coverage": {}}

    def _suggest_match_type(self, search_term: SearchTerm) -> str:
        """Suggest match type for a search term based on performance."""
        # High-converting search terms with specific intent should be exact match
        if (
            search_term.metrics.conversions > self.match_type_conversion_threshold
            and search_term.metrics.ctr > self.match_type_ctr_threshold
        ):
            return "EXACT"
        # Medium performers or broader terms should be phrase match
        elif search_term.metrics.clicks > self.match_type_clicks_threshold:
            return "PHRASE"
        # Low volume terms should use broad match
        else:
            return "BROAD"  # Fixed: broad match modified is deprecated

    def _analyze_local_intent(self, keywords: list[Keyword]) -> dict[str, Any]:
        """Analyze keywords for local intent patterns, useful for retail businesses.

        Returns:
            Dictionary containing:
            - local_keywords: Keywords with local intent
            - summary: Performance summary of local intent keywords
        """
        # Use configurable local patterns from instance

        local_keywords = []
        total_local_cost = 0.0
        total_local_conversions = 0.0
        total_local_clicks = 0
        total_local_impressions = 0

        for keyword in keywords:
            keyword_text_lower = keyword.text.lower()

            # Check if keyword contains local intent
            has_local_intent = any(
                pattern in keyword_text_lower for pattern in self.local_patterns
            )

            if has_local_intent:
                local_keyword_data = {
                    "keyword": keyword.text,
                    "keyword_id": keyword.keyword_id,
                    "impressions": keyword.impressions,
                    "clicks": keyword.clicks,
                    "cost": keyword.cost,
                    "conversions": keyword.conversions,
                    "ctr": keyword.ctr,
                    "cpc": keyword.avg_cpc,
                    "cpa": keyword.cpa if keyword.conversions > 0 else None,
                    "quality_score": keyword.quality_score,
                    "match_type": keyword.match_type,
                    "detected_patterns": [
                        p for p in self.local_patterns if p in keyword_text_lower
                    ],
                }

                local_keywords.append(local_keyword_data)
                total_local_cost += keyword.cost
                total_local_conversions += keyword.conversions
                total_local_clicks += keyword.clicks
                total_local_impressions += keyword.impressions

        # Calculate summary statistics
        summary = {
            "total_local_keywords": len(local_keywords),
            "total_keywords": len(keywords),
            "local_percentage": (len(local_keywords) / len(keywords) * 100)
            if keywords
            else 0,
            "local_cost": total_local_cost,
            "local_conversions": total_local_conversions,
            "local_clicks": total_local_clicks,
            "local_impressions": total_local_impressions,
            "local_ctr": (total_local_clicks / total_local_impressions * 100)
            if total_local_impressions > 0
            else 0,
            "local_conversion_rate": (
                total_local_conversions / total_local_clicks * 100
            )
            if total_local_clicks > 0
            else 0,
            "local_cpa": (total_local_cost / total_local_conversions)
            if total_local_conversions > 0
            else None,
        }

        # Sort local keywords by conversions descending
        local_keywords.sort(key=lambda x: x["conversions"], reverse=True)

        return {
            "local_keywords": local_keywords[:50],  # Top 50 local intent keywords
            "summary": summary,
        }
