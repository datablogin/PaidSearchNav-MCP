"""Advanced Search Term Analyzer for Google Ads audit."""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    Recommendation,
    RecommendationPriority,
    RecommendationType,
    SearchTerm,
)
from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult
from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


class SearchTermIntent(str):
    """Search term intent classification."""

    TRANSACTIONAL = "TRANSACTIONAL"  # Buy/purchase intent
    INFORMATIONAL = "INFORMATIONAL"  # Research/learning intent
    NAVIGATIONAL = "NAVIGATIONAL"  # Looking for specific site/brand
    LOCAL = "LOCAL"  # Location-based searches


class SearchTermAnalyzer(Analyzer):
    """Analyzes search term patterns and opportunities."""

    def __init__(
        self,
        data_provider: DataProvider,
        min_ngram_count: int = 5,
        min_conversions_for_opportunity: int = 1,
        min_conversions_for_high_converting: int = 2,
        high_cost_no_conversion_threshold: float = 50.0,
        low_ctr_threshold: float = 0.5,
        min_impressions_for_ctr_analysis: int = 100,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Provider for fetching Google Ads data
            min_ngram_count: Minimum occurrences for n-gram analysis
            min_conversions_for_opportunity: Minimum conversions to consider as opportunity
            min_conversions_for_high_converting: Minimum conversions for high-converting classification
            high_cost_no_conversion_threshold: Cost threshold for negative keywords with no conversions
            low_ctr_threshold: CTR threshold for low-relevance queries
            min_impressions_for_ctr_analysis: Minimum impressions for CTR-based analysis
        """
        self.data_provider = data_provider

        # Configurable thresholds
        self.min_ngram_count = min_ngram_count
        self.min_conversions_for_opportunity = min_conversions_for_opportunity
        self.min_conversions_for_high_converting = min_conversions_for_high_converting
        self.high_cost_no_conversion_threshold = high_cost_no_conversion_threshold
        self.low_ctr_threshold = low_ctr_threshold
        self.min_impressions_for_ctr_analysis = min_impressions_for_ctr_analysis

        # Pre-compile intent patterns for better performance
        self.transactional_patterns = [
            re.compile(
                r"\b(buy|purchase|order|shop|deal|discount|sale|coupon|price|cheap|best|affordable)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(store|online|delivery|shipping|free shipping)\b", re.IGNORECASE
            ),
            re.compile(r"\b(for sale|on sale|special offer)\b", re.IGNORECASE),
        ]

        self.informational_patterns = [
            re.compile(
                r"\b(how to|what is|why|when|where|guide|tutorial|tips|review)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(vs|versus|compare|comparison|difference|between)\b", re.IGNORECASE
            ),
            re.compile(r"\b(benefits|pros|cons|features)\b", re.IGNORECASE),
        ]

        self.navigational_patterns = [
            re.compile(
                r"\b(website|site|login|sign in|account|official)\b", re.IGNORECASE
            ),
            re.compile(r"\.(com|org|net|gov|edu)\b", re.IGNORECASE),
            re.compile(r"\b(customer service|support|contact)\b", re.IGNORECASE),
        ]

        self.local_patterns = [
            re.compile(
                r"\b(near me|nearby|closest|nearest|local|in my area)\b", re.IGNORECASE
            ),
            re.compile(r"\b(city|town|neighborhood|zip|postal code)\b", re.IGNORECASE),
            re.compile(
                r"\b(store hours|open now|directions|location)\b", re.IGNORECASE
            ),
        ]

        # Pre-compile other common patterns
        self.irrelevant_patterns = [
            re.compile(r"\b(free|gratis|no cost)\b", re.IGNORECASE),
            re.compile(r"\b(diy|homemade|make your own)\b", re.IGNORECASE),
            re.compile(r"\b(jobs|careers|hiring|employment)\b", re.IGNORECASE),
            re.compile(r"\b(complaints|lawsuit|scam)\b", re.IGNORECASE),
        ]

        self.new_product_patterns = [
            re.compile(r"\b(new|latest|2024|2025)\b", re.IGNORECASE),
            re.compile(r"\b(just released|recently|now available)\b", re.IGNORECASE),
            re.compile(r"\b(alternative|replacement|substitute)\b", re.IGNORECASE),
        ]

        self.store_patterns = [
            re.compile(r"\b(store|shop|location|branch|outlet)\b", re.IGNORECASE),
            re.compile(r"\b(hours|open|closed|directions)\b", re.IGNORECASE),
            re.compile(r"\b(visit|find|get to)\b.*\b(store|location)\b", re.IGNORECASE),
        ]

        # Question words
        self.question_words = ["what", "where", "when", "why", "how", "which", "who"]

        # Modifier words for analysis
        self.quality_modifiers = ["best", "top", "premium", "quality", "professional"]
        self.price_modifiers = ["cheap", "affordable", "discount", "budget", "free"]
        self.urgency_modifiers = ["now", "today", "urgent", "immediate", "fast"]

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Advanced Search Term Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Provides deep analysis of search terms including intent classification, "
            "pattern recognition, and advanced opportunity identification."
        )

    def _safe_analysis(self, func, *args, **kwargs) -> Any:
        """Safely execute an analysis function with error handling."""
        analysis_name = kwargs.pop("name", func.__name__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {analysis_name}: {str(e)}")
            return {}

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Perform advanced search term analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Optional parameters like campaigns, ad_groups

        Returns:
            AnalysisResult with detailed search term insights
        """
        logger.info(
            f"Starting advanced search term analysis for {customer_id} "
            f"from {start_date} to {end_date}"
        )

        try:
            # Get optional parameters
            campaigns = kwargs.get("campaigns")
            ad_groups = kwargs.get("ad_groups")

            # Fetch search terms data
            try:
                search_terms = await self.data_provider.get_search_terms(
                    customer_id, start_date, end_date, campaigns, ad_groups
                )
            except Exception as e:
                logger.error(f"Failed to fetch search terms: {str(e)}")
                # Return empty result with error
                return AnalysisResult(
                    customer_id=customer_id,
                    analysis_type="advanced_search_terms",
                    analyzer_name=self.get_name(),
                    start_date=start_date,
                    end_date=end_date,
                    raw_data={"error": f"Failed to fetch search terms: {str(e)}"},
                    recommendations=[],
                    metrics=AnalysisMetrics(
                        total_keywords_analyzed=0,
                        total_search_terms_analyzed=0,
                        total_campaigns_analyzed=0,
                        issues_found=0,
                        critical_issues=0,
                        potential_cost_savings=0.0,
                        potential_conversion_increase=0.0,
                    ),
                    errors=[f"Failed to fetch search terms: {str(e)}"],
                )

            # Handle empty search terms
            if not search_terms:
                logger.warning(f"No search terms found for customer {customer_id}")
                return AnalysisResult(
                    customer_id=customer_id,
                    analysis_type="advanced_search_terms",
                    analyzer_name=self.get_name(),
                    start_date=start_date,
                    end_date=end_date,
                    raw_data={
                        "message": "No search terms found for the specified period"
                    },
                    recommendations=[],
                    metrics=AnalysisMetrics(
                        total_keywords_analyzed=0,
                        total_search_terms_analyzed=0,
                        total_campaigns_analyzed=0,
                        issues_found=0,
                        critical_issues=0,
                        potential_cost_savings=0.0,
                        potential_conversion_increase=0.0,
                    ),
                    errors=[],
                )

            # Perform various analyses with error handling
            intent_analysis = self._safe_analysis(
                self._analyze_intent, search_terms, name="intent analysis"
            )
            ngram_analysis = self._safe_analysis(
                self._analyze_ngrams, search_terms, name="n-gram analysis"
            )
            brand_analysis = self._safe_analysis(
                self._analyze_brand_queries,
                search_terms,
                kwargs.get("brand_terms"),
                name="brand analysis",
            )
            question_analysis = self._safe_analysis(
                self._analyze_questions, search_terms, name="question analysis"
            )
            pattern_analysis = self._safe_analysis(
                self._analyze_patterns, search_terms, name="pattern analysis"
            )

            # Async operations need special handling
            try:
                opportunity_analysis = await self._mine_opportunities(
                    customer_id, search_terms, campaigns, ad_groups
                )
            except Exception as e:
                logger.error(f"Error in opportunity analysis: {str(e)}")
                opportunity_analysis = {}

            negative_analysis = self._safe_analysis(
                self._mine_negative_keywords,
                search_terms,
                name="negative keyword analysis",
            )
            local_analysis = self._safe_analysis(
                self._analyze_local_intent, search_terms, name="local intent analysis"
            )

            # Create comprehensive result
            result = self._create_analysis_result(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                search_terms=search_terms,
                intent_analysis=intent_analysis,
                ngram_analysis=ngram_analysis,
                brand_analysis=brand_analysis,
                question_analysis=question_analysis,
                pattern_analysis=pattern_analysis,
                opportunity_analysis=opportunity_analysis,
                negative_analysis=negative_analysis,
                local_analysis=local_analysis,
            )

            logger.info(
                f"Completed advanced search term analysis. "
                f"Analyzed {len(search_terms)} search terms, "
                f"found {len(result.recommendations)} recommendations"
            )

            return result

        except Exception as e:
            logger.error(f"Unexpected error in search term analysis: {str(e)}")
            # Return a minimal result with error
            return AnalysisResult(
                customer_id=customer_id,
                analysis_type="advanced_search_terms",
                analyzer_name=self.get_name(),
                start_date=start_date,
                end_date=end_date,
                raw_data={"error": f"Analysis failed: {str(e)}"},
                recommendations=[],
                metrics=AnalysisMetrics(
                    total_keywords_analyzed=0,
                    total_search_terms_analyzed=0,
                    total_campaigns_analyzed=0,
                    issues_found=0,
                    critical_issues=0,
                    potential_cost_savings=0.0,
                    potential_conversion_increase=0.0,
                ),
                errors=[f"Analysis failed: {str(e)}"],
            )

    def _analyze_intent(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, dict[str, Any]]:
        """Classify search terms by intent.

        Returns dict with intent classifications and metrics.
        """
        intent_data = defaultdict(
            lambda: {
                "terms": [],
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
            }
        )

        for term in search_terms:
            intent = self._classify_intent(term.search_term)

            intent_data[intent]["terms"].append(term)
            intent_data[intent]["impressions"] += term.metrics.impressions
            intent_data[intent]["clicks"] += term.metrics.clicks
            intent_data[intent]["cost"] += term.metrics.cost
            intent_data[intent]["conversions"] += term.metrics.conversions
            intent_data[intent]["conversion_value"] += term.metrics.conversion_value

        # Calculate performance metrics by intent
        for intent in intent_data:
            data = intent_data[intent]
            if data["clicks"] > 0:
                data["ctr"] = data["clicks"] / data["impressions"] * 100
                data["cpc"] = data["cost"] / data["clicks"]
            else:
                data["ctr"] = 0.0
                data["cpc"] = 0.0

            if data["conversions"] > 0:
                data["cpa"] = data["cost"] / data["conversions"]
                data["conversion_rate"] = (
                    data["conversions"] / data["clicks"] * 100
                    if data["clicks"] > 0
                    else 0.0
                )
            else:
                data["cpa"] = 0.0
                data["conversion_rate"] = 0.0

            if data["cost"] > 0:
                data["roas"] = data["conversion_value"] / data["cost"]
            else:
                data["roas"] = 0.0

        return dict(intent_data)

    def _classify_intent(self, search_term: str) -> str:
        """Classify a single search term's intent."""
        # No need to lower() since patterns use re.IGNORECASE

        # Check patterns in order of priority
        # Local intent has highest priority
        if any(pattern.search(search_term) for pattern in self.local_patterns):
            return SearchTermIntent.LOCAL

        # Navigational before transactional to catch website/login queries
        if any(pattern.search(search_term) for pattern in self.navigational_patterns):
            return SearchTermIntent.NAVIGATIONAL

        # Informational queries
        if any(pattern.search(search_term) for pattern in self.informational_patterns):
            return SearchTermIntent.INFORMATIONAL

        # Transactional queries
        if any(pattern.search(search_term) for pattern in self.transactional_patterns):
            return SearchTermIntent.TRANSACTIONAL

        # Default to transactional for commercial intent
        return SearchTermIntent.TRANSACTIONAL

    def _analyze_ngrams(
        self, search_terms: list[SearchTerm], min_count: int | None = None
    ) -> dict[str, dict[str, Any]]:
        """Analyze n-gram frequency and performance."""
        if min_count is None:
            min_count = self.min_ngram_count
        # Collect n-grams from 1 to 4 words
        ngram_data = defaultdict(
            lambda: {
                "count": 0,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
                "terms": [],
            }
        )

        # Process only terms with meaningful volume for better performance
        for term in search_terms:
            # Skip low-volume terms for n-gram analysis
            if term.metrics.impressions < 10:
                continue

            words = term.search_term.lower().split()

            # Generate n-grams
            for n in range(1, min(len(words) + 1, 5)):  # Up to 4-grams
                for i in range(len(words) - n + 1):
                    ngram = " ".join(words[i : i + n])

                    ngram_data[ngram]["count"] += 1
                    ngram_data[ngram]["impressions"] += term.metrics.impressions
                    ngram_data[ngram]["clicks"] += term.metrics.clicks
                    ngram_data[ngram]["cost"] += term.metrics.cost
                    ngram_data[ngram]["conversions"] += term.metrics.conversions
                    ngram_data[ngram]["terms"].append(term.search_term)

        # Filter by minimum count and calculate metrics
        filtered_ngrams = {}
        for ngram, data in ngram_data.items():
            if data["count"] >= min_count:
                # Calculate performance metrics
                if data["clicks"] > 0:
                    data["ctr"] = data["clicks"] / data["impressions"] * 100
                    data["cpc"] = data["cost"] / data["clicks"]
                    data["conversion_rate"] = data["conversions"] / data["clicks"] * 100
                else:
                    data["ctr"] = 0.0
                    data["cpc"] = 0.0
                    data["conversion_rate"] = 0.0

                if data["conversions"] > 0:
                    data["cpa"] = data["cost"] / data["conversions"]
                else:
                    data["cpa"] = 0.0

                # Keep unique terms only
                data["terms"] = list(set(data["terms"]))[:5]  # Keep top 5 examples

                filtered_ngrams[ngram] = data

        return filtered_ngrams

    def _analyze_brand_queries(
        self, search_terms: list[SearchTerm], brand_terms: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Separate and analyze brand vs non-brand queries."""
        # This is a simplified version - in practice you'd have brand terms configured
        if brand_terms is None:
            brand_terms = []

        brand_data = {
            "brand": {
                "terms": [],
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            },
            "non_brand": {
                "terms": [],
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            },
        }

        for term in search_terms:
            is_brand = any(
                brand.lower() in term.search_term.lower() for brand in brand_terms
            )
            category = "brand" if is_brand else "non_brand"

            brand_data[category]["terms"].append(term)
            brand_data[category]["impressions"] += term.metrics.impressions
            brand_data[category]["clicks"] += term.metrics.clicks
            brand_data[category]["cost"] += term.metrics.cost
            brand_data[category]["conversions"] += term.metrics.conversions

        # Calculate metrics for each category
        for category in brand_data:
            data = brand_data[category]
            if data["clicks"] > 0:
                data["ctr"] = data["clicks"] / data["impressions"] * 100
                data["cpc"] = data["cost"] / data["clicks"]
            else:
                data["ctr"] = 0.0
                data["cpc"] = 0.0

            if data["conversions"] > 0:
                data["cpa"] = data["cost"] / data["conversions"]
            else:
                data["cpa"] = 0.0

            data["term_count"] = len(data["terms"])

        return brand_data

    def _analyze_questions(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, list[SearchTerm]]:
        """Identify and analyze question-based queries."""
        question_queries = defaultdict(list)

        for term in search_terms:
            term_lower = term.search_term.lower()
            for question_word in self.question_words:
                if term_lower.startswith(question_word + " "):
                    question_queries[question_word].append(term)
                    break

        return dict(question_queries)

    def _analyze_patterns(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, dict[str, Any]]:
        """Analyze common patterns and modifiers."""
        pattern_data = {
            "query_length": self._analyze_query_length(search_terms),
            "modifiers": self._analyze_modifiers(search_terms),
            "performance_patterns": self._identify_performance_patterns(search_terms),
        }
        return pattern_data

    def _analyze_query_length(
        self, search_terms: list[SearchTerm]
    ) -> dict[int, dict[str, Any]]:
        """Analyze performance by query length (number of words)."""
        length_data = defaultdict(
            lambda: {
                "count": 0,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            }
        )

        for term in search_terms:
            word_count = len(term.search_term.split())
            length_data[word_count]["count"] += 1
            length_data[word_count]["impressions"] += term.metrics.impressions
            length_data[word_count]["clicks"] += term.metrics.clicks
            length_data[word_count]["cost"] += term.metrics.cost
            length_data[word_count]["conversions"] += term.metrics.conversions

        # Calculate metrics
        for length in length_data:
            data = length_data[length]
            if data["clicks"] > 0:
                data["ctr"] = data["clicks"] / data["impressions"] * 100
                data["avg_cpc"] = data["cost"] / data["clicks"]
            if data["conversions"] > 0:
                data["cpa"] = data["cost"] / data["conversions"]

        return dict(length_data)

    def _analyze_modifiers(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, dict[str, Any]]:
        """Analyze modifier word usage and performance."""
        modifier_categories = {
            "quality": self.quality_modifiers,
            "price": self.price_modifiers,
            "urgency": self.urgency_modifiers,
        }

        modifier_data = defaultdict(
            lambda: {
                "terms": [],
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0.0,
            }
        )

        for term in search_terms:
            term_lower = term.search_term.lower()
            for category, modifiers in modifier_categories.items():
                if any(modifier in term_lower for modifier in modifiers):
                    modifier_data[category]["terms"].append(term)
                    modifier_data[category]["impressions"] += term.metrics.impressions
                    modifier_data[category]["clicks"] += term.metrics.clicks
                    modifier_data[category]["cost"] += term.metrics.cost
                    modifier_data[category]["conversions"] += term.metrics.conversions

        # Calculate metrics
        for category in modifier_data:
            data = modifier_data[category]
            if data["clicks"] > 0:
                data["ctr"] = data["clicks"] / data["impressions"] * 100
                data["cpc"] = data["cost"] / data["clicks"]
            if data["conversions"] > 0:
                data["cpa"] = data["cost"] / data["conversions"]
            data["term_count"] = len(data["terms"])

        return dict(modifier_data)

    def _identify_performance_patterns(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, list[SearchTerm]]:
        """Identify patterns in high and low performing queries."""
        patterns = {
            "high_converting": [],
            "high_ctr": [],
            "low_ctr": [],
            "high_cost_no_conversion": [],
        }

        # Calculate averages for comparison
        total_clicks = sum(t.metrics.clicks for t in search_terms)
        total_impressions = sum(t.metrics.impressions for t in search_terms)
        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )

        for term in search_terms:
            # High converting (2+ conversions)
            if term.metrics.conversions >= self.min_conversions_for_high_converting:
                patterns["high_converting"].append(term)

            # High CTR (2x average)
            if term.metrics.ctr > avg_ctr * 2 and term.metrics.impressions >= 50:
                patterns["high_ctr"].append(term)

            # Low CTR (less than half average)
            if (
                term.metrics.ctr < avg_ctr * 0.5
                and term.metrics.impressions >= self.min_impressions_for_ctr_analysis
            ):
                patterns["low_ctr"].append(term)

            # High cost, no conversion
            if (
                term.metrics.cost > self.high_cost_no_conversion_threshold
                and term.metrics.conversions == 0
            ):
                patterns["high_cost_no_conversion"].append(term)

        return patterns

    async def _mine_opportunities(
        self,
        customer_id: str,
        search_terms: list[SearchTerm],
        campaigns: list[str] | None,
        ad_groups: list[str] | None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Mine for keyword opportunities."""
        # Get existing keywords
        keywords = await self.data_provider.get_keywords(
            customer_id, campaigns, ad_groups
        )
        existing_keywords = {kw.text.lower().strip() for kw in keywords}

        opportunities = {
            "new_exact_match": [],
            "new_phrase_match": [],
            "multiple_variations": [],
            "new_product_interest": [],
        }

        # Single pass through search terms for efficiency
        term_variations = defaultdict(list)
        for term in search_terms:
            normalized_term = term.search_term.lower().strip()
            base_form = self._get_base_form(term.search_term)
            term_variations[base_form].append(term)

            # Skip if already exists as keyword
            if normalized_term in existing_keywords:
                continue

            # High-converting queries not in keywords
            if (
                term.metrics.conversions >= self.min_conversions_for_opportunity
                and term.metrics.cpa < 100
            ):
                # Recommend exact match for long-tail or local intent
                if (
                    len(term.search_term.split()) >= 4
                    or self._classify_intent(term.search_term) == SearchTermIntent.LOCAL
                ):
                    opportunities["new_exact_match"].append(
                        {
                            "term": term.search_term,
                            "conversions": term.metrics.conversions,
                            "cpa": term.metrics.cpa,
                            "revenue": term.metrics.conversion_value,
                            "recommended_match_type": "EXACT",
                            "reason": "High-converting long-tail query",
                        }
                    )
                else:
                    opportunities["new_phrase_match"].append(
                        {
                            "term": term.search_term,
                            "conversions": term.metrics.conversions,
                            "cpa": term.metrics.cpa,
                            "revenue": term.metrics.conversion_value,
                            "recommended_match_type": "PHRASE",
                            "reason": "High-converting general query",
                        }
                    )

        # Find terms with multiple variations
        for base_form, variations in term_variations.items():
            if len(variations) >= 3:
                total_conversions = sum(t.metrics.conversions for t in variations)
                if total_conversions >= 2:
                    opportunities["multiple_variations"].append(
                        {
                            "base_term": base_form,
                            "variations": [t.search_term for t in variations[:5]],
                            "total_conversions": total_conversions,
                            "total_cost": sum(t.metrics.cost for t in variations),
                            "recommendation": "Consider adding as phrase match to capture variations",
                        }
                    )

        # Detect new product/service interest
        new_product_patterns = self._detect_new_product_interest(search_terms)
        opportunities["new_product_interest"] = new_product_patterns

        return opportunities

    def _get_base_form(self, search_term: str) -> str:
        """Get base form of search term by removing common modifiers and normalizing.

        This method performs more sophisticated normalization than simple stop word removal.
        """
        words = search_term.lower().split()

        # Expanded list of modifiers to remove
        modifiers = {
            # Location modifiers
            "near",
            "me",
            "nearby",
            "closest",
            "nearest",
            "local",
            "around",
            # Quality modifiers
            "best",
            "top",
            "good",
            "great",
            "excellent",
            "quality",
            "premium",
            # Price modifiers
            "cheap",
            "cheapest",
            "affordable",
            "discount",
            "budget",
            "free",
            # Shopping modifiers
            "buy",
            "purchase",
            "shop",
            "online",
            "store",
            "stores",
            # Urgency modifiers
            "now",
            "today",
            "urgent",
            "immediate",
            "fast",
            "quick",
            # Size modifiers
            "large",
            "small",
            "big",
            "mini",
            "huge",
            # Common prepositions and articles
            "for",
            "with",
            "at",
            "in",
            "on",
            "the",
            "a",
            "an",
        }

        # Keep only meaningful words
        base_words = []
        for word in words:
            # Skip very short words (likely not meaningful)
            if len(word) <= 2 and word not in ["tv", "pc", "ac"]:
                continue
            # Skip modifiers
            if word in modifiers:
                continue
            # Skip numbers unless they're likely model numbers
            if word.isdigit() and len(word) < 3:
                continue
            base_words.append(word)

        # Return normalized form or original if all words were filtered
        return " ".join(base_words) if base_words else search_term.lower()

    def _detect_new_product_interest(
        self, search_terms: list[SearchTerm]
    ) -> list[dict[str, Any]]:
        """Detect queries indicating interest in new products/services."""
        new_interest = []

        # Look for patterns indicating new interest
        new_patterns = [
            r"\b(new|latest|2024|2025)\b",
            r"\b(just released|recently|now available)\b",
            r"\b(alternative|replacement|substitute)\b",
        ]

        for term in search_terms:
            if any(
                re.search(pattern, term.search_term.lower()) for pattern in new_patterns
            ):
                if term.metrics.impressions >= 50:
                    new_interest.append(
                        {
                            "term": term.search_term,
                            "impressions": term.metrics.impressions,
                            "clicks": term.metrics.clicks,
                            "signal": "Indicates interest in new/updated offerings",
                        }
                    )

        return new_interest

    def _mine_negative_keywords(
        self, search_terms: list[SearchTerm]
    ) -> dict[str, list[dict[str, Any]]]:
        """Mine for negative keyword opportunities."""
        negatives = {
            "irrelevant": [],
            "high_cost_no_conversion": [],
            "off_topic": [],
            "competitor_brand": [],
        }

        # Common irrelevant patterns for retail
        irrelevant_patterns = [
            r"\b(free|gratis|no cost)\b",
            r"\b(diy|homemade|make your own)\b",
            r"\b(jobs|careers|hiring|employment)\b",
            r"\b(complaints|lawsuit|scam)\b",
        ]

        for term in search_terms:
            term_lower = term.search_term.lower()

            # Irrelevant queries
            if any(re.search(pattern, term_lower) for pattern in irrelevant_patterns):
                negatives["irrelevant"].append(
                    {
                        "term": term.search_term,
                        "cost": term.metrics.cost,
                        "impressions": term.metrics.impressions,
                        "reason": "Irrelevant to business",
                        "recommended_level": "account",
                    }
                )
                continue  # Skip other checks if already irrelevant

            # High cost, no conversion
            elif (
                term.metrics.cost > self.high_cost_no_conversion_threshold
                and term.metrics.conversions == 0
            ):
                negatives["high_cost_no_conversion"].append(
                    {
                        "term": term.search_term,
                        "cost": term.metrics.cost,
                        "clicks": term.metrics.clicks,
                        "reason": f"${term.metrics.cost:.2f} spent with no conversions",
                        "recommended_level": "campaign",
                    }
                )

            # Poor CTR indicating low relevance
            elif (
                term.metrics.impressions >= 500
                and term.metrics.ctr < self.low_ctr_threshold
            ):
                negatives["off_topic"].append(
                    {
                        "term": term.search_term,
                        "ctr": term.metrics.ctr,
                        "impressions": term.metrics.impressions,
                        "reason": f"Very low CTR ({term.metrics.ctr:.2f}%)",
                        "recommended_level": "ad_group",
                    }
                )

        return negatives

    def _analyze_local_intent(self, search_terms: list[SearchTerm]) -> dict[str, Any]:
        """Deep analysis of local intent searches."""
        local_data = {
            "near_me_analysis": {
                "terms": [],
                "total_impressions": 0,
                "total_conversions": 0,
                "total_cost": 0.0,
            },
            "city_mentions": defaultdict(list),
            "location_modifiers": defaultdict(list),
            "store_searches": [],
        }

        for term in search_terms:
            term_lower = term.search_term.lower()

            # Near me searches
            if "near me" in term_lower:
                local_data["near_me_analysis"]["terms"].append(term)
                local_data["near_me_analysis"]["total_impressions"] += (
                    term.metrics.impressions
                )
                local_data["near_me_analysis"]["total_conversions"] += (
                    term.metrics.conversions
                )
                local_data["near_me_analysis"]["total_cost"] += term.metrics.cost

            # Store-specific searches
            if any(pattern.search(term.search_term) for pattern in self.store_patterns):
                local_data["store_searches"].append(term)

            # Extract location modifiers
            for modifier in ["nearest", "closest", "nearby", "local"]:
                if modifier in term_lower:
                    local_data["location_modifiers"][modifier].append(term)

        # Calculate performance metrics
        near_me = local_data["near_me_analysis"]
        if near_me["terms"]:
            near_me["avg_cpa"] = (
                near_me["total_cost"] / near_me["total_conversions"]
                if near_me["total_conversions"] > 0
                else 0
            )
            near_me["conversion_rate"] = (
                sum(t.metrics.conversions for t in near_me["terms"])
                / sum(t.metrics.clicks for t in near_me["terms"])
                * 100
                if sum(t.metrics.clicks for t in near_me["terms"]) > 0
                else 0
            )

        return local_data

    def _create_analysis_result(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        search_terms: list[SearchTerm],
        **analysis_data: dict[str, Any],
    ) -> AnalysisResult:
        """Create comprehensive analysis result."""
        # Generate recommendations based on all analyses
        recommendations = self._generate_recommendations(search_terms, **analysis_data)

        # Calculate summary metrics
        total_impressions = sum(t.metrics.impressions for t in search_terms)
        total_clicks = sum(t.metrics.clicks for t in search_terms)
        total_cost = sum(t.metrics.cost for t in search_terms)
        total_conversions = sum(t.metrics.conversions for t in search_terms)

        # Count opportunities
        opportunity_count = sum(
            len(opps)
            for category in analysis_data.get("opportunity_analysis", {}).values()
            for opps in category
            if isinstance(opps, list)
        )

        # Count negative recommendations
        negative_count = sum(
            len(negs)
            for negs in analysis_data.get("negative_analysis", {}).values()
            if isinstance(negs, list)
        )

        # Create custom metrics
        custom_metrics = {
            "intent_breakdown": {
                intent: {
                    "count": len(data["terms"]),
                    "conversion_rate": data.get("conversion_rate", 0),
                    "avg_cpa": data.get("cpa", 0),
                }
                for intent, data in analysis_data.get("intent_analysis", {}).items()
            },
            "query_length_performance": analysis_data.get("pattern_analysis", {}).get(
                "query_length", {}
            ),
            "top_ngrams": self._get_top_ngrams(
                analysis_data.get("ngram_analysis", {}), limit=10
            ),
            "local_intent_summary": {
                "near_me_searches": len(
                    analysis_data.get("local_analysis", {})
                    .get("near_me_analysis", {})
                    .get("terms", [])
                ),
                "store_searches": len(
                    analysis_data.get("local_analysis", {}).get("store_searches", [])
                ),
            },
        }

        metrics = AnalysisMetrics(
            total_keywords_analyzed=0,  # Not applicable
            total_search_terms_analyzed=len(search_terms),
            total_campaigns_analyzed=len(set(t.campaign_id for t in search_terms)),
            issues_found=negative_count,
            critical_issues=len(
                [
                    r
                    for r in recommendations
                    if r.priority == RecommendationPriority.CRITICAL
                ]
            ),
            potential_cost_savings=sum(
                neg["cost"]
                for category in analysis_data.get("negative_analysis", {}).values()
                for neg in category
                if isinstance(neg, dict) and "cost" in neg
            ),
            potential_conversion_increase=(
                opportunity_count * 2.5
            ),  # Estimated 2.5% increase per opportunity
            custom_metrics=custom_metrics,
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="advanced_search_terms",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            metrics=metrics,
            raw_data={
                "summary": {
                    "total_search_terms": len(search_terms),
                    "total_impressions": total_impressions,
                    "total_clicks": total_clicks,
                    "total_cost": total_cost,
                    "total_conversions": total_conversions,
                    "avg_ctr": (total_clicks / total_impressions * 100)
                    if total_impressions > 0
                    else 0,
                    "avg_cpa": (total_cost / total_conversions)
                    if total_conversions > 0
                    else 0,
                },
                "intent_analysis": analysis_data.get("intent_analysis", {}),
                "pattern_analysis": analysis_data.get("pattern_analysis", {}),
                "opportunity_analysis": analysis_data.get("opportunity_analysis", {}),
                "negative_analysis": analysis_data.get("negative_analysis", {}),
                "local_analysis": analysis_data.get("local_analysis", {}),
            },
        )

    def _get_top_ngrams(
        self, ngram_analysis: dict[str, dict[str, Any]], limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get top performing n-grams."""
        # Sort by conversions, then by impressions
        sorted_ngrams = sorted(
            ngram_analysis.items(),
            key=lambda x: (x[1].get("conversions", 0), x[1].get("impressions", 0)),
            reverse=True,
        )

        return [
            {
                "ngram": ngram,
                "count": data["count"],
                "conversions": data.get("conversions", 0),
                "cost": data.get("cost", 0),
                "cpa": data.get("cpa", 0),
            }
            for ngram, data in sorted_ngrams[:limit]
        ]

    def _generate_recommendations(
        self, search_terms: list[SearchTerm], **analysis_data: dict[str, Any]
    ) -> list[Recommendation]:
        """Generate actionable recommendations from analysis."""
        recommendations = []

        # Intent-based recommendations
        intent_data = analysis_data.get("intent_analysis", {})
        for intent, data in intent_data.items():
            if intent == SearchTermIntent.TRANSACTIONAL and data.get("cpa", 0) > 100:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.OPTIMIZE_KEYWORDS,
                        priority=RecommendationPriority.HIGH,
                        title="Optimize Transactional Keywords",
                        description=(
                            f"Transactional queries have high CPA (${data['cpa']:.2f}). "
                            f"Review keyword targeting and landing pages for {len(data['terms'])} terms."
                        ),
                        estimated_cost_savings=data["cost"]
                        * 0.2,  # 20% potential savings
                    )
                )

        # Opportunity recommendations
        opportunities = analysis_data.get("opportunity_analysis", {})

        # New exact match opportunities
        exact_matches = opportunities.get("new_exact_match", [])
        if exact_matches:
            top_opportunity = max(exact_matches, key=lambda x: x["conversions"])
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title=f"Add {len(exact_matches)} High-Converting Exact Match Keywords",
                    description=(
                        f"Found {len(exact_matches)} converting search terms not in keywords. "
                        f"Top opportunity: '{top_opportunity['term']}' with "
                        f"{top_opportunity['conversions']} conversions at ${top_opportunity['cpa']:.2f} CPA."
                    ),
                    estimated_conversion_increase=len(exact_matches) * 2.5,
                    action_data={
                        "keywords": [
                            {"text": opp["term"], "match_type": "EXACT"}
                            for opp in exact_matches[:10]
                        ]
                    },
                )
            )

        # Multiple variations recommendation
        variations = opportunities.get("multiple_variations", [])
        if variations:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_KEYWORD,
                    priority=RecommendationPriority.MEDIUM,
                    title="Add Keywords to Capture Query Variations",
                    description=(
                        f"Found {len(variations)} query patterns with multiple converting variations. "
                        "Consider adding phrase match keywords to capture these efficiently."
                    ),
                    action_data={
                        "patterns": [
                            {
                                "base": var["base_term"],
                                "variations": var["variations"][:3],
                                "conversions": var["total_conversions"],
                            }
                            for var in variations[:5]
                        ]
                    },
                )
            )

        # Negative keyword recommendations
        negatives = analysis_data.get("negative_analysis", {})

        # Collect all negative keywords
        all_negatives = []
        for category, negs in negatives.items():
            if isinstance(negs, list):
                all_negatives.extend(negs)

        if all_negatives:
            total_waste = sum(neg.get("cost", 0) for neg in all_negatives)

            # Separate by priority
            irrelevant = negatives.get("irrelevant", [])
            high_cost_no_conv = negatives.get("high_cost_no_conversion", [])

            # Create recommendation based on what we found
            if irrelevant:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_NEGATIVE,
                        priority=RecommendationPriority.CRITICAL,
                        title=f"Add {len(irrelevant)} Irrelevant Keywords as Negatives",
                        description=(
                            f"Found {len(irrelevant)} irrelevant search terms "
                            f"(e.g., jobs, free, DIY) wasting ${sum(n.get('cost', 0) for n in irrelevant):.2f}."
                        ),
                        estimated_cost_savings=sum(
                            n.get("cost", 0) for n in irrelevant
                        ),
                        action_data={
                            "negatives": [
                                {
                                    "text": neg["term"],
                                    "level": neg["recommended_level"],
                                    "reason": neg["reason"],
                                }
                                for neg in irrelevant[:10]
                            ]
                        },
                    )
                )

            if high_cost_no_conv:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_NEGATIVE,
                        priority=RecommendationPriority.HIGH,
                        title=f"Add {len(high_cost_no_conv)} High-Cost Zero-Conversion Terms as Negatives",
                        description=(
                            f"Identified {len(high_cost_no_conv)} search terms with "
                            f"${sum(n.get('cost', 0) for n in high_cost_no_conv):.2f} in wasted spend and zero conversions."
                        ),
                        estimated_cost_savings=sum(
                            n.get("cost", 0) for n in high_cost_no_conv
                        ),
                        action_data={
                            "negatives": [
                                {
                                    "text": neg["term"],
                                    "level": neg["recommended_level"],
                                    "cost_wasted": neg["cost"],
                                }
                                for neg in high_cost_no_conv[:10]
                            ]
                        },
                    )
                )

        # Local intent recommendations
        local_data = analysis_data.get("local_analysis", {})
        near_me_data = local_data.get("near_me_analysis", {})
        if near_me_data.get("terms") and near_me_data.get("conversion_rate", 0) > 2:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_LOCATION,
                    priority=RecommendationPriority.HIGH,
                    title="Optimize for 'Near Me' Searches",
                    description=(
                        f"'Near me' searches show strong performance with "
                        f"{near_me_data['conversion_rate']:.1f}% conversion rate. "
                        f"Ensure location extensions are active and create dedicated local campaigns."
                    ),
                    estimated_conversion_increase=5.0,
                )
            )

        # N-gram pattern recommendations
        ngram_data = analysis_data.get("ngram_analysis", {})
        high_performing_ngrams = [
            (ngram, data)
            for ngram, data in ngram_data.items()
            if data.get("conversions", 0) >= 5 and len(ngram.split()) >= 2
        ]
        if high_performing_ngrams:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_KEYWORD,
                    priority=RecommendationPriority.MEDIUM,
                    title="Target High-Performing Phrase Patterns",
                    description=(
                        f"Found {len(high_performing_ngrams)} multi-word patterns with "
                        "strong conversion performance. Consider adding these as phrase match keywords."
                    ),
                    action_data={
                        "patterns": [
                            {
                                "phrase": ngram,
                                "conversions": data["conversions"],
                                "occurrences": data["count"],
                            }
                            for ngram, data in sorted(
                                high_performing_ngrams,
                                key=lambda x: x[1]["conversions"],
                                reverse=True,
                            )[:10]
                        ]
                    },
                )
            )

        # Query length insights
        query_length_data = analysis_data.get("pattern_analysis", {}).get(
            "query_length", {}
        )
        long_tail_performance = {
            length: data
            for length, data in query_length_data.items()
            if length >= 4 and data.get("conversions", 0) > 0
        }
        if long_tail_performance:
            avg_long_tail_cpa = sum(
                data.get("cpa", 0) for data in long_tail_performance.values()
            ) / len(long_tail_performance)
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title="Focus on Long-Tail Keywords",
                    description=(
                        f"Queries with 4+ words show good performance with average "
                        f"CPA of ${avg_long_tail_cpa:.2f}. Consider expanding long-tail keyword coverage."
                    ),
                )
            )

        return recommendations
