"""Tests for cache manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.cache.base import CacheBackend
from paidsearchnav.cache.config import CacheConfig, CacheTTLConfig, RedisCacheConfig
from paidsearchnav.cache.manager import (
    CacheManager,
    get_cache_manager,
    set_cache_manager,
)
from paidsearchnav.core.config import Settings


class MockCacheBackend(CacheBackend):
    """Mock cache backend for testing."""

    def __init__(self):
        self.ping_result = True
        self.get_calls = []
        self.set_calls = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return f"value_for_{key}"

    async def set(self, key: str, value, ttl=None):
        self.set_calls.append((key, value, ttl))
        return True

    async def delete(self, key: str):
        return True

    async def exists(self, key: str):
        return True

    async def clear(self, pattern=None):
        return 5

    async def ping(self):
        return self.ping_result

    async def get_stats(self):
        return {"test": True}


class TestCacheManager:
    """Test cache manager functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with cache configuration."""
        settings = MagicMock(spec=Settings)
        settings.cache = CacheConfig(
            enabled=True,
            backend="redis",
            redis=RedisCacheConfig(url="redis://localhost:6379", cluster=False),
            ttl=CacheTTLConfig(),
        )
        return settings

    @pytest.fixture
    def mock_settings_disabled(self):
        """Create mock settings with cache disabled."""
        settings = MagicMock(spec=Settings)
        settings.cache = CacheConfig(enabled=False)
        return settings

    @pytest.fixture
    def mock_settings_no_cache(self):
        """Create mock settings without cache configuration."""
        settings = MagicMock(spec=Settings)
        settings.cache = None
        return settings

    @pytest.mark.asyncio
    async def test_initialize_with_cache_enabled(self, mock_settings):
        """Test initializing cache manager with cache enabled."""
        manager = CacheManager(mock_settings)

        mock_backend = MockCacheBackend()
        with patch("paidsearchnav.cache.manager.RedisCache", return_value=mock_backend):
            await manager.initialize()

            assert manager.is_enabled
            assert manager._initialized
            assert manager._backend == mock_backend

    @pytest.mark.asyncio
    async def test_initialize_with_cache_disabled(self, mock_settings_disabled):
        """Test initializing cache manager with cache disabled."""
        manager = CacheManager(mock_settings_disabled)
        await manager.initialize()

        assert not manager.is_enabled
        assert not manager._initialized
        assert manager._backend is None

    @pytest.mark.asyncio
    async def test_initialize_no_cache_config(self, mock_settings_no_cache):
        """Test initializing cache manager without cache config."""
        manager = CacheManager(mock_settings_no_cache)
        await manager.initialize()

        assert not manager.is_enabled
        assert not manager._initialized
        assert manager._backend is None

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, mock_settings):
        """Test initializing cache manager with connection failure."""
        manager = CacheManager(mock_settings)

        mock_backend = MockCacheBackend()
        mock_backend.ping_result = False

        with patch("paidsearchnav.cache.manager.RedisCache", return_value=mock_backend):
            await manager.initialize()

            assert not manager.is_enabled
            assert not manager._initialized
            assert manager._backend is None

    @pytest.mark.asyncio
    async def test_get_from_cache(self, mock_settings):
        """Test getting value from cache."""
        manager = CacheManager(mock_settings)
        manager._backend = MockCacheBackend()
        manager._initialized = True

        result = await manager.get("test_key")
        assert result == "value_for_test_key"
        assert manager._backend.get_calls == ["test_key"]

    @pytest.mark.asyncio
    async def test_get_cache_disabled(self, mock_settings):
        """Test getting value when cache is disabled."""
        manager = CacheManager(mock_settings)
        # Don't initialize backend

        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_error(self, mock_settings):
        """Test getting value with backend error."""
        manager = CacheManager(mock_settings)

        mock_backend = AsyncMock()
        mock_backend.get.side_effect = Exception("Backend error")
        manager._backend = mock_backend
        manager._initialized = True

        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_in_cache(self, mock_settings):
        """Test setting value in cache."""
        manager = CacheManager(mock_settings)
        manager._backend = MockCacheBackend()
        manager._initialized = True

        result = await manager.set("test_key", "test_value", ttl=3600)
        assert result is True
        assert manager._backend.set_calls == [("test_key", "test_value", 3600)]

    @pytest.mark.asyncio
    async def test_set_cache_disabled(self, mock_settings):
        """Test setting value when cache is disabled."""
        manager = CacheManager(mock_settings)

        result = await manager.set("test_key", "test_value")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_with_error(self, mock_settings):
        """Test setting value with backend error."""
        manager = CacheManager(mock_settings)

        mock_backend = AsyncMock()
        mock_backend.set.side_effect = Exception("Backend error")
        manager._backend = mock_backend
        manager._initialized = True

        result = await manager.set("test_key", "test_value")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_from_cache(self, mock_settings):
        """Test deleting value from cache."""
        manager = CacheManager(mock_settings)

        mock_backend = AsyncMock()
        mock_backend.delete.return_value = True
        manager._backend = mock_backend
        manager._initialized = True

        result = await manager.delete("test_key")
        assert result is True
        mock_backend.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_settings):
        """Test clearing cache."""
        manager = CacheManager(mock_settings)
        manager._backend = MockCacheBackend()
        manager._initialized = True

        result = await manager.clear("test:*")
        assert result == 5

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_settings):
        """Test getting cache statistics."""
        manager = CacheManager(mock_settings)
        manager._backend = MockCacheBackend()
        manager._initialized = True

        stats = await manager.get_stats()
        assert stats == {"enabled": True, "test": True}

    @pytest.mark.asyncio
    async def test_get_stats_disabled(self, mock_settings):
        """Test getting stats when cache is disabled."""
        manager = CacheManager(mock_settings)

        stats = await manager.get_stats()
        assert stats == {"enabled": False}

    @pytest.mark.asyncio
    async def test_close(self, mock_settings):
        """Test closing cache manager."""
        manager = CacheManager(mock_settings)

        mock_backend = AsyncMock()
        manager._backend = mock_backend
        manager._initialized = True

        await manager.close()

        mock_backend.close.assert_called_once()
        assert manager._backend is None
        assert not manager._initialized

    def test_build_key_simple(self, mock_settings):
        """Test building simple cache key."""
        manager = CacheManager(mock_settings)

        key = manager.build_key("customer", "123")
        assert key == "paidsearchnav:customer:123"

    def test_build_key_with_namespace(self, mock_settings):
        """Test building cache key with namespace."""
        manager = CacheManager(mock_settings)

        key = manager.build_key("audit", "456", namespace="cust_789")
        assert key == "paidsearchnav:cust_789:audit:456"

    def test_build_key_multiple_parts(self, mock_settings):
        """Test building cache key with multiple parts."""
        manager = CacheManager(mock_settings)

        key = manager.build_key("report", "audit", "2024", "01", namespace="abc")
        assert key == "paidsearchnav:abc:report:audit:2024:01"

    def test_global_cache_manager(self, mock_settings):
        """Test global cache manager get/set."""
        manager = CacheManager(mock_settings)

        # Initially None
        assert get_cache_manager() is None

        # Set manager
        set_cache_manager(manager)
        assert get_cache_manager() == manager

        # Reset
        set_cache_manager(None)
        assert get_cache_manager() is None
