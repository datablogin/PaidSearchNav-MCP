"""Tests for base cache backend interface."""

import pytest

from paidsearchnav_mcp.cache.base import CacheBackend


class TestCacheBackend:
    """Test base cache backend interface."""

    def test_cache_backend_is_abstract(self):
        """Test that CacheBackend cannot be instantiated."""
        with pytest.raises(TypeError):
            CacheBackend()

    @pytest.mark.asyncio
    async def test_default_get_many(self):
        """Test default implementation of get_many."""

        class MockCache(CacheBackend):
            """Mock cache implementation."""

            async def get(self, key: str):
                if key == "key1":
                    return "value1"
                elif key == "key2":
                    return "value2"
                return None

            async def set(self, key: str, value: str, ttl: int = None):
                return True

            async def delete(self, key: str):
                return True

            async def exists(self, key: str):
                return key in ["key1", "key2"]

            async def clear(self, pattern: str = None):
                return 0

            async def ping(self):
                return True

            async def get_stats(self):
                return {}

        cache = MockCache()
        result = await cache.get_many(["key1", "key2", "key3"])

        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_default_set_many(self):
        """Test default implementation of set_many."""

        class MockCache(CacheBackend):
            """Mock cache implementation."""

            def __init__(self):
                self.storage = {}

            async def get(self, key: str):
                return self.storage.get(key)

            async def set(self, key: str, value: str, ttl: int = None):
                self.storage[key] = value
                return True

            async def delete(self, key: str):
                if key in self.storage:
                    del self.storage[key]
                    return True
                return False

            async def exists(self, key: str):
                return key in self.storage

            async def clear(self, pattern: str = None):
                count = len(self.storage)
                self.storage.clear()
                return count

            async def ping(self):
                return True

            async def get_stats(self):
                return {"size": len(self.storage)}

        cache = MockCache()
        result = await cache.set_many(
            {"key1": "value1", "key2": "value2", "key3": "value3"}
        )

        assert result == {"key1": True, "key2": True, "key3": True}
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_default_delete_many(self):
        """Test default implementation of delete_many."""

        class MockCache(CacheBackend):
            """Mock cache implementation."""

            def __init__(self):
                self.storage = {"key1": "value1", "key2": "value2"}

            async def get(self, key: str):
                return self.storage.get(key)

            async def set(self, key: str, value: str, ttl: int = None):
                self.storage[key] = value
                return True

            async def delete(self, key: str):
                if key in self.storage:
                    del self.storage[key]
                    return True
                return False

            async def exists(self, key: str):
                return key in self.storage

            async def clear(self, pattern: str = None):
                count = len(self.storage)
                self.storage.clear()
                return count

            async def ping(self):
                return True

            async def get_stats(self):
                return {"size": len(self.storage)}

        cache = MockCache()
        result = await cache.delete_many(["key1", "key2", "key3"])

        assert result == {"key1": True, "key2": True, "key3": False}
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
