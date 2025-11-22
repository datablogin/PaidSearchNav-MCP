"""Tests for enhanced secrets handling features."""

import logging
from io import StringIO
from unittest.mock import MagicMock

import pytest

from paidsearchnav.logging.secrets import (
    SecretsRegistry,
    get_secrets_registry,
    mask_secrets,
)


class TestSecretsRegistryEnhancements:
    """Test enhanced features of SecretsRegistry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = SecretsRegistry()

    def test_add_whitelist_pattern(self):
        """Test adding whitelist patterns for false positives."""
        # Add a pattern to whitelist example IDs that look like secrets
        self.registry.add_whitelist_pattern(r"example-[a-f0-9]{32}")

        # This should normally be detected as a secret (hex pattern)
        test_value = "example-abcd1234567890abcd1234567890abcd"

        # But with whitelist, it should not be considered a secret
        assert not self.registry.contains_secret(test_value)

        # Regular secrets should still be detected
        assert self.registry.contains_secret("sk-1234567890abcdef1234567890abcdef")

    def test_add_invalid_whitelist_pattern_raises_error(self):
        """Test that invalid whitelist patterns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid whitelist pattern"):
            self.registry.add_whitelist_pattern("[invalid regex")

    def test_whitelist_in_mask_secrets_in_dict(self):
        """Test that whitelist works in dictionary masking."""
        self.registry.add_whitelist_pattern(r"test-example-[0-9]+")

        data = {
            "real_secret": "sk-1234567890abcdef1234567890abcdef",  # Should be masked
            "example_id": "test-example-12345",  # Should NOT be masked (whitelisted)
            "normal_field": "normal_value",  # Should not be masked
        }

        masked = self.registry.mask_secrets_in_dict(data)

        assert masked["real_secret"] == "***REDACTED***"
        assert masked["example_id"] == "test-example-12345"  # Not masked
        assert masked["normal_field"] == "normal_value"

    def test_disable_masking_for_logger(self):
        """Test disabling masking for specific loggers."""
        logger_name = "high_throughput_logger"

        # Initially masking is enabled
        assert not self.registry.is_logger_masking_disabled(logger_name)

        # Disable masking
        self.registry.disable_masking_for_logger(logger_name)
        assert self.registry.is_logger_masking_disabled(logger_name)

        # Re-enable masking
        self.registry.enable_masking_for_logger(logger_name)
        assert not self.registry.is_logger_masking_disabled(logger_name)

    def test_masking_disabled_logger_performance_optimization(self):
        """Test that disabled loggers skip masking entirely."""
        logger_name = "performance_logger"
        self.registry.disable_masking_for_logger(logger_name)

        data = {
            "password": "secret123",
            "api_key": "sk-1234567890abcdef1234567890abcdef",
        }

        # Should return original data without masking
        result = self.registry.mask_secrets_in_dict(data, logger_name=logger_name)
        assert result == data  # No masking applied

        # But other loggers should still have masking
        result2 = self.registry.mask_secrets_in_dict(data, logger_name="other_logger")
        assert result2["password"] == "***REDACTED***"
        assert result2["api_key"] == "***REDACTED***"

    def test_audit_logging_configuration(self):
        """Test audit logging configuration."""
        # Initially audit logging is disabled
        assert not self.registry._enable_audit_logging
        assert self.registry._audit_logger is None

        # Enable with default logger
        self.registry.enable_audit_logging()
        assert self.registry._enable_audit_logging
        assert self.registry._audit_logger is not None
        assert self.registry._audit_logger.name == "paidsearchnav.security.audit"

        # Enable with custom logger
        custom_logger = logging.getLogger("custom.audit")
        self.registry.enable_audit_logging(custom_logger)
        assert self.registry._audit_logger == custom_logger

        # Disable audit logging
        self.registry.disable_audit_logging()
        assert not self.registry._enable_audit_logging
        assert self.registry._audit_logger is None

    def test_audit_logging_events(self):
        """Test that audit events are logged when secrets are detected."""
        # Set up audit logging with a test logger
        audit_logger = logging.getLogger("test.audit")
        audit_logger.setLevel(logging.DEBUG)

        # Capture audit log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        audit_logger.addHandler(handler)

        self.registry.enable_audit_logging(audit_logger)

        # Test sensitive field detection
        data = {"password": "secret123"}
        self.registry.mask_secrets_in_dict(data)

        # Check that audit event was logged
        log_output = log_capture.getvalue()
        assert "Secret detected and masked" in log_output

        # Clean up
        audit_logger.removeHandler(handler)

    def test_audit_logging_disabled_no_events(self):
        """Test that no audit events are logged when audit logging is disabled."""
        # Set up a test logger but don't enable audit logging
        audit_logger = logging.getLogger("test.audit.disabled")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        audit_logger.addHandler(handler)

        # Process data with secrets
        data = {"password": "secret123"}
        self.registry.mask_secrets_in_dict(data)

        # Should be no audit events
        log_output = log_capture.getvalue()
        assert "Secret detected and masked" not in log_output

        # Clean up
        audit_logger.removeHandler(handler)


class TestMaskSecretsEnhanced:
    """Test enhanced mask_secrets function."""

    def setup_method(self):
        """Reset global state before each test."""
        registry = get_secrets_registry()
        registry._disabled_loggers.clear()
        registry.disable_audit_logging()

    def test_mask_secrets_with_logger_name(self):
        """Test mask_secrets function with logger name parameter."""
        registry = get_secrets_registry()

        # Disable masking for a specific logger
        logger_name = "test_disabled_logger"
        registry.disable_masking_for_logger(logger_name)

        data = {"password": "secret123"}

        # Should skip masking for disabled logger
        result1 = mask_secrets(data, logger_name=logger_name)
        assert result1 == data

        # Should apply masking for other loggers
        result2 = mask_secrets(data, logger_name="other_logger")
        assert result2["password"] == "***REDACTED***"

        # Clean up
        registry.enable_masking_for_logger(logger_name)

    def test_mask_secrets_audit_logging_for_strings(self):
        """Test that audit logging works for string masking."""
        registry = get_secrets_registry()

        # Set up audit logging
        audit_logger = logging.getLogger("test.string.audit")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        audit_logger.addHandler(handler)

        registry.enable_audit_logging(audit_logger)

        # Mask a string with a secret
        text = "My API key is sk-1234567890abcdef1234567890abcdef"
        mask_secrets(text)

        # Check audit event was logged
        log_output = log_capture.getvalue()
        assert "Secret detected and masked" in log_output

        # Clean up
        audit_logger.removeHandler(handler)
        registry.disable_audit_logging()


class TestConfigurationIntegration:
    """Test integration with logging configuration."""

    def setup_method(self):
        """Reset global state before each test."""
        registry = get_secrets_registry()
        registry._disabled_loggers.clear()
        registry.disable_audit_logging()

    def test_whitelist_patterns_from_config(self):
        """Test loading whitelist patterns from configuration."""
        from paidsearchnav.logging.config import LogConfig

        config = LogConfig(
            whitelist_patterns=["test-pattern-[0-9]+", "example-[a-f0-9]{8}"]
        )

        # This would normally be done in configure_logging
        registry = get_secrets_registry()
        for pattern in config.whitelist_patterns:
            registry.add_whitelist_pattern(pattern)

        # Test that whitelisted patterns are not masked
        assert not registry.contains_secret("test-pattern-12345")
        assert not registry.contains_secret("example-abcd1234")

        # But real secrets are still detected
        assert registry.contains_secret("sk-1234567890abcdef1234567890abcdef")

    def test_disabled_loggers_from_config(self):
        """Test loading disabled logger list from configuration."""
        from paidsearchnav.logging.config import LogConfig

        config = LogConfig(
            disabled_masking_loggers=["performance.logger", "high.throughput"]
        )

        # This would normally be done in configure_logging
        registry = get_secrets_registry()
        for logger_name in config.disabled_masking_loggers:
            registry.disable_masking_for_logger(logger_name)

        # Test that specified loggers have masking disabled
        assert registry.is_logger_masking_disabled("performance.logger")
        assert registry.is_logger_masking_disabled("high.throughput")
        assert not registry.is_logger_masking_disabled("other.logger")

    def test_audit_logging_from_config(self):
        """Test enabling audit logging from configuration."""
        from paidsearchnav.logging.config import LogConfig

        config = LogConfig(enable_audit_logging=True)

        # This would normally be done in configure_logging
        registry = get_secrets_registry()
        if config.enable_audit_logging:
            registry.enable_audit_logging()

        # Test that audit logging is enabled
        assert registry._enable_audit_logging
        assert registry._audit_logger is not None


class TestPerformanceOptimizations:
    """Test performance optimization features."""

    def test_early_exit_for_disabled_loggers(self):
        """Test that disabled loggers exit early without processing."""
        registry = get_secrets_registry()

        # Store original methods
        original_mask_dict = registry.mask_secrets_in_dict
        original_mask_list = registry._mask_secrets_in_list
        original_mask_string = registry._mask_secrets_in_string

        try:
            # Mock the masking methods to track if they're called
            registry.mask_secrets_in_dict = MagicMock(return_value={})
            registry._mask_secrets_in_list = MagicMock(return_value=[])
            registry._mask_secrets_in_string = MagicMock(return_value="")

            logger_name = "disabled_logger"
            registry.disable_masking_for_logger(logger_name)

            # Test different data types
            test_data = {"password": "secret"}
            result = mask_secrets(test_data, logger_name=logger_name)

            # Should return original data without calling masking methods
            assert result == test_data
            registry.mask_secrets_in_dict.assert_not_called()
        finally:
            # Restore original methods
            registry.mask_secrets_in_dict = original_mask_dict
            registry._mask_secrets_in_list = original_mask_list
            registry._mask_secrets_in_string = original_mask_string
            # Clean up disabled logger
            registry.enable_masking_for_logger(logger_name)

    def test_whitelist_checked_before_patterns(self):
        """Test that whitelist is checked before expensive pattern matching."""
        registry = SecretsRegistry()

        # Add a whitelist pattern
        registry.add_whitelist_pattern(r"whitelist-[a-f0-9]{32}")

        # Mock the secret patterns to track if they're checked
        original_patterns = registry._secret_patterns
        registry._secret_patterns = [MagicMock() for _ in original_patterns]

        # Test a whitelisted value
        test_value = "whitelist-abcd1234567890abcd1234567890abcd"
        result = registry.contains_secret(test_value)

        # Should return False without checking secret patterns
        assert not result
        for mock_pattern in registry._secret_patterns:
            mock_pattern.search.assert_not_called()


class TestErrorHandling:
    """Test error handling in enhanced features."""

    def setup_method(self):
        """Reset global state before each test."""
        # Get fresh registry for each test
        registry = get_secrets_registry()
        # Clear any disabled loggers from previous tests
        registry._disabled_loggers.clear()
        # Ensure audit logging is disabled
        registry.disable_audit_logging()

    def test_invalid_whitelist_pattern_handling(self):
        """Test graceful handling of invalid whitelist patterns."""
        registry = SecretsRegistry()

        with pytest.raises(ValueError):
            registry.add_whitelist_pattern("[invalid")

    def test_audit_logging_with_none_logger(self):
        """Test that audit logging handles None logger gracefully."""
        registry = SecretsRegistry()

        # Enable audit logging but somehow logger becomes None
        registry._enable_audit_logging = True
        registry._audit_logger = None

        # Should not crash when trying to log
        registry._audit_log_secret_detection("test_context")

        # Should handle properly
        assert True  # If we get here, no exception was raised

    def test_mask_secrets_with_invalid_logger_name(self):
        """Test mask_secrets with None or invalid logger names."""
        data = {"password": "secret123"}

        # Ensure fresh state
        registry = get_secrets_registry()
        registry._disabled_loggers.clear()

        # Make sure "password" is considered sensitive
        assert registry.is_sensitive_key("password")

        # Should work with None logger name
        result1 = mask_secrets(data, logger_name=None)
        assert isinstance(result1, dict)
        assert result1["password"] == "***REDACTED***"

        # Should work with empty string logger name
        result2 = mask_secrets(data, logger_name="")
        assert isinstance(result2, dict)
        assert result2["password"] == "***REDACTED***"
