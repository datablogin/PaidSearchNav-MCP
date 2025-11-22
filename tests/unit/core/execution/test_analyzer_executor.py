"""Tests for analyzer executor error handling and reliability."""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.core.exceptions import APIError, RateLimitError
from paidsearchnav_mcp.core.execution.analyzer_executor import (
    AnalyzerExecutor,
    QuotaManager,
)
from paidsearchnav_mcp.core.interfaces import Analyzer
from paidsearchnav_mcp.models import (
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.models.analysis import AnalysisMetrics, AnalysisResult


class MockAnalyzer(Analyzer):
    """Mock analyzer for testing."""

    def __init__(
        self,
        name: str = "Test Analyzer",
        should_fail: bool = False,
        return_empty: bool = False,
    ):
        self.name = name
        self.should_fail = should_fail
        self.return_empty = return_empty
        self.call_count = 0

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return f"Mock {self.name} for testing"

    async def analyze(
        self, customer_id: str, start_date: datetime, end_date: datetime, **kwargs
    ) -> AnalysisResult:
        self.call_count += 1

        if self.should_fail:
            if self.call_count <= 2:  # Fail first 2 attempts
                raise APIError("Mock API error")

        if self.return_empty:
            return AnalysisResult(
                customer_id=customer_id,
                analysis_type="test",
                analyzer_name=self.name,
                start_date=start_date,
                end_date=end_date,
                recommendations=[],
                metrics=AnalysisMetrics(
                    total_keywords_analyzed=0,
                    total_search_terms_analyzed=0,
                    issues_found=0,
                    critical_issues=0,
                    potential_cost_savings=0.0,
                    potential_conversion_increase=0.0,
                ),
                raw_data={},
            )

        # Return successful result
        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="test",
            analyzer_name=self.name,
            start_date=start_date,
            end_date=end_date,
            recommendations=[
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.HIGH,
                    title="Test Recommendation",
                    description="This is a test recommendation from mock analyzer",
                )
            ],
            metrics=AnalysisMetrics(
                total_keywords_analyzed=100,
                total_search_terms_analyzed=500,
                issues_found=1,
                critical_issues=0,
                potential_cost_savings=250.0,
                potential_conversion_increase=5.0,
            ),
            raw_data={"test_data": "mock_result"},
        )


class TestAnalyzerExecutor:
    """Test cases for AnalyzerExecutor."""

    @pytest.fixture
    def executor(self):
        """Create executor instance for testing."""
        return AnalyzerExecutor(
            max_retries=3,
            retry_delay_base=0.1,  # Fast retries for testing
            min_output_size=50,
            timeout_seconds=5,
        )

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_successful_execution(self, executor, temp_output_dir):
        """Test successful analyzer execution."""
        analyzer = MockAnalyzer("Success Analyzer")
        output_file = temp_output_dir / "test_output.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        assert result.success is True
        assert result.analyzer_name == "Success Analyzer"
        assert result.customer_id == "123-456-789"
        assert result.output_file == output_file
        assert output_file.exists()
        assert output_file.stat().st_size > 50

        # Validate output file content
        with open(output_file, "r") as f:
            data = json.load(f)

        assert data["execution_metadata"]["success"] is True
        assert data["analysis_metadata"]["recommendations_count"] == 1
        assert len(data["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_retry_logic_with_eventual_success(self, executor, temp_output_dir):
        """Test retry logic when analyzer fails initially but succeeds later."""
        analyzer = MockAnalyzer("Retry Analyzer", should_fail=True)
        output_file = temp_output_dir / "retry_output.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        # Should succeed after retries
        assert result.success is True
        assert analyzer.call_count == 3  # Failed twice, succeeded on third attempt
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_empty_result_handling(self, executor, temp_output_dir):
        """Test handling of empty analyzer results."""
        analyzer = MockAnalyzer("Empty Analyzer", return_empty=True)
        output_file = temp_output_dir / "empty_output.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        # Should fail due to empty result
        assert result.success is False
        assert "empty or invalid result" in result.error
        assert (
            output_file.exists() is False
        )  # No file should be created for empty results

        # Error file should be created
        error_file = output_file.with_name(
            f"{output_file.stem}_ERROR{output_file.suffix}"
        )
        assert error_file.exists()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, temp_output_dir):
        """Test timeout handling during analyzer execution."""
        # Create executor with very short timeout
        executor = AnalyzerExecutor(timeout_seconds=0.1, max_retries=1)

        # Create analyzer that takes too long
        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(1.0)  # Sleep longer than timeout
            return Mock()

        analyzer = Mock()
        analyzer.get_name.return_value = "Slow Analyzer"
        analyzer.analyze = slow_analyze

        output_file = temp_output_dir / "timeout_output.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        assert result.success is False
        assert "timed out" in result.error
        assert result.error_file is not None

    @pytest.mark.asyncio
    async def test_file_validation_prevents_zero_length_files(
        self, executor, temp_output_dir
    ):
        """Test that file validation prevents zero-length files."""
        # Mock analyzer that returns result but causes file write to fail
        analyzer = MockAnalyzer("File Validation Test")
        output_file = temp_output_dir / "validation_test.json"

        # Patch json.dump to write empty content
        with patch("json.dump") as mock_dump:
            mock_dump.side_effect = lambda data, f, **kwargs: None  # Write nothing

            result = await executor.execute_analyzer(
                analyzer=analyzer,
                customer_id="123-456-789",
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 31),
                output_path=output_file,
            )

        # Should fail due to file validation
        assert result.success is False
        assert "too small" in result.error
        assert output_file.exists() is False  # Zero-length file should be cleaned up

    @pytest.mark.asyncio
    async def test_graceful_degradation_fallback(self, temp_output_dir):
        """Test graceful degradation with fallback data."""
        # Create executor with fallback enabled
        executor = AnalyzerExecutor(max_retries=1, enable_fallback=True)

        # Create a cache file for fallback
        cache_dir = Path("cache/analyzer_fallbacks")
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = cache_dir / "test_analyzer_123-456-789_20250101_120000.json"
        cache_data = {
            "recommendations": [
                {
                    "type": "OPTIMIZE_KEYWORDS",
                    "priority": "HIGH",
                    "title": "Cached Recommendation",
                    "description": "This is from cached data",
                }
            ],
            "metrics": {
                "total_keywords_analyzed": 50,
                "total_search_terms_analyzed": 200,
            },
            "timestamp": datetime.now().isoformat(),
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        try:
            # Create failing analyzer
            class FailingAnalyzer(Analyzer):
                def get_name(self):
                    return "Test Analyzer"

                def get_description(self):
                    return "Always fails"

                async def analyze(self, *args, **kwargs):
                    raise APIError("Persistent API failure")

            analyzer = FailingAnalyzer()
            output_file = temp_output_dir / "fallback_test.json"

            result = await executor.execute_analyzer(
                analyzer=analyzer,
                customer_id="123-456-789",
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 31),
                output_path=output_file,
            )

            # Should succeed with fallback data
            assert result.success is True
            assert output_file.exists()

            # Verify fallback content
            with open(output_file, "r") as f:
                data = json.load(f)

            assert data["execution_metadata"]["success"] is True
            assert len(data["recommendations"]) >= 1  # Should have fallback disclaimer

        finally:
            # Cleanup
            if cache_file.exists():
                cache_file.unlink()


class TestQuotaManager:
    """Test cases for QuotaManager."""

    @pytest.fixture
    def quota_manager(self):
        """Create quota manager for testing."""
        return QuotaManager(
            daily_quota_limit=1000,
            rate_limit_per_minute=50,
        )

    @pytest.mark.asyncio
    async def test_quota_availability_check(self, quota_manager):
        """Test quota availability checking."""
        # Should allow calls within limits
        assert await quota_manager.check_quota_available(100) is True

        # Should reject calls that exceed daily limit
        assert await quota_manager.check_quota_available(1500) is False

        # Reserve some quota first
        await quota_manager.reserve_quota(80)

        # Should reject calls that exceed minute limit (80 + 30 > 50 per minute)
        assert await quota_manager.check_quota_available(30) is False

    @pytest.mark.asyncio
    async def test_quota_reservation(self, quota_manager):
        """Test quota reservation tracking."""
        await quota_manager.reserve_quota(100)

        status = quota_manager.get_quota_status()
        assert status["daily_usage"] == 100
        assert status["daily_remaining"] == 900
        assert status["quota_percentage"] == 10.0

    @pytest.mark.asyncio
    async def test_quota_reset(self, quota_manager):
        """Test quota reset functionality."""
        # Use some quota
        await quota_manager.reserve_quota(500)

        # Force reset by changing the internal date
        quota_manager._last_reset = (datetime.now() - timedelta(days=1)).date()

        # Check availability should trigger reset
        await quota_manager.check_quota_available(100)

        status = quota_manager.get_quota_status()
        assert status["daily_usage"] == 0  # Should be reset


class TestErrorScenarios:
    """Test various error scenarios and their handling."""

    @pytest.fixture
    def executor(self):
        return AnalyzerExecutor(max_retries=2, retry_delay_base=0.1)

    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_api_error_retry_behavior(self, executor, temp_output_dir):
        """Test retry behavior for API errors."""
        call_count = 0

        async def failing_analyze(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:  # Fail first attempt
                raise APIError("Temporary API failure")

            # Succeed on second attempt
            return AnalysisResult(
                customer_id="123",
                analysis_type="test",
                analyzer_name="Test",
                start_date=datetime.now(),
                end_date=datetime.now(),
                recommendations=[],
                metrics=AnalysisMetrics(
                    total_keywords_analyzed=1,
                    total_search_terms_analyzed=1,
                    issues_found=0,
                    critical_issues=0,
                    potential_cost_savings=0.0,
                    potential_conversion_increase=0.0,
                ),
                raw_data={"test": "data"},
            )

        analyzer = Mock()
        analyzer.get_name.return_value = "Retry Test Analyzer"
        analyzer.analyze = failing_analyze

        output_file = temp_output_dir / "retry_test.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        assert result.success is True
        assert call_count == 2  # Should have retried once
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, executor, temp_output_dir):
        """Test handling of rate limit errors."""

        async def rate_limited_analyze(*args, **kwargs):
            raise RateLimitError("Rate limit exceeded")

        analyzer = Mock()
        analyzer.get_name.return_value = "Rate Limited Analyzer"
        analyzer.analyze = rate_limited_analyze

        output_file = temp_output_dir / "rate_limit_test.json"

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        assert result.success is False
        assert "Rate limit" in result.error
        assert result.error_file is not None
        assert result.error_file.exists()

    @pytest.mark.asyncio
    async def test_multiple_analyzer_execution(self, executor, temp_output_dir):
        """Test execution of multiple analyzers with mixed success/failure."""
        analyzers = [
            MockAnalyzer("Success Analyzer 1"),
            MockAnalyzer("Failing Analyzer", should_fail=True),
            MockAnalyzer("Success Analyzer 2"),
        ]

        results = await executor.execute_multiple_analyzers(
            analyzers=analyzers,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_dir=temp_output_dir,
            concurrent_limit=2,
        )

        assert len(results) == 3

        # Check individual results
        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)

        assert success_count == 2  # Two should succeed
        assert failure_count == 1  # One should fail

        # Check that files exist for successful ones
        successful_files = [
            r.output_file for r in results if r.success and r.output_file
        ]
        assert len(successful_files) == 2

        for file_path in successful_files:
            assert file_path.exists()
            assert file_path.stat().st_size > 50

    @pytest.mark.asyncio
    async def test_corrupted_output_detection(self, executor, temp_output_dir):
        """Test detection and handling of corrupted output files."""
        analyzer = MockAnalyzer("Corruption Test")
        output_file = temp_output_dir / "corruption_test.json"

        # Patch file writing to create invalid JSON
        original_write_and_validate = executor._write_and_validate_output

        async def corrupted_write(*args, **kwargs):
            # Write invalid JSON
            with open(output_file, "w") as f:
                f.write('{"invalid": json}')  # Missing quotes around 'json'

        executor._write_and_validate_output = corrupted_write

        result = await executor.execute_analyzer(
            analyzer=analyzer,
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            output_path=output_file,
        )

        assert result.success is False
        assert "invalid JSON" in result.error
        assert result.error_file is not None

    @pytest.mark.asyncio
    async def test_concurrent_execution_isolation(self, executor, temp_output_dir):
        """Test that concurrent executions don't interfere with each other."""
        # Create analyzers with different delays
        slow_analyzer = MockAnalyzer("Slow Analyzer")
        fast_analyzer = MockAnalyzer("Fast Analyzer")

        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(0.5)
            return fast_analyzer.analyze(*args, **kwargs)

        slow_analyzer.analyze = slow_analyze

        # Execute concurrently
        tasks = [
            executor.execute_analyzer(
                analyzer=slow_analyzer,
                customer_id="123-456-789",
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 31),
                output_path=temp_output_dir / "slow_output.json",
            ),
            executor.execute_analyzer(
                analyzer=fast_analyzer,
                customer_id="123-456-789",
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 31),
                output_path=temp_output_dir / "fast_output.json",
            ),
        ]

        results = await asyncio.gather(*tasks)

        # Both should succeed
        assert all(r.success for r in results)

        # Fast analyzer should complete first (shorter execution time)
        fast_result = next(r for r in results if "Fast" in r.analyzer_name)
        slow_result = next(r for r in results if "Slow" in r.analyzer_name)

        assert fast_result.execution_time < slow_result.execution_time


class TestErrorRecovery:
    """Test error recovery and resilience features."""

    @pytest.mark.asyncio
    async def test_fallback_data_usage(self):
        """Test usage of fallback data when analyzer fails."""
        import tempfile

        from paidsearchnav.core.execution.fallback_system import FallbackDataSource

        with tempfile.TemporaryDirectory() as temp_dir:
            fallback_source = FallbackDataSource(cache_directory=temp_dir)

            # Create mock cache data
            cache_data = {
                "recommendations": [
                    {
                        "type": "OPTIMIZE_KEYWORDS",
                        "priority": "MEDIUM",
                        "title": "Cached Recommendation",
                        "description": "From cache",
                    }
                ],
                "metrics": {"total_keywords_analyzed": 100},
                "timestamp": datetime.now().isoformat(),
            }

            # Save cache data
            await fallback_source.cache_successful_result(
                "Test Analyzer", "123-456-789", cache_data
            )

            # Test fallback retrieval
            fallback_result = await fallback_source.get_fallback_result(
                "Test Analyzer", "123-456-789", datetime.now(), datetime.now()
            )

            assert fallback_result is not None
            assert (
                len(fallback_result.recommendations) >= 1
            )  # Should have fallback disclaimer + cached rec
            assert fallback_result.raw_data.get("fallback_notice") is not None

    @pytest.mark.asyncio
    async def test_partial_result_creation(self):
        """Test creation of partial results when analysis is interrupted."""
        from paidsearchnav.core.execution.fallback_system import PartialResultHandler

        handler = PartialResultHandler()

        partial_data = {
            "keywords_processed": 50,
            "search_terms_processed": 200,
            "completion_percentage": 75,
            "high_cost_keywords": ["expensive keyword 1", "expensive keyword 2"],
        }

        result = handler.create_partial_result(
            analyzer_name="Partial Test Analyzer",
            customer_id="123-456-789",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            partial_data=partial_data,
            error_context="Connection lost during analysis",
        )

        assert result.analysis_type == "partial"
        assert len(result.recommendations) >= 2  # Partial notice + high cost keywords
        assert result.metrics.custom_metrics["is_partial"] is True
        assert result.raw_data["completion_percentage"] == 75
