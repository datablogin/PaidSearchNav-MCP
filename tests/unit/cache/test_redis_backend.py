"""Tests for Redis cache backend."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError, RedisError

from paidsearchnav.cache.backends import RedisCache


class TestRedisCache:
    """Test Redis cache backend."""

    @pytest.fixture
    def redis_cache(self):
        """Create a Redis cache instance."""
        return RedisCache(url="redis://localhost:6379")

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.setex = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        client.exists = AsyncMock(return_value=1)
        client.scan = AsyncMock(return_value=(0, []))
        client.flushdb = AsyncMock(return_value=True)
        client.info = AsyncMock(
            return_value={
                "redis_version": "7.0.0",
                "used_memory_human": "1.5M",
                "connected_clients": 5,
                "total_commands_processed": 1000,
                "keyspace_hits": 800,
                "keyspace_misses": 200,
                "uptime_in_seconds": 3600,
            }
        )
        client.mget = AsyncMock(return_value=[])
        client.pipeline = MagicMock()

        # Setup pipeline mock
        pipeline = AsyncMock()
        pipeline.mset = MagicMock()
        pipeline.expire = MagicMock()
        pipeline.execute = AsyncMock(return_value=[True])
        pipeline.__aenter__ = AsyncMock(return_value=pipeline)
        pipeline.__aexit__ = AsyncMock(return_value=None)
        client.pipeline.return_value = pipeline

        return client

    @pytest.mark.asyncio
    async def test_get_client_single_mode(self, redis_cache, mock_redis_client):
        """Test getting Redis client in single mode."""
        with patch(
            "paidsearchnav.cache.backends.redis.from_url",
            return_value=mock_redis_client,
        ):
            client = await redis_cache._get_client()
            assert client == mock_redis_client

    @pytest.mark.asyncio
    async def test_get_client_cluster_mode(self, mock_redis_client):
        """Test getting Redis client in cluster mode."""
        cache = RedisCache(cluster_mode=True)
        with patch(
            "paidsearchnav.cache.backends.RedisCluster.from_url",
            return_value=mock_redis_client,
        ):
            client = await cache._get_client()
            assert client == mock_redis_client

    @pytest.mark.asyncio
    async def test_get_value(self, redis_cache, mock_redis_client):
        """Test getting a value from cache."""
        mock_redis_client.get.return_value = json.dumps({"key": "value"})

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.get("test_key")
            assert result == {"key": "value"}
            mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_string_value(self, redis_cache, mock_redis_client):
        """Test getting a string value from cache."""
        mock_redis_client.get.return_value = "plain string"

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.get("test_key")
            assert result == "plain string"

    @pytest.mark.asyncio
    async def test_get_none_value(self, redis_cache, mock_redis_client):
        """Test getting None when key doesn't exist."""
        mock_redis_client.get.return_value = None

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.get("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_connection_error(self, redis_cache):
        """Test handling connection error on get."""
        with patch.object(redis_cache, "_get_client", side_effect=ConnectionError()):
            result = await redis_cache.get("test_key")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_redis_error(self, redis_cache, mock_redis_client):
        """Test handling Redis error on get."""
        mock_redis_client.get.side_effect = RedisError("Redis error")

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.get("test_key")
            assert result is None

    @pytest.mark.asyncio
    async def test_set_value(self, redis_cache, mock_redis_client):
        """Test setting a value in cache."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.set("test_key", {"data": "value"})
            assert result is True
            mock_redis_client.set.assert_called_once_with(
                "test_key", json.dumps({"data": "value"})
            )

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, redis_cache, mock_redis_client):
        """Test setting a value with TTL."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.set("test_key", "value", ttl=3600)
            assert result is True
            mock_redis_client.setex.assert_called_once_with("test_key", 3600, "value")

    @pytest.mark.asyncio
    async def test_set_string_value(self, redis_cache, mock_redis_client):
        """Test setting a string value."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.set("test_key", "string value")
            assert result is True
            mock_redis_client.set.assert_called_once_with("test_key", "string value")

    @pytest.mark.asyncio
    async def test_set_connection_error(self, redis_cache):
        """Test handling connection error on set."""
        with patch.object(redis_cache, "_get_client", side_effect=ConnectionError()):
            result = await redis_cache.set("test_key", "value")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_key(self, redis_cache, mock_redis_client):
        """Test deleting a key."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.delete("test_key")
            assert result is True
            mock_redis_client.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, redis_cache, mock_redis_client):
        """Test deleting a nonexistent key."""
        mock_redis_client.delete.return_value = 0

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.delete("nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_exists_key(self, redis_cache, mock_redis_client):
        """Test checking if key exists."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.exists("test_key")
            assert result is True
            mock_redis_client.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_clear_with_pattern(self, redis_cache, mock_redis_client):
        """Test clearing cache with pattern."""
        mock_redis_client.scan.side_effect = [(100, [b"key1", b"key2"]), (0, [b"key3"])]
        mock_redis_client.delete.return_value = 3

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.clear("test:*")
            assert result == 3
            assert mock_redis_client.scan.call_count == 2
            mock_redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all(self, redis_cache, mock_redis_client):
        """Test clearing all cache."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.clear()
            assert result == -1
            mock_redis_client.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping(self, redis_cache, mock_redis_client):
        """Test pinging Redis."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.ping()
            assert result is True
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_connection_error(self, redis_cache):
        """Test ping with connection error."""
        with patch.object(redis_cache, "_get_client", side_effect=ConnectionError()):
            result = await redis_cache.ping()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_stats(self, redis_cache, mock_redis_client):
        """Test getting cache statistics."""
        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            stats = await redis_cache.get_stats()

            assert stats["backend"] == "redis"
            assert stats["connected"] is True
            assert stats["version"] == "7.0.0"
            assert stats["used_memory"] == "1.5M"
            assert stats["connected_clients"] == 5
            assert stats["total_commands_processed"] == 1000
            assert stats["keyspace_hits"] == 800
            assert stats["keyspace_misses"] == 200
            assert stats["hit_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_stats_error(self, redis_cache):
        """Test get stats with error."""
        with patch.object(
            redis_cache, "_get_client", side_effect=ConnectionError("Connection failed")
        ):
            stats = await redis_cache.get_stats()

            assert stats["backend"] == "redis"
            assert stats["connected"] is False
            assert "Connection failed" in stats["error"]

    @pytest.mark.asyncio
    async def test_get_many(self, redis_cache, mock_redis_client):
        """Test getting multiple values."""
        mock_redis_client.mget.return_value = [
            json.dumps({"data": "value1"}),
            None,
            "string_value",
        ]

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.get_many(["key1", "key2", "key3"])

            assert result == {"key1": {"data": "value1"}, "key3": "string_value"}
            mock_redis_client.mget.assert_called_once_with(["key1", "key2", "key3"])

    @pytest.mark.asyncio
    async def test_set_many(self, redis_cache, mock_redis_client):
        """Test setting multiple values."""
        mapping = {"key1": {"data": "value1"}, "key2": "string_value"}

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.set_many(mapping)

            assert result == {"key1": True, "key2": True}

            # Check mset was called with correct values
            pipeline = mock_redis_client.pipeline.return_value
            pipeline.mset.assert_called_once()

            # Verify the prepared data
            call_args = pipeline.mset.call_args[0][0]
            assert call_args["key1"] == json.dumps({"data": "value1"})
            assert call_args["key2"] == "string_value"

    @pytest.mark.asyncio
    async def test_set_many_with_ttl(self, redis_cache, mock_redis_client):
        """Test setting multiple values with TTL."""
        mapping = {"key1": "value1", "key2": "value2"}

        with patch.object(redis_cache, "_get_client", return_value=mock_redis_client):
            result = await redis_cache.set_many(mapping, ttl=3600)

            assert result == {"key1": True, "key2": True}

            # Check expire was called for each key
            pipeline = mock_redis_client.pipeline.return_value
            assert pipeline.expire.call_count == 2

    @pytest.mark.asyncio
    async def test_close(self, redis_cache, mock_redis_client):
        """Test closing Redis connection."""
        redis_cache._client = mock_redis_client

        await redis_cache.close()

        mock_redis_client.close.assert_called_once()
        assert redis_cache._client is None
