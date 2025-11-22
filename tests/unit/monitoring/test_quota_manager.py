"""Tests for advanced quota manager and monitoring system."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav.core.exceptions import RateLimitError
from paidsearchnav.monitoring.quota_manager import (
    AdvancedQuotaManager,
    AnalyzerExecutionQueue,
    monitor_api_health,
)


class TestAdvancedQuotaManager:
    """Test cases for AdvancedQuotaManager."""

    @pytest.fixture
    def quota_manager(self):
        """Create quota manager for testing."""
        return AdvancedQuotaManager(
            daily_quota_limit=1000,
            rate_limit_per_minute=100,
            warning_threshold=0.7,
            critical_threshold=0.9,
        )

    @pytest.mark.asyncio
    async def test_quota_availability_normal_usage(self, quota_manager):
        """Test quota availability under normal usage."""
        # Should allow reasonable requests
        assert await quota_manager.check_quota_availability(50, "TestAnalyzer") is True

        # Reserve quota
        await quota_manager.reserve_quota(50, "TestAnalyzer")

        # Should still allow more requests
        assert await quota_manager.check_quota_availability(100, "TestAnalyzer") is True

    @pytest.mark.asyncio
    async def test_quota_exhaustion_prevention(self, quota_manager):
        """Test prevention of quota exhaustion."""
        # Use most of the quota
        await quota_manager.reserve_quota(950, "HighUsageAnalyzer")

        # Should reject large requests that would exceed quota
        assert (
            await quota_manager.check_quota_availability(100, "TestAnalyzer") is False
        )

        # Should still allow small requests
        assert await quota_manager.check_quota_availability(30, "TestAnalyzer") is True

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, quota_manager):
        """Test per-minute rate limiting."""
        # Use most of the per-minute quota
        await quota_manager.reserve_quota(80, "FastAnalyzer")

        # Should reject requests that would exceed minute limit
        assert await quota_manager.check_quota_availability(30, "TestAnalyzer") is False

        # Should allow smaller requests
        assert await quota_manager.check_quota_availability(15, "TestAnalyzer") is True

    @pytest.mark.asyncio
    async def test_critical_priority_override(self, quota_manager):
        """Test that critical priority can slightly exceed quota."""
        # Exhaust quota
        await quota_manager.reserve_quota(990, "NormalAnalyzer")

        # Normal priority should be rejected
        assert (
            await quota_manager.check_quota_availability(20, "TestAnalyzer", "normal")
            is False
        )

        # Critical priority should be allowed (slight overage)
        assert (
            await quota_manager.check_quota_availability(
                20, "CriticalAnalyzer", "critical"
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_predictive_analysis(self, quota_manager):
        """Test predictive quota exhaustion analysis."""
        # Simulate consistent usage pattern
        for i in range(10):
            await quota_manager.reserve_quota(50, f"Analyzer{i}")
            await asyncio.sleep(0.01)  # Small delay to spread usage

        prediction = await quota_manager.predict_quota_exhaustion()

        # Should predict exhaustion based on usage pattern
        if prediction:
            assert prediction > datetime.now()
            assert prediction < datetime.now() + timedelta(hours=24)

    @pytest.mark.asyncio
    async def test_analyzer_efficiency_tracking(self, quota_manager):
        """Test tracking of analyzer efficiency metrics."""
        # Simulate different analyzer usage patterns
        await quota_manager.reserve_quota(100, "EfficientAnalyzer")
        await quota_manager.reserve_quota(300, "InefficiientAnalyzer")
        await quota_manager.reserve_quota(50, "EfficientAnalyzer")

        metrics = await quota_manager.get_analyzer_efficiency_metrics()

        assert "EfficientAnalyzer" in metrics
        assert "InefficiientAnalyzer" in metrics

        # EfficientAnalyzer should have better efficiency
        efficient_quota = metrics["EfficientAnalyzer"]["total_quota_used"]
        inefficient_quota = metrics["InefficiientAnalyzer"]["total_quota_used"]

        assert efficient_quota < inefficient_quota


class TestAnalyzerExecutionQueue:
    """Test cases for AnalyzerExecutionQueue."""

    @pytest.fixture
    def quota_manager(self):
        return AdvancedQuotaManager(daily_quota_limit=1000, rate_limit_per_minute=100)

    @pytest.fixture
    def execution_queue(self, quota_manager):
        return AnalyzerExecutionQueue(quota_manager, max_concurrent=2)

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, execution_queue):
        """Test that high priority executions are processed first."""
        results = []

        async def mock_execution(name: str):
            await asyncio.sleep(0.1)
            results.append(name)
            return f"Result for {name}"

        # Queue multiple executions with different priorities
        await execution_queue.queue_analyzer_execution(
            "LowPriority", lambda: mock_execution("Low"), 10, priority=3
        )
        await execution_queue.queue_analyzer_execution(
            "HighPriority", lambda: mock_execution("High"), 10, priority=1
        )
        await execution_queue.queue_analyzer_execution(
            "MediumPriority", lambda: mock_execution("Medium"), 10, priority=2
        )

        # Wait for all executions to complete
        await asyncio.sleep(1.0)

        # High priority should be processed first
        assert results[0] == "High"

    @pytest.mark.asyncio
    async def test_concurrent_execution_limit(self, execution_queue):
        """Test that concurrent execution limit is respected."""
        execution_times = []

        async def timed_execution(name: str):
            start = datetime.now()
            await asyncio.sleep(0.2)
            end = datetime.now()
            execution_times.append((name, start, end))
            return f"Result for {name}"

        # Queue 4 executions (limit is 2)
        tasks = []
        for i in range(4):
            task = asyncio.create_task(
                execution_queue.queue_analyzer_execution(
                    f"Analyzer{i}", lambda name=f"A{i}": timed_execution(name), 10
                )
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Check that no more than 2 were running concurrently
        for time_point in execution_times:
            start_time = time_point[1]
            concurrent_count = sum(
                1
                for other_time in execution_times
                if other_time[1] <= start_time <= other_time[2]
            )
            assert concurrent_count <= 2

    @pytest.mark.asyncio
    async def test_quota_constraint_handling(self, execution_queue):
        """Test handling of quota constraints in queue."""
        # Exhaust most quota
        await execution_queue.quota_manager.reserve_quota(950, "PreviousAnalyzer")

        # Try to queue high-quota analyzer
        result = await execution_queue.queue_analyzer_execution(
            "HighQuotaAnalyzer",
            lambda: asyncio.sleep(0.1),
            100,  # Would exceed quota
            max_wait_time=1,  # Short wait time
        )

        # Should timeout due to quota constraints
        assert result is None


class TestAPIHealthMonitoring:
    """Test cases for API health monitoring."""

    @pytest.mark.asyncio
    async def test_successful_health_check(self):
        """Test API health check with successful response."""
        mock_client = Mock()
        mock_client.get_campaigns = AsyncMock(return_value=[Mock(), Mock()])

        health = await monitor_api_health(mock_client)

        assert health["api_reachable"] is True
        assert health["authentication_valid"] is True
        assert health["response_time"] is not None
        assert health["campaigns_accessible"] is True

    @pytest.mark.asyncio
    async def test_authentication_failure_detection(self):
        """Test detection of authentication failures."""
        mock_client = Mock()
        mock_client.get_campaigns = AsyncMock(
            side_effect=Exception("Authentication failed: Invalid credentials")
        )

        health = await monitor_api_health(mock_client)

        assert health["api_reachable"] is False
        assert health["authentication_valid"] is False
        assert "authentication" in health.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_quota_exhaustion_detection(self):
        """Test detection of quota exhaustion."""
        mock_client = Mock()
        mock_client.get_campaigns = AsyncMock(
            side_effect=RateLimitError("Quota exceeded")
        )

        health = await monitor_api_health(mock_client)

        assert health["quota_status"] == "exhausted"
        assert health["error_type"] == "RateLimitError"


class TestAlertSystem:
    """Test cases for quota alert system."""

    @pytest.mark.asyncio
    async def test_warning_threshold_alerts(self):
        """Test that warning alerts are generated at threshold."""
        quota_manager = AdvancedQuotaManager(
            daily_quota_limit=1000,
            warning_threshold=0.7,
        )

        # Use quota up to warning threshold
        await quota_manager.reserve_quota(700, "TestAnalyzer")

        # Next request should trigger warning
        await quota_manager.check_quota_availability(50, "TestAnalyzer")

        status = await quota_manager.get_quota_status()
        recent_alerts = status.get("recent_alerts", [])

        # Should have warning alert
        warning_alerts = [a for a in recent_alerts if a["severity"] == "warning"]
        assert len(warning_alerts) > 0

    @pytest.mark.asyncio
    async def test_critical_threshold_alerts(self):
        """Test that critical alerts are generated at threshold."""
        quota_manager = AdvancedQuotaManager(
            daily_quota_limit=1000,
            critical_threshold=0.9,
        )

        # Use quota up to critical threshold
        await quota_manager.reserve_quota(900, "TestAnalyzer")

        # Next request should trigger critical alert
        await quota_manager.check_quota_availability(50, "TestAnalyzer")

        status = await quota_manager.get_quota_status()
        recent_alerts = status.get("recent_alerts", [])

        # Should have critical alert
        critical_alerts = [a for a in recent_alerts if a["severity"] == "critical"]
        assert len(critical_alerts) > 0
