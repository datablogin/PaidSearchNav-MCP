"""Test CLI utilities module."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav_mcp.cli.utils import (
    MAX_CUSTOMER_ID_LENGTH,
    MIN_CUSTOMER_ID_LENGTH,
    MIN_TOKEN_LENGTH,
    CLIConfigurationError,
    categorize_error,
    create_google_ads_client,
    format_cli_error,
    format_cli_success,
    format_cli_warning,
    get_context_flags,
    get_settings_safely,
    handle_common_cli_errors,
    log_cli_operation,
    sanitize_error_message,
    validate_customer_id,
)
from paidsearchnav_mcp.core.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    RateLimitError,
    ValidationError,
)


class TestCLIConfigurationError:
    """Test custom CLI configuration error class."""

    def test_cli_configuration_error_basic(self):
        """Test basic CLIConfigurationError creation."""
        error = CLIConfigurationError("Test error message")
        assert str(error) == "Test error message"

    def test_cli_configuration_error_with_suggestion(self):
        """Test CLIConfigurationError with suggestion."""
        error = CLIConfigurationError("Test error", "Try this fix")
        assert str(error) == "Test error\n💡 Try this fix"


class TestGetSettingsSafely:
    """Test get_settings_safely function."""

    @patch("paidsearchnav.cli.utils.Settings.from_env")
    def test_get_settings_safely_success(self, mock_from_env):
        """Test successful settings loading."""
        from paidsearchnav.core.config import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.validate_required_settings = Mock()
        mock_from_env.return_value = mock_settings

        result = get_settings_safely()

        assert result == mock_settings
        mock_from_env.assert_called_once()
        mock_settings.validate_required_settings.assert_called_once()

    @patch("paidsearchnav.cli.utils.Settings.from_env")
    def test_get_settings_safely_file_not_found(self, mock_from_env):
        """Test settings loading with missing .env file."""
        mock_from_env.side_effect = FileNotFoundError("No .env file")

        with pytest.raises(CLIConfigurationError) as exc_info:
            get_settings_safely()

        assert "Configuration file not found" in str(exc_info.value)
        assert "Make sure you have a .env file" in str(exc_info.value)

    @patch("paidsearchnav.cli.utils.Settings.from_env")
    def test_get_settings_safely_value_error(self, mock_from_env):
        """Test settings loading with invalid configuration."""
        mock_from_env.side_effect = ValueError("Invalid config value")

        with pytest.raises(CLIConfigurationError) as exc_info:
            get_settings_safely()

        assert "Invalid configuration" in str(exc_info.value)
        assert "Check your .env file format" in str(exc_info.value)

    @patch("paidsearchnav.cli.utils.Settings.from_env")
    def test_get_settings_safely_unexpected_error(self, mock_from_env):
        """Test settings loading with unexpected error."""
        mock_from_env.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(CLIConfigurationError) as exc_info:
            get_settings_safely()

        assert "Failed to load configuration" in str(exc_info.value)
        assert "Please check your .env file" in str(exc_info.value)


class TestCreateGoogleAdsClient:
    """Test create_google_ads_client function."""

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    @patch("paidsearchnav.cli.utils.GoogleAdsAPIClient")
    def test_create_google_ads_client_success(
        self, mock_client_class, mock_get_settings
    ):
        """Test successful Google Ads client creation."""
        from pydantic import SecretStr

        from paidsearchnav.core.config import GoogleAdsConfig, Settings

        # Mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.google_ads = GoogleAdsConfig(
            developer_token=SecretStr("valid_token_123456"),
            client_id="123456.apps.googleusercontent.com",
            client_secret=SecretStr("valid_secret_123456"),
            refresh_token=SecretStr("valid_refresh_123456"),
        )
        mock_get_settings.return_value = mock_settings

        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        result = create_google_ads_client()

        assert result == mock_client
        mock_client_class.assert_called_once_with(
            developer_token="valid_token_123456",
            client_id="123456.apps.googleusercontent.com",
            client_secret="valid_secret_123456",
            refresh_token="valid_refresh_123456",
        )

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    def test_create_google_ads_client_no_config(self, mock_get_settings):
        """Test Google Ads client creation with missing config."""
        from paidsearchnav.core.config import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.google_ads = None
        mock_get_settings.return_value = mock_settings

        with pytest.raises(CLIConfigurationError) as exc_info:
            create_google_ads_client()

        assert "Google Ads configuration not found" in str(exc_info.value)
        assert "Add Google Ads credentials to your .env file" in str(exc_info.value)

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    def test_create_google_ads_client_missing_fields(self, mock_get_settings):
        """Test Google Ads client creation with missing required fields."""
        from pydantic import SecretStr

        from paidsearchnav.core.config import Settings

        mock_settings = Mock(spec=Settings)
        # Mock incomplete google_ads config without using the real class
        mock_google_ads = Mock()
        mock_google_ads.developer_token = SecretStr("test_token")
        mock_google_ads.client_id = "test_id"
        mock_google_ads.client_secret = None  # Missing
        mock_google_ads.refresh_token = None  # Missing
        mock_settings.google_ads = mock_google_ads
        mock_get_settings.return_value = mock_settings

        with pytest.raises(CLIConfigurationError) as exc_info:
            create_google_ads_client()

        assert "Missing Google Ads credentials" in str(exc_info.value)
        assert "PSN_GOOGLE_ADS_CLIENT_SECRET" in str(exc_info.value)
        assert "PSN_GOOGLE_ADS_REFRESH_TOKEN" in str(exc_info.value)

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    def test_create_google_ads_client_invalid_values(self, mock_get_settings):
        """Test Google Ads client creation with invalid credential values."""
        from pydantic import SecretStr

        from paidsearchnav.core.config import GoogleAdsConfig, Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.google_ads = GoogleAdsConfig(
            developer_token=SecretStr("short"),  # Too short
            client_id="invalid_format",  # Wrong format
            client_secret=SecretStr("valid_secret_123456"),
            refresh_token=SecretStr("valid_refresh_123456"),
        )
        mock_get_settings.return_value = mock_settings

        with pytest.raises(CLIConfigurationError) as exc_info:
            create_google_ads_client()

        assert "Invalid Google Ads credentials" in str(exc_info.value)

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    @patch("paidsearchnav.cli.utils.GoogleAdsAPIClient")
    def test_create_google_ads_client_initialization_error(
        self, mock_client_class, mock_get_settings
    ):
        """Test Google Ads client creation with client initialization error."""
        from pydantic import SecretStr

        from paidsearchnav.core.config import GoogleAdsConfig, Settings

        # Mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.google_ads = GoogleAdsConfig(
            developer_token=SecretStr("valid_token_123456"),
            client_id="123456.apps.googleusercontent.com",
            client_secret=SecretStr("valid_secret_123456"),
            refresh_token=SecretStr("valid_refresh_123456"),
        )
        mock_get_settings.return_value = mock_settings

        # Mock client initialization failure
        mock_client_class.side_effect = RuntimeError("Failed to initialize client")

        with pytest.raises(CLIConfigurationError) as exc_info:
            create_google_ads_client()

        assert "Failed to initialize Google Ads API client" in str(exc_info.value)
        assert "Check that your credentials are valid" in str(exc_info.value)


class TestValidateCustomerId:
    """Test validate_customer_id function."""

    @pytest.mark.parametrize(
        "customer_id,expected",
        [
            ("1234567890", "1234567890"),
            ("123-456-7890", "1234567890"),
            ("123 456 7890", "1234567890"),
            (" 1234567890 ", "1234567890"),
            ("12345678", "12345678"),  # 8 digits (minimum)
            ("123456789012", "123456789012"),  # 12 digits (maximum)
        ],
    )
    def test_validate_customer_id_valid(self, customer_id, expected):
        """Test customer ID validation with valid inputs."""
        result = validate_customer_id(customer_id)
        assert result == expected

    @pytest.mark.parametrize(
        "customer_id,expected_error",
        [
            ("", "Customer ID is required"),
            ("abc123", "Invalid customer ID format"),
            ("123abc", "Invalid customer ID format"),
            ("1234567", "Invalid customer ID length"),  # Too short
            ("1234567890123", "Invalid customer ID length"),  # Too long
        ],
    )
    def test_validate_customer_id_invalid(self, customer_id, expected_error):
        """Test customer ID validation with invalid inputs."""
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id(customer_id)
        assert expected_error in str(exc_info.value)


class TestErrorHandlingDecorator:
    """Test handle_common_cli_errors decorator."""

    def test_handle_common_cli_errors_success(self):
        """Test decorator with successful function execution."""

        @handle_common_cli_errors
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_handle_common_cli_errors_cli_config_error(self):
        """Test decorator with CLIConfigurationError."""

        @handle_common_cli_errors
        def test_func():
            raise CLIConfigurationError("Test config error")

        with pytest.raises(CLIConfigurationError) as exc_info:
            test_func()
        assert "Test config error" in str(exc_info.value)

    def test_handle_common_cli_errors_click_exception(self):
        """Test decorator with ClickException."""
        import click

        @handle_common_cli_errors
        def test_func():
            raise click.ClickException("Test click error")

        with pytest.raises(click.ClickException) as exc_info:
            test_func()
        assert "Test click error" in str(exc_info.value)

    def test_handle_common_cli_errors_unexpected_error(self):
        """Test decorator with unexpected error."""
        import click

        @handle_common_cli_errors
        def test_func():
            raise RuntimeError("Unexpected error")

        with pytest.raises(click.ClickException) as exc_info:
            test_func()
        # The new enhanced decorator uses categorize_error, so we expect different message format
        assert "Unexpected error: Unexpected error" in str(exc_info.value)
        assert "check your configuration" in str(exc_info.value)


class TestFormatFunctions:
    """Test CLI formatting functions."""

    def test_format_cli_success(self):
        """Test success message formatting."""
        result = format_cli_success("Operation completed")
        assert result == "✓ Operation completed"

        result = format_cli_success("Operation completed", "Details here")
        assert result == "✓ Operation completed\n  Details here"

    def test_format_cli_warning(self):
        """Test warning message formatting."""
        result = format_cli_warning("Warning message")
        assert result == "⚠️  Warning message"

        result = format_cli_warning("Warning message", "Suggestion here")
        assert result == "⚠️  Warning message\n💡 Suggestion here"

    def test_format_cli_error(self):
        """Test error message formatting."""
        result = format_cli_error("Error occurred")
        assert result == "❌ Error occurred"

        result = format_cli_error("Error occurred", "Try this fix")
        assert result == "❌ Error occurred\n💡 Try this fix"


class TestCLIIntegration:
    """Test CLI integration with utilities."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_cli_command_with_utilities(self):
        """Test CLI command using utility functions."""
        import click

        @click.command()
        @click.option("--customer-id", required=True)
        @handle_common_cli_errors
        def test_command(customer_id: str):
            validated_id = validate_customer_id(customer_id)
            click.echo(f"Validated ID: {validated_id}")

        result = self.runner.invoke(test_command, ["--customer-id", "123-456-7890"])
        assert result.exit_code == 0
        assert "Validated ID: 1234567890" in result.output

    def test_cli_command_with_validation_error(self):
        """Test CLI command with validation error."""
        import click

        @click.command()
        @click.option("--customer-id", required=True)
        @handle_common_cli_errors
        def test_command(customer_id: str):
            validated_id = validate_customer_id(customer_id)
            click.echo(f"Validated ID: {validated_id}")

        result = self.runner.invoke(test_command, ["--customer-id", "invalid"])
        assert result.exit_code != 0
        assert "Invalid customer ID format" in result.output
        assert "💡" in result.output  # Should contain suggestion


class TestSanitizeErrorMessage:
    """Test error message sanitization."""

    @pytest.mark.parametrize(
        "error_msg,expected",
        [
            ("No sensitive info", "No sensitive info"),
            ("token=abc123xyz789def", "token=***HIDDEN***"),
            ("secret='mysecret123456'", "secret=***HIDDEN***"),
            ("password: mypassword456789", "password=***HIDDEN***"),
            ("user@example.com failed", "***EMAIL*** failed"),
            ("https://user:pass@api.com", "https://***:***@api.com"),
            ("customer_id: 1234567890", "customer_id: ***CUSTOMER_ID***"),
            (
                "Multiple 1234567890 and user@test.com",
                "Multiple ***CUSTOMER_ID*** and ***EMAIL***",
            ),
        ],
    )
    def test_sanitize_error_message(self, error_msg, expected):
        """Test error message sanitization with various patterns."""
        result = sanitize_error_message(error_msg)
        assert result == expected

    def test_sanitize_error_message_empty(self):
        """Test sanitization with empty message."""
        result = sanitize_error_message("")
        assert result == ""

    def test_sanitize_error_message_none(self):
        """Test sanitization with None message."""
        result = sanitize_error_message(None)
        assert result is None


class TestCategorizeError:
    """Test error categorization functionality."""

    def test_categorize_authentication_error(self):
        """Test categorization of authentication errors."""
        error = AuthenticationError("Invalid credentials")
        category, message, suggestion = categorize_error(error)

        assert category == "Authentication"
        assert "Authentication failed" in message
        assert "credentials" in suggestion.lower()

    def test_categorize_authorization_error(self):
        """Test categorization of authorization errors."""
        error = AuthorizationError("Access denied")
        category, message, suggestion = categorize_error(error)

        assert category == "Authorization"
        assert "Access denied" in message
        assert "permissions" in suggestion.lower()

    def test_categorize_rate_limit_error(self):
        """Test categorization of rate limit errors."""
        error = RateLimitError("Too many requests")
        category, message, suggestion = categorize_error(error)

        assert category == "Rate Limit"
        assert "rate limit exceeded" in message.lower()
        assert "wait" in suggestion.lower()

    def test_categorize_configuration_error(self):
        """Test categorization of configuration errors."""
        error = ConfigurationError("Missing config value")
        category, message, suggestion = categorize_error(error)

        assert category == "Configuration"
        assert "Configuration error" in message
        assert ".env file" in suggestion

    def test_categorize_validation_error(self):
        """Test categorization of validation errors."""
        error = ValidationError("Invalid data format")
        category, message, suggestion = categorize_error(error)

        assert category == "Validation"
        assert "Data validation failed" in message
        assert "format" in suggestion.lower()

    def test_categorize_api_error(self):
        """Test categorization of API errors."""
        error = APIError("API call failed")
        category, message, suggestion = categorize_error(error)

        assert category == "API"
        assert "API request failed" in message
        assert "connection" in suggestion.lower()

    def test_categorize_value_error_google_ads(self):
        """Test categorization of ValueError with Google Ads context."""
        error = ValueError("Google Ads developer token invalid")
        category, message, suggestion = categorize_error(error)

        assert category == "Configuration"
        assert "Google Ads configuration error" in message
        assert "credentials" in suggestion.lower()

    def test_categorize_value_error_generic(self):
        """Test categorization of generic ValueError."""
        error = ValueError("Invalid parameter")
        category, message, suggestion = categorize_error(error)

        assert category == "Validation"
        assert "Invalid value" in message
        assert "format" in suggestion.lower()

    def test_categorize_connection_error(self):
        """Test categorization of connection errors."""
        error = ConnectionError("Network unreachable")
        category, message, suggestion = categorize_error(error)

        assert category == "Network"
        assert "Network connection failed" in message
        assert "internet connection" in suggestion.lower()

    def test_categorize_file_not_found_error(self):
        """Test categorization of file not found errors."""
        error = FileNotFoundError("Config file missing")
        category, message, suggestion = categorize_error(error)

        assert category == "File"
        assert "File not found" in message
        assert "permissions" in suggestion.lower()

    def test_categorize_permission_error(self):
        """Test categorization of permission errors."""
        error = PermissionError("Access denied")
        category, message, suggestion = categorize_error(error)

        assert category == "Permission"
        assert "Permission denied" in message
        assert "permissions" in suggestion.lower()

    def test_categorize_timeout_error(self):
        """Test categorization of timeout errors."""
        error = TimeoutError("Operation timed out")
        category, message, suggestion = categorize_error(error)

        assert category == "Timeout"
        assert "Operation timed out" in message
        assert "network connection" in suggestion.lower()

    def test_categorize_unknown_error(self):
        """Test categorization of unknown errors."""
        error = RuntimeError("Unknown error occurred")
        category, message, suggestion = categorize_error(error)

        assert category == "Unexpected"
        assert "Unexpected error" in message
        assert "contact support" in suggestion.lower()

    def test_categorize_error_sanitization(self):
        """Test that error categorization includes sanitization."""
        error = ValueError(
            "token=secret123abc failed"
        )  # Make token longer to trigger sanitization
        category, message, suggestion = categorize_error(error)

        assert "***HIDDEN***" in message
        assert "secret123abc" not in message


class TestEnhancedErrorHandlingDecorator:
    """Test enhanced error handling decorator with debug/verbose support."""

    def test_enhanced_decorator_success(self):
        """Test decorator with successful execution."""

        @handle_common_cli_errors
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_enhanced_decorator_with_debug_mode(self, mock_get_context):
        """Test decorator with debug mode enabled."""
        import click

        # Mock context with debug mode
        mock_ctx = Mock()
        mock_ctx.obj = {"debug": True, "verbose": False}
        mock_get_context.return_value = mock_ctx

        @handle_common_cli_errors
        def test_func():
            raise ValueError("Test error")

        with pytest.raises(click.ClickException) as exc_info:
            test_func()

        error_message = str(exc_info.value)
        assert "🔍 Debug Information:" in error_message
        assert "Category:" in error_message
        assert "Technical Error:" in error_message
        assert "Exception Type:" in error_message

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_enhanced_decorator_with_verbose_mode(self, mock_get_context):
        """Test decorator with verbose mode enabled."""
        import click

        # Mock context with verbose mode
        mock_ctx = Mock()
        mock_ctx.obj = {"debug": False, "verbose": True}
        mock_get_context.return_value = mock_ctx

        @handle_common_cli_errors
        def test_func():
            raise ValueError("Test error")

        with pytest.raises(click.ClickException) as exc_info:
            test_func()

        error_message = str(exc_info.value)
        assert "📋 Additional Details:" in error_message
        assert "Error Category:" in error_message
        assert "Exception Type:" in error_message
        assert (
            "🔍 Debug Information:" not in error_message
        )  # Should not be in verbose mode

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_enhanced_decorator_debug_suggestion(self, mock_get_context):
        """Test decorator suggests debug mode for unexpected errors."""
        import click

        # Mock context without debug mode
        mock_ctx = Mock()
        mock_ctx.obj = {"debug": False, "verbose": False}
        mock_get_context.return_value = mock_ctx

        @handle_common_cli_errors
        def test_func():
            raise RuntimeError("Unexpected error")  # Should trigger debug suggestion

        with pytest.raises(click.ClickException) as exc_info:
            test_func()

        error_message = str(exc_info.value)
        assert "Run with --debug for detailed technical information" in error_message


class TestGetContextFlags:
    """Test context flag retrieval functions."""

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_get_context_flags_with_flags(self, mock_get_context):
        """Test getting context flags when they exist."""
        mock_ctx = Mock()
        mock_ctx.obj = {"debug": True, "verbose": False}
        mock_get_context.return_value = mock_ctx

        debug, verbose = get_context_flags()
        assert debug is True
        assert verbose is False

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_get_context_flags_no_context(self, mock_get_context):
        """Test getting context flags when no context exists."""
        mock_get_context.return_value = None

        debug, verbose = get_context_flags()
        assert debug is False
        assert verbose is False

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_get_context_flags_no_obj(self, mock_get_context):
        """Test getting context flags when context has no obj."""
        mock_ctx = Mock()
        mock_ctx.obj = None
        mock_get_context.return_value = mock_ctx

        debug, verbose = get_context_flags()
        assert debug is False
        assert verbose is False


class TestLogCliOperation:
    """Test CLI operation logging functionality."""

    @patch("paidsearchnav.cli.utils.get_context_flags")
    @patch("paidsearchnav.cli.utils.logger")
    @patch("paidsearchnav.cli.utils.click.echo")
    def test_log_cli_operation_debug_mode(self, mock_echo, mock_logger, mock_get_flags):
        """Test CLI operation logging in debug mode."""
        mock_get_flags.return_value = (True, False)  # debug=True, verbose=False

        log_cli_operation("Test operation", "Test details")

        mock_logger.debug.assert_called_once_with(
            "CLI Operation: Test operation - Test details"
        )
        mock_echo.assert_not_called()  # Should not echo in debug-only mode

    @patch("paidsearchnav.cli.utils.get_context_flags")
    @patch("paidsearchnav.cli.utils.logger")
    @patch("paidsearchnav.cli.utils.click.echo")
    def test_log_cli_operation_verbose_mode(
        self, mock_echo, mock_logger, mock_get_flags
    ):
        """Test CLI operation logging in verbose mode."""
        mock_get_flags.return_value = (False, True)  # debug=False, verbose=True

        log_cli_operation("Test operation", "Test details")

        mock_logger.info.assert_called_once_with("CLI Operation: Test operation")
        mock_echo.assert_called_once_with("ℹ️  Test operation", err=False)

    @patch("paidsearchnav.cli.utils.get_context_flags")
    @patch("paidsearchnav.cli.utils.logger")
    @patch("paidsearchnav.cli.utils.click.echo")
    def test_log_cli_operation_both_modes(self, mock_echo, mock_logger, mock_get_flags):
        """Test CLI operation logging with both debug and verbose enabled."""
        mock_get_flags.return_value = (True, True)  # debug=True, verbose=True

        log_cli_operation("Test operation", "Test details")

        mock_logger.debug.assert_called_once_with(
            "CLI Operation: Test operation - Test details"
        )
        mock_echo.assert_called_once_with("ℹ️  Test operation (Test details)", err=False)

    @patch("paidsearchnav.cli.utils.get_context_flags")
    @patch("paidsearchnav.cli.utils.logger")
    @patch("paidsearchnav.cli.utils.click.echo")
    def test_log_cli_operation_normal_mode(
        self, mock_echo, mock_logger, mock_get_flags
    ):
        """Test CLI operation logging in normal mode."""
        mock_get_flags.return_value = (False, False)  # debug=False, verbose=False

        log_cli_operation("Test operation", "Test details")

        mock_logger.debug.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_echo.assert_not_called()


class TestErrorChaining:
    """Test error chaining and cause handling."""

    @patch("paidsearchnav.cli.utils.click.get_current_context")
    def test_error_with_cause(self, mock_get_context):
        """Test error handling with __cause__ attribute in debug mode."""
        import click

        # Mock context with debug mode
        mock_ctx = Mock()
        mock_ctx.obj = {"debug": True, "verbose": False}
        mock_get_context.return_value = mock_ctx

        @handle_common_cli_errors
        def test_func():
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise RuntimeError("Chained error") from e

        with pytest.raises(click.ClickException) as exc_info:
            test_func()

        error_message = str(exc_info.value)
        assert "Caused By:" in error_message
        assert "Original error" in error_message

    def test_categorize_error_with_none_message(self):
        """Test error categorization with None in error message."""
        error = ValueError(None)
        category, message, suggestion = categorize_error(error)

        assert category == "Validation"
        assert "Invalid value" in message

    def test_sanitize_large_error_message(self):
        """Test sanitization performance with large error messages."""
        # Create a large error message with sensitive data
        large_msg = "Error: " + "token=abc123def456ghi789 " * 1000 + "user@example.com"

        result = sanitize_error_message(large_msg)

        # Should sanitize all instances
        assert "abc123def456ghi789" not in result
        assert "***HIDDEN***" in result
        assert "***EMAIL***" in result


class TestConstantsUsage:
    """Test that constants are properly used."""

    def test_customer_id_validation_uses_constants(self):
        """Test that customer ID validation uses the defined constants."""
        # Test minimum length boundary
        short_id = "1" * (MIN_CUSTOMER_ID_LENGTH - 1)
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id(short_id)
        assert f"{MIN_CUSTOMER_ID_LENGTH}-{MAX_CUSTOMER_ID_LENGTH} digits long" in str(
            exc_info.value
        )

        # Test maximum length boundary
        long_id = "1" * (MAX_CUSTOMER_ID_LENGTH + 1)
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id(long_id)
        assert f"{MIN_CUSTOMER_ID_LENGTH}-{MAX_CUSTOMER_ID_LENGTH} digits long" in str(
            exc_info.value
        )

    def test_token_validation_uses_constants(self):
        """Test that token validation uses the MIN_TOKEN_LENGTH constant."""
        from pydantic import SecretStr

        from paidsearchnav.core.config import GoogleAdsConfig

        # Mock settings with short token
        mock_settings = Mock()
        short_token = "x" * (MIN_TOKEN_LENGTH - 1)
        mock_settings.google_ads = GoogleAdsConfig(
            developer_token=SecretStr(short_token),
            client_id="test.apps.googleusercontent.com",
            client_secret=SecretStr("valid_secret_123456789"),
            refresh_token=SecretStr("valid_refresh_123456789"),
        )

        with patch(
            "paidsearchnav.cli.utils.get_settings_safely", return_value=mock_settings
        ):
            with pytest.raises(CLIConfigurationError) as exc_info:
                create_google_ads_client()
            assert "Developer token appears to be invalid" in str(exc_info.value)


class TestRegexPerformance:
    """Test compiled regex patterns."""

    def test_compiled_patterns_work(self):
        """Test that compiled regex patterns work correctly."""
        from paidsearchnav.cli.utils import _SENSITIVE_PATTERNS

        # Test that patterns are compiled
        for pattern, replacement in _SENSITIVE_PATTERNS:
            assert hasattr(pattern, "sub"), "Pattern should be compiled"

        # Test pattern functionality
        test_msg = "token=abc123def456 user@test.com https://user:pass@api.com customer_id: 1234567890"
        result = sanitize_error_message(test_msg)

        assert "***HIDDEN***" in result
        assert "***EMAIL***" in result
        assert "***:***@" in result
        assert "***CUSTOMER_ID***" in result
