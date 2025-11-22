"""Search Terms Analyzer for Google Ads audit with performance optimizations."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator

from paidsearchnav.core.config import AnalyzerThresholds
from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    Recommendation,
    RecommendationPriority,
    RecommendationType,
    SearchTerm,
    SearchTermAnalysisResult,
    SearchTermClassification,
)
from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


class SearchTermsAnalyzer(Analyzer):
    """Analyzes search terms to identify opportunities and waste with optimized performance."""

    # Default batch size for processing
    DEFAULT_BATCH_SIZE = 1000
    # Minimum batch size to prevent excessive overhead
    MIN_BATCH_SIZE = 100
    # Maximum batch size to prevent memory issues
    MAX_BATCH_SIZE = 10000

    def __init__(
        self,
        data_provider: DataProvider,
        thresholds: AnalyzerThresholds | None = None,
        batch_size: int | None = None,
    ):
        """Initialize the analyzer.

        Args:
            data_provider: Provider for fetching Google Ads data
            thresholds: Configurable analyzer thresholds (uses defaults if None)
            batch_size: Size of batches for processing (uses DEFAULT_BATCH_SIZE if None)

        Raises:
            ValueError: If batch_size is outside valid range
        """
        self.data_provider = data_provider
        self.thresholds = thresholds or AnalyzerThresholds()

        # Validate and set batch size
        if batch_size is not None:
            if batch_size < self.MIN_BATCH_SIZE:
                raise ValueError(
                    f"batch_size must be at least {self.MIN_BATCH_SIZE}, got {batch_size}"
                )
            if batch_size > self.MAX_BATCH_SIZE:
                raise ValueError(
                    f"batch_size cannot exceed {self.MAX_BATCH_SIZE}, got {batch_size}"
                )
            self.batch_size = batch_size
        else:
            self.batch_size = self.DEFAULT_BATCH_SIZE

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Search Terms Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes search terms report with optimized performance for large datasets. "
            "Identifies high-performing queries to add as keywords and poor-performing "
            "queries to add as negatives using batch processing and streaming calculations."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> SearchTermAnalysisResult:
        """Analyze search terms for the given period with optimized performance."""
        logger.info(
            f"Starting optimized search terms analysis for {customer_id} "
            f"from {start_date} to {end_date} with batch size {self.batch_size}"
        )

        # Get optional parameters
        campaigns = kwargs.get("campaigns")
        ad_groups = kwargs.get("ad_groups")

        # Initialize accumulator for streaming calculations
        accumulator = StreamingAccumulator()
        classified_terms = defaultdict(list)

        # Build keyword lookup set (memory efficient - only texts)
        keyword_texts = await self._build_keyword_lookup_optimized(
            customer_id, campaigns, ad_groups
        )

        # Process search terms in batches
        batch_count = 0
        async for batch in self._fetch_search_terms_batched(
            customer_id, start_date, end_date, campaigns, ad_groups
        ):
            batch_count += 1
            logger.debug(f"Processing batch {batch_count} with {len(batch)} items")

            # Process batch
            batch_classified = await self._process_batch(
                batch, keyword_texts, accumulator
            )

            # Merge classifications
            for classification, terms in batch_classified.items():
                classified_terms[classification].extend(terms)

        # Calculate final account average CPA from accumulated data
        account_avg_cpa = accumulator.get_average_cpa(
            self.thresholds.default_cpa_fallback
        )

        # Create analysis result with accumulated metrics
        result = self._create_optimized_analysis_result(
            customer_id,
            start_date,
            end_date,
            accumulator,
            dict(classified_terms),
            account_avg_cpa,
        )

        logger.info(
            f"Completed optimized search terms analysis. Processed {batch_count} batches, "
            f"{accumulator.total_terms} total terms. Found {len(result.add_candidates)} add candidates, "
            f"{len(result.negative_candidates)} negative candidates"
        )

        return result

    async def _build_keyword_lookup_optimized(
        self,
        customer_id: str,
        campaigns: list[str] | None,
        ad_groups: list[str] | None,
    ) -> set[str]:
        """Build keyword lookup set with pagination to reduce memory usage."""
        keyword_texts = set()
        page_size = 5000  # Large page size for keywords since we only store text

        # Fetch keywords with pagination
        keywords = await self.data_provider.get_keywords(
            customer_id,
            campaigns=campaigns,
            ad_groups=ad_groups,
            include_metrics=False,  # Don't need metrics for lookup
            page_size=page_size,
        )

        for keyword in keywords:
            if keyword.status == "ENABLED":
                # Normalize keyword text
                normalized = keyword.text.lower().strip()
                keyword_texts.add(normalized)

        logger.debug(f"Built keyword lookup with {len(keyword_texts)} unique keywords")
        return keyword_texts

    async def _fetch_search_terms_batched(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None,
        ad_groups: list[str] | None,
    ) -> AsyncIterator[list[SearchTerm]]:
        """Fetch search terms in batches for memory-efficient processing."""
        # For now, fetch all search terms at once
        # TODO: Implement proper pagination with offset/cursor support in data providers
        all_search_terms = await self.data_provider.get_search_terms(
            customer_id,
            start_date,
            end_date,
            campaigns=campaigns,
            ad_groups=ad_groups,
        )

        # Process in batches
        for i in range(0, len(all_search_terms), self.batch_size):
            batch = all_search_terms[i : i + self.batch_size]

            # Filter by minimum impressions and detect local intent
            filtered_batch = []
            for search_term in batch:
                if search_term.metrics.impressions >= self.thresholds.min_impressions:
                    search_term.detect_local_intent()
                    filtered_batch.append(search_term)

            if filtered_batch:
                yield filtered_batch

    async def _process_batch(
        self,
        batch: list[SearchTerm],
        keyword_texts: set[str],
        accumulator: "StreamingAccumulator",
    ) -> dict[SearchTermClassification, list[SearchTerm]]:
        """Process a batch of search terms."""
        classified = defaultdict(list)

        for search_term in batch:
            # Update streaming metrics
            accumulator.update(search_term)

            # Use current average CPA for classification
            current_avg_cpa = accumulator.get_average_cpa(
                self.thresholds.default_cpa_fallback
            )

            # Classify the term
            classification, reason = self._classify_single_term(
                search_term, keyword_texts, current_avg_cpa
            )

            search_term.classification = classification
            search_term.classification_reason = reason
            search_term.recommendation = self._get_recommendation(
                search_term, classification
            )

            classified[classification].append(search_term)

        return dict(classified)

    def _calculate_average_cpa(self, search_terms: list[SearchTerm]) -> float:
        """Calculate account average CPA from search terms."""
        total_cost = sum(st.metrics.cost for st in search_terms)
        total_conversions = sum(st.metrics.conversions for st in search_terms)

        if total_conversions > 0:
            return total_cost / total_conversions
        else:
            # If no conversions, use configurable default CPA
            return self.thresholds.default_cpa_fallback

    def _classify_search_terms(
        self,
        search_terms: list[SearchTerm],
        keyword_texts: set[str],
        account_avg_cpa: float,
    ) -> dict[SearchTermClassification, list[SearchTerm]]:
        """Classify search terms into categories."""
        classified = defaultdict(list)

        for search_term in search_terms:
            classification, reason = self._classify_single_term(
                search_term, keyword_texts, account_avg_cpa
            )

            search_term.classification = classification
            search_term.classification_reason = reason
            search_term.recommendation = self._get_recommendation(
                search_term, classification
            )

            classified[classification].append(search_term)

        return dict(classified)

    def _classify_single_term(
        self,
        search_term: SearchTerm,
        keyword_texts: set[str],
        account_avg_cpa: float,
    ) -> tuple[SearchTermClassification, str]:
        """Classify a single search term with optimized logic."""
        normalized_term = search_term.search_term.lower().strip()

        # Early exit for already covered terms
        if normalized_term in keyword_texts:
            return (
                SearchTermClassification.ALREADY_COVERED,
                "Exact match with existing keyword",
            )

        # Check performance metrics in order of computational cost
        metrics = search_term.metrics

        # High performers (check conversions first as it's most selective)
        if metrics.conversions >= self.thresholds.min_conversions_for_add:
            # Check efficiency
            if (
                metrics.cpa <= account_avg_cpa * self.thresholds.max_cpa_multiplier
                or metrics.roas >= self.thresholds.min_roas_for_add
            ):
                return (
                    SearchTermClassification.ADD_CANDIDATE,
                    f"High performing: {metrics.conversions:.1f} conversions, "
                    f"CPA: ${metrics.cpa:.2f}",
                )

        # Wasteful terms (no conversions with significant spend/clicks)
        if metrics.conversions == 0:
            min_waste_cost = account_avg_cpa * 0.5
            if (
                metrics.clicks >= self.thresholds.min_clicks_for_negative
                and metrics.cost >= min_waste_cost
            ):
                return (
                    SearchTermClassification.NEGATIVE_CANDIDATE,
                    f"Wasteful spend: ${metrics.cost:.2f} cost, "
                    f"{metrics.clicks} clicks, no conversions",
                )

        # Poor CTR check (computationally cheaper than is_wasteful)
        if (
            metrics.impressions >= self.thresholds.min_impressions_for_ctr_check
            and metrics.ctr < self.thresholds.max_ctr_for_negative
        ):
            return (
                SearchTermClassification.NEGATIVE_CANDIDATE,
                f"Poor relevance: {metrics.ctr:.2f}% CTR",
            )

        # Edge cases for review
        if (
            metrics.clicks >= 5
            and 0 < metrics.conversions < self.thresholds.min_conversions_for_add
        ):
            return (
                SearchTermClassification.REVIEW_NEEDED,
                f"Borderline performance: {metrics.conversions:.1f} conversions",
            )

        # Significant spend without clear classification
        if metrics.cost >= account_avg_cpa * 0.25:
            return (
                SearchTermClassification.REVIEW_NEEDED,
                "Significant spend without clear classification",
            )

        # Default: low volume
        return (
            SearchTermClassification.ALREADY_COVERED,
            "Low volume, likely covered by existing broad match",
        )

    def _get_recommendation(
        self, search_term: SearchTerm, classification: SearchTermClassification
    ) -> str:
        """Get specific recommendation for a search term."""
        if classification == SearchTermClassification.ADD_CANDIDATE:
            # Recommend match type based on term characteristics
            if (
                search_term.contains_near_me
                or len(search_term.search_term.split()) >= 4
            ):
                match_type = "Exact"
            else:
                match_type = "Phrase"

            return f"Add as {match_type} match keyword in ad group '{search_term.ad_group_name}'"

        elif classification == SearchTermClassification.NEGATIVE_CANDIDATE:
            # Recommend negative level based on scope
            if search_term.metrics.impressions >= 1000:
                level = "account"
            elif search_term.metrics.impressions >= 100:
                level = "campaign"
            else:
                level = "ad group"

            return f"Add as negative keyword at {level} level"

        elif classification == SearchTermClassification.REVIEW_NEEDED:
            return "Manual review recommended - consider business context"

        else:
            return "No action needed"

    def _create_optimized_analysis_result(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        accumulator: "StreamingAccumulator",
        classified_terms: dict[SearchTermClassification, list[SearchTerm]],
        account_avg_cpa: float,
    ) -> SearchTermAnalysisResult:
        """Create analysis result from accumulated data."""
        # Calculate potential impact
        potential_savings = sum(
            st.metrics.cost
            for st in classified_terms.get(
                SearchTermClassification.NEGATIVE_CANDIDATE, []
            )
        )
        potential_revenue = sum(
            st.metrics.conversion_value
            for st in classified_terms.get(SearchTermClassification.ADD_CANDIDATE, [])
        )

        # Generate recommendations
        recommendations = self._generate_recommendations_optimized(
            classified_terms,
            accumulator.total_cost,
            accumulator.total_conversions,
            potential_savings,
        )

        # Create classification summary
        classification_summary = {
            classification: len(terms)
            for classification, terms in classified_terms.items()
        }

        return SearchTermAnalysisResult(
            customer_id=customer_id,
            analysis_type="search_terms",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            total_search_terms=accumulator.total_terms,
            total_impressions=accumulator.total_impressions,
            total_clicks=accumulator.total_clicks,
            total_cost=accumulator.total_cost,
            total_conversions=accumulator.total_conversions,
            add_candidates=classified_terms.get(
                SearchTermClassification.ADD_CANDIDATE, []
            ),
            negative_candidates=classified_terms.get(
                SearchTermClassification.NEGATIVE_CANDIDATE, []
            ),
            already_covered=classified_terms.get(
                SearchTermClassification.ALREADY_COVERED, []
            ),
            review_needed=classified_terms.get(
                SearchTermClassification.REVIEW_NEEDED, []
            ),
            classification_summary=classification_summary,
            local_intent_terms=accumulator.local_intent_count,
            near_me_terms=accumulator.near_me_count,
            potential_savings=potential_savings,
            potential_revenue=potential_revenue,
            recommendations=self._convert_recommendations_to_objects(recommendations),
        )

    def _create_analysis_result(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        all_search_terms: list[SearchTerm],
        classified_terms: dict[SearchTermClassification, list[SearchTerm]],
    ) -> SearchTermAnalysisResult:
        """Create the final analysis result."""
        # Calculate totals
        total_impressions = sum(st.metrics.impressions for st in all_search_terms)
        total_clicks = sum(st.metrics.clicks for st in all_search_terms)
        total_cost = sum(st.metrics.cost for st in all_search_terms)
        total_conversions = sum(st.metrics.conversions for st in all_search_terms)

        # Calculate local intent metrics
        local_intent_terms = sum(1 for st in all_search_terms if st.is_local_intent)
        near_me_terms = sum(1 for st in all_search_terms if st.contains_near_me)

        # Calculate potential impact
        potential_savings = sum(
            st.metrics.cost
            for st in classified_terms.get(
                SearchTermClassification.NEGATIVE_CANDIDATE, []
            )
        )
        potential_revenue = sum(
            st.metrics.conversion_value
            for st in classified_terms.get(SearchTermClassification.ADD_CANDIDATE, [])
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            classified_terms, total_cost, total_conversions
        )

        # Create classification summary
        classification_summary = {
            classification: len(terms)
            for classification, terms in classified_terms.items()
        }

        return SearchTermAnalysisResult(
            customer_id=customer_id,
            analysis_type="search_terms",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            total_search_terms=len(all_search_terms),
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_cost=total_cost,
            total_conversions=total_conversions,
            add_candidates=classified_terms.get(
                SearchTermClassification.ADD_CANDIDATE, []
            ),
            negative_candidates=classified_terms.get(
                SearchTermClassification.NEGATIVE_CANDIDATE, []
            ),
            already_covered=classified_terms.get(
                SearchTermClassification.ALREADY_COVERED, []
            ),
            review_needed=classified_terms.get(
                SearchTermClassification.REVIEW_NEEDED, []
            ),
            classification_summary=classification_summary,
            local_intent_terms=local_intent_terms,
            near_me_terms=near_me_terms,
            potential_savings=potential_savings,
            potential_revenue=potential_revenue,
            recommendations=self._convert_recommendations_to_objects(recommendations),
        )

    def _generate_recommendations_optimized(
        self,
        classified_terms: dict[SearchTermClassification, list[SearchTerm]],
        total_cost: float,
        total_conversions: float,
        potential_savings: float,
    ) -> list[str]:
        """Generate actionable recommendations with pre-calculated metrics."""
        recommendations = []

        add_candidates = classified_terms.get(
            SearchTermClassification.ADD_CANDIDATE, []
        )
        negative_candidates = classified_terms.get(
            SearchTermClassification.NEGATIVE_CANDIDATE, []
        )

        if add_candidates:
            # Sort only top 5 for recommendation text
            top_adds = sorted(
                add_candidates[:10],  # Limit sort to first 10 for efficiency
                key=lambda x: x.metrics.conversion_value,
                reverse=True,
            )[:5]

            if top_adds:
                recommendations.append(
                    f"Add {len(add_candidates)} high-performing search terms as keywords, "
                    f"starting with '{top_adds[0].search_term}' "
                    f"({top_adds[0].metrics.conversions:.1f} conversions)"
                )

        if negative_candidates and total_cost > 0:
            savings_pct = potential_savings / total_cost * 100
            recommendations.append(
                f"Add {len(negative_candidates)} negative keywords to save "
                f"${potential_savings:.2f} ({savings_pct:.1f}% of total spend)"
            )

        # Local intent recommendations
        local_terms = sum(1 for st in add_candidates if st.is_local_intent)
        if local_terms:
            recommendations.append(
                f"Found {local_terms} high-performing local intent queries. "
                "Consider creating location-specific ad groups."
            )

        # Near me specific
        near_me_terms = sum(1 for st in add_candidates if st.contains_near_me)
        if near_me_terms:
            recommendations.append(
                f"{near_me_terms} 'near me' searches are converting well. "
                "Ensure location extensions are active."
            )

        # Quality recommendations
        if total_conversions == 0:
            recommendations.append(
                "No conversions found in search terms. Review conversion tracking setup."
            )
        elif len(negative_candidates) > len(add_candidates) * 2:
            recommendations.append(
                "High ratio of negative to positive terms suggests keyword targeting "
                "may be too broad. Review match types."
            )

        return recommendations

    def _generate_recommendations(
        self,
        classified_terms: dict[SearchTermClassification, list[SearchTerm]],
        total_cost: float,
        total_conversions: float,
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        add_candidates = classified_terms.get(
            SearchTermClassification.ADD_CANDIDATE, []
        )
        negative_candidates = classified_terms.get(
            SearchTermClassification.NEGATIVE_CANDIDATE, []
        )

        if add_candidates:
            top_adds = sorted(
                add_candidates, key=lambda x: x.metrics.conversion_value, reverse=True
            )[:5]
            recommendations.append(
                f"Add {len(add_candidates)} high-performing search terms as keywords, "
                f"starting with '{top_adds[0].search_term}' "
                f"({top_adds[0].metrics.conversions:.1f} conversions)"
            )

        if negative_candidates:
            savings_pct = (
                sum(st.metrics.cost for st in negative_candidates) / total_cost * 100
            )
            recommendations.append(
                f"Add {len(negative_candidates)} negative keywords to save "
                f"${sum(st.metrics.cost for st in negative_candidates):.2f} "
                f"({savings_pct:.1f}% of total spend)"
            )

        # Local intent recommendations
        local_terms = [st for st in add_candidates if st.is_local_intent]
        if local_terms:
            recommendations.append(
                f"Found {len(local_terms)} high-performing local intent queries. "
                "Consider creating location-specific ad groups."
            )

        # Near me specific
        near_me_terms = [st for st in add_candidates if st.contains_near_me]
        if near_me_terms:
            recommendations.append(
                f"{len(near_me_terms)} 'near me' searches are converting well. "
                "Ensure location extensions are active."
            )

        # Quality recommendations
        if total_conversions == 0:
            recommendations.append(
                "No conversions found in search terms. Review conversion tracking setup."
            )
        elif len(negative_candidates) > len(add_candidates) * 2:
            recommendations.append(
                "High ratio of negative to positive terms suggests keyword targeting "
                "may be too broad. Review match types."
            )

        return recommendations

    def _convert_recommendations_to_objects(
        self, recommendations: list[str]
    ) -> list[Recommendation]:
        """Convert string recommendations to Recommendation objects."""
        rec_objects = []

        for rec_text in recommendations:
            # Determine type and priority based on recommendation text
            if "Add" in rec_text and "high-performing" in rec_text:
                rec_type = RecommendationType.ADD_KEYWORD
                priority = RecommendationPriority.HIGH
            elif "negative" in rec_text:
                rec_type = RecommendationType.ADD_NEGATIVE
                priority = RecommendationPriority.HIGH
            elif "local intent" in rec_text:
                rec_type = RecommendationType.OPTIMIZE_LOCATION
                priority = RecommendationPriority.MEDIUM
            elif "near me" in rec_text:
                rec_type = RecommendationType.OPTIMIZE_LOCATION
                priority = RecommendationPriority.MEDIUM
            else:
                rec_type = RecommendationType.OTHER
                priority = RecommendationPriority.LOW

            rec_objects.append(
                Recommendation(
                    type=rec_type,
                    priority=priority,
                    title=rec_text[:50] + "..." if len(rec_text) > 50 else rec_text,
                    description=rec_text,
                )
            )

        return rec_objects


class StreamingAccumulator:
    """Accumulator for streaming metric calculations to avoid loading all data in memory."""

    def __init__(self):
        """Initialize the accumulator."""
        self.total_terms = 0
        self.total_impressions = 0
        self.total_clicks = 0
        self.total_cost = 0.0
        self.total_conversions = 0.0
        self.total_conversion_value = 0.0
        self.local_intent_count = 0
        self.near_me_count = 0

    def update(self, search_term: SearchTerm) -> None:
        """Update accumulated metrics with a search term."""
        self.total_terms += 1
        self.total_impressions += search_term.metrics.impressions
        self.total_clicks += search_term.metrics.clicks
        self.total_cost += search_term.metrics.cost
        self.total_conversions += search_term.metrics.conversions
        self.total_conversion_value += search_term.metrics.conversion_value

        if search_term.is_local_intent:
            self.local_intent_count += 1
        if search_term.contains_near_me:
            self.near_me_count += 1

    def get_average_cpa(self, default: float) -> float:
        """Calculate current average CPA."""
        if self.total_conversions > 0:
            return self.total_cost / self.total_conversions
        return default
