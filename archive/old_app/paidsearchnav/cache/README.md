# Cache Module

The cache module provides a high-performance caching layer for the PaidSearchNav API using Redis as the backend.

## Features

- **Async/await support**: Full asynchronous implementation for non-blocking operations
- **Flexible decorators**: Easy-to-use decorators for automatic caching
- **Configurable TTLs**: Different TTL settings for various data types
- **Cache namespacing**: Automatic key namespacing to prevent collisions
- **Graceful degradation**: API continues to work if cache is unavailable
- **Monitoring**: Built-in cache statistics and health checks

## Configuration

Configure caching through environment variables:

```bash
# Enable/disable caching
PSN_CACHE_ENABLED=true
PSN_CACHE_BACKEND=redis

# Redis connection
PSN_CACHE_REDIS_URL=redis://localhost:6379
PSN_CACHE_REDIS_CLUSTER=false
PSN_CACHE_REDIS_PASSWORD=your_password

# TTL settings (in seconds)
PSN_CACHE_TTL_DEFAULT=300              # 5 minutes
PSN_CACHE_TTL_CUSTOMER_LIST=3600       # 1 hour
PSN_CACHE_TTL_AUDIT_REPORT=86400       # 24 hours
PSN_CACHE_TTL_RECOMMENDATIONS=3600     # 1 hour
PSN_CACHE_TTL_ANALYZER_RESULTS=1800    # 30 minutes
PSN_CACHE_TTL_API_RESPONSES=300        # 5 minutes
```

## Usage

### Basic Usage with Decorators

```python
from paidsearchnav.cache.decorators import cache

@cache(ttl=3600, key_prefix="customer_list")
async def get_customer_list(account_id: str) -> List[Customer]:
    # Expensive operation that will be cached for 1 hour
    return await fetch_from_google_ads(account_id)

# Cache with namespace
@cache(ttl=1800, namespace_param="customer_id")
async def get_audit_results(customer_id: str, audit_id: str) -> AuditResult:
    # Results will be namespaced by customer_id
    return await fetch_audit_results(audit_id)

# Cache with conditions
@cache(ttl=300, condition=lambda result: result.success)
async def process_data(data: dict) -> ProcessResult:
    # Only cache successful results
    return await process(data)

# Bypass cache with refresh parameter
result = await get_customer_list(account_id, refresh=True)
```

### Manual Cache Operations

```python
from paidsearchnav.cache.manager import get_cache_manager

cache_manager = get_cache_manager()

# Set a value
await cache_manager.set("my_key", {"data": "value"}, ttl=3600)

# Get a value
value = await cache_manager.get("my_key")

# Delete a value
await cache_manager.delete("my_key")

# Clear cache with pattern
await cache_manager.clear("customer:*")  # Clear all customer-related keys

# Get cache statistics
stats = await cache_manager.get_stats()
```

### Key Building

The cache module provides automatic key building with namespacing:

```python
# Build a cache key
key = cache_manager.build_key("audit", "123", namespace="cust_456")
# Result: "paidsearchnav:cust_456:audit:123"
```

## Cache Patterns

### Customer Data
- **Key pattern**: `paidsearchnav:customer:{customer_id}`
- **TTL**: 1 hour
- **Use case**: Customer metadata, account information

### Audit Reports
- **Key pattern**: `paidsearchnav:{customer_id}:audit:{audit_id}`
- **TTL**: 24 hours
- **Use case**: Completed audit reports, historical data

### API Responses
- **Key pattern**: `paidsearchnav:api:{endpoint}:{hash}`
- **TTL**: 5 minutes
- **Use case**: Frequently accessed API responses

## Monitoring

### Health Check
```python
# Check if cache is available
is_healthy = await cache_manager.ping()
```

### Statistics
```python
stats = await cache_manager.get_stats()
# Returns:
{
    "backend": "redis",
    "connected": true,
    "version": "7.0.0",
    "used_memory": "1.5M",
    "hit_rate": 85.5,
    "keyspace_hits": 1000,
    "keyspace_misses": 200
}
```

## Headers

The API adds cache-related headers to responses:

- `X-Cache-Status`: `HIT` or `MISS`
- `Cache-Control`: Standard HTTP cache control directives

## Best Practices

1. **Use appropriate TTLs**: Balance between performance and data freshness
2. **Namespace by customer**: Prevent data leakage between customers
3. **Handle cache failures gracefully**: Always assume cache might be unavailable
4. **Monitor hit rates**: Aim for 80%+ hit rate for frequently accessed data
5. **Use refresh parameter**: Allow users to bypass cache when needed

## Performance Considerations

- Redis single-instance can handle 100k+ operations/second
- Use Redis Cluster for horizontal scaling
- Network latency is typically <1ms for local Redis
- JSON serialization adds minimal overhead (~0.1ms)

## Troubleshooting

### Cache not working
1. Check if `PSN_CACHE_ENABLED=true`
2. Verify Redis is running and accessible
3. Check logs for connection errors
4. Verify Redis URL format

### Low hit rate
1. Check if TTLs are too short
2. Verify key generation is consistent
3. Look for cache bypass patterns
4. Monitor cache evictions

### Performance issues
1. Check Redis memory usage
2. Monitor network latency
3. Consider using Redis Cluster
4. Optimize serialization for large objects