"""Tests for BigQuery timeout configuration."""

import os
from unittest.mock import patch

import pytest

from paidsearchnav.platforms.bigquery.timeout_config import (
    CustomerTier,
    Environment,
    OperationTimeouts,
    TimeoutConfigManager,
    get_timeout_config,
    timeout_manager,
)


class TestOperationTimeouts:
    """Test OperationTimeouts dataclass."""

    def test_default_values(self):
        """Test default timeout values."""
        config = OperationTimeouts()

        assert config.query_timeout == 300  # 5 minutes
        assert config.export_timeout == 1800  # 30 minutes
        assert config.connection_timeout == 30  # 30 seconds
        assert config.auth_timeout == 10  # 10 seconds
        assert config.job_poll_interval == 5
        assert config.max_retry_attempts == 3
        assert config.retry_delay == 2

    def test_custom_values(self):
        """Test custom timeout values."""
        config = OperationTimeouts(
            query_timeout=600,
            export_timeout=3600,
            connection_timeout=45,
            auth_timeout=15,
        )

        assert config.query_timeout == 600
        assert config.export_timeout == 3600
        assert config.connection_timeout == 45
        assert config.auth_timeout == 15

    def test_validation_query_timeout(self):
        """Test validation for query timeout."""
        with pytest.raises(ValueError, match="Query timeout must be positive"):
            OperationTimeouts(query_timeout=0)

        with pytest.raises(ValueError, match="Query timeout must be positive"):
            OperationTimeouts(query_timeout=-1)

    def test_validation_export_timeout(self):
        """Test validation for export timeout."""
        with pytest.raises(ValueError, match="Export timeout must be positive"):
            OperationTimeouts(export_timeout=0)

        with pytest.raises(ValueError, match="Export timeout must be positive"):
            OperationTimeouts(export_timeout=-1)

    def test_validation_connection_timeout(self):
        """Test validation for connection timeout."""
        with pytest.raises(ValueError, match="Connection timeout must be positive"):
            OperationTimeouts(connection_timeout=0)

    def test_validation_auth_timeout(self):
        """Test validation for auth timeout."""
        with pytest.raises(ValueError, match="Auth timeout must be positive"):
            OperationTimeouts(auth_timeout=0)


class TestTimeoutConfigManager:
    """Test TimeoutConfigManager class."""

    def test_detect_environment_default(self):
        """Test environment detection with default value."""
        with patch.dict(os.environ, {}, clear=True):
            manager = TimeoutConfigManager()
            assert manager.environment == Environment.DEVELOPMENT

    def test_detect_environment_from_env_var(self):
        """Test environment detection from environment variable."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            assert manager.environment == Environment.PRODUCTION

    def test_detect_environment_invalid(self):
        """Test environment detection with invalid value."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "invalid"}):
            manager = TimeoutConfigManager()
            assert manager.environment == Environment.DEVELOPMENT

    def test_tier_configs_standard(self):
        """Test standard tier configuration in production environment."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            assert config.query_timeout == 180  # 3 minutes
            assert config.export_timeout == 900  # 15 minutes

    def test_tier_configs_premium(self):
        """Test premium tier configuration in production environment."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.PREMIUM)

            assert config.query_timeout == 300  # 5 minutes
            assert config.export_timeout == 1800  # 30 minutes

    def test_tier_configs_enterprise(self):
        """Test enterprise tier configuration in production environment."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.ENTERPRISE)

            assert config.query_timeout == 600  # 10 minutes
            assert config.export_timeout == 3600  # 60 minutes

    def test_environment_multipliers_development(self):
        """Test development environment multipliers."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "development"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Development has 0.5 multiplier
            assert config.query_timeout == 90  # 180 * 0.5
            assert config.export_timeout == 450  # 900 * 0.5

    def test_environment_multipliers_staging(self):
        """Test staging environment multipliers."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "staging"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Staging has 0.8 multiplier
            assert config.query_timeout == 144  # 180 * 0.8
            assert config.export_timeout == 720  # 900 * 0.8

    def test_environment_multipliers_production(self):
        """Test production environment multipliers."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Production has 1.0 multiplier
            assert config.query_timeout == 180  # 180 * 1.0
            assert config.export_timeout == 900  # 900 * 1.0

    def test_environment_overrides(self):
        """Test environment variable overrides."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "999",
            "PSN_BIGQUERY_EXPORT_TIMEOUT": "1999",
            "PSN_BIGQUERY_CONNECTION_TIMEOUT": "99",
            "PSN_BIGQUERY_AUTH_TIMEOUT": "19",
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            assert config.query_timeout == 999
            assert config.export_timeout == 1999
            assert config.connection_timeout == 99
            assert config.auth_timeout == 19

    def test_environment_overrides_invalid_values(self):
        """Test environment variable overrides with invalid values."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "invalid",
        }
        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Should use default value when invalid
            assert config.query_timeout == 180

    def test_operation_adjustments_large_export(self):
        """Test operation-specific adjustments for large export."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD, "large_export")

            # Large export should have 2x multiplier
            assert config.query_timeout == 360  # 180 * 2
            assert config.export_timeout == 1800  # 900 * 2

    def test_operation_adjustments_complex_query(self):
        """Test operation-specific adjustments for complex query."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD, "complex_query")

            # Complex query should have 1.5x multiplier
            assert config.query_timeout == 270  # 180 * 1.5
            assert config.export_timeout == 1350  # 900 * 1.5

    def test_operation_adjustments_batch_operation(self):
        """Test operation-specific adjustments for batch operation."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(
                CustomerTier.STANDARD, "batch_operation"
            )

            # Batch operation should have 3x multiplier
            assert config.query_timeout == 540  # 180 * 3
            assert config.export_timeout == 2700  # 900 * 3

    def test_operation_adjustments_unknown(self):
        """Test operation-specific adjustments for unknown operation."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(
                CustomerTier.STANDARD, "unknown_operation"
            )

            # Unknown operation should have no multiplier
            assert config.query_timeout == 180
            assert config.export_timeout == 900

    def test_fallback_timeouts(self):
        """Test fallback timeout values."""
        manager = TimeoutConfigManager()

        assert manager.get_fallback_timeout("query") == 120
        assert manager.get_fallback_timeout("export") == 600
        assert manager.get_fallback_timeout("connection") == 15
        assert manager.get_fallback_timeout("auth") == 5
        assert manager.get_fallback_timeout("unknown") == 60


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_timeout_config_function(self):
        """Test get_timeout_config convenience function."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            # Create a new manager to pick up environment changes
            from paidsearchnav.platforms.bigquery.timeout_config import (
                TimeoutConfigManager,
            )

            with patch(
                "paidsearchnav.platforms.bigquery.timeout_config.timeout_manager",
                TimeoutConfigManager(),
            ):
                config = get_timeout_config(CustomerTier.PREMIUM)

                assert isinstance(config, OperationTimeouts)
                assert config.query_timeout == 300  # 5 minutes

    def test_get_timeout_config_with_operation(self):
        """Test get_timeout_config with operation type."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "production"}):
            # Create a new manager to pick up environment changes
            from paidsearchnav.platforms.bigquery.timeout_config import (
                TimeoutConfigManager,
            )

            with patch(
                "paidsearchnav.platforms.bigquery.timeout_config.timeout_manager",
                TimeoutConfigManager(),
            ):
                config = get_timeout_config(CustomerTier.PREMIUM, "large_export")

                # Should have large_export multiplier (2x)
                assert config.query_timeout == 600  # 300 * 2

    def test_global_timeout_manager(self):
        """Test global timeout manager instance."""
        assert isinstance(timeout_manager, TimeoutConfigManager)

        # Test that it works
        config = timeout_manager.get_timeout_config(CustomerTier.STANDARD)
        assert isinstance(config, OperationTimeouts)


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_production_enterprise_large_export(self):
        """Test production enterprise tier with large export."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_EXPORT_TIMEOUT": "7200",  # Override to 2 hours
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.ENTERPRISE, "large_export")

            # Should use override value instead of calculated value
            assert config.export_timeout == 7200
            assert config.query_timeout == 1200  # 600 * 2 (large_export multiplier)

    def test_development_standard_with_overrides(self):
        """Test development environment with standard tier and overrides."""
        env_vars = {
            "PSN_ENVIRONMENT": "development",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "60",  # Very short for dev
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Override should take precedence
            assert config.query_timeout == 60
            # Export timeout should still use development multiplier
            assert config.export_timeout == 450  # 900 * 0.5

    def test_staging_premium_complex_query(self):
        """Test staging environment with premium tier and complex query."""
        with patch.dict(os.environ, {"PSN_ENVIRONMENT": "staging"}):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.PREMIUM, "complex_query")

            # Base: 300, environment: 0.8, operation: 1.5
            assert config.query_timeout == 360  # 300 * 0.8 * 1.5
            assert config.export_timeout == 2160  # 1800 * 0.8 * 1.5

    def test_environment_variable_validation_bounds(self):
        """Test environment variable validation with bounds checking."""
        # Test values within bounds
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "600",  # Within bounds (10-3600)
            "PSN_BIGQUERY_EXPORT_TIMEOUT": "7200",  # Within bounds (60-14400)
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            assert config.query_timeout == 600
            assert config.export_timeout == 7200

    def test_environment_variable_validation_out_of_bounds(self):
        """Test environment variable validation rejects out-of-bounds values."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "5",  # Below minimum (10)
            "PSN_BIGQUERY_EXPORT_TIMEOUT": "20000",  # Above maximum (14400)
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Should use default values when environment vars are out of bounds
            assert config.query_timeout == 180  # Default standard tier value
            assert config.export_timeout == 900  # Default standard tier value

    def test_environment_variable_validation_invalid_types(self):
        """Test environment variable validation rejects non-integer values."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_BIGQUERY_QUERY_TIMEOUT": "not_a_number",
            "PSN_BIGQUERY_EXPORT_TIMEOUT": "12.5",  # Float instead of int
        }

        with patch.dict(os.environ, env_vars):
            manager = TimeoutConfigManager()
            config = manager.get_timeout_config(CustomerTier.STANDARD)

            # Should use default values when environment vars are invalid
            assert config.query_timeout == 180  # Default standard tier value
            assert config.export_timeout == 900  # Default standard tier value
