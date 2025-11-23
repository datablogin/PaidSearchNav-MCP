"""Redis cache client for MCP server."""

import hashlib
import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheClient:
    """Redis cache client for MCP server.

    Provides async caching capabilities with JSON serialization/deserialization,
    automatic key generation from parameters, and configurable TTL.

    Examples:
        >>> cache = CacheClient("redis://localhost:6379/0")
        >>> await cache.set("my_key", {"data": "value"}, ttl=600)
        >>> result = await cache.get("my_key")
        >>> {"data": "value"}

        >>> # Generate key from parameters
        >>> key = cache._make_key("search_terms", {"customer_id": "123", "date": "2024-01-01"})
        >>> await cache.set(key, {"results": [...]})
    """

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        """Initialize Redis cache client.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            default_ttl: Default time-to-live in seconds (default: 3600 = 1 hour)
        """
        self.redis = Redis.from_url(redis_url, decode_responses=False)
        self.default_ttl = default_ttl
        self._connected = False
        logger.info(f"CacheClient initialized with TTL={default_ttl}s")

    def _make_key(self, prefix: str, params: dict[str, Any]) -> str:
        """Generate cache key from parameters using MD5 hash.

        Creates deterministic cache keys by sorting parameters and hashing them.
        This ensures identical parameter sets always generate the same key.

        Args:
            prefix: Key prefix (e.g., "search_terms", "campaigns")
            params: Dictionary of parameters to hash

        Returns:
            Cache key in format "{prefix}:{hash}"

        Examples:
            >>> client._make_key("search_terms", {"customer_id": "123"})
            "search_terms:abc123..."
        """
        param_str = json.dumps(params, sort_keys=True)
        hash_str = hashlib.md5(param_str.encode()).hexdigest()
        key = f"{prefix}:{hash_str}"
        logger.debug(f"Generated cache key: {key} from params: {params}")
        return key

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get cached value by key.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached dictionary if found, None otherwise

        Raises:
            json.JSONDecodeError: If cached data is not valid JSON
            Exception: If Redis connection fails
        """
        try:
            data = await self.redis.get(key)
            if data:
                result: dict[str, Any] = json.loads(data)
                logger.debug(f"Cache hit for key: {key}")
                return result
            logger.debug(f"Cache miss for key: {key}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data for key {key}: {e}")
            # Delete corrupted cache entry
            await self.delete(key)
            return None
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            raise

    async def set(
        self, key: str, value: dict[str, Any], ttl: int | None = None
    ) -> None:
        """Set cached value with TTL.

        Args:
            key: Cache key to set
            value: Dictionary to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (uses default_ttl if None)

        Raises:
            TypeError: If value is not JSON serializable
            Exception: If Redis connection fails
        """
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            await self.redis.setex(key, ttl, serialized)
            logger.debug(f"Cache set for key: {key} with TTL={ttl}s")
        except TypeError as e:
            logger.error(f"Failed to serialize value for key {key}: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            raise

    async def delete(self, key: str) -> bool:
        """Delete cached value by key.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        try:
            result = await self.redis.delete(key)
            deleted = bool(result)
            if deleted:
                logger.debug(f"Cache deleted for key: {key}")
            else:
                logger.debug(f"Cache key not found for deletion: {key}")
            return deleted
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            raise

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            raise

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern.

        Useful for invalidating cached data for a specific resource type.

        Args:
            pattern: Redis key pattern (e.g., "search_terms:*", "campaigns:*")

        Returns:
            Number of keys deleted

        Examples:
            >>> # Clear all search terms cache
            >>> await cache.clear_pattern("search_terms:*")
            42
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted: int = await self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} keys matching pattern: {pattern}")
                return deleted

            logger.debug(f"No keys found matching pattern: {pattern}")
            return 0
        except Exception as e:
            logger.error(f"Redis clear_pattern error for pattern {pattern}: {e}")
            raise

    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Cache key to check

        Returns:
            Remaining TTL in seconds, -1 if no expiry, -2 if key doesn't exist
        """
        try:
            ttl: int = await self.redis.ttl(key)
            return ttl
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            raise

    async def ping(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            await self.redis.ping()
            self._connected = True
            logger.debug("Redis connection healthy")
            return True
        except Exception as e:
            self._connected = False
            logger.error(f"Redis ping failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection.

        Should be called when shutting down the application.
        """
        try:
            await self.redis.aclose()
            self._connected = False
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        """Check if client has established Redis connection.

        Returns:
            True if connected, False otherwise
        """
        return self._connected
