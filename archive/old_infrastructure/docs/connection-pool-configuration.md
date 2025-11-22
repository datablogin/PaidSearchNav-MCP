# Connection Pool Configuration Guide

This guide provides comprehensive documentation for configuring database and cache connection pools in PaidSearchNav.

## Overview

PaidSearchNav uses connection pooling to efficiently manage database and cache connections, reducing overhead and improving performance. The system supports multiple pool implementations:

- **SQLAlchemy Database Pools** - For PostgreSQL, MySQL, and SQLite databases
- **Redis Connection Pools** - For caching and rate limiting

## Database Connection Pools

### SQLAlchemy Pool Configuration

The primary database connection pool is configured through the `DatabaseConnection` class in `paidsearchnav/integrations/database.py`.

#### Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `pool_size` | 10 | 1-50 | Number of connections to maintain in the pool |
| `max_overflow` | 20 | 0-100 | Maximum overflow connections beyond pool_size |
| `pool_timeout` | 30.0 | 1-300 | Seconds to wait before timing out when acquiring a connection |
| `pool_recycle` | 3600 | 300-7200 | Seconds before recycling connections (prevents timeout) |
| `pool_pre_ping` | True | - | Test connections before use to verify they are still valid |

#### Pool Types by Database

- **PostgreSQL/MySQL**: Uses `QueuePool` with full pooling capabilities
- **SQLite**: Uses `NullPool` (no pooling) for thread safety

### Configuration Examples

#### Basic Configuration

```python
from paidsearchnav.integrations.database import DatabaseConnection

# Development configuration (SQLite)
db_conn = DatabaseConnection(
    connection_string="sqlite:///./paidsearchnav.db"
)

# Production configuration (PostgreSQL)
db_conn = DatabaseConnection(
    connection_string="postgresql://user:pass@localhost/dbname",
    pool_size=20,
    max_overflow=40,
    pool_timeout=60.0
)
```

#### Environment Variables

```bash
# Database connection with pool settings
export PSN_STORAGE_CONNECTION_STRING="postgresql://user:pass@localhost/dbname"
export PSN_DB_POOL_SIZE=20
export PSN_DB_MAX_OVERFLOW=40
export PSN_DB_POOL_TIMEOUT=60
```

### Best Practices for Different Scenarios

#### High-Traffic Production Environment

```python
# Recommended settings for high concurrency
config = {
    "pool_size": 25,        # Higher base pool
    "max_overflow": 50,     # Allow more overflow connections
    "pool_timeout": 30.0,   # Standard timeout
    "pool_recycle": 1800,   # Recycle every 30 minutes
    "pool_pre_ping": True   # Always verify connections
}
```

#### Low-Traffic Development Environment

```python
# Conservative settings for development
config = {
    "pool_size": 5,         # Smaller pool
    "max_overflow": 10,     # Limited overflow
    "pool_timeout": 10.0,   # Shorter timeout
    "pool_recycle": 3600,   # Less frequent recycling
    "pool_pre_ping": True   # Still verify connections
}
```

#### Batch Processing / ETL Workloads

```python
# Settings optimized for long-running queries
config = {
    "pool_size": 15,        # Moderate pool size
    "max_overflow": 30,     # Good overflow capacity
    "pool_timeout": 120.0,  # Longer timeout for slow queries
    "pool_recycle": 7200,   # Less recycling for stable connections
    "pool_pre_ping": True   # Verify connections
}
```

## Redis Connection Pools

### Cache Connection Pool

The Redis cache pool is configured in `paidsearchnav/cache/backends.py`.

#### Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_connections` | 50 | 10-200 | Maximum connections in the Redis pool |

#### Configuration Example

```python
from paidsearchnav.cache.backends import RedisCache

# Standard Redis configuration
cache = RedisCache(
    url="redis://localhost:6379/0",
    max_connections=100  # Increase for high-traffic scenarios
)

# Redis Cluster configuration
cache = RedisCache(
    startup_nodes=[
        {"host": "node1", "port": 7000},
        {"host": "node2", "port": 7001},
        {"host": "node3", "port": 7002}
    ],
    max_connections=150  # Higher limit for cluster
)
```

### Rate Limiting Connection Pool

The rate limiting system uses a separate Redis connection pool configured through `CentralizedStateStorage`.

```python
# Environment variable configuration
export PSN_REDIS_URL="redis://localhost:6379/1"
export PSN_REDIS_MAX_CONNECTIONS=20
```

## Tuning Guide

### Determining Optimal Pool Size

1. **Calculate Base Pool Size**:
   ```
   pool_size = (number_of_workers × average_connections_per_worker)
   ```

2. **Add Overflow Capacity**:
   ```
   max_overflow = pool_size × 2
   ```

3. **Monitor and Adjust**:
   - Track `pool_in_use` vs `pool_size`
   - If consistently at capacity, increase pool_size
   - If rarely above 50% usage, decrease pool_size

### Performance Considerations

#### Connection Overhead

- **PostgreSQL**: ~5-10ms per new connection
- **MySQL**: ~3-7ms per new connection
- **Redis**: ~1-3ms per new connection

#### Memory Usage

- Each database connection uses ~1-5MB of memory
- Redis connections use ~100KB-1MB depending on buffer sizes

### Monitoring Pool Health

Use the built-in metrics to monitor pool performance:

```python
from paidsearchnav.api.routes.analysis import AnalysisStorageService

service = AnalysisStorageService()
metrics = await service.get_performance_metrics()

print(f"Pool Size: {metrics['pool_size']}")
print(f"Connections In Use: {metrics['pool_in_use']}")
print(f"Connections Available: {metrics['pool_available']}")
```

## Troubleshooting Common Issues

### 1. Pool Timeout Errors

**Symptoms**: `QueuePool limit of size X overflow Y reached`

**Solutions**:
- Increase `pool_size` and `max_overflow`
- Check for connection leaks (connections not being returned)
- Review long-running queries

### 2. Stale Connections

**Symptoms**: `OperationalError: server closed the connection unexpectedly`

**Solutions**:
- Enable `pool_pre_ping=True`
- Reduce `pool_recycle` time
- Check firewall/network timeout settings

### 3. High Connection Churn

**Symptoms**: Frequent connection creation/destruction in logs

**Solutions**:
- Increase `pool_size` to reduce overflow usage
- Increase `pool_recycle` time for stable connections
- Check for application restarts or connection errors

### 4. Memory Exhaustion

**Symptoms**: Out of memory errors, high memory usage

**Solutions**:
- Reduce `pool_size` and `max_overflow`
- Check for connection leaks
- Monitor query result sizes

## Advanced Configuration

### Custom Pool Classes

For specialized requirements, you can implement custom pool classes:

```python
from sqlalchemy.pool import Pool

class CustomPool(Pool):
    def __init__(self, creator, **kw):
        super().__init__(creator, **kw)
        # Custom initialization
    
    def _do_get(self):
        # Custom connection acquisition logic
        return super()._do_get()
```

### Connection Lifecycle Hooks

Add custom logic for connection events:

```python
from sqlalchemy import event
from sqlalchemy.pool import Pool

@event.listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Custom connection initialization
    if 'sqlite' in connection_record.info['dialect'].name:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

## Security Considerations

1. **Connection String Security**:
   - Never hardcode credentials
   - Use environment variables or secure vaults
   - Rotate credentials regularly

2. **SSL/TLS Configuration**:
   ```python
   # PostgreSQL with SSL
   connection_string = "postgresql://user:pass@host/db?sslmode=require"
   
   # MySQL with SSL
   connection_string = "mysql://user:pass@host/db?ssl_ca=/path/to/ca.pem"
   ```

3. **Connection Limits**:
   - Set appropriate limits to prevent DoS
   - Monitor for unusual connection patterns
   - Implement rate limiting at application level

## Recommended Configurations by Deployment Size

### Small (< 100 concurrent users)
```python
{
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "redis_max_connections": 50
}
```

### Medium (100-1000 concurrent users)
```python
{
    "pool_size": 25,
    "max_overflow": 50,
    "pool_timeout": 30,
    "redis_max_connections": 100
}
```

### Large (> 1000 concurrent users)
```python
{
    "pool_size": 50,
    "max_overflow": 100,
    "pool_timeout": 60,
    "redis_max_connections": 200
}
```

## References

- [SQLAlchemy Pool Documentation](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [Redis-py Connection Pooling](https://redis-py.readthedocs.io/en/stable/connections.html)
- [PostgreSQL Connection Pooling Best Practices](https://wiki.postgresql.org/wiki/Number_Of_Database_Connections)