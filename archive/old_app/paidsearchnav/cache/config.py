"""Cache configuration models."""

from pydantic import BaseModel, Field


class RedisCacheConfig(BaseModel):
    """Redis cache configuration."""

    url: str = Field(
        default="redis://localhost:6379", description="Redis connection URL"
    )
    cluster: bool = Field(
        default=False, description="Whether to use Redis cluster mode"
    )
    password: str | None = Field(
        default=None, description="Redis password (if required)"
    )


class CacheTTLConfig(BaseModel):
    """Cache TTL configuration for different data types."""

    default: int = Field(default=300, description="Default TTL in seconds (5 minutes)")
    customer_list: int = Field(
        default=3600, description="TTL for customer list data (1 hour)"
    )
    audit_report: int = Field(
        default=86400, description="TTL for audit reports (24 hours)"
    )
    recommendations: int = Field(
        default=3600, description="TTL for recommendations (1 hour)"
    )
    analyzer_results: int = Field(
        default=1800, description="TTL for analyzer results (30 minutes)"
    )
    api_responses: int = Field(
        default=300, description="TTL for API response transformations (5 minutes)"
    )


class CacheConfig(BaseModel):
    """Cache configuration."""

    enabled: bool = Field(default=False, description="Whether caching is enabled")
    backend: str = Field(
        default="redis",
        description="Cache backend type (currently only 'redis' supported)",
    )
    redis: RedisCacheConfig = Field(
        default_factory=RedisCacheConfig, description="Redis-specific configuration"
    )
    ttl: CacheTTLConfig = Field(
        default_factory=CacheTTLConfig,
        description="TTL configuration for different data types",
    )
