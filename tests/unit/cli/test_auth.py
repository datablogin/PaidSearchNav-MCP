"""Tests for CLI auth commands."""

import os
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.auth import auth
from paidsearchnav.core.config import Settings


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_google_ads_config():
    """Mock Google Ads configuration."""
    return {
        "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "test-developer-token",
        "PSN_GOOGLE_ADS_CLIENT_ID": "test-client-id",
        "PSN_GOOGLE_ADS_CLIENT_SECRET": "test-client-secret",
        "PSN_GOOGLE_ADS_REFRESH_TOKEN": "test-refresh-token",
        "PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
    }


class TestAuthLoginCommand:
    """Test the auth login command."""

    def test_login_command_uses_settings_from_env(
        self, cli_runner, mock_google_ads_config
    ):
        """Test that login command uses Settings.from_env()."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth.OAuth2TokenManager"
                ) as mock_token_manager:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_from_env.return_value = mock_settings

                    # Mock the OAuth2TokenManager
                    mock_manager = Mock()
                    mock_credentials = Mock()
                    mock_credentials.token = "test-access-token-1234567890"
                    mock_manager.get_credentials.return_value = mock_credentials
                    mock_token_manager.return_value = mock_manager

                    # Run the command
                    result = cli_runner.invoke(
                        auth, ["login", "--customer-id", "1234567890"]
                    )

                    # Verify Settings.from_env() was called
                    mock_from_env.assert_called_once()

                    # Verify OAuth2TokenManager was created with the settings
                    mock_token_manager.assert_called_once_with(mock_settings)

                    # Verify get_credentials was called with correct customer_id
                    mock_manager.get_credentials.assert_called_once_with(
                        customer_id="1234567890", force_auth_method=None
                    )

                    # Verify success output
                    assert result.exit_code == 0
                    assert "Authenticating for customer ID: 1234567890" in result.output
                    assert "✅ Authentication successful!" in result.output
                    assert "Access token: test-access-token-12..." in result.output

    def test_login_command_with_force_browser(self, cli_runner, mock_google_ads_config):
        """Test that login command respects force browser option."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth.OAuth2TokenManager"
                ) as mock_token_manager:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_from_env.return_value = mock_settings

                    # Mock the OAuth2TokenManager
                    mock_manager = Mock()
                    mock_credentials = Mock()
                    mock_credentials.token = "test-access-token-1234567890"
                    mock_manager.get_credentials.return_value = mock_credentials
                    mock_token_manager.return_value = mock_manager

                    # Run the command with force browser
                    result = cli_runner.invoke(
                        auth,
                        ["login", "--customer-id", "1234567890", "--force", "browser"],
                    )

                    # Verify get_credentials was called with force_auth_method
                    mock_manager.get_credentials.assert_called_once_with(
                        customer_id="1234567890", force_auth_method="browser"
                    )

                    # Verify success output
                    assert result.exit_code == 0

    def test_login_command_with_force_device(self, cli_runner, mock_google_ads_config):
        """Test that login command respects force device option."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth.OAuth2TokenManager"
                ) as mock_token_manager:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_from_env.return_value = mock_settings

                    # Mock the OAuth2TokenManager
                    mock_manager = Mock()
                    mock_credentials = Mock()
                    mock_credentials.token = "test-access-token-1234567890"
                    mock_manager.get_credentials.return_value = mock_credentials
                    mock_token_manager.return_value = mock_manager

                    # Run the command with force device
                    result = cli_runner.invoke(
                        auth,
                        ["login", "--customer-id", "1234567890", "--force", "device"],
                    )

                    # Verify get_credentials was called with force_auth_method
                    mock_manager.get_credentials.assert_called_once_with(
                        customer_id="1234567890", force_auth_method="device"
                    )

                    # Verify success output
                    assert result.exit_code == 0

    def test_login_command_handles_authentication_failure(
        self, cli_runner, mock_google_ads_config
    ):
        """Test that login command handles authentication failures gracefully."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth.OAuth2TokenManager"
                ) as mock_token_manager:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_from_env.return_value = mock_settings

                    # Mock the OAuth2TokenManager to raise an exception
                    mock_manager = Mock()
                    mock_manager.get_credentials.side_effect = Exception(
                        "Authentication failed"
                    )
                    mock_token_manager.return_value = mock_manager

                    # Run the command
                    result = cli_runner.invoke(
                        auth, ["login", "--customer-id", "1234567890"]
                    )

                    # Verify failure output
                    assert result.exit_code == 1
                    assert (
                        "❌ Authentication failed: Authentication failed"
                        in result.output
                    )

    def test_login_command_missing_customer_id(self, cli_runner):
        """Test that login command requires customer-id parameter."""
        result = cli_runner.invoke(auth, ["login"])

        assert result.exit_code == 2
        assert "Missing option '--customer-id'" in result.output


class TestAuthTestDeviceFlowCommand:
    """Test the auth test-device-flow command."""

    def test_test_device_flow_uses_settings_from_env(
        self, cli_runner, mock_google_ads_config
    ):
        """Test that test-device-flow command uses Settings.from_env()."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth._is_headless_environment"
                ) as mock_is_headless:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_settings.google_ads.client_id = "test-client-id"
                    mock_from_env.return_value = mock_settings

                    # Mock headless environment detection
                    mock_is_headless.return_value = False

                    # Run the command
                    result = cli_runner.invoke(auth, ["test-device-flow"])

                    # Verify Settings.from_env() was called
                    mock_from_env.assert_called_once()

                    # Verify output contains expected sections
                    assert result.exit_code == 0
                    assert (
                        "🔍 Testing OAuth2 Device Flow Authentication" in result.output
                    )
                    assert "1. Environment Detection:" in result.output
                    assert "4. Configuration Check:" in result.output
                    assert "✅ Google Ads credentials configured" in result.output

    def test_test_device_flow_handles_missing_config(self, cli_runner):
        """Test that test-device-flow command handles missing configuration."""
        with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
            with patch(
                "paidsearchnav.cli.auth._is_headless_environment"
            ) as mock_is_headless:
                # Mock the Settings.from_env() call to return None google_ads
                mock_settings = Mock()
                mock_settings.google_ads = None
                mock_from_env.return_value = mock_settings

                # Mock headless environment detection
                mock_is_headless.return_value = False

                # Run the command
                result = cli_runner.invoke(auth, ["test-device-flow"])

                # Verify Settings.from_env() was called
                mock_from_env.assert_called_once()

                # Verify output contains expected error message
                assert result.exit_code == 0
                assert "❌ Google Ads credentials not configured" in result.output
                assert (
                    "Set PSN_GOOGLE_ADS_CLIENT_ID and PSN_GOOGLE_ADS_CLIENT_SECRET"
                    in result.output
                )

    def test_test_device_flow_handles_settings_exception(self, cli_runner):
        """Test that test-device-flow command handles Settings exceptions."""
        with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
            with patch(
                "paidsearchnav.cli.auth._is_headless_environment"
            ) as mock_is_headless:
                # Mock the Settings.from_env() call to raise an exception
                mock_from_env.side_effect = Exception("Configuration error")

                # Mock headless environment detection
                mock_is_headless.return_value = False

                # Run the command
                result = cli_runner.invoke(auth, ["test-device-flow"])

                # Verify Settings.from_env() was called
                mock_from_env.assert_called_once()

                # Verify output contains expected error message
                assert result.exit_code == 0
                assert "❌ Configuration error: Configuration error" in result.output

    def test_test_device_flow_detects_headless_environment(
        self, cli_runner, mock_google_ads_config
    ):
        """Test that test-device-flow command detects headless environments."""
        with patch.dict(os.environ, mock_google_ads_config):
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                with patch(
                    "paidsearchnav.cli.auth._is_headless_environment"
                ) as mock_is_headless:
                    # Mock the Settings.from_env() call
                    mock_settings = Mock()
                    mock_settings.google_ads = Mock()
                    mock_settings.google_ads.client_id = "test-client-id"
                    mock_from_env.return_value = mock_settings

                    # Mock headless environment detection
                    mock_is_headless.return_value = True

                    # Run the command
                    result = cli_runner.invoke(auth, ["test-device-flow"])

                    # Verify headless detection is called
                    mock_is_headless.assert_called_once()

                    # Verify output shows headless environment
                    assert result.exit_code == 0
                    assert "Headless environment detected: True" in result.output
                    assert "Expected method: device flow" in result.output


class TestAuthCommandIntegration:
    """Integration tests for auth commands."""

    def test_auth_commands_dont_use_regular_settings_constructor(self, cli_runner):
        """Test that auth commands don't use Settings() constructor."""
        # This test ensures we don't regress back to using Settings()

        with patch("paidsearchnav.cli.auth.Settings") as mock_settings_class:
            with patch("paidsearchnav.cli.auth.Settings.from_env") as mock_from_env:
                # Mock the Settings.from_env() call
                mock_settings = Mock()
                mock_settings.google_ads = None
                mock_from_env.return_value = mock_settings

                # Run the test-device-flow command (easier to test than login)
                result = cli_runner.invoke(auth, ["test-device-flow"])

                # Verify Settings class constructor was NOT called
                mock_settings_class.assert_not_called()

                # Verify Settings.from_env() was called
                mock_from_env.assert_called_once()

                # Command should complete successfully
                assert result.exit_code == 0

    def test_auth_commands_environment_variable_loading(self, cli_runner):
        """Test that auth commands can load from environment variables."""
        env_vars = {
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "test-token",
            "PSN_GOOGLE_ADS_CLIENT_ID": "test-client-id",
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "test-secret",
        }

        with patch.dict(os.environ, env_vars):
            # Test that we can create Settings.from_env() without errors
            settings = Settings.from_env()

            # Verify Google Ads configuration is loaded
            assert settings.google_ads is not None
            assert settings.google_ads.client_id == "test-client-id"
            assert (
                settings.google_ads.developer_token.get_secret_value() == "test-token"
            )
            assert settings.google_ads.client_secret.get_secret_value() == "test-secret"
