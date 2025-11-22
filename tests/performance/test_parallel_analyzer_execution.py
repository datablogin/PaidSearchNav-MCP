"""Performance tests for parallel analyzer execution."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav_mcp.scheduler.jobs import AuditJob
from paidsearchnav_mcp.scheduler.models import AuditJobConfig


class MockAnalyzer:
    """Mock analyzer that simulates work with configurable delay."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.call_count = 0

    async def analyze(self, **kwargs):
        """Simulate analysis work."""
        self.call_count += 1
        await asyncio.sleep(self.delay)
        return MagicMock(
            id=f"analysis_{self.call_count}",
            analyzer_name=kwargs.get("analyzer_name", "mock"),
            customer_id=kwargs["customer_id"],
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
        )


@pytest.mark.asyncio
class TestParallelAnalyzerExecution:
    """Test parallel execution of analyzers."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = MagicMock()
        settings.scheduler = MagicMock()
        settings.scheduler.max_parallel_analyzers = 3
        return settings

    @pytest.fixture
    def job_config(self):
        """Create test job configuration."""
        return AuditJobConfig(
            customer_id="123456789",
            analyzers=None,  # Run all analyzers
            generate_report=False,
        )

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = MagicMock()
        storage.save_analysis = AsyncMock()
        return storage

    async def test_parallel_execution_faster_than_sequential(
        self, settings, job_config, mock_storage
    ):
        """Test that parallel execution is faster than sequential."""
        # Create analyzers with delay
        analyzer_delay = 0.5
        mock_analyzers = {
            "keyword_match": MockAnalyzer(analyzer_delay),
            "search_terms": MockAnalyzer(analyzer_delay),
            "negative_conflicts": MockAnalyzer(analyzer_delay),
            "geo_performance": MockAnalyzer(analyzer_delay),
            "pmax": MockAnalyzer(analyzer_delay),
            "shared_negatives": MockAnalyzer(analyzer_delay),
        }

        # Mock the required components
        with (
            patch("paidsearchnav.scheduler.jobs.GoogleAdsClient") as mock_client_class,
            patch("paidsearchnav.scheduler.jobs.AnalysisRepository") as mock_repo_class,
            patch("paidsearchnav.scheduler.jobs.ReportGenerator") as mock_report_class,
        ):
            # Configure mocks
            mock_client_class.return_value = MagicMock()
            mock_repo_class.return_value = mock_storage
            mock_report_class.return_value = MagicMock()

            # Create job
            job = AuditJob(job_config, settings)

            # Override analyzers with our mock ones
            job.available_analyzers = mock_analyzers

            # Time parallel execution
            start_time = time.time()
            result = await job.execute({})
            parallel_duration = time.time() - start_time

            # With 6 analyzers at 0.5s each and max 3 parallel, should take ~1s
            # Sequential would take 3s
            assert parallel_duration < 2.0  # Allow some overhead
            assert result["analyzers_run"] == 6
            assert len(result["errors"]) == 0

    async def test_respects_max_parallel_analyzers(
        self, settings, job_config, mock_storage
    ):
        """Test that the max_parallel_analyzers setting is respected."""
        # Track concurrent executions
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def track_concurrent_analyze(**kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.1)  # Simulate work

            async with lock:
                current_concurrent -= 1

            return MagicMock(id="test_analysis")

        # Create analyzers that track concurrency
        mock_analyzers = {}
        for name in [
            "keyword_match",
            "search_terms",
            "negative_conflicts",
            "geo_performance",
            "pmax",
            "shared_negatives",
        ]:
            analyzer = MagicMock()
            analyzer.analyze = track_concurrent_analyze
            mock_analyzers[name] = analyzer

        # Test with max_parallel_analyzers = 2
        settings.scheduler.max_parallel_analyzers = 2

        # Mock the required components
        with (
            patch("paidsearchnav.scheduler.jobs.GoogleAdsClient") as mock_client_class,
            patch("paidsearchnav.scheduler.jobs.AnalysisRepository") as mock_repo_class,
            patch("paidsearchnav.scheduler.jobs.ReportGenerator") as mock_report_class,
        ):
            # Configure mocks
            mock_client_class.return_value = MagicMock()
            mock_repo_class.return_value = mock_storage
            mock_report_class.return_value = MagicMock()

            # Create job
            job = AuditJob(job_config, settings)
            job.available_analyzers = mock_analyzers

            await job.execute({})

            # Should never exceed 2 concurrent analyzers
            assert max_concurrent <= 2

    async def test_error_handling_in_parallel_execution(
        self, settings, job_config, mock_storage
    ):
        """Test that errors in one analyzer don't affect others."""
        # Create mix of successful and failing analyzers
        mock_analyzers = {
            "keyword_match": MockAnalyzer(0.1),
            "search_terms": MockAnalyzer(0.1),
            "negative_conflicts": MagicMock(),  # This one will fail
            "geo_performance": MockAnalyzer(0.1),
            "pmax": MagicMock(),  # This one will also fail
            "shared_negatives": MockAnalyzer(0.1),
        }

        # Configure failing analyzers
        mock_analyzers["negative_conflicts"].analyze = AsyncMock(
            side_effect=Exception("Negative conflicts error")
        )
        mock_analyzers["pmax"].analyze = AsyncMock(side_effect=Exception("PMax error"))

        # Mock the required components
        with (
            patch("paidsearchnav.scheduler.jobs.GoogleAdsClient") as mock_client_class,
            patch("paidsearchnav.scheduler.jobs.AnalysisRepository") as mock_repo_class,
            patch("paidsearchnav.scheduler.jobs.ReportGenerator") as mock_report_class,
        ):
            # Configure mocks
            mock_client_class.return_value = MagicMock()
            mock_repo_class.return_value = mock_storage
            mock_report_class.return_value = MagicMock()

            # Create job
            job = AuditJob(job_config, settings)
            job.available_analyzers = mock_analyzers

            result = await job.execute({})

            # Should have 4 successful and 2 errors
            assert result["analyzers_run"] == 4
            assert len(result["errors"]) == 2

            # Check error details
            error_analyzers = {e["analyzer"] for e in result["errors"]}
            assert "negative_conflicts" in error_analyzers
            assert "pmax" in error_analyzers

    async def test_performance_with_different_parallelism_levels(
        self, settings, job_config, mock_storage
    ):
        """Test performance with different parallelism levels."""
        analyzer_delay = 0.2
        mock_analyzers = {
            f"analyzer_{i}": MockAnalyzer(analyzer_delay) for i in range(10)
        }

        durations = {}

        for max_parallel in [1, 2, 5, 10]:
            settings.scheduler.max_parallel_analyzers = max_parallel

            # Mock the required components
            with (
                patch(
                    "paidsearchnav.scheduler.jobs.GoogleAdsClient"
                ) as mock_client_class,
                patch(
                    "paidsearchnav.scheduler.jobs.AnalysisRepository"
                ) as mock_repo_class,
                patch(
                    "paidsearchnav.scheduler.jobs.ReportGenerator"
                ) as mock_report_class,
            ):
                # Configure mocks
                mock_client_class.return_value = MagicMock()
                mock_repo_class.return_value = mock_storage
                mock_report_class.return_value = MagicMock()

                # Create job
                job = AuditJob(job_config, settings)
                job.available_analyzers = mock_analyzers.copy()

                start_time = time.time()
                await job.execute({})
                durations[max_parallel] = time.time() - start_time

        # Verify that higher parallelism results in faster execution
        assert durations[1] > durations[2]
        assert durations[2] > durations[5]
        assert durations[5] >= durations[10]  # May be equal due to having only 10 tasks

        # With 10 analyzers at 0.2s each:
        # - Sequential (1): ~2s
        # - Parallel (2): ~1s
        # - Parallel (5): ~0.4s
        # - Parallel (10): ~0.2s
        assert durations[1] > 1.5  # Allow overhead
        assert durations[10] < 0.5  # Should be much faster


@pytest.mark.asyncio
async def test_parallel_execution_memory_efficiency():
    """Test that parallel execution doesn't create excessive memory usage."""
    # This is more of a smoke test to ensure we're not creating
    # unnecessary copies of data or holding onto references
    settings = MagicMock()
    settings.scheduler = MagicMock()
    settings.scheduler.max_parallel_analyzers = 3

    job_config = AuditJobConfig(
        customer_id="123456789",
        analyzers=None,
        generate_report=False,
    )

    # Create analyzers that track their instances
    analyzer_instances = []

    class TrackingAnalyzer:
        def __init__(self):
            analyzer_instances.append(self)

        async def analyze(self, **kwargs):
            await asyncio.sleep(0.01)
            return MagicMock(id="test")

    mock_analyzers = {
        name: TrackingAnalyzer()
        for name in [
            "keyword_match",
            "search_terms",
            "negative_conflicts",
            "geo_performance",
            "pmax",
            "shared_negatives",
        ]
    }

    mock_storage = MagicMock()
    mock_storage.save_analysis = AsyncMock()

    # Mock the required components
    with (
        patch("paidsearchnav.scheduler.jobs.GoogleAdsClient") as mock_client_class,
        patch("paidsearchnav.scheduler.jobs.AnalysisRepository") as mock_repo_class,
        patch("paidsearchnav.scheduler.jobs.ReportGenerator") as mock_report_class,
    ):
        # Configure mocks
        mock_client_class.return_value = MagicMock()
        mock_repo_class.return_value = mock_storage
        mock_report_class.return_value = MagicMock()

        # Create job
        job = AuditJob(job_config, settings)
        job.available_analyzers = mock_analyzers

        await job.execute({})

        # Should only have created 6 analyzer instances
        assert len(analyzer_instances) == 6
