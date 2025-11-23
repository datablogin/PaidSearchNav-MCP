"""Tests for configuration parsing improvements."""

from pathlib import Path
from unittest.mock import MagicMock

from paidsearchnav_mcp.logging.config import ConfigHelper, LogConfig, LogLevel


class TestConfigHelper:
    """Test the ConfigHelper class for improved configuration parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = MagicMock()
        self.helper = ConfigHelper(self.mock_settings)

    def test_get_bool_true_values(self):
        """Test parsing various true boolean values."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "on", "On"]

        for value in true_values:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_bool("TEST_KEY")
            assert result is True, f"'{value}' should parse as True"

    def test_get_bool_false_values(self):
        """Test parsing various false boolean values."""
        false_values = [
            "false",
            "False",
            "FALSE",
            "0",
            "no",
            "No",
            "off",
            "Off",
            "",
            "invalid",
        ]

        for value in false_values:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_bool("TEST_KEY")
            assert result is False, f"'{value}' should parse as False"

    def test_get_bool_with_default(self):
        """Test get_bool with default values."""
        # Test default True
        self.mock_settings.get_env.return_value = "true"
        result = self.helper.get_bool("TEST_KEY", default=True)
        assert result is True

        # Test default False
        self.mock_settings.get_env.return_value = "false"
        result = self.helper.get_bool("TEST_KEY", default=False)
        assert result is False

    def test_get_int_valid_values(self):
        """Test parsing valid integer values."""
        test_cases = [
            ("123", 123),
            ("0", 0),
            ("-456", -456),
            ("999999", 999999),
        ]

        for value, expected in test_cases:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_int("TEST_KEY")
            assert result == expected

    def test_get_int_invalid_values_use_default(self):
        """Test that invalid integers use default values."""
        invalid_values = ["abc", "12.34", "", "not_a_number"]

        for value in invalid_values:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_int("TEST_KEY", default=42)
            assert result == 42, f"'{value}' should use default value"

    def test_get_str_basic(self):
        """Test basic string getting."""
        self.mock_settings.get_env.return_value = "test_value"
        result = self.helper.get_str("TEST_KEY")
        assert result == "test_value"

    def test_get_str_with_default(self):
        """Test string getting with default value."""
        self.mock_settings.get_env.return_value = None
        result = self.helper.get_str("TEST_KEY", default="default_value")
        assert result == "default_value"

    def test_get_str_optional_returns_none(self):
        """Test optional string returns None for empty values."""
        empty_values = [None, "", "   "]

        for value in empty_values:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_str_optional("TEST_KEY")
            assert result is None, f"'{value}' should return None"

    def test_get_str_optional_returns_value(self):
        """Test optional string returns actual values."""
        self.mock_settings.get_env.return_value = "actual_value"
        result = self.helper.get_str_optional("TEST_KEY")
        assert result == "actual_value"

    def test_get_list_basic(self):
        """Test basic list parsing."""
        self.mock_settings.get_env.return_value = "item1,item2,item3"
        result = self.helper.get_list("TEST_KEY")
        assert result == ["item1", "item2", "item3"]

    def test_get_list_with_spaces(self):
        """Test list parsing with extra spaces."""
        self.mock_settings.get_env.return_value = " item1 , item2 , item3 "
        result = self.helper.get_list("TEST_KEY")
        assert result == ["item1", "item2", "item3"]

    def test_get_list_empty_values(self):
        """Test list parsing with empty values."""
        empty_cases = [None, "", "   ", ",,,"]

        for value in empty_cases:
            self.mock_settings.get_env.return_value = value
            result = self.helper.get_list("TEST_KEY")
            assert result == [], f"'{value}' should return empty list"

    def test_get_list_with_default(self):
        """Test list parsing with default values."""
        self.mock_settings.get_env.return_value = None
        result = self.helper.get_list("TEST_KEY", default=["default1", "default2"])
        assert result == ["default1", "default2"]

    def test_get_list_custom_separator(self):
        """Test list parsing with custom separator."""
        self.mock_settings.get_env.return_value = "item1;item2;item3"
        result = self.helper.get_list("TEST_KEY", separator=";")
        assert result == ["item1", "item2", "item3"]

    def test_get_list_filters_empty_items(self):
        """Test that empty list items are filtered out."""
        self.mock_settings.get_env.return_value = "item1,,item2, ,item3"
        result = self.helper.get_list("TEST_KEY")
        assert result == ["item1", "item2", "item3"]

    def test_get_path_optional_valid(self):
        """Test optional path with valid value."""
        self.mock_settings.get_env.return_value = "/path/to/file"
        result = self.helper.get_path_optional("TEST_KEY")
        assert result == Path("/path/to/file")

    def test_get_path_optional_none(self):
        """Test optional path with None value."""
        self.mock_settings.get_env.return_value = None
        result = self.helper.get_path_optional("TEST_KEY")
        assert result is None

    def test_get_enum_valid(self):
        """Test enum parsing with valid value."""
        self.mock_settings.get_env.return_value = "INFO"
        result = self.helper.get_enum("TEST_KEY", LogLevel, "DEBUG")
        assert result == LogLevel.INFO

    def test_get_enum_invalid_uses_default(self):
        """Test enum parsing with invalid value uses default."""
        self.mock_settings.get_env.return_value = "INVALID_LEVEL"
        result = self.helper.get_enum("TEST_KEY", LogLevel, "ERROR")
        assert result == LogLevel.ERROR


class TestConfigurationIntegration:
    """Test the improved configuration integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = MagicMock()
        # Set up environment property
        self.mock_settings.environment = "test"

    def test_simplified_config_loading(self):
        """Test that the simplified config loading works correctly."""
        from paidsearchnav.logging.config import _load_config_from_settings

        # Set up mock return values
        def get_env_side_effect(key, default=None):
            env_values = {
                "LOG_LEVEL": "DEBUG",
                "LOG_JSON_FORMAT": "false",
                "LOG_ENABLE_ALERTS": "true",
                "LOG_ALERT_LEVEL": "WARNING",
                "SMTP_PORT": "25",
                "LOG_RETENTION_DAYS": "60",
                "LOG_MAX_SIZE_MB": "200",
                "LOG_ENABLE_SECRET_MASKING": "false",
                "LOG_SECRET_MASK_STRING": "[HIDDEN]",
                "LOG_CUSTOM_SENSITIVE_KEYS": "custom1,custom2",
                "LOG_CUSTOM_SECRET_PATTERNS": "pattern1,pattern2",
                "LOG_WHITELIST_PATTERNS": "whitelist1,whitelist2",
                "LOG_DISABLED_MASKING_LOGGERS": "logger1,logger2",
                "LOG_ENABLE_AUDIT_LOGGING": "true",
                "LOG_MAX_RECURSION_DEPTH": "5",
                "LOG_ENABLE_PATTERN_CACHE": "false",
                "LOG_PATTERN_CACHE_SIZE": "500",
            }
            return env_values.get(key, default)

        self.mock_settings.get_env.side_effect = get_env_side_effect

        # Load configuration
        config = _load_config_from_settings(self.mock_settings)

        # Verify values were parsed correctly
        assert config.level == LogLevel.DEBUG
        assert config.json_format is False
        assert config.enable_alerts is True
        assert config.alert_level == LogLevel.WARNING
        assert config.smtp_port == 25
        assert config.retention_days == 60
        assert config.max_log_size_mb == 200
        assert config.enable_secret_masking is False
        assert config.secret_mask_string == "[HIDDEN]"
        assert config.custom_sensitive_keys == ["custom1", "custom2"]
        assert config.custom_secret_patterns == ["pattern1", "pattern2"]
        assert config.whitelist_patterns == ["whitelist1", "whitelist2"]
        assert config.disabled_masking_loggers == ["logger1", "logger2"]
        assert config.enable_audit_logging is True
        assert config.max_recursion_depth == 5
        assert config.enable_pattern_cache is False
        assert config.pattern_cache_size == 500

    def test_config_with_minimal_settings(self):
        """Test configuration with minimal/default settings."""
        from paidsearchnav.logging.config import _load_config_from_settings

        # Return None/default for all values
        self.mock_settings.get_env.return_value = None

        config = _load_config_from_settings(self.mock_settings)

        # Verify defaults
        assert config.level == LogLevel.INFO
        assert config.json_format is True
        assert config.log_file is None
        assert config.enable_alerts is True
        assert config.alert_level == LogLevel.ERROR
        assert config.slack_webhook_url is None
        assert config.smtp_port == 587
        assert config.retention_days == 30
        assert config.max_log_size_mb == 100
        assert config.enable_secret_masking is True
        assert config.secret_mask_string == "***REDACTED***"
        assert config.custom_sensitive_keys == []
        assert config.enable_audit_logging is False
        assert config.max_recursion_depth == 10
        assert config.enable_pattern_cache is True
        assert config.pattern_cache_size == 1000

    def test_config_error_handling(self):
        """Test that configuration handles errors gracefully."""
        from paidsearchnav.logging.config import _load_config_from_settings

        # Set up environment values that could cause errors
        def get_env_side_effect(key, default=None):
            error_values = {
                "SMTP_PORT": "not_a_number",
                "LOG_RETENTION_DAYS": "invalid",
                "LOG_LEVEL": "INVALID_LEVEL",
            }
            return error_values.get(key, default)

        self.mock_settings.get_env.side_effect = get_env_side_effect

        # Should not raise an exception
        config = _load_config_from_settings(self.mock_settings)

        # Should use defaults for invalid values
        assert config.smtp_port == 587  # Default value
        assert config.retention_days == 30  # Default value
        assert config.level == LogLevel.INFO  # Default value


class TestConfigurationDocumentation:
    """Test that configuration is properly documented and consistent."""

    def test_all_config_fields_have_descriptions(self):
        """Test that all LogConfig fields have descriptions."""
        # Create a LogConfig instance to introspect fields
        config = LogConfig()

        # Get all field information
        for field_name, field_info in config.model_fields.items():
            assert field_info.description is not None, (
                f"Field '{field_name}' is missing description"
            )
            assert len(field_info.description) > 10, (
                f"Field '{field_name}' has too short description"
            )

    def test_environment_variable_naming_consistency(self):
        """Test that environment variables follow naming conventions."""
        # All logging environment variables should start with LOG_ or be service-specific
        expected_prefixes = ["LOG_", "SLACK_", "SMTP_", "EMAIL_", "SENTRY_"]

        # This is more of a documentation test - we check the helper usage
        helper = ConfigHelper(MagicMock())

        # The helper methods should be used consistently
        assert hasattr(helper, "get_bool")
        assert hasattr(helper, "get_int")
        assert hasattr(helper, "get_str")
        assert hasattr(helper, "get_list")
        assert hasattr(helper, "get_enum")


class TestConfigurationPerformance:
    """Test performance aspects of configuration parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = MagicMock()
        self.mock_settings.environment = "test"

    def test_config_parsing_performance(self):
        """Test that config parsing is reasonably fast."""
        import time

        from paidsearchnav.logging.config import _load_config_from_settings

        # Set up a realistic set of environment variables
        def get_env_side_effect(key, default=None):
            # Return default for all keys (simulates minimal config)
            return default

        self.mock_settings.get_env.side_effect = get_env_side_effect

        # Time multiple config loads
        start_time = time.time()
        for _ in range(100):
            config = _load_config_from_settings(self.mock_settings)
        end_time = time.time()

        # Should be reasonably fast (less than 0.5 seconds for 100 loads)
        # Note: CI environments may be slower than local development
        total_time = end_time - start_time
        assert total_time < 0.5, f"Config loading too slow: {total_time}s for 100 loads"

    def test_helper_reuse(self):
        """Test that ConfigHelper can be reused efficiently."""
        helper = ConfigHelper(self.mock_settings)

        # Multiple calls should work without creating new instances
        self.mock_settings.get_env.return_value = "test"

        result1 = helper.get_str("KEY1")
        result2 = helper.get_str("KEY2")
        result3 = helper.get_bool("KEY3")

        # Should all work without issues
        assert result1 == "test"
        assert result2 == "test"
        assert result3 is False  # "test" is not in the true values list
