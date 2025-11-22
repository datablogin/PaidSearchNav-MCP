"""Storage backends for Google Ads rate limiting."""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import redis.asyncio as redis
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from paidsearchnav.core.config import RedisConfig

# Avoid circular import by importing OperationType at type checking time only
if TYPE_CHECKING:
    from paidsearchnav.platforms.google.rate_limiting import OperationType
else:
    # Define a simple enum for runtime use
    from enum import Enum

    class OperationType(Enum):
        SEARCH = "search"
        MUTATE = "mutate"
        REPORT = "report"
        BULK_MUTATE = "bulk_mutate"
        ACCOUNT_INFO = "account_info"


logger = logging.getLogger(__name__)


class RateLimitStorageBackend(ABC):
    """Abstract base class for rate limiting storage backends."""

    @abstractmethod
    async def get_request_history(
        self, customer_id: str, operation_type: OperationType
    ) -> List[float]:
        """Get request history timestamps for a customer and operation type."""
        pass

    @abstractmethod
    async def add_request(
        self,
        customer_id: str,
        operation_type: OperationType,
        timestamp: float,
        operation_size: int = 1,
    ) -> None:
        """Add request timestamp(s) to history."""
        pass

    @abstractmethod
    async def get_quota_usage(self, customer_id: str) -> Dict[str, Any]:
        """Get current quota usage for a customer."""
        pass

    @abstractmethod
    async def update_quota_usage(self, customer_id: str, api_cost: int) -> None:
        """Update quota usage for a customer."""
        pass

    @abstractmethod
    async def cleanup_old_entries(self, cutoff_time: float) -> int:
        """Remove entries older than cutoff_time. Returns number of entries removed."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        pass


class InMemoryRateLimitStorage(RateLimitStorageBackend):
    """In-memory storage backend for rate limiting (single instance only)."""

    def __init__(self):
        self._request_history: Dict[str, Dict[str, List[float]]] = {}
        self._quota_usage: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_request_history(
        self, customer_id: str, operation_type: OperationType
    ) -> List[float]:
        """Get request history timestamps for a customer and operation type."""
        async with self._lock:
            customer_history = self._request_history.get(customer_id, {})
            return customer_history.get(operation_type.value, []).copy()

    async def add_request(
        self,
        customer_id: str,
        operation_type: OperationType,
        timestamp: float,
        operation_size: int = 1,
    ) -> None:
        """Add request timestamp(s) to history."""
        async with self._lock:
            if customer_id not in self._request_history:
                self._request_history[customer_id] = {}

            customer_history = self._request_history[customer_id]
            operation_key = operation_type.value

            if operation_key not in customer_history:
                customer_history[operation_key] = []

            # Add multiple entries for larger operations
            for _ in range(operation_size):
                customer_history[operation_key].append(timestamp)

    async def get_quota_usage(self, customer_id: str) -> Dict[str, Any]:
        """Get current quota usage for a customer."""
        async with self._lock:
            return self._quota_usage.get(customer_id, {}).copy()

    async def update_quota_usage(self, customer_id: str, api_cost: int) -> None:
        """Update quota usage for a customer."""
        async with self._lock:
            now = datetime.utcnow()

            if customer_id not in self._quota_usage:
                self._quota_usage[customer_id] = {
                    "daily_usage": 0,
                    "reset_time": now.replace(hour=0, minute=0, second=0, microsecond=0)
                    + timedelta(days=1),
                    "peak_usage": 0,
                    "last_updated": now,
                }

            quota_info = self._quota_usage[customer_id]

            # Reset daily usage if needed
            if now >= quota_info["reset_time"]:
                quota_info["daily_usage"] = 0
                quota_info["reset_time"] = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)

            # Update usage
            quota_info["daily_usage"] += api_cost
            quota_info["peak_usage"] = max(
                quota_info["peak_usage"], quota_info["daily_usage"]
            )
            quota_info["last_updated"] = now

    async def cleanup_old_entries(self, cutoff_time: float) -> int:
        """Remove entries older than cutoff_time. Returns number of entries removed."""
        async with self._lock:
            cleaned_entries = 0

            for customer_id in list(self._request_history.keys()):
                customer_history = self._request_history[customer_id]

                for operation_type in list(customer_history.keys()):
                    old_count = len(customer_history[operation_type])
                    # Filter out old requests
                    customer_history[operation_type] = [
                        ts
                        for ts in customer_history[operation_type]
                        if ts > cutoff_time
                    ]
                    cleaned_entries += old_count - len(customer_history[operation_type])

                    # Remove empty operation types
                    if not customer_history[operation_type]:
                        del customer_history[operation_type]

                # Remove empty customer entries
                if not customer_history:
                    del self._request_history[customer_id]

            return cleaned_entries

    async def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        return True


class RedisRateLimitStorage(RateLimitStorageBackend):
    """Redis-based storage backend for distributed rate limiting."""

    def __init__(self, config: RedisConfig):
        self.config = config
        self.redis_pool: Optional[redis.Redis] = None
        self._lock_script: Optional[str] = None
        self._unlock_script: Optional[str] = None
        self._setup_complete = False

    async def _ensure_connection(self) -> redis.Redis:
        """Ensure Redis connection is established."""
        if not self._setup_complete:
            await self._setup_redis()

        if self.redis_pool is None:
            raise RuntimeError("Redis connection not initialized")

        return self.redis_pool

    async def _setup_redis(self) -> None:
        """Setup Redis connection and Lua scripts."""
        try:
            # Parse Redis URL if needed
            if self.config.url.startswith("redis://"):
                self.redis_pool = redis.from_url(
                    self.config.url,
                    password=self.config.auth_token.get_secret_value()
                    if self.config.auth_token
                    else None,
                    db=self.config.db,
                    max_connections=self.config.max_connections,
                    socket_connect_timeout=self.config.connection_timeout,
                    socket_timeout=self.config.socket_timeout,
                    retry_on_timeout=self.config.retry_on_timeout,
                    health_check_interval=self.config.health_check_interval,
                )
            else:
                # Manual configuration
                self.redis_pool = redis.Redis(
                    host="localhost",
                    port=6379,
                    db=self.config.db,
                    password=self.config.auth_token.get_secret_value()
                    if self.config.auth_token
                    else None,
                    max_connections=self.config.max_connections,
                    socket_connect_timeout=self.config.connection_timeout,
                    socket_timeout=self.config.socket_timeout,
                    retry_on_timeout=self.config.retry_on_timeout,
                    health_check_interval=self.config.health_check_interval,
                )

            # Test connection
            await self.redis_pool.ping()

            # Setup Lua scripts for atomic operations
            await self._setup_lua_scripts()

            self._setup_complete = True
            logger.info("Redis connection established successfully")

        except Exception as e:
            logger.error(f"Failed to setup Redis connection: {e}")
            raise

    async def _setup_lua_scripts(self) -> None:
        """Setup Lua scripts for atomic distributed locking."""
        # Distributed lock script
        self._lock_script = """
        local key = KEYS[1]
        local value = ARGV[1]
        local ttl = tonumber(ARGV[2])

        if redis.call('SET', key, value, 'NX', 'EX', ttl) then
            return 1
        else
            return 0
        end
        """

        # Distributed unlock script
        self._unlock_script = """
        local key = KEYS[1]
        local value = ARGV[1]

        if redis.call('GET', key) == value then
            return redis.call('DEL', key)
        else
            return 0
        end
        """

        # Cleanup script for efficient batch cleanup
        self._cleanup_script = """
        local prefix = ARGV[1]
        local cutoff_time = tonumber(ARGV[2])
        local ttl = tonumber(ARGV[3])
        local cleaned = 0

        local keys = redis.call('KEYS', prefix .. '*')
        for i=1,#keys do
            local key = keys[i]
            -- Skip quota and lock keys
            if not string.find(key, ':quota:') and not string.find(key, ':lock') then
                local timestamps = redis.call('LRANGE', key, 0, -1)
                local old_count = #timestamps

                if old_count > 0 then
                    -- Filter out old timestamps
                    local recent = {}
                    for j=1,#timestamps do
                        if tonumber(timestamps[j]) > cutoff_time then
                            table.insert(recent, timestamps[j])
                        end
                    end

                    -- Replace the list with recent timestamps
                    redis.call('DEL', key)
                    if #recent > 0 then
                        redis.call('LPUSH', key, unpack(recent))
                        redis.call('EXPIRE', key, ttl)
                    end

                    cleaned = cleaned + (old_count - #recent)
                end
            end
        end

        return cleaned
        """

    @retry(
        retry=retry_if_exception_type((redis.RedisError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=5),
    )
    async def get_request_history(
        self, customer_id: str, operation_type: OperationType
    ) -> List[float]:
        """Get request history timestamps for a customer and operation type."""
        redis_client = await self._ensure_connection()
        key = f"{self.config.rate_limit_key_prefix}{customer_id}:{operation_type.value}"

        try:
            # Get list of timestamps from Redis
            timestamps = await redis_client.lrange(key, 0, -1)
            return [float(ts) for ts in timestamps]
        except redis.RedisError as e:
            logger.error(f"Redis error getting request history: {e}")
            raise

    @retry(
        retry=retry_if_exception_type((redis.RedisError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=5),
    )
    async def add_request(
        self,
        customer_id: str,
        operation_type: OperationType,
        timestamp: float,
        operation_size: int = 1,
    ) -> None:
        """Add request timestamp(s) to history."""
        redis_client = await self._ensure_connection()
        key = f"{self.config.rate_limit_key_prefix}{customer_id}:{operation_type.value}"

        try:
            pipe = redis_client.pipeline()

            # Add multiple entries for larger operations
            for _ in range(operation_size):
                pipe.lpush(key, timestamp)

            # Set TTL for automatic cleanup
            pipe.expire(key, self.config.rate_limit_key_ttl)

            await pipe.execute()

        except redis.RedisError as e:
            logger.error(f"Redis error adding request: {e}")
            raise

    @retry(
        retry=retry_if_exception_type((redis.RedisError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=5),
    )
    async def get_quota_usage(self, customer_id: str) -> Dict[str, Any]:
        """Get current quota usage for a customer."""
        redis_client = await self._ensure_connection()
        key = f"{self.config.rate_limit_key_prefix}quota:{customer_id}"

        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return {}
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting quota usage: {e}")
            return {}

    @retry(
        retry=retry_if_exception_type((redis.RedisError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=5),
    )
    async def update_quota_usage(self, customer_id: str, api_cost: int) -> None:
        """Update quota usage for a customer."""
        redis_client = await self._ensure_connection()
        key = f"{self.config.rate_limit_key_prefix}quota:{customer_id}"

        try:
            # Use distributed lock for atomic quota updates
            lock_key = f"{key}:lock"
            lock_value = f"{time.time()}:{uuid.uuid4()}"

            async with self._distributed_lock(lock_key, lock_value):
                # Get current quota
                current_quota = await self.get_quota_usage(customer_id)

                now = datetime.utcnow()

                if not current_quota:
                    current_quota = {
                        "daily_usage": 0,
                        "reset_time": (
                            now.replace(hour=0, minute=0, second=0, microsecond=0)
                            + timedelta(days=1)
                        ).isoformat(),
                        "peak_usage": 0,
                        "last_updated": now.isoformat(),
                    }

                # Reset daily usage if needed
                reset_time = datetime.fromisoformat(current_quota["reset_time"])
                if now >= reset_time:
                    current_quota["daily_usage"] = 0
                    current_quota["reset_time"] = (
                        now.replace(hour=0, minute=0, second=0, microsecond=0)
                        + timedelta(days=1)
                    ).isoformat()

                # Update usage
                current_quota["daily_usage"] += api_cost
                current_quota["peak_usage"] = max(
                    current_quota["peak_usage"], current_quota["daily_usage"]
                )
                current_quota["last_updated"] = now.isoformat()

                # Save updated quota with TTL
                await redis_client.setex(
                    key, self.config.rate_limit_key_ttl, json.dumps(current_quota)
                )

        except redis.RedisError as e:
            logger.error(f"Redis error updating quota usage: {e}")
            raise

    async def cleanup_old_entries(self, cutoff_time: float) -> int:
        """Remove entries older than cutoff_time. Returns number of entries removed."""
        redis_client = await self._ensure_connection()

        try:
            # Use Lua script for efficient batch cleanup
            if hasattr(self, "_cleanup_script") and self._cleanup_script:
                result = await redis_client.eval(
                    self._cleanup_script,
                    0,  # No key arguments
                    self.config.rate_limit_key_prefix,
                    str(cutoff_time),
                    str(self.config.rate_limit_key_ttl),
                )
                return int(result) if result else 0
            else:
                # Fallback to individual key processing if script not available
                return await self._cleanup_individual_keys(redis_client, cutoff_time)

        except redis.RedisError as e:
            logger.error(f"Redis error during cleanup: {e}")
            return 0

    async def _cleanup_individual_keys(
        self, redis_client: redis.Redis, cutoff_time: float
    ) -> int:
        """Fallback cleanup method for individual key processing."""
        cleaned_entries = 0

        try:
            # Get all rate limiting keys
            pattern = f"{self.config.rate_limit_key_prefix}*"
            async for key in redis_client.scan_iter(match=pattern):
                key_str = key.decode() if isinstance(key, bytes) else key

                # Skip quota and lock keys
                if ":quota:" in key_str or ":lock" in key_str:
                    continue

                # Get all timestamps and remove old ones
                timestamps = await redis_client.lrange(key_str, 0, -1)
                old_count = len(timestamps)

                if timestamps:
                    # Remove old timestamps
                    pipe = redis_client.pipeline()
                    pipe.delete(key_str)

                    # Re-add recent timestamps
                    recent_timestamps = [
                        ts for ts in timestamps if float(ts) > cutoff_time
                    ]

                    if recent_timestamps:
                        pipe.lpush(key_str, *recent_timestamps)
                        pipe.expire(key_str, self.config.rate_limit_key_ttl)

                    await pipe.execute()
                    cleaned_entries += old_count - len(recent_timestamps)

        except redis.RedisError as e:
            logger.error(f"Redis error during individual key cleanup: {e}")

        return cleaned_entries

    async def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        try:
            redis_client = await self._ensure_connection()
            await redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def _distributed_lock(self, lock_key: str, lock_value: str):
        """Context manager for distributed locking."""
        if (
            self.redis_pool is None
            or self._lock_script is None
            or self._unlock_script is None
        ):
            raise RuntimeError("Redis connection not properly initialized")

        return DistributedLock(
            self.redis_pool,
            lock_key,
            lock_value,
            self.config.distributed_lock_timeout,
            self.config.distributed_lock_retry_delay,
            self._lock_script,
            self._unlock_script,
        )

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_pool:
            await self.redis_pool.close()
            self._setup_complete = False


class DistributedLock:
    """Distributed lock implementation using Redis."""

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_key: str,
        lock_value: str,
        timeout: float,
        retry_delay: float,
        lock_script: str,
        unlock_script: str,
    ):
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.lock_value = lock_value
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.lock_script = lock_script
        self.unlock_script = unlock_script
        self.acquired = False

    async def __aenter__(self):
        """Acquire the distributed lock."""
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Try to acquire lock using Lua script
                result = await self.redis_client.eval(
                    self.lock_script,
                    1,
                    self.lock_key,
                    self.lock_value,
                    int(self.timeout),
                )

                if result == 1:
                    self.acquired = True
                    return self

                # Wait before retrying
                await asyncio.sleep(self.retry_delay)

            except redis.RedisError as e:
                logger.error(f"Error acquiring distributed lock: {e}")
                await asyncio.sleep(self.retry_delay)

        raise TimeoutError(
            f"Failed to acquire lock {self.lock_key} within {self.timeout}s"
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the distributed lock."""
        if self.acquired:
            try:
                await self.redis_client.eval(
                    self.unlock_script, 1, self.lock_key, self.lock_value
                )
            except redis.RedisError as e:
                logger.error(f"Error releasing distributed lock: {e}")
            finally:
                self.acquired = False


class FailoverRedisRateLimitStorage(RateLimitStorageBackend):
    """Redis storage with automatic failover to in-memory storage."""

    def __init__(self, redis_config: RedisConfig):
        self.redis_storage = RedisRateLimitStorage(redis_config)
        self.memory_storage = InMemoryRateLimitStorage()
        self._redis_available = True
        self._last_redis_check = 0
        self._redis_check_interval = redis_config.redis_health_check_interval

    async def _is_redis_available(self) -> bool:
        """Check if Redis is available, with caching to avoid excessive checks."""
        now = time.time()
        if now - self._last_redis_check < self._redis_check_interval:
            return self._redis_available

        self._last_redis_check = now
        try:
            new_redis_status = await self.redis_storage.health_check()
            if not new_redis_status and self._redis_available:
                logger.warning(
                    "Redis is unavailable, falling back to in-memory storage"
                )
            elif (
                new_redis_status and not self._redis_available
            ):  # Was previously unavailable
                logger.info("Redis is now available again")
            self._redis_available = new_redis_status
        except Exception as e:
            logger.error(f"Error checking Redis availability: {e}")
            self._redis_available = False

        return self._redis_available

    async def _execute_with_failover(self, operation_name: str, redis_op, memory_op):
        """Execute operation with Redis, falling back to memory on failure."""
        if await self._is_redis_available():
            try:
                return await redis_op()
            except Exception as e:
                logger.warning(
                    f"Redis operation {operation_name} failed: {e}, falling back to memory"
                )
                self._redis_available = False
                return await memory_op()
        else:
            return await memory_op()

    async def get_request_history(
        self, customer_id: str, operation_type: OperationType
    ) -> List[float]:
        """Get request history with Redis failover."""
        return await self._execute_with_failover(
            "get_request_history",
            lambda: self.redis_storage.get_request_history(customer_id, operation_type),
            lambda: self.memory_storage.get_request_history(
                customer_id, operation_type
            ),
        )

    async def add_request(
        self,
        customer_id: str,
        operation_type: OperationType,
        timestamp: float,
        operation_size: int = 1,
    ) -> None:
        """Add request with Redis failover."""
        await self._execute_with_failover(
            "add_request",
            lambda: self.redis_storage.add_request(
                customer_id, operation_type, timestamp, operation_size
            ),
            lambda: self.memory_storage.add_request(
                customer_id, operation_type, timestamp, operation_size
            ),
        )

    async def get_quota_usage(self, customer_id: str) -> Dict[str, Any]:
        """Get quota usage with Redis failover."""
        return await self._execute_with_failover(
            "get_quota_usage",
            lambda: self.redis_storage.get_quota_usage(customer_id),
            lambda: self.memory_storage.get_quota_usage(customer_id),
        )

    async def update_quota_usage(self, customer_id: str, api_cost: int) -> None:
        """Update quota usage with Redis failover."""
        await self._execute_with_failover(
            "update_quota_usage",
            lambda: self.redis_storage.update_quota_usage(customer_id, api_cost),
            lambda: self.memory_storage.update_quota_usage(customer_id, api_cost),
        )

    async def cleanup_old_entries(self, cutoff_time: float) -> int:
        """Cleanup old entries with Redis failover."""
        return await self._execute_with_failover(
            "cleanup_old_entries",
            lambda: self.redis_storage.cleanup_old_entries(cutoff_time),
            lambda: self.memory_storage.cleanup_old_entries(cutoff_time),
        )

    async def health_check(self) -> bool:
        """Check health of the storage backend."""
        redis_healthy = await self.redis_storage.health_check()
        memory_healthy = await self.memory_storage.health_check()

        # As long as one backend is healthy, we're operational
        return redis_healthy or memory_healthy

    async def close(self) -> None:
        """Close connections."""
        await self.redis_storage.close()
        # Memory storage doesn't need closing


def create_storage_backend(
    redis_config: Optional[RedisConfig] = None,
) -> RateLimitStorageBackend:
    """Factory function to create appropriate storage backend."""
    if redis_config and isinstance(redis_config, RedisConfig) and redis_config.enabled:
        logger.info("Using Redis backend with failover for rate limiting storage")
        return FailoverRedisRateLimitStorage(redis_config)
    else:
        logger.info("Using in-memory backend for rate limiting storage")
        return InMemoryRateLimitStorage()
