"""Integration tests for CLI configuration loading improvements."""

import os
import tempfile
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.accounts import accounts
from paidsearchnav.cli.geo import geo
from paidsearchnav.cli.utils import (
    CLIConfigurationError,
    create_google_ads_client,
    get_settings_safely,
    validate_customer_id,
)


class TestCLIConfigurationIntegration:
    """Integration tests for CLI configuration loading."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_cli_with_missing_env_file(self):
        """Test CLI behavior when .env file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory without .env file
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with patch(
                    "paidsearchnav.cli.utils.Settings.from_env"
                ) as mock_from_env:
                    mock_from_env.side_effect = FileNotFoundError("No .env file")

                    result = self.runner.invoke(accounts, ["list"])

                    # Should get helpful error message
                    assert result.exit_code != 0
                    assert "Configuration file not found" in result.output
                    assert "Make sure you have a .env file" in result.output
            finally:
                os.chdir(original_cwd)

    def test_cli_with_invalid_env_format(self):
        """Test CLI behavior with invalid .env file format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            # Write invalid .env content
            f.write("INVALID_FORMAT_LINE")
            f.flush()

            try:
                with patch(
                    "paidsearchnav.cli.utils.Settings.from_env"
                ) as mock_from_env:
                    mock_from_env.side_effect = ValueError("Invalid config format")

                    result = self.runner.invoke(accounts, ["list"])

                    assert result.exit_code != 0
                    assert "Invalid configuration" in result.output
                    assert "Check your .env file format" in result.output
            finally:
                os.unlink(f.name)

    def test_cli_with_missing_google_ads_config(self):
        """Test CLI behavior when Google Ads configuration is missing."""
        with patch("paidsearchnav.cli.utils.Settings.from_env") as mock_from_env:
            from paidsearchnav.core.config import Settings

            mock_settings = Settings()
            # Mock settings without google_ads configuration
            mock_settings.google_ads = None
            mock_from_env.return_value = mock_settings

            result = self.runner.invoke(geo, ["analyze", "--customer-id", "1234567890"])

            assert result.exit_code != 0
            assert "Google Ads configuration not found" in result.output
            assert "Add Google Ads credentials to your .env file" in result.output

    def test_cli_with_incomplete_google_ads_config(self):
        """Test CLI behavior with incomplete Google Ads configuration."""
        with patch("paidsearchnav.cli.utils.Settings.from_env") as mock_from_env:
            from pydantic import SecretStr

            from paidsearchnav.core.config import GoogleAdsConfig, Settings

            mock_settings = Settings()
            # Mock settings with incomplete google_ads configuration
            mock_settings.google_ads = GoogleAdsConfig(
                developer_token=SecretStr("test_token"),
                client_id="test_id",
                # Missing client_secret and refresh_token
            )
            mock_from_env.return_value = mock_settings

            result = self.runner.invoke(geo, ["analyze", "--customer-id", "1234567890"])

            assert result.exit_code != 0
            assert "Missing Google Ads credentials" in result.output

    @pytest.mark.parametrize(
        "invalid_id,expected_error",
        [
            ("", "Customer ID is required"),
            ("abc123", "Invalid customer ID format"),
            ("123", "Invalid customer ID length"),
            ("123456789012345", "Invalid customer ID length"),
            ("123-456-7890", None),  # Should be normalized successfully
        ],
    )
    def test_customer_id_validation(self, invalid_id, expected_error):
        """Test customer ID validation with various invalid inputs."""
        if expected_error:
            with pytest.raises(CLIConfigurationError) as exc_info:
                validate_customer_id(invalid_id)
            assert expected_error in str(exc_info.value)
        else:
            # Should normalize successfully
            result = validate_customer_id(invalid_id)
            assert result == "1234567890"

    def test_accounts_list_with_invalid_root_mcc(self):
        """Test accounts list command with invalid root MCC."""
        result = self.runner.invoke(accounts, ["list", "--root-mcc", "invalid_mcc"])

        assert result.exit_code != 0
        assert "Invalid customer ID format" in result.output

    def test_geo_analyze_with_invalid_customer_id(self):
        """Test geo analyze command with invalid customer ID."""
        result = self.runner.invoke(geo, ["analyze", "--customer-id", "abc123"])

        assert result.exit_code != 0
        assert "Invalid customer ID format" in result.output

    def test_geo_compare_with_invalid_customer_id(self):
        """Test geo compare command with invalid customer ID."""
        result = self.runner.invoke(
            geo, ["compare", "--customer-id", "123", "--locations", "Dallas,Austin"]
        )

        assert result.exit_code != 0
        assert "Invalid customer ID length" in result.output

    def test_error_handling_decorator_catches_unexpected_errors(self):
        """Test that the error handling decorator catches unexpected errors."""
        with patch("paidsearchnav.cli.utils.get_settings_safely") as mock_get_settings:
            mock_get_settings.side_effect = RuntimeError("Unexpected error")

            result = self.runner.invoke(accounts, ["list"])

            assert result.exit_code != 0
            assert "An unexpected error occurred" in result.output
            assert "check your configuration" in result.output


class TestCLIUtilityFunctions:
    """Test CLI utility functions directly."""

    def test_get_settings_safely_with_valid_config(self):
        """Test get_settings_safely with valid configuration."""
        with patch("paidsearchnav.cli.utils.Settings.from_env") as mock_from_env:
            from paidsearchnav.core.config import Settings

            mock_settings = Settings()
            mock_settings.validate_required_settings = lambda: None
            mock_from_env.return_value = mock_settings

            result = get_settings_safely()

            assert result == mock_settings
            mock_from_env.assert_called_once()

    def test_get_settings_safely_with_file_not_found(self):
        """Test get_settings_safely when .env file not found."""
        with patch("paidsearchnav.cli.utils.Settings.from_env") as mock_from_env:
            mock_from_env.side_effect = FileNotFoundError("No .env file")

            with pytest.raises(CLIConfigurationError) as exc_info:
                get_settings_safely()

            assert "Configuration file not found" in str(exc_info.value)
            assert "Make sure you have a .env file" in str(exc_info.value)

    def test_create_google_ads_client_with_valid_config(self):
        """Test create_google_ads_client with valid configuration."""
        with (
            patch("paidsearchnav.cli.utils.get_settings_safely") as mock_get_settings,
            patch("paidsearchnav.cli.utils.GoogleAdsAPIClient") as mock_client_class,
        ):
            from pydantic import SecretStr

            from paidsearchnav.core.config import GoogleAdsConfig, Settings

            mock_settings = Settings()
            mock_settings.google_ads = GoogleAdsConfig(
                developer_token=SecretStr("valid_token_123456"),
                client_id="123456.apps.googleusercontent.com",
                client_secret=SecretStr("valid_secret_123456"),
                refresh_token=SecretStr("valid_refresh_123456"),
            )
            mock_get_settings.return_value = mock_settings

            mock_client = mock_client_class.return_value

            result = create_google_ads_client()

            assert result == mock_client
            mock_client_class.assert_called_once_with(
                developer_token="valid_token_123456",
                client_id="123456.apps.googleusercontent.com",
                client_secret="valid_secret_123456",
                refresh_token="valid_refresh_123456",
            )

    def test_create_google_ads_client_with_no_config(self):
        """Test create_google_ads_client when Google Ads config is missing."""
        with patch("paidsearchnav.cli.utils.get_settings_safely") as mock_get_settings:
            from paidsearchnav.core.config import Settings

            mock_settings = Settings()
            mock_settings.google_ads = None
            mock_get_settings.return_value = mock_settings

            with pytest.raises(CLIConfigurationError) as exc_info:
                create_google_ads_client()

            assert "Google Ads configuration not found" in str(exc_info.value)
            assert "Add Google Ads credentials to your .env file" in str(exc_info.value)

    def test_create_google_ads_client_with_invalid_credentials(self):
        """Test create_google_ads_client with invalid credential formats."""
        with patch("paidsearchnav.cli.utils.get_settings_safely") as mock_get_settings:
            from pydantic import SecretStr

            from paidsearchnav.core.config import GoogleAdsConfig, Settings

            mock_settings = Settings()
            mock_settings.google_ads = GoogleAdsConfig(
                developer_token=SecretStr("short"),  # Too short
                client_id="invalid_client_id",  # Wrong format
                client_secret=SecretStr("valid_secret_123456"),
                refresh_token=SecretStr("valid_refresh_123456"),
            )
            mock_get_settings.return_value = mock_settings

            with pytest.raises(CLIConfigurationError) as exc_info:
                create_google_ads_client()

            assert "Invalid Google Ads credentials" in str(exc_info.value)

    @pytest.mark.parametrize(
        "customer_id,expected",
        [
            ("1234567890", "1234567890"),
            ("123-456-7890", "1234567890"),
            ("123 456 7890", "1234567890"),
            (" 1234567890 ", "1234567890"),
            ("123456789", "123456789"),  # Valid 9-digit
            ("123456789012", "123456789012"),  # Valid 12-digit
        ],
    )
    def test_validate_customer_id_valid_formats(self, customer_id, expected):
        """Test customer ID validation with valid formats."""
        result = validate_customer_id(customer_id)
        assert result == expected

    def test_validate_customer_id_empty(self):
        """Test customer ID validation with empty input."""
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id("")
        assert "Customer ID is required" in str(exc_info.value)

    def test_validate_customer_id_non_numeric(self):
        """Test customer ID validation with non-numeric input."""
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id("abc123def")
        assert "Invalid customer ID format" in str(exc_info.value)

    def test_validate_customer_id_wrong_length(self):
        """Test customer ID validation with wrong length."""
        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id("123")  # Too short
        assert "Invalid customer ID length" in str(exc_info.value)

        with pytest.raises(CLIConfigurationError) as exc_info:
            validate_customer_id("1234567890123456")  # Too long
        assert "Invalid customer ID length" in str(exc_info.value)


class TestCLIUserExperience:
    """Test CLI user experience improvements."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_helpful_error_messages_contain_suggestions(self):
        """Test that error messages contain helpful suggestions."""
        result = self.runner.invoke(accounts, ["list", "--root-mcc", "invalid"])

        assert result.exit_code != 0
        assert "💡" in result.output  # Contains suggestion emoji
        assert "Customer ID should contain only digits" in result.output

    def test_error_messages_are_user_friendly(self):
        """Test that error messages are user-friendly and actionable."""
        with patch("paidsearchnav.cli.utils.get_settings_safely") as mock_get_settings:
            mock_get_settings.side_effect = FileNotFoundError()

            result = self.runner.invoke(accounts, ["list"])

            assert result.exit_code != 0
            # Should not contain technical stack traces
            assert "Traceback" not in result.output
            assert "FileNotFoundError" not in result.output
            # Should contain helpful guidance
            assert "Make sure you have a .env file" in result.output
