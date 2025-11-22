"""Integration tests for CLI auth commands with environment variables."""

import os
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.auth import auth


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def complete_env_config():
    """Complete Google Ads environment configuration."""
    return {
        "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "test-developer-token-123",
        "PSN_GOOGLE_ADS_CLIENT_ID": "test-client-id-456",
        "PSN_GOOGLE_ADS_CLIENT_SECRET": "test-client-secret-789",
        "PSN_GOOGLE_ADS_REFRESH_TOKEN": "test-refresh-token-abc",
        "PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
    }


class TestAuthIntegrationWithEnvironment:
    """Integration tests verifying full auth flow with environment variables."""

    def test_full_auth_flow_with_environment_variables(
        self, cli_runner, complete_env_config
    ):
        """Test complete authentication flow using environment variables."""
        with patch.dict(os.environ, complete_env_config):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                # Mock successful authentication
                mock_manager = Mock()
                mock_credentials = Mock()
                mock_credentials.token = "test-access-token-full-integration"
                mock_manager.get_credentials.return_value = mock_credentials
                mock_token_manager.return_value = mock_manager

                # Run the login command
                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "1234567890"]
                )

                # Verify successful authentication
                assert result.exit_code == 0
                assert "Authenticating for customer ID: 1234567890" in result.output
                assert "✅ Authentication successful!" in result.output
                assert "Access token: test-access-token-fu..." in result.output

                # Verify OAuth2TokenManager was called with properly loaded settings
                mock_token_manager.assert_called_once()
                settings = mock_token_manager.call_args[0][0]

                # Verify environment variables were loaded into settings
                assert settings.google_ads is not None
                assert settings.google_ads.client_id == "test-client-id-456"
                assert (
                    settings.google_ads.client_secret.get_secret_value()
                    == "test-client-secret-789"
                )
                assert (
                    settings.google_ads.developer_token.get_secret_value()
                    == "test-developer-token-123"
                )

    def test_auth_flow_with_partial_environment_config(
        self, cli_runner, complete_env_config
    ):
        """Test auth flow behavior with missing environment variables."""
        # Remove client secret to simulate incomplete config
        incomplete_config = complete_env_config.copy()
        del incomplete_config["PSN_GOOGLE_ADS_CLIENT_SECRET"]

        with patch.dict(os.environ, incomplete_config, clear=True):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                # Mock token manager to verify it receives incomplete config
                mock_manager = Mock()
                mock_token_manager.return_value = mock_manager
                mock_manager.get_credentials.side_effect = Exception(
                    "Client secret not configured"
                )

                # Run the login command
                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "1234567890"]
                )

                # Verify authentication fails with proper error
                assert result.exit_code == 1
                assert "❌ Authentication failed" in result.output
                assert "Client secret not configured" in result.output

    def test_test_device_flow_with_environment_variables(
        self, cli_runner, complete_env_config
    ):
        """Test device flow command with environment variables."""
        with patch.dict(os.environ, complete_env_config):
            with patch(
                "paidsearchnav.cli.auth._is_headless_environment"
            ) as mock_is_headless:
                # Mock headless environment
                mock_is_headless.return_value = True

                # Run the test-device-flow command
                result = cli_runner.invoke(auth, ["test-device-flow"])

                # Verify command succeeds and loads environment config
                assert result.exit_code == 0
                assert "🔍 Testing OAuth2 Device Flow Authentication" in result.output
                assert "Headless environment detected: True" in result.output
                assert "Expected method: device flow" in result.output
                assert "✅ Google Ads credentials configured" in result.output

    def test_force_authentication_methods_with_environment(
        self, cli_runner, complete_env_config
    ):
        """Test force authentication methods with environment variables."""
        with patch.dict(os.environ, complete_env_config):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                mock_manager = Mock()
                mock_credentials = Mock()
                mock_credentials.token = "test-token-forced"
                mock_manager.get_credentials.return_value = mock_credentials
                mock_token_manager.return_value = mock_manager

                # Test force browser
                result = cli_runner.invoke(
                    auth,
                    ["login", "--customer-id", "1234567890", "--force", "browser"],
                )

                assert result.exit_code == 0
                mock_manager.get_credentials.assert_called_with(
                    customer_id="1234567890", force_auth_method="browser"
                )

                # Reset mock
                mock_manager.reset_mock()

                # Test force device
                result = cli_runner.invoke(
                    auth,
                    ["login", "--customer-id", "1234567890", "--force", "device"],
                )

                assert result.exit_code == 0
                mock_manager.get_credentials.assert_called_with(
                    customer_id="1234567890", force_auth_method="device"
                )

    def test_environment_variable_precedence(self, cli_runner):
        """Test that environment variables take precedence over defaults."""
        # Test with specific environment values
        test_config = {
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "env-developer-token",
            "PSN_GOOGLE_ADS_CLIENT_ID": "env-client-id",
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "env-client-secret",
            "PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID": "9876543210",
        }

        with patch.dict(os.environ, test_config):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                mock_manager = Mock()
                mock_credentials = Mock()
                mock_credentials.token = "test-token"
                mock_manager.get_credentials.return_value = mock_credentials
                mock_token_manager.return_value = mock_manager

                # Run command
                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "9876543210"]
                )

                assert result.exit_code == 0

                # Verify the settings object received the environment values
                settings = mock_token_manager.call_args[0][0]
                assert settings.google_ads.client_id == "env-client-id"
                assert (
                    settings.google_ads.client_secret.get_secret_value()
                    == "env-client-secret"
                )
                assert (
                    settings.google_ads.developer_token.get_secret_value()
                    == "env-developer-token"
                )

    def test_token_storage_integration(self, cli_runner, complete_env_config):
        """Test that authentication integrates with token storage."""
        with patch.dict(os.environ, complete_env_config):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                # Mock token manager with storage behavior
                mock_manager = Mock()
                mock_credentials = Mock()
                mock_credentials.token = "stored-token-123"
                mock_manager.get_credentials.return_value = mock_credentials
                mock_token_manager.return_value = mock_manager

                # Run authentication
                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "1234567890"]
                )

                assert result.exit_code == 0
                assert "Access token: stored-token-123..." in result.output

                # Verify token manager was properly initialized with settings
                mock_token_manager.assert_called_once()
                settings = mock_token_manager.call_args[0][0]
                assert settings.google_ads is not None

                # Verify credentials were requested
                mock_manager.get_credentials.assert_called_once_with(
                    customer_id="1234567890", force_auth_method=None
                )


class TestAuthEnvironmentErrorHandling:
    """Test error handling with various environment configurations."""

    def test_missing_all_environment_variables(self, cli_runner):
        """Test behavior when no Google Ads environment variables are set."""
        # Clear all PSN environment variables
        clean_env = {
            k: v for k, v in os.environ.items() if not k.startswith("PSN_GOOGLE_ADS")
        }

        with patch.dict(os.environ, clean_env, clear=True):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                mock_manager = Mock()
                mock_token_manager.return_value = mock_manager
                mock_manager.get_credentials.side_effect = Exception(
                    "Google Ads configuration not provided"
                )

                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "1234567890"]
                )

                assert result.exit_code == 1
                assert "❌ Authentication failed" in result.output
                assert "Google Ads configuration not provided" in result.output

    def test_invalid_environment_variable_format(self, cli_runner):
        """Test handling of malformed environment variables."""
        invalid_config = {
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "",  # Empty token
            "PSN_GOOGLE_ADS_CLIENT_ID": "   ",  # Whitespace only
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "secret",  # Valid secret
        }

        with patch.dict(os.environ, invalid_config, clear=True):
            with patch(
                "paidsearchnav.cli.auth.OAuth2TokenManager"
            ) as mock_token_manager:
                mock_manager = Mock()
                mock_token_manager.return_value = mock_manager
                mock_manager.get_credentials.side_effect = Exception(
                    "Invalid credentials format"
                )

                result = cli_runner.invoke(
                    auth, ["login", "--customer-id", "1234567890"]
                )

                assert result.exit_code == 1
                assert "❌ Authentication failed" in result.output
                assert "Invalid credentials format" in result.output

    def test_device_flow_environment_detection(self, cli_runner, complete_env_config):
        """Test device flow detection with various environment configurations."""
        # Test with CI environment
        ci_env = complete_env_config.copy()
        ci_env["CI"] = "true"

        with patch.dict(os.environ, ci_env):
            result = cli_runner.invoke(auth, ["test-device-flow"])

            assert result.exit_code == 0
            assert "Headless environment detected: True" in result.output
            assert "Expected method: device flow" in result.output
            assert "CI: true" in result.output

        # Test with explicit headless flag
        headless_env = complete_env_config.copy()
        headless_env["PSN_HEADLESS"] = "true"

        with patch.dict(os.environ, headless_env):
            result = cli_runner.invoke(auth, ["test-device-flow"])

            assert result.exit_code == 0
            assert "Headless environment detected: True" in result.output
            assert "PSN_HEADLESS: true" in result.output
