"""Tests for cache decorators."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.cache.decorators import (
    _build_cache_key,
    _get_default_ttl,
    _hash_arguments,
    cache,
    cache_key,
)
from paidsearchnav.cache.manager import CacheManager


class TestCacheDecorators:
    """Test cache decorator functionality."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager."""
        manager = AsyncMock(spec=CacheManager)
        manager.is_enabled = True
        manager.get = AsyncMock(return_value=None)
        manager.set = AsyncMock(return_value=True)
        manager.build_key = MagicMock(
            side_effect=lambda prefix,
            *parts,
            namespace=None: f"paidsearchnav:{namespace + ':' if namespace else ''}{prefix}:{':'.join(str(p) for p in parts)}"
        )
        return manager

    @pytest.mark.asyncio
    async def test_cache_decorator_basic(self, mock_cache_manager):
        """Test basic cache decorator functionality."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache(ttl=3600)
            async def test_func(x: int) -> int:
                return x * 2

            # First call - cache miss
            result = await test_func(5)
            assert result == 10

            # Verify cache was checked and set
            mock_cache_manager.get.assert_called_once()
            mock_cache_manager.set.assert_called_once()

            # Check the set call
            set_call = mock_cache_manager.set.call_args
            assert set_call[0][1] == 10  # Cached value
            assert set_call[0][2] == 3600  # TTL

    @pytest.mark.asyncio
    async def test_cache_decorator_hit(self, mock_cache_manager):
        """Test cache decorator with cache hit."""
        mock_cache_manager.get.return_value = 42

        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache()
            async def test_func(x: int) -> int:
                return x * 2

            result = await test_func(5)
            assert result == 42  # Cached value

            # Function should not be called, only cache get
            mock_cache_manager.get.assert_called_once()
            mock_cache_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_decorator_bypass(self, mock_cache_manager):
        """Test cache decorator with bypass parameter."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache()
            async def test_func(x: int, refresh: bool = False) -> int:
                return x * 3

            result = await test_func(5, refresh=True)
            assert result == 15

            # Cache should not be used
            mock_cache_manager.get.assert_not_called()
            mock_cache_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_decorator_custom_key_prefix(self, mock_cache_manager):
        """Test cache decorator with custom key prefix."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache(key_prefix="custom_key")
            async def test_func(x: int) -> int:
                return x * 4

            await test_func(5)

            # Check that custom key prefix was used
            get_call = mock_cache_manager.get.call_args
            key = get_call[0][0]
            assert "custom_key" in key

    @pytest.mark.asyncio
    async def test_cache_decorator_namespace_param(self, mock_cache_manager):
        """Test cache decorator with namespace parameter."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache(namespace_param="customer_id")
            async def get_data(customer_id: str, include_deleted: bool = False) -> dict:
                return {"customer": customer_id, "deleted": include_deleted}

            await get_data("cust_123", include_deleted=True)

            # Check that namespace was included in key
            get_call = mock_cache_manager.get.call_args
            key = get_call[0][0]
            assert "cust_123" in key

    @pytest.mark.asyncio
    async def test_cache_decorator_exclude_params(self, mock_cache_manager):
        """Test cache decorator with excluded parameters."""
        call_count = 0

        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache(exclude_params=["timestamp"])
            async def test_func(value: str, timestamp: int) -> str:
                nonlocal call_count
                call_count += 1
                return f"{value}_{call_count}"

            # First call
            result1 = await test_func("test", 12345)
            assert result1 == "test_1"

            # Set cache to return the cached value
            mock_cache_manager.get.return_value = "test_1"

            # Second call with different timestamp - should hit cache
            result2 = await test_func("test", 67890)
            assert result2 == "test_1"  # Cached value

            # Only one actual function call
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_cache_decorator_condition(self, mock_cache_manager):
        """Test cache decorator with condition function."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache(condition=lambda result: result > 0)
            async def test_func(x: int) -> int:
                return x

            # Positive result - should cache
            await test_func(5)
            mock_cache_manager.set.assert_called_once()

            # Reset mocks
            mock_cache_manager.set.reset_mock()

            # Negative result - should not cache
            await test_func(-5)
            mock_cache_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_decorator_disabled(self):
        """Test cache decorator when cache is disabled."""
        mock_manager = AsyncMock(spec=CacheManager)
        mock_manager.is_enabled = False

        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_manager,
        ):

            @cache()
            async def test_func(x: int) -> int:
                return x * 5

            result = await test_func(3)
            assert result == 15

            # Cache methods should not be called
            mock_manager.get.assert_not_called()
            mock_manager.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_decorator_no_manager(self):
        """Test cache decorator when no cache manager exists."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager", return_value=None
        ):

            @cache()
            async def test_func(x: int) -> int:
                return x * 6

            result = await test_func(2)
            assert result == 12

    def test_cache_decorator_sync_function(self):
        """Test cache decorator on sync function."""
        with patch("paidsearchnav.cache.decorators.logger") as mock_logger:

            @cache()
            def sync_func(x: int) -> int:
                return x * 7

            result = sync_func(2)
            assert result == 14

            # Should log warning about sync function
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_decorator(self, mock_cache_manager):
        """Test cache_key decorator."""
        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_cache_manager,
        ):

            @cache_key("reports", "summary")
            async def get_report_summary(report_id: str) -> dict:
                return {"id": report_id, "summary": "test"}

            await get_report_summary("report_123")

            # Check that key parts were used
            get_call = mock_cache_manager.get.call_args
            key = get_call[0][0]
            assert "reports:summary" in key

    def test_build_cache_key(self):
        """Test _build_cache_key function."""
        mock_manager = MagicMock()
        mock_manager.build_key = MagicMock(return_value="test_key")

        def test_func(customer_id: str, include_deleted: bool = False):
            pass

        with patch(
            "paidsearchnav.cache.decorators.get_cache_manager",
            return_value=mock_manager,
        ):
            key = _build_cache_key(
                test_func,
                ("cust_123",),
                {"include_deleted": True},
                "custom_prefix",
                "customer_id",
                None,
                ["customer_id", "include_deleted"],
            )

            # Verify build_key was called with correct arguments
            mock_manager.build_key.assert_called_once()
            call_args = mock_manager.build_key.call_args
            assert call_args[0][0] == "custom_prefix"  # prefix
            assert call_args[1]["namespace"] == "cust_123"  # namespace

    def test_hash_arguments(self):
        """Test _hash_arguments function."""
        args1 = {"key1": "value1", "key2": 42}
        args2 = {"key2": 42, "key1": "value1"}  # Different order
        args3 = {"key1": "value2", "key2": 42}  # Different value

        hash1 = _hash_arguments(args1)
        hash2 = _hash_arguments(args2)
        hash3 = _hash_arguments(args3)

        # Same arguments in different order should produce same hash
        assert hash1 == hash2

        # Different arguments should produce different hash
        assert hash1 != hash3

        # Hash should be 16 characters (SHA-256 truncated)
        assert len(hash1) == 16

    def test_get_default_ttl(self):
        """Test _get_default_ttl function."""
        # Test various function name patterns
        assert _get_default_ttl("get_report", None) == 86400  # 24 hours
        assert _get_default_ttl("fetch_audit_data", None) == 86400
        assert _get_default_ttl("get_customer_list", None) == 3600  # 1 hour
        assert _get_default_ttl("get_account_info", None) == 3600
        assert _get_default_ttl("list_items", None) == 300  # 5 minutes
        assert _get_default_ttl("search_terms", None) == 300
        assert _get_default_ttl("get_realtime_data", None) == 60  # 1 minute
        assert _get_default_ttl("get_current_metrics", None) == 60
        assert _get_default_ttl("unknown_function", None) == 300  # Default

        # Test with key prefix override
        assert _get_default_ttl("some_function", "report") == 86400
        assert _get_default_ttl("some_function", "customer_data") == 3600
