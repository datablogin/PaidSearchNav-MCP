"""Base cache backend interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time to live in seconds (None for default)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key

        Returns:
            True if the key was deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key

        Returns:
            True if the key exists, False otherwise
        """
        pass

    @abstractmethod
    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Optional pattern to match keys (e.g., "customer:*")

        Returns:
            Number of keys deleted
        """
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Check if the cache backend is available.

        Returns:
            True if the backend is available, False otherwise
        """
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        pass

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from the cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key-value pairs (missing keys omitted)

        Note:
            This is a default implementation using individual get() calls.
            Subclasses should override this method to use backend-specific
            bulk operations for better performance (e.g., Redis MGET).
        """
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(
        self, mapping: dict[str, Any], ttl: Optional[int] = None
    ) -> dict[str, bool]:
        """Set multiple values in the cache.

        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds (None for default)

        Returns:
            Dictionary of key-success pairs

        Note:
            This is a default implementation using individual set() calls.
            Subclasses should override this method to use backend-specific
            bulk operations for better performance (e.g., Redis MSET).
        """
        result = {}
        for key, value in mapping.items():
            result[key] = await self.set(key, value, ttl)
        return result

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple values from the cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key-success pairs

        Note:
            This is a default implementation using individual delete() calls.
            Subclasses should override this method to use backend-specific
            bulk operations for better performance (e.g., Redis DEL with multiple keys).
        """
        result = {}
        for key in keys:
            result[key] = await self.delete(key)
        return result
