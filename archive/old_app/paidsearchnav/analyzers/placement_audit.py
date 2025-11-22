"""Placement Audit Analyzer.

This analyzer evaluates placement performance in Google Ads campaigns to identify
underperforming placements, detect spam/low-quality websites, and provide
automated exclusion recommendations for improved campaign quality.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    Placement,
    PlacementAuditAnalysisResult,
    PlacementCategory,
    PlacementMetrics,
    PlacementQualityScore,
    PlacementType,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider


@dataclass
class PlacementAuditConfig:
    """Configuration for placement audit analysis thresholds."""

    # Quality scoring thresholds
    CTR_EXCELLENT: float = 2.0
    CTR_GOOD: float = 1.0
    CTR_FAIR: float = 0.5
    CTR_MINIMAL: float = 0.1

    CONV_RATE_EXCELLENT: float = 5.0
    CONV_RATE_GOOD: float = 2.0
    CONV_RATE_FAIR: float = 1.0
    CONV_RATE_MINIMAL: float = 0.5

    ROAS_EXCELLENT: float = 4.0
    ROAS_GOOD: float = 2.0
    ROAS_FAIR: float = 1.0
    ROAS_MINIMAL: float = 0.5

    # Quality score boundaries
    QUALITY_EXCELLENT: float = 90.0
    QUALITY_GOOD: float = 75.0
    QUALITY_FAIR: float = 60.0
    QUALITY_POOR: float = 40.0

    # Component weights
    CTR_WEIGHT: float = 40.0
    CONVERSION_WEIGHT: float = 30.0
    ROAS_WEIGHT: float = 20.0
    BRAND_SAFETY_WEIGHT: float = 10.0

    # Spam detection thresholds
    SPAM_HIGH_IMPRESSIONS: int = 10000
    SPAM_LOW_CTR: float = 0.1
    SPAM_HIGH_COST_NO_CONV: float = 50.0

    # Spam risk scoring
    SPAM_VOLUME_SCORE: float = 30.0
    SPAM_VERY_POOR_SCORE: float = 40.0
    SPAM_POOR_SCORE: float = 20.0
    SPAM_NO_CONV_SCORE: float = 30.0


class PlacementAuditAnalyzer(Analyzer):
    """Analyzes placement performance to identify optimization opportunities."""

    def __init__(
        self,
        data_provider: DataProvider,
        min_impressions: int = 100,
        min_ctr_threshold: float = 0.5,
        max_cpa_multiplier: float = 3.0,
        spam_threshold: float = 70.0,
        high_cost_threshold: float = 100.0,
        config: PlacementAuditConfig | None = None,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Data provider for fetching placement data
            min_impressions: Minimum impressions to include in analysis
            min_ctr_threshold: Minimum CTR threshold (%)
            max_cpa_multiplier: Max acceptable CPA multiplier vs account average
            spam_threshold: Spam risk score threshold (0-100)
            high_cost_threshold: Cost threshold to flag high-cost placements
            config: Configuration object with quality and spam thresholds
        """
        self.data_provider = data_provider
        self.min_impressions = min_impressions
        self.min_ctr_threshold = min_ctr_threshold
        self.max_cpa_multiplier = max_cpa_multiplier
        self.spam_threshold = spam_threshold
        self.high_cost_threshold = high_cost_threshold
        self.config = config or PlacementAuditConfig()

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Placement Audit Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes placement performance to identify underperforming placements, "
            "detect spam/low-quality websites, and provide automated exclusion "
            "recommendations for improved campaign quality."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> PlacementAuditAnalysisResult:
        """Run placement audit analysis.

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

        try:
            # Fetch placement data
            placement_data = await self.data_provider.get_placement_data(
                customer_id=customer_id,
                campaigns=campaigns,
                ad_groups=ad_groups,
                start_date=start_date,
                end_date=end_date,
            )

            # Handle empty data
            if not placement_data:
                return self._create_empty_result(customer_id, start_date, end_date)

            # Filter by minimum impressions
            placement_data = [
                p
                for p in placement_data
                if p.get("impressions", 0) >= self.min_impressions
            ]

            # Convert to Placement objects
            placements = await self._convert_to_placements(placement_data)

            # Analyze placements
            result = await self._analyze_placements(
                placements, customer_id, start_date, end_date
            )

            return result
        except Exception as e:
            # Return empty result with error handling
            return self._create_empty_result(customer_id, start_date, end_date)

    async def _convert_to_placements(
        self, placement_data: list[dict[str, Any]]
    ) -> list[Placement]:
        """Convert raw placement data to Placement objects."""
        if not placement_data:
            return []

        placements = []

        for data in placement_data:
            # Create placement metrics
            metrics = PlacementMetrics(
                impressions=data.get("impressions", 0),
                clicks=data.get("clicks", 0),
                cost=data.get("cost", 0.0),
                conversions=data.get("conversions", 0.0),
                conversion_value=data.get("conversion_value", 0.0),
                ctr=data.get("ctr", 0.0),
                cpc=data.get("cpc", 0.0),
                cpa=data.get("cpa", 0.0),
                roas=data.get("roas", 0.0),
            )

            # Determine placement type
            placement_type = self._determine_placement_type(
                data.get("placement_name", "")
            )

            # Categorize placement
            category = self._categorize_placement(data.get("placement_name", ""))

            # Determine quality score
            quality_score = self._calculate_quality_score(metrics, data)

            # Detect character set
            character_set = self._detect_character_set(data.get("placement_name", ""))

            # Create placement object
            placement = Placement(
                placement_id=data.get("placement_id", ""),
                placement_name=data.get("placement_name", ""),
                display_name=data.get("display_name", data.get("placement_name", "")),
                placement_type=placement_type,
                category=category,
                quality_score=quality_score,
                is_brand_safe=data.get("is_brand_safe", True),
                is_relevant=data.get("is_relevant", True),
                character_set=character_set,
                country_code=data.get("country_code"),
                metrics=metrics,
                campaign_ids=data.get("campaign_ids", []),
                ad_group_ids=data.get("ad_group_ids", []),
                is_excluded=data.get("is_excluded", False),
                exclusion_reason=data.get("exclusion_reason"),
            )

            placements.append(placement)

        return placements

    def _determine_placement_type(self, placement_name: str) -> PlacementType:
        """Determine placement type based on name/URL."""
        if not placement_name:
            return PlacementType.UNKNOWN

        placement_lower = placement_name.lower()

        if "youtube.com" in placement_lower:
            if "/watch" in placement_lower:
                return PlacementType.YOUTUBE_VIDEO
            elif "/channel" in placement_lower or "/c/" in placement_lower:
                return PlacementType.YOUTUBE_CHANNEL
            else:
                return PlacementType.VIDEO

        if placement_lower.startswith("http"):
            return PlacementType.WEBSITE

        # Check for video before website patterns
        if "video" in placement_lower:
            return PlacementType.VIDEO

        if "app" in placement_lower or "mobile" in placement_lower:
            return PlacementType.MOBILE_APP

        # Check for common website patterns
        if "." in placement_name and any(
            placement_lower.endswith(ext)
            for ext in [".com", ".net", ".org", ".co", ".io"]
        ):
            return PlacementType.WEBSITE

        return PlacementType.WEBSITE  # Default to website for domain names

    def _categorize_placement(self, placement_name: str) -> PlacementCategory:
        """Categorize placement based on name/URL."""
        if not placement_name:
            return PlacementCategory.UNKNOWN

        placement_lower = placement_name.lower()

        # Define category keywords
        category_keywords = {
            PlacementCategory.NEWS: [
                "news",
                "newspaper",
                "breaking",
                "headlines",
                "journalism",
                "reuters",
                "cnn",
                "bbc",
                "guardian",
                "times",
            ],
            PlacementCategory.ENTERTAINMENT: [
                "entertainment",
                "movie",
                "film",
                "celebrity",
                "music",
                "hollywood",
                "netflix",
                "hulu",
                "disney",
                "warner",
            ],
            PlacementCategory.RETAIL: [
                "shop",
                "store",
                "retail",
                "buy",
                "sale",
                "amazon",
                "walmart",
                "target",
                "ebay",
                "etsy",
                "commerce",
            ],
            PlacementCategory.HEALTH: [
                "health",
                "medical",
                "doctor",
                "hospital",
                "medicine",
                "wellness",
                "fitness",
                "nutrition",
                "pharmacy",
            ],
            PlacementCategory.FINANCE: [
                "finance",
                "bank",
                "investment",
                "money",
                "credit",
                "loan",
                "mortgage",
                "insurance",
                "trading",
                "stocks",
            ],
            PlacementCategory.TECHNOLOGY: [
                "tech",
                "technology",
                "software",
                "hardware",
                "computer",
                "digital",
                "internet",
                "web",
                "app",
                "mobile",
            ],
            PlacementCategory.TRAVEL: [
                "travel",
                "vacation",
                "hotel",
                "flight",
                "booking",
                "trip",
                "tourism",
                "airline",
                "cruise",
                "resort",
            ],
            PlacementCategory.SPORTS: [
                "sports",
                "football",
                "basketball",
                "baseball",
                "soccer",
                "tennis",
                "golf",
                "hockey",
                "nfl",
                "nba",
                "espn",
            ],
            PlacementCategory.EDUCATION: [
                "education",
                "school",
                "university",
                "college",
                "learning",
                "course",
                "academic",
                "student",
                "teacher",
                "study",
            ],
            PlacementCategory.FOOD: [
                "food",
                "restaurant",
                "recipe",
                "cooking",
                "chef",
                "dining",
                "eat",
                "kitchen",
                "culinary",
                "menu",
            ],
            PlacementCategory.AUTOMOTIVE: [
                "car",
                "auto",
                "vehicle",
                "truck",
                "motorcycle",
                "automotive",
                "dealer",
                "repair",
                "parts",
                "driving",
            ],
            PlacementCategory.REAL_ESTATE: [
                "real estate",
                "property",
                "home",
                "house",
                "apartment",
                "rent",
                "buy",
                "mortgage",
                "realtor",
                "housing",
            ],
            PlacementCategory.GAMING: [
                "game",
                "gaming",
                "video game",
                "console",
                "player",
                "online game",
                "mobile game",
                "esports",
                "twitch",
            ],
            PlacementCategory.SOCIAL: [
                "social",
                "facebook",
                "twitter",
                "instagram",
                "tiktok",
                "linkedin",
                "snapchat",
                "pinterest",
                "social media",
            ],
        }

        # Check for category matches
        for category, keywords in category_keywords.items():
            if any(keyword in placement_lower for keyword in keywords):
                return category

        return PlacementCategory.OTHER

    def _calculate_quality_score(
        self, metrics: PlacementMetrics, data: dict[str, Any]
    ) -> PlacementQualityScore:
        """Calculate quality score based on performance metrics."""
        score = 0.0

        # Calculate component scores
        score += self._calculate_ctr_score(metrics.ctr)
        score += self._calculate_conversion_score(metrics)
        score += self._calculate_roas_score(metrics.roas)
        score += self._calculate_brand_safety_score(data)

        # Map total score to quality enum
        return self._map_score_to_quality(score)

    def _calculate_ctr_score(self, ctr: float) -> float:
        """Calculate CTR component of quality score."""
        config = self.config

        if ctr >= config.CTR_EXCELLENT:
            return config.CTR_WEIGHT
        elif ctr >= config.CTR_GOOD:
            return config.CTR_WEIGHT * 0.75
        elif ctr >= config.CTR_FAIR:
            return config.CTR_WEIGHT * 0.5
        elif ctr >= config.CTR_MINIMAL:
            return config.CTR_WEIGHT * 0.25
        else:
            return 0.0

    def _calculate_conversion_score(self, metrics: PlacementMetrics) -> float:
        """Calculate conversion rate component of quality score."""
        config = self.config
        conv_rate = (
            (metrics.conversions / metrics.clicks * 100) if metrics.clicks > 0 else 0.0
        )

        if conv_rate >= config.CONV_RATE_EXCELLENT:
            return config.CONVERSION_WEIGHT
        elif conv_rate >= config.CONV_RATE_GOOD:
            return config.CONVERSION_WEIGHT * 0.67
        elif conv_rate >= config.CONV_RATE_FAIR:
            return config.CONVERSION_WEIGHT * 0.5
        elif conv_rate >= config.CONV_RATE_MINIMAL:
            return config.CONVERSION_WEIGHT * 0.33
        else:
            return 0.0

    def _calculate_roas_score(self, roas: float) -> float:
        """Calculate ROAS component of quality score."""
        config = self.config

        if roas >= config.ROAS_EXCELLENT:
            return config.ROAS_WEIGHT
        elif roas >= config.ROAS_GOOD:
            return config.ROAS_WEIGHT * 0.75
        elif roas >= config.ROAS_FAIR:
            return config.ROAS_WEIGHT * 0.5
        elif roas >= config.ROAS_MINIMAL:
            return config.ROAS_WEIGHT * 0.25
        else:
            return 0.0

    def _calculate_brand_safety_score(self, data: dict[str, Any]) -> float:
        """Calculate brand safety component of quality score."""
        return (
            self.config.BRAND_SAFETY_WEIGHT if data.get("is_brand_safe", True) else 0.0
        )

    def _map_score_to_quality(self, score: float) -> PlacementQualityScore:
        """Map numeric score to quality enum."""
        config = self.config

        if score >= config.QUALITY_EXCELLENT:
            return PlacementQualityScore.EXCELLENT
        elif score >= config.QUALITY_GOOD:
            return PlacementQualityScore.GOOD
        elif score >= config.QUALITY_FAIR:
            return PlacementQualityScore.FAIR
        elif score >= config.QUALITY_POOR:
            return PlacementQualityScore.POOR
        else:
            return PlacementQualityScore.VERY_POOR

    def _detect_character_set(self, placement_name: str) -> str | None:
        """Detect character set/language from placement name."""
        if not placement_name:
            return None

        # Check for non-Latin characters
        if re.search(r"[^\x00-\x7F]", placement_name):
            # Check for specific character sets
            if re.search(r"[\u4e00-\u9fff]", placement_name):
                return "Chinese"
            elif re.search(r"[\u0400-\u04ff]", placement_name):
                return "Cyrillic"
            elif re.search(r"[\u0600-\u06ff]", placement_name):
                return "Arabic"
            elif re.search(r"[\u3040-\u309f\u30a0-\u30ff]", placement_name):
                return "Japanese"
            elif re.search(r"[\uac00-\ud7af]", placement_name):
                return "Korean"
            else:
                return "Non-Latin"

        return "Latin"

    async def _analyze_placements(
        self,
        placements: list[Placement],
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> PlacementAuditAnalysisResult:
        """Analyze placements and generate recommendations."""
        # Handle empty placements case
        if not placements:
            return self._create_empty_result(customer_id, start_date, end_date)

        # Calculate account averages
        account_averages = self._calculate_account_averages(placements)

        # Categorize placements
        underperforming = []
        high_cost = []
        spam_placements = []
        exclusion_recommendations = []

        for placement in placements:
            # Check if underperforming
            if placement.is_underperforming:
                underperforming.append(placement)

            # Check if high cost
            if placement.is_high_cost:
                high_cost.append(placement)

            # Check spam risk
            if placement.spam_risk_score >= self.spam_threshold:
                spam_placements.append(placement)

            # Check if should be excluded
            if self._should_exclude_placement(placement, account_averages):
                exclusion_recommendations.append(placement)

        # Generate category and quality analysis
        category_performance = self._analyze_category_performance(placements)
        quality_distribution = self._analyze_quality_distribution(placements)
        character_set_analysis = self._analyze_character_sets(placements)

        # Calculate summary statistics
        total_cost = sum(p.metrics.cost for p in placements)
        total_conversions = sum(p.metrics.conversions for p in placements)
        avg_ctr = (
            sum(p.metrics.ctr for p in placements) / len(placements)
            if placements
            else 0.0
        )
        avg_cpa = (
            sum(p.metrics.cpa for p in placements) / len(placements)
            if placements
            else 0.0
        )

        # Calculate potential savings
        potential_savings = sum(p.metrics.cost for p in exclusion_recommendations)
        wasted_spend_percentage = (
            (potential_savings / total_cost * 100) if total_cost > 0 else 0.0
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            underperforming,
            high_cost,
            spam_placements,
            exclusion_recommendations,
            account_averages,
        )

        # Create result
        result = PlacementAuditAnalysisResult(
            customer_id=customer_id,
            analysis_type="placement_audit",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            all_placements=placements,
            underperforming_placements=underperforming,
            high_cost_placements=high_cost,
            spam_placements=spam_placements,
            exclusion_recommendations=exclusion_recommendations,
            category_performance=category_performance,
            quality_distribution=quality_distribution,
            character_set_analysis=character_set_analysis,
            total_placements=len(placements),
            total_placement_cost=total_cost,
            total_placement_conversions=total_conversions,
            avg_placement_ctr=avg_ctr,
            avg_placement_cpa=avg_cpa,
            potential_cost_savings=potential_savings,
            wasted_spend_percentage=wasted_spend_percentage,
            recommendations=recommendations,
        )

        return result

    def _create_empty_result(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> PlacementAuditAnalysisResult:
        """Create empty result when no placements are found."""
        return PlacementAuditAnalysisResult(
            customer_id=customer_id,
            analysis_type="placement_audit",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            all_placements=[],
            underperforming_placements=[],
            high_cost_placements=[],
            spam_placements=[],
            exclusion_recommendations=[],
            category_performance={},
            quality_distribution={},
            character_set_analysis={},
            total_placements=0,
            total_placement_cost=0.0,
            total_placement_conversions=0.0,
            avg_placement_ctr=0.0,
            avg_placement_cpa=0.0,
            potential_cost_savings=0.0,
            wasted_spend_percentage=0.0,
            recommendations=[],
        )

    def _calculate_account_averages(
        self, placements: list[Placement]
    ) -> dict[str, float]:
        """Calculate account-level averages for comparison."""
        if not placements:
            return {"ctr": 0.0, "cpa": 0.0, "roas": 0.0}

        total_impressions = sum(p.metrics.impressions for p in placements)
        total_clicks = sum(p.metrics.clicks for p in placements)
        total_cost = sum(p.metrics.cost for p in placements)
        total_conversions = sum(p.metrics.conversions for p in placements)
        total_conversion_value = sum(p.metrics.conversion_value for p in placements)

        return {
            "ctr": (total_clicks / total_impressions * 100)
            if total_impressions > 0
            else 0.0,
            "cpa": (total_cost / total_conversions) if total_conversions > 0 else 0.0,
            "roas": (total_conversion_value / total_cost) if total_cost > 0 else 0.0,
        }

    def _should_exclude_placement(
        self, placement: Placement, account_averages: dict[str, float]
    ) -> bool:
        """Determine if placement should be excluded."""
        # High spam risk
        if placement.spam_risk_score >= self.spam_threshold:
            return True

        # Very poor quality
        if placement.quality_score == PlacementQualityScore.VERY_POOR:
            return True

        # High cost with no conversions
        if (
            placement.metrics.cost > self.high_cost_threshold
            and placement.metrics.conversions == 0
        ):
            return True

        # CPA significantly above account average
        if (
            account_averages["cpa"] > 0
            and placement.metrics.cpa
            > account_averages["cpa"] * self.max_cpa_multiplier
        ):
            return True

        # CTR significantly below threshold
        if placement.metrics.ctr < self.min_ctr_threshold:
            return True

        return False

    def _analyze_category_performance(
        self, placements: list[Placement]
    ) -> dict[PlacementCategory, dict[str, Any]]:
        """Analyze performance by category."""
        if not placements:
            return {}

        category_stats = defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "impressions": 0,
                "clicks": 0,
            }
        )

        for placement in placements:
            stats = category_stats[placement.category]
            stats["count"] += 1
            stats["cost"] += placement.metrics.cost
            stats["conversions"] += placement.metrics.conversions
            stats["impressions"] += placement.metrics.impressions
            stats["clicks"] += placement.metrics.clicks

        # Calculate derived metrics
        for category, stats in category_stats.items():
            stats["ctr"] = (
                (stats["clicks"] / stats["impressions"] * 100)
                if stats["impressions"] > 0
                else 0.0
            )
            stats["cpa"] = (
                (stats["cost"] / stats["conversions"])
                if stats["conversions"] > 0
                else 0.0
            )
            stats["avg_cost_per_placement"] = stats["cost"] / stats["count"]

        return dict(category_stats)

    def _analyze_quality_distribution(
        self, placements: list[Placement]
    ) -> dict[PlacementQualityScore, int]:
        """Analyze distribution of quality scores."""
        if not placements:
            return {}

        distribution = defaultdict(int)
        for placement in placements:
            distribution[placement.quality_score] += 1
        return dict(distribution)

    def _analyze_character_sets(
        self, placements: list[Placement]
    ) -> dict[str, dict[str, Any]]:
        """Analyze performance by character set."""
        if not placements:
            return {}

        charset_stats = defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "avg_cpa": 0.0,
            }
        )

        for placement in placements:
            charset = placement.character_set or "Unknown"
            stats = charset_stats[charset]
            stats["count"] += 1
            stats["cost"] += placement.metrics.cost
            stats["conversions"] += placement.metrics.conversions

        # Calculate average CPA
        for charset, stats in charset_stats.items():
            stats["avg_cpa"] = (
                (stats["cost"] / stats["conversions"])
                if stats["conversions"] > 0
                else 0.0
            )

        return dict(charset_stats)

    def _generate_recommendations(
        self,
        underperforming: list[Placement],
        high_cost: list[Placement],
        spam_placements: list[Placement],
        exclusion_recommendations: list[Placement],
        account_averages: dict[str, float],
    ) -> list[Recommendation]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # High priority: Exclude spam placements
        if spam_placements:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"Exclude {len(spam_placements)} spam/low-quality placements",
                    description=(
                        f"Found {len(spam_placements)} placements with high spam risk scores. "
                        f"These placements have poor performance metrics and should be excluded "
                        f"to prevent wasted spend."
                    ),
                    estimated_cost_savings=sum(p.metrics.cost for p in spam_placements),
                    action_data={
                        "placement_ids": [p.placement_id for p in spam_placements],
                        "exclusion_type": "spam_prevention",
                    },
                )
            )

        # High priority: Exclude high-cost, non-converting placements
        high_cost_no_conv = [p for p in high_cost if p.metrics.conversions == 0]
        if high_cost_no_conv:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.HIGH,
                    title=f"Exclude {len(high_cost_no_conv)} high-cost non-converting placements",
                    description=(
                        f"Found {len(high_cost_no_conv)} placements with high cost "
                        f"but zero conversions. Total wasted spend: "
                        f"${sum(p.metrics.cost for p in high_cost_no_conv):.2f}"
                    ),
                    estimated_cost_savings=sum(
                        p.metrics.cost for p in high_cost_no_conv
                    ),
                    action_data={
                        "placement_ids": [p.placement_id for p in high_cost_no_conv],
                        "exclusion_type": "cost_optimization",
                    },
                )
            )

        # Medium priority: Review underperforming placements
        if underperforming:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OTHER,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Review {len(underperforming)} underperforming placements",
                    description=(
                        f"Found {len(underperforming)} placements with poor CTR or "
                        f"quality scores. Review these placements for potential optimization "
                        f"or exclusion."
                    ),
                    estimated_cost_savings=sum(p.metrics.cost for p in underperforming)
                    * 0.3,
                    action_data={
                        "placement_ids": [p.placement_id for p in underperforming],
                        "action_type": "review_and_optimize",
                    },
                )
            )

        # Medium priority: Character set exclusions
        non_english_placements = [
            p
            for p in exclusion_recommendations
            if p.character_set
            and p.character_set.lower() not in ["latin", "english", "en"]
        ]
        if non_english_placements:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE,
                    priority=RecommendationPriority.MEDIUM,
                    title=f"Exclude {len(non_english_placements)} non-English placements",
                    description=(
                        f"Found {len(non_english_placements)} placements with non-English "
                        f"character sets that may not be relevant to your target audience."
                    ),
                    estimated_cost_savings=sum(
                        p.metrics.cost for p in non_english_placements
                    ),
                    action_data={
                        "placement_ids": [
                            p.placement_id for p in non_english_placements
                        ],
                        "exclusion_type": "language_relevance",
                    },
                )
            )

        # Low priority: Quality improvement suggestions
        very_poor_quality = [
            p
            for p in exclusion_recommendations
            if p.quality_score == PlacementQualityScore.VERY_POOR
        ]
        if very_poor_quality:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.IMPROVE_QUALITY,
                    priority=RecommendationPriority.LOW,
                    title=f"Improve quality for {len(very_poor_quality)} poor-quality placements",
                    description=(
                        f"Found {len(very_poor_quality)} placements with very poor quality scores. "
                        f"Consider improving ad creative or targeting to better match these placements."
                    ),
                    estimated_conversion_increase=10.0,
                    action_data={
                        "placement_ids": [p.placement_id for p in very_poor_quality],
                        "action_type": "quality_improvement",
                    },
                )
            )

        return recommendations
