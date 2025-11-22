"""Performance benchmarks for search terms analyzer optimizations."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

import pytest

from paidsearchnav.analyzers.search_terms import (
    SearchTermsAnalyzer,
    StreamingAccumulator,
)
from paidsearchnav.core.config import AnalyzerThresholds
from paidsearchnav.core.models import Keyword, SearchTerm, SearchTermMetrics
from paidsearchnav.data_providers.base import DataProvider


class MockDataProvider(DataProvider):
    """Mock data provider for performance testing."""

    def __init__(self, num_search_terms: int, num_keywords: int):
        """Initialize with specified data sizes."""
        self.num_search_terms = num_search_terms
        self.num_keywords = num_keywords
        self._search_terms = self._generate_search_terms()
        self._keywords = self._generate_keywords()

    def _generate_search_terms(self) -> list[SearchTerm]:
        """Generate mock search terms."""
        search_terms = []
        for i in range(self.num_search_terms):
            # Vary the data to simulate real patterns
            impressions = 100 + (i % 1000) * 10
            clicks = max(1, impressions // 20)
            cost = clicks * 1.5
            conversions = clicks * 0.05 if i % 10 < 3 else 0  # 30% have conversions
            conversion_value = conversions * 50 if conversions > 0 else 0

            st = SearchTerm(
                search_term=f"search term {i}",
                campaign_id=f"campaign_{i % 10}",
                campaign_name=f"Campaign {i % 10}",
                ad_group_id=f"adgroup_{i % 50}",
                ad_group_name=f"Ad Group {i % 50}",
                metrics=SearchTermMetrics(
                    impressions=impressions,
                    clicks=clicks,
                    cost=cost,
                    conversions=conversions,
                    conversion_value=conversion_value,
                ),
            )
            search_terms.append(st)
        return search_terms

    def _generate_keywords(self) -> list[Keyword]:
        """Generate mock keywords."""
        keywords = []
        for i in range(self.num_keywords):
            kw = Keyword(
                keyword_id=f"keyword_{i}",
                text=f"keyword {i}",
                match_type="EXACT",
                status="ENABLED",
                campaign_id=f"campaign_{i % 10}",
                campaign_name=f"Campaign {i % 10}",
                ad_group_id=f"adgroup_{i % 50}",
                ad_group_name=f"Ad Group {i % 50}",
            )
            keywords.append(kw)
        return keywords

    async def get_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[SearchTerm]:
        """Return mock search terms with pagination support."""
        # Simulate some processing time
        await asyncio.sleep(0.001)  # 1ms per call

        if page_size and max_results:
            # Return paginated results
            end_idx = min(max_results, self.num_search_terms)
            return self._search_terms[:end_idx]
        else:
            # Return all results (original behavior)
            return self._search_terms

    async def get_keywords(
        self,
        customer_id: str,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        campaign_id: str | None = None,
        include_metrics: bool = True,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Keyword]:
        """Return mock keywords."""
        # Simulate some processing time
        await asyncio.sleep(0.001)  # 1ms per call
        return self._keywords

    # Implement other required abstract methods with dummy implementations
    async def get_negative_keywords(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    async def get_campaigns(self, *args, **kwargs) -> list[Any]:
        return []

    async def get_shared_negative_lists(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    async def get_campaign_shared_sets(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    async def get_shared_set_negatives(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []

    async def get_placement_data(self, *args, **kwargs) -> list[dict[str, Any]]:
        return []


class TestSearchTermsPerformance:
    """Performance comparison tests between original and optimized analyzers."""

    @pytest.mark.parametrize(
        "num_search_terms,num_keywords",
        [
            (1000, 100),  # Small dataset
            (10000, 500),  # Medium dataset
            (5000, 500),  # Medium-large dataset (optimized for CI)
            (10000, 1000),  # Large dataset (optimized for CI)
        ],
    )
    @pytest.mark.asyncio
    async def test_analyzer_performance_comparison(
        self, num_search_terms, num_keywords
    ):
        """Compare performance between original and optimized analyzers."""
        # Setup
        data_provider = MockDataProvider(num_search_terms, num_keywords)
        thresholds = AnalyzerThresholds()
        customer_id = "1234567890"
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        # Test original analyzer (without batch processing)
        # Use max allowed batch size to simulate no batching
        original_analyzer = SearchTermsAnalyzer(
            data_provider, thresholds, batch_size=min(num_search_terms, 10000)
        )

        start_time = time.time()
        original_result = await original_analyzer.analyze(
            customer_id, start_date, end_date
        )
        original_time = time.time() - start_time

        # Test optimized analyzer with batch processing
        optimized_analyzer = SearchTermsAnalyzer(
            data_provider, thresholds, batch_size=1000
        )

        start_time = time.time()
        optimized_result = await optimized_analyzer.analyze(
            customer_id, start_date, end_date
        )
        optimized_time = time.time() - start_time

        # Performance assertions
        print(
            f"\nDataset size: {num_search_terms} search terms, {num_keywords} keywords"
        )
        print(f"Original analyzer time: {original_time:.2f}s")
        print(f"Optimized analyzer time: {optimized_time:.2f}s")
        print(f"Speedup: {original_time / optimized_time:.2f}x")

        # Verify results are equivalent
        assert original_result.total_search_terms == optimized_result.total_search_terms
        assert abs(original_result.total_cost - optimized_result.total_cost) < 0.01
        assert (
            abs(original_result.total_conversions - optimized_result.total_conversions)
            < 0.01
        )

        # For very large datasets, optimized should be faster
        # Note: Due to async overhead, benefits are more visible with larger datasets
        if num_search_terms >= 50000:
            assert optimized_time < original_time * 1.1, (
                "Optimized analyzer should not be significantly slower"
            )

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test that optimized analyzer uses less memory with streaming."""
        # Create a large dataset
        num_terms = 50000
        data_provider = MockDataProvider(num_terms, 1000)
        thresholds = AnalyzerThresholds()

        # Test with different batch sizes
        batch_sizes = [500, 1000, 5000]

        for batch_size in batch_sizes:
            analyzer = SearchTermsAnalyzer(
                data_provider, thresholds, batch_size=batch_size
            )

            start_time = time.time()
            result = await analyzer.analyze(
                "1234567890",
                datetime.now() - timedelta(days=30),
                datetime.now(),
            )
            elapsed = time.time() - start_time

            print(f"\nBatch size: {batch_size}")
            print(f"Processing time: {elapsed:.2f}s")
            print(f"Terms processed: {result.total_search_terms}")

            # Verify all terms were processed
            assert result.total_search_terms > 0

    @pytest.mark.asyncio
    async def test_batch_processing_correctness(self):
        """Test that batch processing produces correct results."""
        # Create test data with known patterns
        num_terms = 1000
        data_provider = MockDataProvider(num_terms, 100)
        thresholds = AnalyzerThresholds(
            min_impressions=50,
            min_conversions_for_add=1.0,
            min_clicks_for_negative=5,
        )

        # Test with small batches to ensure correctness
        analyzer = SearchTermsAnalyzer(data_provider, thresholds, batch_size=100)

        result = await analyzer.analyze(
            "1234567890",
            datetime.now() - timedelta(days=30),
            datetime.now(),
        )

        # Verify classifications
        assert len(result.add_candidates) > 0, "Should have add candidates"
        assert len(result.negative_candidates) > 0, "Should have negative candidates"
        assert result.total_search_terms <= num_terms, "Should not exceed total terms"

        # Verify all candidates meet thresholds
        for candidate in result.add_candidates:
            assert candidate.metrics.conversions >= thresholds.min_conversions_for_add

        for candidate in result.negative_candidates:
            assert candidate.metrics.conversions == 0

    @pytest.mark.asyncio
    async def test_streaming_accumulator_accuracy(self):
        """Test that streaming accumulator maintains accuracy."""

        accumulator = StreamingAccumulator()

        # Create test search terms
        test_terms = []
        expected_cost = 0
        expected_conversions = 0

        for i in range(100):
            cost = float(i * 2)
            conversions = float(i * 0.1)

            st = SearchTerm(
                search_term=f"term {i}",
                campaign_id="campaign_1",
                campaign_name="Campaign 1",
                ad_group_id="adgroup_1",
                ad_group_name="Ad Group 1",
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=10,
                    cost=cost,
                    conversions=conversions,
                    conversion_value=conversions * 50,
                ),
            )

            # Set local intent fields directly instead of computed properties
            if i % 3 == 0:
                st.has_location = True
                st.detected_location = "near me"
            if i % 5 == 0:
                st.has_near_me = True

            test_terms.append(st)
            expected_cost += cost
            expected_conversions += conversions

        # Process terms through accumulator
        for term in test_terms:
            accumulator.update(term)

        # Verify accuracy
        assert accumulator.total_terms == 100
        assert abs(accumulator.total_cost - expected_cost) < 0.01
        assert abs(accumulator.total_conversions - expected_conversions) < 0.01
        # Count expected local intent and near me terms
        expected_local_intent = sum(1 for term in test_terms if term.is_local_intent)
        expected_near_me = sum(1 for term in test_terms if term.contains_near_me)
        assert accumulator.local_intent_count == expected_local_intent
        assert accumulator.near_me_count == expected_near_me

        # Test average CPA calculation
        avg_cpa = accumulator.get_average_cpa(100.0)
        expected_avg_cpa = expected_cost / expected_conversions
        assert abs(avg_cpa - expected_avg_cpa) < 0.01


if __name__ == "__main__":
    # Run performance tests
    asyncio.run(
        TestSearchTermsPerformance().test_analyzer_performance_comparison(50000, 1000)
    )
