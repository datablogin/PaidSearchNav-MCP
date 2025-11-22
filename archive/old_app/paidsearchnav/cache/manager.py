"""Cache manager for handling cache operations."""

import json
import logging
from typing import Any, Optional

from redis.exceptions import ConnectionError

from paidsearchnav.core.config import Settings

from .backends import RedisCache, sanitize_redis_url
from .base import CacheBackend

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages cache operations and backend selection."""

    def __init__(self, settings: Settings):
        """Initialize cache manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._backend: Optional[CacheBackend] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the cache backend."""
        if self._initialized:
            return

        cache_config = getattr(self.settings, "cache", None)
        if not cache_config or not cache_config.enabled:
            logger.info("Cache is disabled in configuration")
            return

        backend_type = cache_config.backend.lower()

        if backend_type == "redis":
            redis_config = cache_config.redis
            self._backend = RedisCache(
                url=redis_config.url,
                cluster_mode=redis_config.cluster,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                ssl=redis_config.url.startswith("rediss://"),
            )

            # Test connection
            if await self._backend.ping():
                logger.info(
                    f"Successfully connected to Redis cache at {sanitize_redis_url(redis_config.url)}"
                )
                self._initialized = True
            else:
                logger.error(
                    f"Failed to connect to Redis cache at {sanitize_redis_url(redis_config.url)}"
                )
                self._backend = None
        else:
            logger.error(f"Unsupported cache backend: {backend_type}")

    @property
    def backend(self) -> Optional[CacheBackend]:
        """Get the cache backend."""
        return self._backend

    @property
    def is_enabled(self) -> bool:
        """Check if cache is enabled."""
        return self._backend is not None and self._initialized

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        if not self.is_enabled:
            return None

        try:
            return await self._backend.get(key)
        except ConnectionError as e:
            logger.warning(f"Cache connection error getting key {key}: {e}")
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Cache deserialization error for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected cache error getting key {key}: {type(e).__name__}: {e}"
            )
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache."""
        if not self.is_enabled:
            return False

        try:
            return await self._backend.set(key, value, ttl)
        except ConnectionError as e:
            logger.warning(f"Cache connection error setting key {key}: {e}")
            return False
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Cache serialization error for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected cache error setting key {key}: {type(e).__name__}: {e}"
            )
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        if not self.is_enabled:
            return False

        try:
            return await self._backend.delete(key)
        except ConnectionError as e:
            logger.warning(f"Cache connection error deleting key {key}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected cache error deleting key {key}: {type(e).__name__}: {e}"
            )
            return False

    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries."""
        if not self.is_enabled:
            return 0

        try:
            return await self._backend.clear(pattern)
        except ConnectionError as e:
            logger.warning(f"Cache connection error clearing pattern {pattern}: {e}")
            return 0
        except Exception as e:
            logger.error(
                f"Unexpected cache error clearing pattern {pattern}: {type(e).__name__}: {e}"
            )
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        if not self.is_enabled:
            return {"enabled": False}

        try:
            stats = await self._backend.get_stats()
            stats["enabled"] = True
            return stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": True, "error": str(e)}

    async def close(self) -> None:
        """Close the cache backend."""
        if self._backend and hasattr(self._backend, "close"):
            try:
                await self._backend.close()
            except Exception as e:
                logger.error(f"Error closing cache backend: {e}")
        self._backend = None
        self._initialized = False

    async def __aenter__(self):
        """Context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    def build_key(
        self, prefix: str, *parts: str | int, namespace: Optional[str] = None
    ) -> str:
        """Build a cache key with proper namespacing.

        Args:
            prefix: Key prefix (e.g., "customer", "audit")
            *parts: Additional key parts
            namespace: Optional namespace (e.g., customer_id)

        Returns:
            Formatted cache key

        Example:
            build_key("audit", "123", namespace="cust_456")
            => "paidsearchnav:cust_456:audit:123"
        """
        key_parts = ["paidsearchnav"]

        if namespace:
            key_parts.append(str(namespace))

        key_parts.append(prefix)
        key_parts.extend(str(part) for part in parts)

        return ":".join(key_parts)


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance."""
    return _cache_manager


def set_cache_manager(manager: CacheManager) -> None:
    """Set the global cache manager instance."""
    global _cache_manager
    _cache_manager = manager
