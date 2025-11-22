"""Cache decorators for automatic caching."""

import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Callable, Optional, TypeVar

from .manager import get_cache_manager

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def cache(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    namespace_param: Optional[str] = None,
    exclude_params: Optional[list[str]] = None,
    condition: Optional[Callable[..., bool]] = None,
    bypass_param: str = "refresh",
) -> Callable[[F], F]:
    """Cache decorator for functions and methods.

    Args:
        ttl: Time to live in seconds (None uses default)
        key_prefix: Custom key prefix (defaults to function name)
        namespace_param: Parameter to use as namespace (e.g., "customer_id")
        exclude_params: Parameters to exclude from cache key
        condition: Function to determine if result should be cached
        bypass_param: Query parameter that bypasses cache (e.g., ?refresh=true)

    Example:
        @cache(ttl=3600, key_prefix="customer_list", namespace_param="account_id")
        async def get_customer_list(account_id: str, include_deleted: bool = False):
            # Expensive operation
            return await fetch_from_google_ads(account_id, include_deleted)
    """

    def decorator(func: F) -> F:
        # Get function signature for parameter inspection
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # Determine if function is async
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            if not cache_manager or not cache_manager.is_enabled:
                return await func(*args, **kwargs)

            # Check bypass parameter
            if bypass_param in kwargs and kwargs.get(bypass_param):
                logger.debug(
                    f"Bypassing cache for {func.__name__} due to {bypass_param}=true"
                )
                return await func(*args, **kwargs)

            # Build cache key
            cache_key = _build_cache_key(
                func,
                args,
                kwargs,
                key_prefix,
                namespace_param,
                exclude_params,
                param_names,
            )

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value

            logger.debug(f"Cache miss for key: {cache_key}")

            # Call the function
            result = await func(*args, **kwargs)

            # Check if result should be cached
            if condition is None or condition(result):
                # Determine TTL
                cache_ttl = ttl
                if cache_ttl is None:
                    # Use default TTL based on function name patterns
                    cache_ttl = _get_default_ttl(func.__name__, key_prefix)

                # Cache the result
                success = await cache_manager.set(cache_key, result, cache_ttl)
                if success:
                    logger.debug(
                        f"Cached result for key: {cache_key} (TTL: {cache_ttl}s)"
                    )
                else:
                    logger.warning(f"Failed to cache result for key: {cache_key}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't use cache
            logger.warning(
                f"Cache decorator on sync function {func.__name__} - caching disabled"
            )
            return func(*args, **kwargs)

        return async_wrapper if is_async else sync_wrapper

    return decorator


def cache_key(*key_parts: str) -> Callable[[F], F]:
    """Simple cache key decorator for explicit key control.

    Args:
        *key_parts: Parts of the cache key

    Example:
        @cache_key("reports", "summary")
        async def get_report_summary(report_id: str):
            return await generate_summary(report_id)
    """

    def decorator(func: F) -> F:
        return cache(key_prefix=":".join(key_parts))(func)

    return decorator


def _build_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_prefix: Optional[str],
    namespace_param: Optional[str],
    exclude_params: Optional[list[str]],
    param_names: list[str],
) -> str:
    """Build a cache key from function and arguments."""
    cache_manager = get_cache_manager()

    # Get all arguments as a dictionary
    bound_args = {}
    for i, arg in enumerate(args):
        if i < len(param_names):
            bound_args[param_names[i]] = arg
    bound_args.update(kwargs)

    # Extract namespace if specified
    namespace = None
    if namespace_param and namespace_param in bound_args:
        namespace = str(bound_args[namespace_param])

    # Remove excluded parameters
    if exclude_params:
        for param in exclude_params:
            bound_args.pop(param, None)

    # Remove bypass parameter
    bound_args.pop("refresh", None)

    # Use function name as prefix if not specified
    if not key_prefix:
        key_prefix = func.__name__

    # Create a stable hash of the arguments
    args_hash = _hash_arguments(bound_args)

    # Build the final key
    return cache_manager.build_key(key_prefix, args_hash, namespace=namespace)


def _hash_arguments(args: dict[str, Any]) -> str:
    """Create a stable hash of function arguments.

    Uses SHA-256 for better collision resistance than MD5.
    Returns 16 characters of the hash (64 bits) for reasonable
    collision resistance while keeping keys manageable.
    """
    # Sort keys for stability
    sorted_args = sorted(args.items())

    # Convert to JSON for hashing
    try:
        args_json = json.dumps(sorted_args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Fallback to string representation
        args_json = str(sorted_args)

    # Create hash using SHA-256
    return hashlib.sha256(args_json.encode()).hexdigest()[:16]


def _get_default_ttl(func_name: str, key_prefix: Optional[str]) -> int:
    """Get default TTL based on function name patterns."""
    # Define TTL patterns (in seconds)
    ttl_patterns = {
        # Long cache (24 hours)
        "report": 86400,
        "audit": 86400,
        "historical": 86400,
        # Medium cache (1 hour)
        "customer": 3600,
        "account": 3600,
        "recommendation": 3600,
        "analysis": 3600,
        # Short cache (5 minutes)
        "list": 300,
        "search": 300,
        "status": 300,
        "health": 300,
        # Very short cache (1 minute)
        "realtime": 60,
        "current": 60,
        "active": 60,
    }

    # Check key prefix first
    check_name = key_prefix or func_name
    check_name = check_name.lower()

    # Find matching pattern
    for pattern, ttl in ttl_patterns.items():
        if pattern in check_name:
            return ttl

    # Default to 5 minutes
    return 300
