"""Benchmark to demonstrate customer access control query optimization performance."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav_mcp.storage.api_repository import APIRepository
from paidsearchnav_mcp.storage.models import UserType


class TestCustomerAccessPerformance:
    """Performance benchmarks for customer access control optimization."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository for testing."""
        from pathlib import Path

        from paidsearchnav.core.config import Settings

        # Create a mock settings object with all required attributes
        mock_settings = MagicMock(spec=Settings)
        mock_settings.environment = "test"
        mock_settings.database_url = "sqlite:///:memory:"
        mock_settings.data_dir = Path("/tmp")
        mock_settings.debug = False
        # Add logging attribute to avoid AttributeError
        mock_settings.logging = MagicMock()

        repo = APIRepository(mock_settings)
        repo.AsyncSessionLocal = MagicMock()
        return repo

    @pytest.mark.asyncio
    async def test_performance_single_query_vs_multiple(self, mock_repository):
        """Benchmark the performance improvement of single query vs multiple queries."""
        # Number of iterations for the benchmark
        iterations = 1000

        # Mock session
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Simulate query latency (5ms per query)
        async def simulate_query_latency(*args, **kwargs):
            await asyncio.sleep(0.005)  # 5ms simulated database latency
            result = MagicMock()
            # Return appropriate result based on query count
            if mock_session.execute.call_count == 1:
                # First query - user type
                result.fetchone.return_value = (UserType.AGENCY.value,)
            elif mock_session.execute.call_count == 2:
                # Second query - customer owner
                result.fetchone.return_value = ("client-user-789",)
            else:
                # Third query - customer access
                result.fetchone.return_value = ("read",)
            return result

        # Test OLD implementation (3 queries for agency user with granted access)
        print("\n=== Simulating OLD implementation (3 sequential queries) ===")
        mock_session.execute.side_effect = simulate_query_latency
        mock_session.execute.call_count = 0

        start_time = time.time()
        for _ in range(iterations):
            # Simulate 3 sequential queries
            await mock_session.execute("SELECT user_type...")
            await mock_session.execute("SELECT customer owner...")
            await mock_session.execute("SELECT customer access...")
            mock_session.execute.call_count = 0  # Reset for consistent behavior

        old_duration = time.time() - start_time
        old_avg_ms = (old_duration / iterations) * 1000

        print(f"Total time for {iterations} iterations: {old_duration:.2f}s")
        print(f"Average time per access check: {old_avg_ms:.2f}ms")
        print("Queries per access check: 3")

        # Test NEW implementation (1 query with JOINs)
        print("\n=== Simulating NEW implementation (1 optimized query) ===")

        # Reset mock
        mock_session.execute.reset_mock()
        mock_session.execute.side_effect = None

        # Mock single JOIN query result
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.AGENCY.value,  # user_type
            "client-user-789",  # owner_id
            "read",  # access_level
        )

        async def simulate_single_query(*args, **kwargs):
            await asyncio.sleep(0.005)  # Same 5ms latency per query
            return query_result

        mock_session.execute.side_effect = simulate_single_query

        start_time = time.time()
        for _ in range(iterations):
            result = await mock_repository.user_has_customer_access(
                "agency-user-123", "customer-456"
            )
            assert result is True

        new_duration = time.time() - start_time
        new_avg_ms = (new_duration / iterations) * 1000

        print(f"Total time for {iterations} iterations: {new_duration:.2f}s")
        print(f"Average time per access check: {new_avg_ms:.2f}ms")
        print("Queries per access check: 1")

        # Calculate improvement
        improvement_factor = old_duration / new_duration
        time_saved_ms = old_avg_ms - new_avg_ms

        print("\n=== Performance Improvement ===")
        print(f"Speed improvement: {improvement_factor:.1f}x faster")
        print(f"Time saved per check: {time_saved_ms:.2f}ms")
        print(
            f"Percentage improvement: {((old_duration - new_duration) / old_duration * 100):.1f}%"
        )

        # For high-volume scenarios
        daily_checks = 100000  # Example: 100k access checks per day
        daily_time_saved = (
            (time_saved_ms * daily_checks) / 1000 / 60
        )  # Convert to minutes
        print(f"\nFor {daily_checks:,} daily access checks:")
        print(f"Time saved per day: {daily_time_saved:.1f} minutes")

        # Assert significant improvement
        assert improvement_factor >= 2.5, (
            f"Expected at least 2.5x improvement, got {improvement_factor:.1f}x"
        )
