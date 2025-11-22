"""Tests for retry logic."""

import pytest

from paidsearchnav_mcp.exports.retry import RetryPolicy, exponential_backoff_with_jitter


class TestExponentialBackoff:
    """Test exponential backoff function."""

    def test_exponential_backoff_basic(self):
        """Test basic exponential backoff calculation."""
        # First attempt (0) should have base delay
        delay = exponential_backoff_with_jitter(
            0, base_delay=1.0, max_delay=60.0, jitter=0.0
        )
        assert delay == 1.0

        # Second attempt should double
        delay = exponential_backoff_with_jitter(
            1, base_delay=1.0, max_delay=60.0, jitter=0.0
        )
        assert delay == 2.0

        # Third attempt should double again
        delay = exponential_backoff_with_jitter(
            2, base_delay=1.0, max_delay=60.0, jitter=0.0
        )
        assert delay == 4.0

    def test_exponential_backoff_max_delay(self):
        """Test that backoff respects max delay."""
        # Large attempt number should cap at max_delay
        delay = exponential_backoff_with_jitter(
            10, base_delay=1.0, max_delay=10.0, jitter=0.0
        )
        assert delay == 10.0

    def test_exponential_backoff_with_jitter(self):
        """Test backoff with jitter."""
        # With jitter, delay should vary
        delays = []
        for _ in range(10):
            delay = exponential_backoff_with_jitter(
                2, base_delay=1.0, max_delay=60.0, jitter=0.1
            )
            delays.append(delay)

        # Base delay for attempt 2 is 4.0, with 10% jitter range is 3.6-4.4
        assert all(3.6 <= d <= 4.4 for d in delays)
        # Should have some variation
        assert len(set(delays)) > 1


class TestRetryPolicy:
    """Test RetryPolicy class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful execution without retry."""

        async def success_func():
            return "success"

        policy = RetryPolicy(max_attempts=3)
        result = await policy.execute(success_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on failure."""
        attempt_count = 0

        async def failing_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Test error")
            return "success"

        policy = RetryPolicy(
            max_attempts=3,
            backoff_func=lambda x: 0.01,  # Fast backoff for testing
            retriable_exceptions=(ValueError,),
        )

        result = await policy.execute(failing_func)

        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test max attempts exceeded."""

        async def always_failing():
            raise ValueError("Always fails")

        policy = RetryPolicy(
            max_attempts=2,
            backoff_func=lambda x: 0.01,
            retriable_exceptions=(ValueError,),
        )

        with pytest.raises(ValueError) as exc_info:
            await policy.execute(always_failing)

        assert "Always fails" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_retriable_exception(self):
        """Test non-retriable exception is raised immediately."""
        attempt_count = 0

        async def func_with_non_retriable():
            nonlocal attempt_count
            attempt_count += 1
            raise TypeError("Non-retriable error")

        policy = RetryPolicy(
            max_attempts=3,
            retriable_exceptions=(ValueError,),  # Only ValueError is retriable
        )

        with pytest.raises(TypeError) as exc_info:
            await policy.execute(func_with_non_retriable)

        assert "Non-retriable error" in str(exc_info.value)
        assert attempt_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_sync_function(self):
        """Test retry with synchronous function."""
        attempt_count = 0

        def sync_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Test error")
            return "sync success"

        policy = RetryPolicy(
            max_attempts=3,
            backoff_func=lambda x: 0.01,
            retriable_exceptions=(ValueError,),
        )

        result = await policy.execute(sync_func)

        assert result == "sync success"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        retry_calls = []

        def on_retry(exception, attempt):
            retry_calls.append((str(exception), attempt))

        async def failing_func():
            raise ValueError("Test error")

        policy = RetryPolicy(
            max_attempts=3,
            backoff_func=lambda x: 0.01,
            retriable_exceptions=(ValueError,),
            on_retry=on_retry,
        )

        with pytest.raises(ValueError):
            await policy.execute(failing_func)

        # Should have been called twice (before 2nd and 3rd attempts)
        assert len(retry_calls) == 2
        assert retry_calls[0] == ("Test error", 1)
        assert retry_calls[1] == ("Test error", 2)

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Test that backoff delays are applied."""
        import time

        attempt_times = []

        async def func_with_timing():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise ValueError("Need more attempts")
            return "done"

        # Use fixed delays for predictable testing
        def fixed_backoff(attempt):
            return 0.1 * (attempt + 1)  # 0.1s, 0.2s, etc.

        policy = RetryPolicy(
            max_attempts=3,
            backoff_func=fixed_backoff,
            retriable_exceptions=(ValueError,),
        )

        result = await policy.execute(func_with_timing)

        assert result == "done"
        assert len(attempt_times) == 3

        # Check delays between attempts (with some tolerance)
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]

        assert 0.08 <= delay1 <= 0.12  # ~0.1s
        assert 0.18 <= delay2 <= 0.22  # ~0.2s

    @pytest.mark.asyncio
    async def test_multiple_exception_types(self):
        """Test multiple retriable exception types."""
        attempt_count = 0

        async def func_with_different_errors():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count == 1:
                raise ValueError("First error")
            elif attempt_count == 2:
                raise RuntimeError("Second error")
            return "success"

        policy = RetryPolicy(
            max_attempts=3,
            backoff_func=lambda x: 0.01,
            retriable_exceptions=(ValueError, RuntimeError),
        )

        result = await policy.execute(func_with_different_errors)

        assert result == "success"
        assert attempt_count == 3
