"""Timeout configuration for BigQuery operations."""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CustomerTier(Enum):
    """Customer service tiers."""

    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Environment(Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class OperationTimeouts:
    """Timeout configuration for different BigQuery operations."""

    # Core operation timeouts (in seconds)
    query_timeout: int = 300  # 5 minutes for standard queries
    export_timeout: int = 1800  # 30 minutes for large exports
    connection_timeout: int = 30  # 30 seconds for connection establishment
    auth_timeout: int = 10  # 10 seconds for authentication

    # Advanced timeouts
    job_poll_interval: int = 5  # 5 seconds between job status polls
    max_retry_attempts: int = 3  # Maximum retry attempts
    retry_delay: int = 2  # Delay between retries (seconds)

    def __post_init__(self) -> None:
        """Validate timeout values."""
        if self.query_timeout <= 0:
            raise ValueError("Query timeout must be positive")
        if self.export_timeout <= 0:
            raise ValueError("Export timeout must be positive")
        if self.connection_timeout <= 0:
            raise ValueError("Connection timeout must be positive")
        if self.auth_timeout <= 0:
            raise ValueError("Auth timeout must be positive")


class TimeoutConfigManager:
    """Manages timeout configurations based on customer tier and environment."""

    # Base timeout configurations by customer tier
    _TIER_CONFIGS = {
        CustomerTier.STANDARD: OperationTimeouts(
            query_timeout=180,  # 3 minutes
            export_timeout=900,  # 15 minutes
            connection_timeout=30,
            auth_timeout=10,
        ),
        CustomerTier.PREMIUM: OperationTimeouts(
            query_timeout=300,  # 5 minutes
            export_timeout=1800,  # 30 minutes
            connection_timeout=30,
            auth_timeout=10,
        ),
        CustomerTier.ENTERPRISE: OperationTimeouts(
            query_timeout=600,  # 10 minutes
            export_timeout=3600,  # 60 minutes
            connection_timeout=45,
            auth_timeout=15,
        ),
    }

    # Environment multipliers
    _ENV_MULTIPLIERS = {
        Environment.DEVELOPMENT: 0.5,  # Shorter timeouts for dev
        Environment.STAGING: 0.8,  # Slightly shorter for staging
        Environment.PRODUCTION: 1.0,  # Full timeouts for prod
    }

    def __init__(self) -> None:
        """Initialize timeout configuration manager."""
        self._environment = self._detect_environment()
        self._custom_overrides = self._load_environment_overrides()

    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables."""
        env_name = os.getenv("PSN_ENVIRONMENT", "development").lower()

        try:
            return Environment(env_name)
        except ValueError:
            logger.warning(
                f"Unknown environment '{env_name}', defaulting to development"
            )
            return Environment.DEVELOPMENT

    def _load_environment_overrides(self) -> Dict[str, int]:
        """Load timeout overrides from environment variables with validation."""
        overrides = {}

        # Environment variable mapping with validation bounds
        env_vars = {
            "PSN_BIGQUERY_QUERY_TIMEOUT": ("query_timeout", 10, 3600),  # 10s to 1 hour
            "PSN_BIGQUERY_EXPORT_TIMEOUT": (
                "export_timeout",
                60,
                14400,
            ),  # 1min to 4 hours
            "PSN_BIGQUERY_CONNECTION_TIMEOUT": (
                "connection_timeout",
                5,
                300,
            ),  # 5s to 5 min
            "PSN_BIGQUERY_AUTH_TIMEOUT": ("auth_timeout", 1, 120),  # 1s to 2 min
            "PSN_BIGQUERY_JOB_POLL_INTERVAL": (
                "job_poll_interval",
                1,
                60,
            ),  # 1s to 1 min
            "PSN_BIGQUERY_MAX_RETRY_ATTEMPTS": (
                "max_retry_attempts",
                1,
                10,
            ),  # 1 to 10 attempts
            "PSN_BIGQUERY_RETRY_DELAY": ("retry_delay", 1, 60),  # 1s to 1 min
        }

        for env_var, (config_key, min_val, max_val) in env_vars.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    int_value = int(value)
                    if min_val <= int_value <= max_val:
                        overrides[config_key] = int_value
                        logger.info(
                            f"Using environment override: {config_key}={int_value}"
                        )
                    else:
                        logger.warning(
                            f"Invalid value for {env_var}: {value} "
                            f"(must be between {min_val} and {max_val})"
                        )
                except ValueError:
                    logger.warning(
                        f"Invalid value for {env_var}: {value} (must be integer)"
                    )

        return overrides

    def get_timeout_config(
        self, customer_tier: CustomerTier, operation_type: Optional[str] = None
    ) -> OperationTimeouts:
        """
        Get timeout configuration for a customer tier and operation.

        Args:
            customer_tier: Customer service tier
            operation_type: Optional operation type for specific overrides

        Returns:
            Configured timeout settings
        """
        # Get base configuration for tier
        base_config = self._TIER_CONFIGS[customer_tier]

        # Apply environment multiplier
        env_multiplier = self._ENV_MULTIPLIERS[self._environment]

        # Create adjusted configuration
        adjusted_config = OperationTimeouts(
            query_timeout=int(base_config.query_timeout * env_multiplier),
            export_timeout=int(base_config.export_timeout * env_multiplier),
            connection_timeout=int(base_config.connection_timeout * env_multiplier),
            auth_timeout=int(base_config.auth_timeout * env_multiplier),
            job_poll_interval=base_config.job_poll_interval,
            max_retry_attempts=base_config.max_retry_attempts,
            retry_delay=base_config.retry_delay,
        )

        # Apply operation-specific adjustments
        if operation_type:
            adjusted_config = self._apply_operation_adjustments(
                adjusted_config, operation_type
            )

        # Apply environment variable overrides (after operation adjustments)
        if self._custom_overrides:
            for key, value in self._custom_overrides.items():
                if hasattr(adjusted_config, key):
                    setattr(adjusted_config, key, value)

        return adjusted_config

    def _apply_operation_adjustments(
        self, config: OperationTimeouts, operation_type: str
    ) -> OperationTimeouts:
        """Apply operation-specific timeout adjustments."""
        # Operation-specific multipliers
        operation_multipliers = {
            "large_export": 2.0,  # Double timeout for large exports
            "complex_query": 1.5,  # 50% more time for complex queries
            "batch_operation": 3.0,  # Triple timeout for batch operations
        }

        multiplier = operation_multipliers.get(operation_type, 1.0)

        if multiplier != 1.0:
            return OperationTimeouts(
                query_timeout=int(config.query_timeout * multiplier),
                export_timeout=int(config.export_timeout * multiplier),
                connection_timeout=config.connection_timeout,  # Keep connection timeout unchanged
                auth_timeout=config.auth_timeout,  # Keep auth timeout unchanged
                job_poll_interval=config.job_poll_interval,
                max_retry_attempts=config.max_retry_attempts,
                retry_delay=config.retry_delay,
            )

        return config

    @property
    def environment(self) -> Environment:
        """Get current environment."""
        return self._environment

    def get_fallback_timeout(self, operation: str) -> int:
        """Get fallback timeout for when tier-specific config fails."""
        fallback_timeouts = {
            "query": 120,  # 2 minutes
            "export": 600,  # 10 minutes
            "connection": 15,  # 15 seconds
            "auth": 5,  # 5 seconds
        }
        return fallback_timeouts.get(operation, 60)


# Global timeout manager instance
timeout_manager = TimeoutConfigManager()


def get_timeout_config(
    customer_tier: CustomerTier, operation_type: Optional[str] = None
) -> OperationTimeouts:
    """
    Convenience function to get timeout configuration.

    Args:
        customer_tier: Customer service tier
        operation_type: Optional operation type for specific overrides

    Returns:
        Configured timeout settings
    """
    return timeout_manager.get_timeout_config(customer_tier, operation_type)
