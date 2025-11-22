"""Cache backend implementations."""

import json
import logging
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster
from redis.exceptions import ConnectionError, RedisError

from .base import CacheBackend

logger = logging.getLogger(__name__)


def sanitize_redis_url(url: str) -> str:
    """Sanitize Redis URL for logging by removing credentials."""
    try:
        parsed = urlparse(url)
        # Replace password with asterisks
        if parsed.password:
            sanitized = parsed._replace(
                netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"
                if parsed.username
                else f"{parsed.hostname}:{parsed.port}"
            )
            return urlunparse(sanitized)
        return url
    except Exception:
        # If parsing fails, return a generic message
        return "redis://***"


class RedisCache(CacheBackend):
    """Redis cache backend implementation."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        cluster_mode: bool = False,
        max_connections: int = 50,
        decode_responses: bool = True,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        retry_on_timeout: bool = True,
        ssl: bool = False,
        **kwargs,
    ):
        """Initialize Redis cache backend.

        Args:
            url: Redis URL (redis://host:port/db)
            cluster_mode: Whether to use Redis cluster
            max_connections: Maximum number of connections
            decode_responses: Whether to decode responses as strings
            socket_connect_timeout: Socket connection timeout
            socket_timeout: Socket operation timeout
            retry_on_timeout: Whether to retry on timeout
            ssl: Whether to use SSL
            **kwargs: Additional Redis client arguments
        """
        self.url = url
        self.cluster_mode = cluster_mode
        self._client: Optional[redis.Redis | RedisCluster] = None

        # Connection pool settings
        self.connection_kwargs = {
            "decode_responses": decode_responses,
            "socket_connect_timeout": socket_connect_timeout,
            "socket_timeout": socket_timeout,
            "retry_on_timeout": retry_on_timeout,
            "ssl": ssl,
            "max_connections": max_connections,
            **kwargs,
        }

    async def _get_client(self) -> redis.Redis | RedisCluster:
        """Get or create Redis client."""
        if self._client is None:
            if self.cluster_mode:
                self._client = RedisCluster.from_url(self.url, **self.connection_kwargs)
            else:
                self._client = redis.from_url(self.url, **self.connection_kwargs)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                return None

            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except ConnectionError:
            logger.warning(
                f"Redis connection error getting key: {key} (URL: {sanitize_redis_url(self.url)})"
            )
            return None
        except RedisError as e:
            logger.error(f"Redis error getting key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache."""
        try:
            client = await self._get_client()

            # Serialize value to JSON if not a string
            if not isinstance(value, (str, bytes)):
                value = json.dumps(value)

            if ttl:
                result = await client.setex(key, ttl, value)
            else:
                result = await client.set(key, value)

            return bool(result)

        except ConnectionError:
            logger.warning(
                f"Redis connection error setting key: {key} (URL: {sanitize_redis_url(self.url)})"
            )
            return False
        except RedisError as e:
            logger.error(f"Redis error setting key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return bool(result)
        except ConnectionError:
            logger.warning(
                f"Redis connection error deleting key: {key} (URL: {sanitize_redis_url(self.url)})"
            )
            return False
        except RedisError as e:
            logger.error(f"Redis error deleting key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return bool(result)
        except ConnectionError:
            logger.warning(
                f"Redis connection error checking key: {key} (URL: {sanitize_redis_url(self.url)})"
            )
            return False
        except RedisError as e:
            logger.error(f"Redis error checking key {key}: {e}")
            return False

    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries."""
        try:
            client = await self._get_client()

            if pattern:
                # Use SCAN to find keys matching pattern
                keys = []
                cursor = 0
                while True:
                    cursor, batch = await client.scan(cursor, match=pattern, count=100)
                    keys.extend(batch)
                    if cursor == 0:
                        break

                if keys:
                    result = await client.delete(*keys)
                    return result
                return 0
            else:
                # Clear all keys (dangerous in production!)
                await client.flushdb()
                return -1  # Unknown number of keys deleted

        except ConnectionError:
            logger.warning(
                f"Redis connection error clearing cache (URL: {sanitize_redis_url(self.url)})"
            )
            return 0
        except RedisError as e:
            logger.error(f"Redis error clearing cache: {e}")
            return 0

    async def ping(self) -> bool:
        """Check if the cache backend is available."""
        try:
            client = await self._get_client()
            result = await client.ping()
            return result
        except (ConnectionError, RedisError):
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            client = await self._get_client()
            info = await client.info()

            # Extract relevant stats
            stats = {
                "backend": "redis",
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }

            # Calculate hit rate
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            total = hits + misses
            stats["hit_rate"] = (hits / total * 100) if total > 0 else 0.0

            return stats

        except (ConnectionError, RedisError) as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"backend": "redis", "connected": False, "error": str(e)}

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from the cache efficiently."""
        if not keys:
            return {}

        try:
            client = await self._get_client()
            values = await client.mget(keys)

            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[key] = value

            return result

        except ConnectionError:
            logger.warning(
                f"Redis connection error in get_many (URL: {sanitize_redis_url(self.url)})"
            )
            return {}
        except RedisError as e:
            logger.error(f"Redis error in get_many: {e}")
            return {}

    async def set_many(
        self, mapping: dict[str, Any], ttl: Optional[int] = None
    ) -> dict[str, bool]:
        """Set multiple values in the cache efficiently."""
        if not mapping:
            return {}

        try:
            client = await self._get_client()

            # Prepare values for mset
            prepared = {}
            for key, value in mapping.items():
                if not isinstance(value, (str, bytes)):
                    prepared[key] = json.dumps(value)
                else:
                    prepared[key] = value

            # Use pipeline for atomic operation
            async with client.pipeline() as pipe:
                pipe.mset(prepared)

                # Set TTL if specified
                if ttl:
                    for key in prepared:
                        pipe.expire(key, ttl)

                await pipe.execute()

            # Return success for all keys
            return {key: True for key in mapping}

        except ConnectionError:
            logger.warning(
                f"Redis connection error in set_many (URL: {sanitize_redis_url(self.url)})"
            )
            return {key: False for key in mapping}
        except RedisError as e:
            logger.error(f"Redis error in set_many: {e}")
            return {key: False for key in mapping}

    async def close(self):
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self):
        """Context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
