"""Tests for Redis-based rate limiting storage backend."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav_mcp.core.config import RedisConfig, Settings
from paidsearchnav_mcp.platforms.google.rate_limiting import (
    GoogleAdsRateLimiter,
    OperationType,
)
from paidsearchnav_mcp.platforms.google.storage import (
    FailoverRedisRateLimitStorage,
    InMemoryRateLimitStorage,
    RedisRateLimitStorage,
    create_storage_backend,
)


class TestRedisRateLimitStorage:
    """Test Redis storage backend for rate limiting."""

    @pytest.fixture
    def redis_config(self):
        """Create Redis configuration for testing."""
        return RedisConfig(
            enabled=True,
            url="redis://localhost:6379/0",
            max_connections=10,
            connection_timeout=1.0,
            socket_timeout=1.0,
            rate_limit_key_prefix="test:rate_limit:",
            rate_limit_key_ttl=3600,
            distributed_lock_timeout=5.0,
            distributed_lock_retry_delay=0.1,
        )

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()

        # Basic Redis operations
        mock_redis.ping.return_value = True
        mock_redis.lrange.return_value = []
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = None
        mock_redis.eval.return_value = 1  # Lock acquired successfully
        mock_redis.scan_iter.return_value = iter([])
        mock_redis.delete.return_value = None
        mock_redis.close.return_value = None

        # Pipeline operations - pipeline() is sync, methods are sync, only execute is async
        # The pipeline() method should return the mock_pipeline directly, not a coroutine
        from unittest.mock import Mock

        mock_redis.pipeline = Mock(return_value=mock_pipeline)

        # Pipeline methods are synchronous but return the pipeline for chaining
        mock_pipeline.lpush = Mock(return_value=mock_pipeline)
        mock_pipeline.expire = Mock(return_value=mock_pipeline)
        mock_pipeline.delete = Mock(return_value=mock_pipeline)
        # Only execute is async
        mock_pipeline.execute = AsyncMock(return_value=[None, None])

        return mock_redis

    @pytest.mark.asyncio
    async def test_redis_storage_initialization(self, redis_config, mock_redis):
        """Test Redis storage backend initialization."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            # Should not be setup yet
            assert not storage._setup_complete

            # Initialize connection
            await storage._ensure_connection()

            # Should be setup now
            assert storage._setup_complete
            assert storage.redis_pool is not None
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_storage_get_request_history(self, redis_config, mock_redis):
        """Test getting request history from Redis."""
        mock_redis.lrange.return_value = [b"1000.0", b"2000.0", b"3000.0"]

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            history = await storage.get_request_history(
                "customer123", OperationType.SEARCH
            )

            assert history == [1000.0, 2000.0, 3000.0]
            mock_redis.lrange.assert_called_with(
                "test:rate_limit:customer123:search", 0, -1
            )

    @pytest.mark.asyncio
    async def test_redis_storage_add_request(self, redis_config, mock_redis):
        """Test adding request to Redis storage."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            await storage.add_request("customer123", OperationType.SEARCH, 1500.0, 2)

            # Should call pipeline and execute
            mock_redis.pipeline.assert_called_once()
            pipeline = mock_redis.pipeline.return_value

            # Should call lpush twice for operation_size=2
            assert pipeline.lpush.call_count == 2
            pipeline.expire.assert_called_once()
            pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_storage_quota_usage(self, redis_config, mock_redis):
        """Test quota usage tracking in Redis."""
        # Mock getting empty quota initially
        mock_redis.get.return_value = None

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            # Get empty quota
            quota = await storage.get_quota_usage("customer123")
            assert quota == {}

            # Mock the distributed lock context manager properly
            # Create a mock that acts as an async context manager
            class MockDistributedLock:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None

            mock_lock = MockDistributedLock()

            with patch.object(storage, "_distributed_lock", return_value=mock_lock):
                # Update quota usage
                await storage.update_quota_usage("customer123", 100)

                # Should call setex to save quota data
                mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_storage_cleanup(self, redis_config, mock_redis):
        """Test cleanup of old entries in Redis."""
        # Mock the eval return value (number of cleaned entries)
        mock_redis.eval.return_value = 5

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            cutoff_time = 1500.0
            cleaned = await storage.cleanup_old_entries(cutoff_time)

            # Should use Lua script for cleanup
            mock_redis.eval.assert_called_once()
            assert cleaned == 5

    @pytest.mark.asyncio
    async def test_redis_storage_health_check(self, redis_config, mock_redis):
        """Test Redis health check."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)

            # Healthy case
            mock_redis.ping.return_value = True
            assert await storage.health_check() is True

            # Unhealthy case
            mock_redis.ping.side_effect = Exception("Connection failed")
            assert await storage.health_check() is False

    @pytest.mark.asyncio
    async def test_redis_storage_close(self, redis_config, mock_redis):
        """Test closing Redis connection."""
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            storage = RedisRateLimitStorage(redis_config)
            await storage._ensure_connection()

            await storage.close()
            mock_redis.close.assert_called_once()
            assert not storage._setup_complete


class TestInMemoryRateLimitStorage:
    """Test in-memory storage backend for rate limiting."""

    @pytest.fixture
    def storage(self):
        """Create in-memory storage for testing."""
        return InMemoryRateLimitStorage()

    @pytest.mark.asyncio
    async def test_memory_storage_basic_operations(self, storage):
        """Test basic operations of in-memory storage."""
        customer_id = "customer123"
        operation_type = OperationType.SEARCH
        timestamp = time.time()

        # Initially empty
        history = await storage.get_request_history(customer_id, operation_type)
        assert history == []

        # Add request
        await storage.add_request(customer_id, operation_type, timestamp, 1)

        # Should have the request
        history = await storage.get_request_history(customer_id, operation_type)
        assert len(history) == 1
        assert history[0] == timestamp

        # Add multiple requests
        await storage.add_request(customer_id, operation_type, timestamp + 1, 3)
        history = await storage.get_request_history(customer_id, operation_type)
        assert len(history) == 4  # 1 + 3

    @pytest.mark.asyncio
    async def test_memory_storage_quota_tracking(self, storage):
        """Test quota tracking in memory storage."""
        customer_id = "customer123"

        # Initially empty
        quota = await storage.get_quota_usage(customer_id)
        assert quota == {}

        # Update quota
        await storage.update_quota_usage(customer_id, 100)

        # Should have quota data
        quota = await storage.get_quota_usage(customer_id)
        assert quota["daily_usage"] == 100
        assert "reset_time" in quota
        assert "peak_usage" in quota

    @pytest.mark.asyncio
    async def test_memory_storage_cleanup(self, storage):
        """Test cleanup of old entries in memory storage."""
        customer_id = "customer123"
        operation_type = OperationType.SEARCH

        old_time = time.time() - 86500  # 25 hours ago
        new_time = time.time()

        # Add old and new requests
        await storage.add_request(customer_id, operation_type, old_time, 1)
        await storage.add_request(customer_id, operation_type, new_time, 1)

        # Should have 2 requests
        history = await storage.get_request_history(customer_id, operation_type)
        assert len(history) == 2

        # Cleanup old entries
        cutoff_time = time.time() - 3600  # 1 hour ago
        cleaned = await storage.cleanup_old_entries(cutoff_time)

        # Should have removed 1 old entry
        assert cleaned == 1
        history = await storage.get_request_history(customer_id, operation_type)
        assert len(history) == 1
        assert history[0] == new_time

    @pytest.mark.asyncio
    async def test_memory_storage_health_check(self, storage):
        """Test memory storage health check."""
        assert await storage.health_check() is True


class TestStorageBackendFactory:
    """Test storage backend factory function."""

    def test_create_redis_backend(self):
        """Test creating Redis backend when enabled."""
        redis_config = RedisConfig(enabled=True)
        backend = create_storage_backend(redis_config)
        assert isinstance(backend, FailoverRedisRateLimitStorage)

    def test_create_memory_backend_when_redis_disabled(self):
        """Test creating memory backend when Redis disabled."""
        redis_config = RedisConfig(enabled=False)
        backend = create_storage_backend(redis_config)
        assert isinstance(backend, InMemoryRateLimitStorage)

    def test_create_memory_backend_when_no_config(self):
        """Test creating memory backend when no Redis config."""
        backend = create_storage_backend(None)
        assert isinstance(backend, InMemoryRateLimitStorage)


class TestRateLimiterWithRedisBackend:
    """Test rate limiter integration with Redis backend."""

    @pytest.fixture
    def settings_with_redis(self):
        """Create settings with Redis enabled."""
        from paidsearchnav.core.config import GoogleAdsConfig

        settings = Settings()
        settings.redis = RedisConfig(enabled=True)
        settings.google_ads = GoogleAdsConfig(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_secret",
        )
        return settings

    @pytest.fixture
    def settings_without_redis(self):
        """Create settings with Redis disabled."""
        from paidsearchnav.core.config import GoogleAdsConfig

        settings = Settings()
        settings.redis = RedisConfig(enabled=False)
        settings.google_ads = GoogleAdsConfig(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_secret",
        )
        return settings

    @pytest.mark.asyncio
    async def test_rate_limiter_uses_redis_backend(self, settings_with_redis):
        """Test that rate limiter uses Redis backend when configured."""
        rate_limiter = GoogleAdsRateLimiter(settings_with_redis)
        assert isinstance(rate_limiter._storage, FailoverRedisRateLimitStorage)

    @pytest.mark.asyncio
    async def test_rate_limiter_uses_memory_backend(self, settings_without_redis):
        """Test that rate limiter uses memory backend when Redis disabled."""
        rate_limiter = GoogleAdsRateLimiter(settings_without_redis)
        assert isinstance(rate_limiter._storage, InMemoryRateLimitStorage)

    @pytest.mark.asyncio
    async def test_rate_limiter_health_check(self, settings_without_redis):
        """Test rate limiter health check."""
        rate_limiter = GoogleAdsRateLimiter(settings_without_redis)
        assert await rate_limiter.health_check() is True

    @pytest.mark.asyncio
    async def test_rate_limiter_close(self, settings_without_redis):
        """Test rate limiter close method."""
        rate_limiter = GoogleAdsRateLimiter(settings_without_redis)
        # Should not raise exception
        await rate_limiter.close()

    @pytest.mark.asyncio
    async def test_rate_limiter_with_redis_backend_mock(self, settings_with_redis):
        """Test rate limiter operations with mocked Redis backend."""
        mock_storage = AsyncMock()
        mock_storage.get_request_history.return_value = []
        mock_storage.health_check.return_value = True
        mock_storage.cleanup_old_entries.return_value = 0

        with patch(
            "paidsearchnav.platforms.google.storage.FailoverRedisRateLimitStorage",
            return_value=mock_storage,
        ):
            rate_limiter = GoogleAdsRateLimiter(settings_with_redis)

            # Test basic rate limit check
            result = await rate_limiter.check_rate_limit(
                "customer123", OperationType.SEARCH
            )
            assert result is True
            mock_storage.get_request_history.assert_called_once()

            # Test recording request
            await rate_limiter.record_request("customer123", OperationType.SEARCH)
            mock_storage.add_request.assert_called_once()

            # Test rate limit status
            await rate_limiter.get_rate_limit_status(
                "customer123", OperationType.SEARCH
            )
            assert mock_storage.get_request_history.call_count == 2
            mock_storage.get_quota_usage.assert_called_once()

            # Test health check
            assert await rate_limiter.health_check() is True
            mock_storage.health_check.assert_called_once()


class TestDistributedLocking:
    """Test distributed locking functionality."""

    @pytest.mark.asyncio
    async def test_distributed_lock_acquisition(self):
        """Test distributed lock acquisition and release."""
        from paidsearchnav.platforms.google.storage import DistributedLock

        mock_redis = AsyncMock()
        mock_redis.eval.side_effect = [1, 1]  # Lock acquired, then released

        lock = DistributedLock(
            mock_redis,
            "test:lock",
            "test:value",
            timeout=1.0,
            retry_delay=0.1,
            lock_script="test_lock_script",
            unlock_script="test_unlock_script",
        )

        # Test successful lock acquisition
        async with lock:
            assert lock.acquired is True

        # Lock should be released
        assert lock.acquired is False
        assert mock_redis.eval.call_count == 2

    @pytest.mark.asyncio
    async def test_distributed_lock_timeout(self):
        """Test distributed lock timeout."""
        from paidsearchnav.platforms.google.storage import DistributedLock

        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 0  # Lock acquisition fails

        lock = DistributedLock(
            mock_redis,
            "test:lock",
            "test:value",
            timeout=0.1,  # Very short timeout
            retry_delay=0.05,
            lock_script="test_lock_script",
            unlock_script="test_unlock_script",
        )

        # Should raise TimeoutError
        with pytest.raises(TimeoutError):
            async with lock:
                pass

    @pytest.mark.asyncio
    async def test_distributed_lock_redis_error(self):
        """Test distributed lock with Redis errors."""
        import redis

        from paidsearchnav.platforms.google.storage import DistributedLock

        mock_redis = AsyncMock()
        mock_redis.eval.side_effect = redis.RedisError("Redis error")

        lock = DistributedLock(
            mock_redis,
            "test:lock",
            "test:value",
            timeout=0.1,  # Very short timeout
            retry_delay=0.05,
            lock_script="test_lock_script",
            unlock_script="test_unlock_script",
        )

        # Should raise TimeoutError after retries
        with pytest.raises(TimeoutError):
            async with lock:
                pass
