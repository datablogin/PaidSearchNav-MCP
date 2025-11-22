"""Performance tests for shared negative validator optimizations."""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from paidsearchnav_mcp.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer
from paidsearchnav_mcp.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav_mcp.models.keyword import Keyword, KeywordMatchType, KeywordStatus


class MockDataProvider:
    """Mock data provider that simulates API call delays."""

    def __init__(self, api_delay: float = 0.1):
        self.api_delay = api_delay
        self.call_count = 0
        self.parallel_calls = 0
        self.max_parallel_calls = 0
        self._current_parallel_calls = 0
        self._lock = asyncio.Lock()

    async def get_campaigns(self, customer_id: str, **kwargs):
        """Mock get_campaigns."""
        await asyncio.sleep(0.01)  # Minimal delay
        return [
            Campaign(
                campaign_id=f"campaign_{i}",
                customer_id=customer_id,
                name=f"Campaign {i}",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=100.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MAXIMIZE_CONVERSIONS,
                impressions=10000,
                clicks=1000,
                conversions=100,
                cost=1000.0,
            )
            for i in range(10)
        ]

    async def get_shared_negative_lists(self, customer_id: str):
        """Mock get_shared_negative_lists."""
        await asyncio.sleep(0.01)
        return [{"id": f"list_{i}", "name": f"Shared List {i}"} for i in range(5)]

    async def get_campaign_shared_sets(self, customer_id: str, campaign_id: str):
        """Mock get_campaign_shared_sets."""
        await asyncio.sleep(0.01)
        # Return 2 shared sets per campaign
        return [
            {"id": "list_0", "name": "Shared List 0"},
            {"id": "list_1", "name": "Shared List 1"},
        ]

    async def get_shared_set_negatives(self, customer_id: str, shared_set_id: str):
        """Mock get_shared_set_negatives with delay to simulate API call."""
        async with self._lock:
            self._current_parallel_calls += 1
            self.max_parallel_calls = max(
                self.max_parallel_calls, self._current_parallel_calls
            )

        try:
            self.call_count += 1
            await asyncio.sleep(self.api_delay)  # Simulate API delay

            # Return 100 negative keywords per shared list
            return [
                {"text": f"negative_{shared_set_id}_{i}", "match_type": "BROAD"}
                for i in range(100)
            ]
        finally:
            async with self._lock:
                self._current_parallel_calls -= 1

    async def get_keywords(
        self, customer_id: str, campaigns: list[str], page_size: int | None = None
    ):
        """Mock get_keywords with pagination support."""
        await asyncio.sleep(0.05)  # Simulate API delay

        # If page_size is provided, it indicates pagination support is being used
        num_keywords = page_size if page_size else 5000  # Large number if no pagination

        return [
            Keyword(
                keyword_id=f"kw_{i}",
                text=f"keyword {i}",
                match_type=KeywordMatchType.BROAD,
                campaign_id=campaigns[0] if campaigns else "campaign_0",
                campaign_name="Campaign 0",
                ad_group_id="adgroup_0",
                ad_group_name="Ad Group 0",
                status=KeywordStatus.ENABLED,
                impressions=100,
                clicks=10,
                conversions=1,
                cost=10.0,
            )
            for i in range(min(num_keywords, 1000))  # Cap at 1000 for testing
        ]


@pytest.mark.asyncio
class TestSharedNegativeOptimizations:
    """Test performance optimizations for shared negative validator."""

    async def test_batch_api_calls_performance(self):
        """Test that batch API calls are faster than sequential calls."""
        # Create analyzer with mock data provider
        mock_provider = MockDataProvider(api_delay=0.05)  # Shorter delay for testing
        analyzer = SharedNegativeValidatorAnalyzer(mock_provider)

        # Run analysis
        start_time = time.time()
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            check_conflicts=True,  # Enable to test batch API calls
        )
        duration = time.time() - start_time

        # With 5 shared lists and batch processing, should complete quickly
        # Sequential would take 5 * 0.05 = 0.25s minimum, parallel should be faster
        print(f"Analysis took {duration:.3f}s")
        print(f"Max parallel calls: {mock_provider.max_parallel_calls}")
        print(f"Total API calls: {mock_provider.call_count}")

        # Verify parallelism occurred
        assert mock_provider.max_parallel_calls >= 2  # At least some parallelism
        assert mock_provider.call_count >= 5  # All shared lists fetched

        # Verify analysis completed successfully
        assert result.customer_id == "123456789"
        assert result.analysis_type == "shared_negative_validation"

    async def test_pagination_for_large_keyword_sets(self):
        """Test that pagination is used for large keyword sets."""
        mock_provider = MockDataProvider()

        # Track get_keywords calls to verify pagination
        original_get_keywords = mock_provider.get_keywords
        get_keywords_calls = []

        async def tracked_get_keywords(*args, **kwargs):
            get_keywords_calls.append(kwargs)
            return await original_get_keywords(*args, **kwargs)

        mock_provider.get_keywords = tracked_get_keywords

        # Create analyzer with specific page size
        analyzer = SharedNegativeValidatorAnalyzer(
            mock_provider,
            keywords_page_size=500,  # Small page size to verify it's used
        )

        # Run analysis
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            check_conflicts=True,  # Enable conflict checking to trigger keyword fetching
        )

        # Verify pagination was used
        assert len(get_keywords_calls) > 0
        for call in get_keywords_calls:
            assert "page_size" in call
            assert call["page_size"] == 500

    async def test_configurable_conflicts_limit(self):
        """Test that conflicts limit is configurable."""
        mock_provider = MockDataProvider()

        # Mock to return many conflicts
        async def mock_get_keywords(*args, **kwargs):
            # Return keywords that will conflict with negatives
            return [
                Keyword(
                    keyword_id=f"kw_{i}",
                    text=f"negative_list_0_{i}",  # Will conflict with negatives
                    match_type=KeywordMatchType.BROAD,
                    campaign_id="campaign_0",
                    campaign_name="Campaign 0",
                    ad_group_id="adgroup_0",
                    ad_group_name="Ad Group 0",
                    status=KeywordStatus.ENABLED,
                    impressions=100,
                    clicks=10,
                    conversions=1,
                    cost=10.0,
                )
                for i in range(20)  # 20 conflicts
            ]

        mock_provider.get_keywords = mock_get_keywords

        # Test with custom conflicts limit
        analyzer = SharedNegativeValidatorAnalyzer(
            mock_provider,
            max_conflicts_per_campaign=5,  # Custom limit
        )

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            check_conflicts=True,
        )

        # Check that conflicts are limited
        if result.raw_data["conflict_campaigns"]:
            for conflict in result.raw_data["conflict_campaigns"]:
                assert len(conflict["conflicts"]) <= 5
