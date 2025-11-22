"""Tests for retry logic."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav_mcp.scheduler.interfaces import JobStatus, JobType
from paidsearchnav_mcp.scheduler.models import JobExecution
from paidsearchnav_mcp.scheduler.retry import (
    RetryableJob,
    RetryPolicy,
    create_default_retry_policy,
)


class TestRetryPolicy:
    """Test RetryPolicy class."""

    def test_get_delay_exponential(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )

        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(3) == 8.0

    def test_get_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        policy = RetryPolicy(
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )

        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(3) == 5.0  # Capped
        assert policy.get_delay(10) == 5.0  # Still capped

    def test_get_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        policy = RetryPolicy(
            initial_delay=10.0,
            jitter=True,
        )

        # With jitter, delay should be between base and base * 1.25
        delay = policy.get_delay(0)
        assert 10.0 <= delay <= 12.5

    def test_should_retry_attempt_limit(self):
        """Test retry decision based on attempt limit."""
        policy = RetryPolicy(max_attempts=3)
        error = ConnectionError("Test error")

        assert policy.should_retry(0, error) is True
        assert policy.should_retry(1, error) is True
        assert policy.should_retry(2, error) is True
        assert policy.should_retry(3, error) is False  # Max attempts reached

    def test_is_retryable_error(self):
        """Test retryable error detection."""
        policy = RetryPolicy()

        # Retryable errors
        assert policy.is_retryable_error(ConnectionError("Connection failed"))
        assert policy.is_retryable_error(TimeoutError("Request timeout"))

        # Rate limit error (mock with status_code)
        rate_limit_error = Mock(status_code=429)
        assert policy.is_retryable_error(rate_limit_error)

        # Google Ads errors
        assert policy.is_retryable_error(Exception("RESOURCE_TEMPORARILY_UNAVAILABLE"))
        assert policy.is_retryable_error(Exception("Quota exceeded"))
        assert policy.is_retryable_error(Exception("Internal error"))

        # Non-retryable errors
        assert not policy.is_retryable_error(ValueError("Invalid input"))
        assert not policy.is_retryable_error(KeyError("Missing key"))


class TestRetryableJob:
    """Test RetryableJob class."""

    @pytest.mark.asyncio
    async def test_execute_success_first_try(self):
        """Test successful execution on first try."""
        # Mock job function
        job_func = AsyncMock(return_value={"status": "success"})

        # Create retryable job
        policy = RetryPolicy(max_attempts=3)
        retryable_job = RetryableJob(job_func, policy)

        # Create execution
        execution = JobExecution(
            id="test_exec",
            job_id="test_job",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        # Execute
        result = await retryable_job.execute(execution, {"test": "context"})

        assert result == {"status": "success"}
        assert job_func.call_count == 1
        assert execution.retry_count == 0

    @pytest.mark.asyncio
    async def test_execute_success_after_retry(self):
        """Test successful execution after retry."""
        # Mock job function that fails once then succeeds
        job_func = AsyncMock(
            side_effect=[
                ConnectionError("Connection failed"),
                {"status": "success"},
            ]
        )

        # Create retryable job with fast retry
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,  # Fast for testing
        )
        retryable_job = RetryableJob(job_func, policy)

        # Create execution
        execution = JobExecution(
            id="test_exec",
            job_id="test_job",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        # Execute
        result = await retryable_job.execute(execution, {"test": "context"})

        assert result == {"status": "success"}
        assert job_func.call_count == 2
        assert execution.retry_count == 1

    @pytest.mark.asyncio
    async def test_execute_all_retries_exhausted(self):
        """Test failure when all retries are exhausted."""
        # Mock job function that always fails
        job_func = AsyncMock(side_effect=ConnectionError("Connection failed"))

        # Create retryable job with fast retry
        policy = RetryPolicy(
            max_attempts=2,
            initial_delay=0.01,  # Fast for testing
        )
        retryable_job = RetryableJob(job_func, policy)

        # Create execution
        execution = JobExecution(
            id="test_exec",
            job_id="test_job",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        # Execute and expect failure
        with pytest.raises(ConnectionError, match="Connection failed"):
            await retryable_job.execute(execution, {"test": "context"})

        assert job_func.call_count == 3  # Initial + 2 retries
        assert execution.retry_count == 2

    @pytest.mark.asyncio
    async def test_execute_non_retryable_error(self):
        """Test immediate failure on non-retryable error."""
        # Mock job function that raises non-retryable error
        job_func = AsyncMock(side_effect=ValueError("Invalid value"))

        # Create retryable job
        policy = RetryPolicy(max_attempts=3)
        retryable_job = RetryableJob(job_func, policy)

        # Create execution
        execution = JobExecution(
            id="test_exec",
            job_id="test_job",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        # Execute and expect immediate failure
        with pytest.raises(ValueError, match="Invalid value"):
            await retryable_job.execute(execution, {"test": "context"})

        assert job_func.call_count == 1  # No retries
        assert execution.retry_count == 0

    @pytest.mark.asyncio
    async def test_execute_with_retry_callback(self):
        """Test retry callback is called."""
        # Mock job function that fails once
        job_func = AsyncMock(
            side_effect=[
                ConnectionError("Connection failed"),
                {"status": "success"},
            ]
        )

        # Mock retry callback
        on_retry = Mock()

        # Create retryable job
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
        )
        retryable_job = RetryableJob(job_func, policy, on_retry)

        # Create execution
        execution = JobExecution(
            id="test_exec",
            job_id="test_job",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        # Execute
        await retryable_job.execute(execution, {"test": "context"})

        # Verify callback was called
        assert on_retry.call_count == 1
        assert on_retry.call_args[0][0] == 0  # Attempt number
        assert isinstance(on_retry.call_args[0][1], ConnectionError)


class TestCreateDefaultRetryPolicy:
    """Test create_default_retry_policy function."""

    def test_create_with_defaults(self):
        """Test creating policy with default settings."""
        policy = create_default_retry_policy()

        assert policy.max_attempts == 3
        assert policy.initial_delay == 1.0
        assert policy.max_delay == 300.0
        assert policy.exponential_base == 2.0
        assert policy.jitter is True

    def test_create_with_custom_settings(self):
        """Test creating policy with custom settings."""
        settings = {
            "retry_attempts": 5,
            "retry_initial_delay": 2.0,
            "retry_max_delay": 600.0,
            "retry_exponential_base": 3.0,
            "retry_jitter": False,
        }

        policy = create_default_retry_policy(settings)

        assert policy.max_attempts == 5
        assert policy.initial_delay == 2.0
        assert policy.max_delay == 600.0
        assert policy.exponential_base == 3.0
        assert policy.jitter is False
