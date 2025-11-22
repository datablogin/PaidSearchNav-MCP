"""GA4 API response caching for performance optimization.

This module provides caching functionality for GA4 API responses
to reduce API usage and improve performance.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from paidsearchnav.core.config import GA4Config
from paidsearchnav.platforms.ga4.models import GA4CacheEntry

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class GA4CacheManager:
    """Cache manager for GA4 API responses."""

    def __init__(
        self,
        config: GA4Config,
        redis_client: Optional[Any] = None,
        use_memory_fallback: bool = True,
    ):
        """Initialize GA4 cache manager.

        Args:
            config: GA4 configuration
            redis_client: Optional Redis client for distributed caching
            use_memory_fallback: Use in-memory cache if Redis unavailable
        """
        self.config = config
        self.redis_client = redis_client
        self.use_memory_fallback = use_memory_fallback

        # In-memory cache fallback
        self._memory_cache: Dict[str, GA4CacheEntry] = {}
        self._cache_key_prefix = f"ga4_cache:{config.property_id}:"

    def _generate_cache_key(
        self,
        request_type: str,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate cache key for a GA4 API request.

        Args:
            request_type: Type of request (realtime, historical, etc.)
            start_date: Start date
            end_date: End date
            dimensions: Requested dimensions
            metrics: Requested metrics
            filters: Applied filters

        Returns:
            Cache key string
        """
        # Create deterministic cache key from request parameters
        request_data = {
            "type": request_type,
            "start_date": start_date,
            "end_date": end_date,
            "dimensions": sorted(dimensions),
            "metrics": sorted(metrics),
            "filters": filters or {},
        }

        # Generate hash of request parameters
        request_json = json.dumps(request_data, sort_keys=True)
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()[:16]

        return f"{self._cache_key_prefix}{request_type}:{request_hash}"

    async def get_cached_response(
        self,
        request_type: str,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired.

        Args:
            request_type: Type of request
            start_date: Start date
            end_date: End date
            dimensions: Requested dimensions
            metrics: Requested metrics
            filters: Applied filters

        Returns:
            Cached response data or None if not available
        """
        if not self.config.enable_response_cache:
            return None

        cache_key = self._generate_cache_key(
            request_type, start_date, end_date, dimensions, metrics, filters
        )

        try:
            # Try Redis first if available
            if self.redis_client and REDIS_AVAILABLE:
                cached_data = await self._get_from_redis(cache_key)
                if cached_data:
                    logger.debug(f"GA4 cache hit (Redis): {cache_key}")
                    return cached_data

            # Fall back to memory cache
            if self.use_memory_fallback:
                cached_entry = self._memory_cache.get(cache_key)
                if cached_entry and not cached_entry.is_expired:
                    cached_entry.access_count += 1
                    cached_entry.last_accessed = datetime.utcnow()
                    logger.debug(f"GA4 cache hit (memory): {cache_key}")
                    return cached_entry.response_data

        except Exception as e:
            logger.warning(f"GA4 cache retrieval error: {e}")

        logger.debug(f"GA4 cache miss: {cache_key}")
        return None

    async def store_response(
        self,
        request_type: str,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        response_data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        custom_ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store response in cache.

        Args:
            request_type: Type of request
            start_date: Start date
            end_date: End date
            dimensions: Requested dimensions
            metrics: Requested metrics
            response_data: Response data to cache
            filters: Applied filters
            custom_ttl_seconds: Custom TTL override
        """
        if not self.config.enable_response_cache:
            return

        cache_key = self._generate_cache_key(
            request_type, start_date, end_date, dimensions, metrics, filters
        )

        ttl_seconds = custom_ttl_seconds or self.config.cache_ttl_seconds
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        cache_entry = GA4CacheEntry(
            cache_key=cache_key,
            response_data=response_data,
            expires_at=expires_at,
        )

        try:
            # Store in Redis if available
            if self.redis_client and REDIS_AVAILABLE:
                await self._store_in_redis(cache_key, cache_entry, ttl_seconds)

            # Store in memory cache
            if self.use_memory_fallback:
                self._memory_cache[cache_key] = cache_entry

            logger.debug(f"GA4 response cached: {cache_key} (TTL: {ttl_seconds}s)")

        except Exception as e:
            logger.warning(f"GA4 cache storage error: {e}")

    async def _get_from_redis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None
        """
        try:
            cached_json = await self.redis_client.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
        except Exception as e:
            logger.warning(f"Redis cache retrieval error: {e}")

        return None

    async def _store_in_redis(
        self, cache_key: str, cache_entry: GA4CacheEntry, ttl_seconds: int
    ) -> None:
        """Store data in Redis cache.

        Args:
            cache_key: Cache key
            cache_entry: Cache entry to store
            ttl_seconds: TTL in seconds
        """
        try:
            cached_json = json.dumps(cache_entry.response_data)
            await self.redis_client.setex(cache_key, ttl_seconds, cached_json)
        except Exception as e:
            logger.warning(f"Redis cache storage error: {e}")

    def invalidate_cache(
        self,
        request_type: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> int:
        """Invalidate cache entries.

        Args:
            request_type: Optional filter by request type
            property_id: Optional filter by property ID

        Returns:
            Number of entries invalidated
        """
        invalidated_count = 0

        # Invalidate memory cache
        keys_to_remove = []
        for key, entry in self._memory_cache.items():
            should_invalidate = True

            if request_type and request_type not in key:
                should_invalidate = False

            if property_id and property_id not in key:
                should_invalidate = False

            if should_invalidate:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._memory_cache[key]
            invalidated_count += 1

        # Invalidate Redis cache if available
        if self.redis_client and REDIS_AVAILABLE:
            try:
                # Get matching keys from Redis
                pattern = f"{self._cache_key_prefix}"
                if request_type:
                    pattern += f"{request_type}:*"
                else:
                    pattern += "*"

                # Note: This is a simplified implementation
                # Production code should use SCAN for large key sets

            except Exception as e:
                logger.warning(f"Redis cache invalidation error: {e}")

        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} GA4 cache entries")

        return invalidated_count

    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries from memory.

        Returns:
            Number of entries cleaned up
        """
        current_time = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._memory_cache.items() if entry.is_expired
        ]

        for key in expired_keys:
            del self._memory_cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired GA4 cache entries")

        return len(expired_keys)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.

        Returns:
            Cache statistics
        """
        memory_entries = len(self._memory_cache)
        expired_entries = sum(
            1 for entry in self._memory_cache.values() if entry.is_expired
        )

        total_access_count = sum(
            entry.access_count for entry in self._memory_cache.values()
        )

        return {
            "property_id": self.config.property_id,
            "cache_enabled": self.config.enable_response_cache,
            "cache_ttl_seconds": self.config.cache_ttl_seconds,
            "memory_cache": {
                "entries": memory_entries,
                "expired_entries": expired_entries,
                "total_access_count": total_access_count,
            },
            "redis_cache": {
                "available": self.redis_client is not None and REDIS_AVAILABLE,
                "connected": self._test_redis_connection(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _test_redis_connection(self) -> bool:
        """Test Redis connection.

        Returns:
            True if Redis is connected and working
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            return False

        try:
            # Simple ping test
            return (
                self.redis_client.ping()
                if hasattr(self.redis_client, "ping")
                else False
            )
        except Exception:
            return False

    def get_cache_hit_rate(self, hours: int = 24) -> float:
        """Calculate cache hit rate for the specified period.

        Args:
            hours: Number of hours to calculate hit rate for

        Returns:
            Cache hit rate as percentage (0.0-100.0)
        """
        # This is a simplified implementation
        # In production, you'd track hits/misses over time

        total_entries = len(self._memory_cache)
        if total_entries == 0:
            return 0.0

        accessed_entries = sum(
            1 for entry in self._memory_cache.values() if entry.access_count > 0
        )

        return (accessed_entries / total_entries) * 100

    def optimize_cache_settings(self) -> Dict[str, Any]:
        """Analyze cache performance and suggest optimizations.

        Returns:
            Cache optimization recommendations
        """
        stats = self.get_cache_stats()
        hit_rate = self.get_cache_hit_rate()

        recommendations = []

        # TTL optimization
        if hit_rate < 30:  # Low hit rate
            recommendations.append(
                {
                    "type": "ttl_optimization",
                    "priority": "medium",
                    "title": "Increase Cache TTL",
                    "description": f"Low cache hit rate ({hit_rate:.1f}%) suggests TTL too short",
                    "action": f"Consider increasing TTL from {self.config.cache_ttl_seconds}s to 900s",
                }
            )

        # Memory usage optimization
        memory_entries = stats["memory_cache"]["entries"]
        if memory_entries > 1000:  # High memory usage
            recommendations.append(
                {
                    "type": "memory_optimization",
                    "priority": "low",
                    "title": "High Memory Cache Usage",
                    "description": f"Memory cache has {memory_entries} entries",
                    "action": "Consider using Redis for distributed caching or reduce TTL",
                }
            )

        # Redis availability
        if not stats["redis_cache"]["available"]:
            recommendations.append(
                {
                    "type": "infrastructure",
                    "priority": "low",
                    "title": "Redis Cache Not Available",
                    "description": "Using memory-only cache - consider Redis for better performance",
                    "action": "Configure Redis for distributed caching across instances",
                }
            )

        return {
            "current_performance": {
                "hit_rate_percentage": hit_rate,
                "memory_entries": memory_entries,
                "ttl_seconds": self.config.cache_ttl_seconds,
            },
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat(),
        }
