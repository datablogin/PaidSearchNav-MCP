"""Tests for monitoring utilities."""

import asyncio
import time
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.logging.monitoring import (
    MetricsCollector,
    gauge,
    increment,
    timed,
    timer,
    timing,
    track_job,
)


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_increment(self):
        """Test incrementing counter metrics."""
        collector = MetricsCollector()

        collector.increment("requests", 1)
        collector.increment("requests", 2)

        metrics = collector.get_metrics()
        assert metrics["requests"] == 3

    def test_increment_with_tags(self):
        """Test incrementing with tags."""
        collector = MetricsCollector()

        collector.increment("requests", 1, tags={"endpoint": "/api/v1"})
        collector.increment("requests", 1, tags={"endpoint": "/api/v2"})
        collector.increment("requests", 2, tags={"endpoint": "/api/v1"})

        metrics = collector.get_metrics()
        assert metrics["requests,endpoint=/api/v1"] == 3
        assert metrics["requests,endpoint=/api/v2"] == 1

    def test_gauge(self):
        """Test setting gauge metrics."""
        collector = MetricsCollector()

        collector.gauge("memory_usage", 75.5)
        collector.gauge("memory_usage", 80.2)

        metrics = collector.get_metrics()
        assert metrics["memory_usage"] == 80.2

    def test_gauge_with_tags(self):
        """Test setting gauge with tags."""
        collector = MetricsCollector()

        collector.gauge("cpu_usage", 50.0, tags={"core": "0"})
        collector.gauge("cpu_usage", 60.0, tags={"core": "1"})

        metrics = collector.get_metrics()
        assert metrics["cpu_usage,core=0"] == 50.0
        assert metrics["cpu_usage,core=1"] == 60.0

    def test_reset(self):
        """Test resetting metrics."""
        collector = MetricsCollector()

        collector.increment("test", 5)
        collector.gauge("gauge", 10.0)
        assert len(collector.get_metrics()) == 2

        collector.reset()
        assert len(collector.get_metrics()) == 0


class TestModuleFunctions:
    """Test module-level metric functions."""

    @patch("paidsearchnav.logging.monitoring._metrics")
    def test_increment_function(self, mock_metrics):
        """Test increment function."""
        increment("test.metric", 5, tags={"type": "test"})
        mock_metrics.increment.assert_called_once_with(
            "test.metric", 5, {"type": "test"}
        )

    @patch("paidsearchnav.logging.monitoring._metrics")
    def test_gauge_function(self, mock_metrics):
        """Test gauge function."""
        gauge("test.gauge", 42.0, tags={"env": "prod"})
        mock_metrics.gauge.assert_called_once_with("test.gauge", 42.0, {"env": "prod"})

    @patch("paidsearchnav.logging.monitoring._metrics")
    def test_timing_function(self, mock_metrics):
        """Test timing function."""
        timing("api.latency", 125.5, tags={"endpoint": "/users"})
        mock_metrics.timing.assert_called_once_with(
            "api.latency", 125.5, {"endpoint": "/users"}
        )


class TestTimer:
    """Test timer context manager."""

    @patch("paidsearchnav.logging.monitoring.timing")
    def test_timer_context_manager(self, mock_timing):
        """Test timer context manager."""
        with timer("operation.duration"):
            time.sleep(0.01)  # Sleep for 10ms

        # Check timing was called
        mock_timing.assert_called_once()
        args = mock_timing.call_args[0]
        assert args[0] == "operation.duration"
        assert args[1] >= 10  # At least 10ms

    @patch("paidsearchnav.logging.monitoring.timing")
    def test_timer_with_tags(self, mock_timing):
        """Test timer with tags."""
        with timer("db.query", tags={"table": "users"}):
            pass

        mock_timing.assert_called_once()
        assert mock_timing.call_args[0][0] == "db.query"
        assert mock_timing.call_args[0][2] == {"table": "users"}

    @patch("paidsearchnav.logging.monitoring.timing")
    def test_timer_with_exception(self, mock_timing):
        """Test timer handles exceptions."""
        try:
            with timer("failing.operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Timing should still be recorded
        mock_timing.assert_called_once()


class TestTimedDecorator:
    """Test timed decorator."""

    @patch("paidsearchnav.logging.monitoring.timing")
    def test_timed_decorator(self, mock_timing):
        """Test timed decorator."""

        @timed("custom.metric")
        def test_function():
            time.sleep(0.01)
            return "result"

        result = test_function()

        assert result == "result"
        mock_timing.assert_called_once()
        assert mock_timing.call_args[0][0] == "custom.metric"
        assert mock_timing.call_args[0][1] >= 10

    @patch("paidsearchnav.logging.monitoring.timing")
    def test_timed_decorator_default_name(self, mock_timing):
        """Test timed decorator with default metric name."""

        @timed()
        def my_function():
            return "result"

        my_function()

        mock_timing.assert_called_once()
        assert mock_timing.call_args[0][0] == "function.my_function"


class TestTrackJob:
    """Test track_job decorator."""

    @pytest.mark.asyncio
    @patch("paidsearchnav.logging.monitoring.increment")
    @patch("paidsearchnav.logging.monitoring.timing")
    @patch("paidsearchnav.logging.monitoring.logger")
    async def test_track_job_async_success(
        self, mock_logger, mock_timing, mock_increment
    ):
        """Test tracking async job success."""

        @track_job("test_job")
        async def async_job(customer_id: str, job_id: str):
            await asyncio.sleep(0.01)
            return "success"

        result = await async_job(customer_id="123", job_id="abc")

        assert result == "success"

        # Check metrics
        assert mock_increment.call_count == 2
        mock_increment.assert_any_call("job.started", tags={"type": "test_job"})
        mock_increment.assert_any_call("job.completed", tags={"type": "test_job"})

        # Check timing
        mock_timing.assert_called_once()
        assert mock_timing.call_args[0][0] == "job.duration"

        # Check logging
        assert mock_logger.info.call_count == 2

    @pytest.mark.asyncio
    @patch("paidsearchnav.logging.monitoring.increment")
    @patch("paidsearchnav.logging.monitoring.logger")
    async def test_track_job_async_failure(self, mock_logger, mock_increment):
        """Test tracking async job failure."""

        @track_job("failing_job")
        async def async_job(customer_id: str, job_id: str):
            raise ValueError("Job failed")

        with pytest.raises(ValueError):
            await async_job(customer_id="123", job_id="abc")

        # Check metrics
        assert mock_increment.call_count == 2
        mock_increment.assert_any_call("job.started", tags={"type": "failing_job"})
        mock_increment.assert_any_call("job.failed", tags={"type": "failing_job"})

        # Check error logging
        mock_logger.error.assert_called_once()

    @patch("paidsearchnav.logging.monitoring.increment")
    @patch("paidsearchnav.logging.monitoring.timing")
    @patch("paidsearchnav.logging.monitoring.logger")
    def test_track_job_sync_success(self, mock_logger, mock_timing, mock_increment):
        """Test tracking sync job success."""

        @track_job("sync_job")
        def sync_job(customer_id: str, job_id: str):
            time.sleep(0.01)
            return "success"

        result = sync_job(customer_id="123", job_id="abc")

        assert result == "success"

        # Check metrics
        assert mock_increment.call_count == 2
        mock_increment.assert_any_call("job.started", tags={"type": "sync_job"})
        mock_increment.assert_any_call("job.completed", tags={"type": "sync_job"})

    @patch("paidsearchnav.logging.monitoring.increment")
    @patch("paidsearchnav.logging.monitoring.logger")
    def test_track_job_sync_failure(self, mock_logger, mock_increment):
        """Test tracking sync job failure."""

        @track_job("failing_sync_job")
        def sync_job(customer_id: str, job_id: str):
            raise RuntimeError("Sync job failed")

        with pytest.raises(RuntimeError):
            sync_job(customer_id="123", job_id="abc")

        # Check failure metrics
        mock_increment.assert_any_call("job.failed", tags={"type": "failing_sync_job"})
