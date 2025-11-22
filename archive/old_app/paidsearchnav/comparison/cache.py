"""Caching support for comparison operations."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ComparisonCache:
    """Cache manager for comparison results and trend data."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 3600,
        enable_cache: bool = True,
    ):
        """Initialize cache manager."""
        self.enable_cache = enable_cache
        self.default_ttl = default_ttl
        self.redis_client: Optional[redis.Redis] = None

        if enable_cache and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except (RedisError, Exception) as e:
                logger.warning(f"Failed to initialize Redis cache: {e}")
                self.redis_client = None

    def _generate_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from parameters."""
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.sha256(sorted_params.encode()).hexdigest()
        return f"comparison:{prefix}:{param_hash}"

    def get_comparison_result(
        self, baseline_id: str, comparison_id: str, options: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached comparison result."""
        if not self._is_cache_available():
            return None

        params = {
            "baseline_id": baseline_id,
            "comparison_id": comparison_id,
            "options": options,
        }
        cache_key = self._generate_cache_key("compare", params)

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(
                    f"Cache hit for comparison {baseline_id} vs {comparison_id}"
                )
                return json.loads(cached_data)
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving from cache: {e}")

        return None

    def set_comparison_result(
        self,
        baseline_id: str,
        comparison_id: str,
        options: Dict[str, Any],
        result: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache comparison result."""
        if not self._is_cache_available():
            return False

        params = {
            "baseline_id": baseline_id,
            "comparison_id": comparison_id,
            "options": options,
        }
        cache_key = self._generate_cache_key("compare", params)

        try:
            serialized = json.dumps(result)
            self.redis_client.setex(
                cache_key,
                ttl or self.default_ttl,
                serialized,
            )
            logger.debug(
                f"Cached comparison result for {baseline_id} vs {comparison_id}"
            )
            return True
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error caching result: {e}")
            return False

    def get_trend_data(
        self,
        customer_id: str,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached trend data."""
        if not self._is_cache_available():
            return None

        params = {
            "customer_id": customer_id,
            "metric_type": metric_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": granularity,
        }
        cache_key = self._generate_cache_key("trend", params)

        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for trend data {customer_id}/{metric_type}")
                return json.loads(cached_data)
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving trend from cache: {e}")

        return None

    def set_trend_data(
        self,
        customer_id: str,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache trend data."""
        if not self._is_cache_available():
            return False

        params = {
            "customer_id": customer_id,
            "metric_type": metric_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": granularity,
        }
        cache_key = self._generate_cache_key("trend", params)

        try:
            serialized = json.dumps(data)
            self.redis_client.setex(
                cache_key,
                ttl or self.default_ttl,
                serialized,
            )
            logger.debug(f"Cached trend data for {customer_id}/{metric_type}")
            return True
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error caching trend data: {e}")
            return False

    def invalidate_customer_cache(self, customer_id: str) -> int:
        """Invalidate all cache entries for a customer."""
        if not self._is_cache_available():
            return 0

        try:
            # Find all keys related to this customer
            # Use more specific patterns to avoid broad scans
            patterns = [
                f'comparison:trend:*"customer_id": "{customer_id}"*',
                f'comparison:compare:*"customer_id": "{customer_id}"*',
            ]

            keys = []
            for pattern in patterns:
                keys.extend(list(self.redis_client.scan_iter(match=pattern, count=100)))

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(
                    f"Invalidated {deleted} cache entries for customer {customer_id}"
                )
                return deleted

            return 0
        except RedisError as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._is_cache_available():
            return {"enabled": False, "available": False}

        try:
            info = self.redis_client.info()
            return {
                "enabled": True,
                "available": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands": info.get("total_commands_processed", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "evicted_keys": info.get("evicted_keys", 0),
            }
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": True, "available": False, "error": str(e)}

    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """Calculate cache hit rate from Redis info."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses

        if total == 0:
            return 0.0

        return (hits / total) * 100

    def _is_cache_available(self) -> bool:
        """Check if cache is enabled and available."""
        if not self.enable_cache or not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except RedisError:
            return False

    def set_with_sliding_expiration(
        self, key: str, value: Dict[str, Any], ttl: int
    ) -> bool:
        """Set value with sliding expiration (resets TTL on access)."""
        if not self._is_cache_available():
            return False

        try:
            pipeline = self.redis_client.pipeline()
            pipeline.setex(key, ttl, json.dumps(value))
            pipeline.expire(key, ttl)  # Reset TTL
            pipeline.execute()
            return True
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error setting with sliding expiration: {e}")
            return False


class InMemoryCache:
    """Simple in-memory cache for environments without Redis."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """Initialize in-memory cache."""
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            value, expiry = self.cache[key]
            if expiry > datetime.utcnow():
                return value
            else:
                # Expired, remove it
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        # Evict oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            # Simple FIFO eviction
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        expiry = datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl)
        self.cache[key] = (value, expiry)
        return True

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries."""
        count = len(self.cache)
        self.cache.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = datetime.utcnow()
        expired_keys = [k for k, (_, exp) in self.cache.items() if exp <= now]

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)
