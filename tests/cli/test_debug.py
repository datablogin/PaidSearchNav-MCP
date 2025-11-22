"""Tests for the debug CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.main import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create a mock settings object."""
    settings = MagicMock()
    settings.environment.value = "development"
    settings.debug = False
    settings.data_dir.exists.return_value = True
    settings.data_dir.__str__ = MagicMock(return_value="/home/user/.paidsearchnav")

    # Google Ads config
    settings.google_ads = MagicMock()
    settings.google_ads.api_version = "v18"
    settings.google_ads.developer_token = "test-token"
    settings.google_ads.client_id = "test-client-id"
    # Mock client_secret as SecretStr with get_secret_value method
    settings.google_ads.client_secret = MagicMock()
    settings.google_ads.client_secret.get_secret_value.return_value = "test-secret"
    settings.google_ads.login_customer_id = "1234567890"
    settings.google_ads.enable_rate_limiting = True
    settings.google_ads.search_requests_per_minute = 300
    settings.google_ads.search_requests_per_hour = 18000
    settings.google_ads.search_requests_per_day = 432000
    settings.google_ads.mutate_requests_per_minute = 100
    settings.google_ads.mutate_requests_per_hour = 6000
    settings.google_ads.mutate_requests_per_day = 144000
    settings.google_ads.report_requests_per_minute = 133
    settings.google_ads.report_requests_per_hour = 7980
    settings.google_ads.report_requests_per_day = 191520
    settings.google_ads.bulk_requests_per_minute = 15
    settings.google_ads.bulk_requests_per_hour = 900
    settings.google_ads.bulk_requests_per_day = 21600
    settings.google_ads.max_retries = 3
    settings.google_ads.backoff_multiplier = 2.0
    settings.google_ads.max_backoff_seconds = 60.0

    # Storage config
    settings.storage.backend.value = "postgresql"
    settings.storage.connection_string = "postgresql://localhost/test"

    # Redis config
    settings.redis.enabled = False
    settings.redis.url = "redis://localhost:6379"

    # Scheduler config
    settings.scheduler.enabled = True
    settings.scheduler.default_schedule = "0 0 1 */3 *"

    # Features
    settings.features.enable_pmax_analysis = True
    settings.features.enable_geo_dashboard = True
    settings.features.enable_auto_negatives = False

    # Logging
    settings.logging.level = "INFO"
    settings.logging.email_alerts_to = None
    settings.logging.webhook_url = None
    settings.logging.slack_webhook_url = None
    settings.logging.webhook_timeout = 30
    settings.logging.webhook_ssl_verify = True
    settings.logging.email_recipients = []

    # JWT secret key mock
    settings.jwt_secret_key = MagicMock()
    settings.jwt_secret_key.get_secret_value.return_value = "test-jwt-secret"

    return settings


class TestDebugInfo:
    """Test the debug info command."""

    @patch("paidsearchnav.cli.debug.Settings")
    @patch("paidsearchnav.cli.debug.psutil")
    def test_info_success(
        self, mock_psutil, mock_settings_class, runner, mock_settings
    ):
        """Test successful debug info display."""
        mock_settings_class.from_env.return_value = mock_settings

        # Mock psutil memory info
        mock_memory = MagicMock()
        mock_memory.total = 16 * 1024**3  # 16GB
        mock_memory.available = 8 * 1024**3  # 8GB
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        # Mock disk usage
        mock_disk = MagicMock()
        mock_disk.free = 100 * 1024**3  # 100GB
        mock_disk.used = 50 * 1024**3  # 50GB
        mock_disk.total = 150 * 1024**3  # 150GB
        mock_psutil.disk_usage.return_value = mock_disk

        result = runner.invoke(cli, ["debug", "info"])

        assert result.exit_code == 0
        assert "PaidSearchNav Debug Information" in result.output
        assert "System Information" in result.output
        assert "Configuration Status" in result.output
        assert "Feature Flags" in result.output
        assert "16.0 GB" in result.output  # Total memory
        assert "Google Ads API" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_info_config_error(self, mock_settings_class, runner):
        """Test debug info with configuration error."""
        mock_settings_class.from_env.side_effect = Exception("Config error")

        result = runner.invoke(cli, ["debug", "info"])

        assert result.exit_code == 0
        assert "Configuration Error" in result.output


class TestDebugValidateConfig:
    """Test the validate-config command."""

    @patch("paidsearchnav.cli.debug.Settings")
    def test_validate_config_success(self, mock_settings_class, runner, mock_settings):
        """Test successful configuration validation."""
        mock_settings_class.from_env.return_value = mock_settings
        mock_settings.validate_required_settings.return_value = None

        result = runner.invoke(cli, ["debug", "validate-config"])

        assert result.exit_code == 0
        assert "Configuration Validation" in result.output
        assert "Required settings validation passed" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_validate_config_with_errors(
        self, mock_settings_class, runner, mock_settings
    ):
        """Test configuration validation with errors."""
        mock_settings_class.from_env.return_value = mock_settings
        mock_settings.validate_required_settings.side_effect = ValueError(
            "Missing required setting"
        )
        mock_settings.environment.value = "production"
        mock_settings.debug = True  # Debug mode in production - warning

        result = runner.invoke(cli, ["debug", "validate-config"])

        assert result.exit_code == 0
        assert "Configuration Errors" in result.output
        assert "Configuration Warnings" in result.output
        assert "Missing required setting" in result.output
        assert "Debug mode is enabled in production" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_validate_config_jwt_warning(
        self, mock_settings_class, runner, mock_settings
    ):
        """Test JWT secret key validation in production."""
        mock_settings_class.from_env.return_value = mock_settings
        mock_settings.validate_required_settings.return_value = None
        mock_settings.environment.value = "production"
        mock_settings.debug = False
        mock_settings.jwt_secret_key.get_secret_value.return_value = (
            "change-me-in-production"
        )

        result = runner.invoke(cli, ["debug", "validate-config"])

        assert result.exit_code == 0
        assert "JWT secret key is still set to default value" in result.output


class TestDebugTestDb:
    """Test the test-db command."""

    @patch("paidsearchnav.cli.debug.AnalysisRepository")
    @patch("paidsearchnav.cli.debug.Settings")
    @patch("paidsearchnav.cli.debug.asyncio")
    def test_db_test_success(
        self, mock_asyncio, mock_settings_class, mock_repo_class, runner, mock_settings
    ):
        """Test successful database connectivity test."""
        mock_settings_class.from_env.return_value = mock_settings

        # Mock repository and session
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_session = MagicMock()
        mock_async_session_context = MagicMock()
        mock_async_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session_context.__aexit__ = AsyncMock(return_value=None)
        mock_repo.AsyncSessionLocal.return_value = mock_async_session_context

        # Mock database queries
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_result.fetchall.return_value = [
            ("customers",),
            ("audits",),
            ("analysis_records",),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock asyncio.run to return success
        mock_asyncio.run.return_value = True

        result = runner.invoke(cli, ["debug", "test-db"])

        assert result.exit_code == 0
        assert "Database Connectivity Test" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_db_test_setup_error(self, mock_settings_class, runner):
        """Test database test with setup error."""
        mock_settings_class.from_env.side_effect = Exception("Setup error")

        result = runner.invoke(cli, ["debug", "test-db"])

        assert result.exit_code == 0
        assert "Database test setup failed" in result.output


class TestDebugTestAuth:
    """Test the test-auth command."""

    @patch("paidsearchnav.cli.debug.GoogleAdsAPIClient")
    @patch("paidsearchnav.cli.debug.OAuth2TokenManager")
    @patch("paidsearchnav.cli.debug.Settings")
    def test_auth_test_success(
        self,
        mock_settings_class,
        mock_token_manager_class,
        mock_client_class,
        runner,
        mock_settings,
    ):
        """Test successful authentication test."""
        mock_settings_class.from_env.return_value = mock_settings

        # Mock token manager
        mock_token_manager = MagicMock()
        mock_token_manager_class.return_value = mock_token_manager
        mock_token_manager.get_credentials.return_value = MagicMock()

        # Mock API client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock customer data
        mock_customer = MagicMock()
        mock_customer.id = "1234567890"
        mock_customer.descriptive_name = "Test Customer"
        mock_customer.status.name = "ENABLED"
        mock_client.list_customers.return_value = [mock_customer]

        result = runner.invoke(
            cli, ["debug", "test-auth", "--customer-id", "1234567890"]
        )

        assert result.exit_code == 0
        assert "Google Ads API Authentication Test" in result.output
        assert "Successfully retrieved credentials" in result.output
        assert "API client initialized successfully" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_auth_test_no_config(self, mock_settings_class, runner, mock_settings):
        """Test authentication test with no Google Ads configuration."""
        mock_settings.google_ads = None
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "test-auth"])

        assert result.exit_code == 0
        assert "Google Ads configuration not found" in result.output

    @patch("paidsearchnav.cli.debug.OAuth2TokenManager")
    @patch("paidsearchnav.cli.debug.Settings")
    def test_auth_test_no_customer_id(
        self, mock_settings_class, mock_token_manager_class, runner, mock_settings
    ):
        """Test authentication test with no customer ID."""
        mock_settings.google_ads.login_customer_id = None
        mock_settings_class.from_env.return_value = mock_settings

        # Mock token manager to avoid initialization issues
        mock_token_manager = MagicMock()
        mock_token_manager_class.return_value = mock_token_manager

        result = runner.invoke(cli, ["debug", "test-auth"])

        assert result.exit_code == 0
        assert "No customer ID provided or configured" in result.output


class TestDebugApiUsage:
    """Test the api-usage command."""

    @patch("paidsearchnav.cli.debug.Settings")
    def test_api_usage_success(self, mock_settings_class, runner, mock_settings):
        """Test successful API usage display."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "api-usage"])

        assert result.exit_code == 0
        assert "Google Ads API Usage Monitor" in result.output
        assert "Configured Rate Limits" in result.output
        assert "300" in result.output  # Search requests per minute
        assert "Rate Limiting: Enabled" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_api_usage_no_config(self, mock_settings_class, runner, mock_settings):
        """Test API usage with no Google Ads configuration."""
        mock_settings.google_ads = None
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "api-usage"])

        assert result.exit_code == 0
        assert "Google Ads configuration not found" in result.output


class TestDebugClearCache:
    """Test the clear-cache command."""

    @patch("redis.from_url")
    @patch("paidsearchnav.cli.debug.Settings")
    def test_clear_cache_redis_success(
        self, mock_settings_class, mock_redis_from_url, runner, mock_settings
    ):
        """Test successful Redis cache clearing."""
        mock_settings.redis.enabled = True
        mock_settings_class.from_env.return_value = mock_settings

        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_from_url.return_value = mock_redis_client
        mock_redis_client.keys.return_value = [b"psn:key1", b"psn:key2"]
        mock_redis_client.delete.return_value = 2

        result = runner.invoke(
            cli, ["debug", "clear-cache", "--type", "redis", "--confirm"]
        )

        assert result.exit_code == 0
        assert "Cleared 2 Redis cache entries" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_clear_cache_local_success(
        self, mock_settings_class, runner, mock_settings, tmp_path
    ):
        """Test successful local cache clearing."""
        mock_settings.data_dir = tmp_path
        mock_settings_class.from_env.return_value = mock_settings

        # Create some cache files
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.cache").write_text("cache data")

        result = runner.invoke(
            cli, ["debug", "clear-cache", "--type", "local", "--confirm"]
        )

        assert result.exit_code == 0
        assert "Cache clear operation completed" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_clear_cache_cancelled(self, mock_settings_class, runner, mock_settings):
        """Test cache clear cancellation."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "clear-cache"], input="n\n")

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output


class TestDebugResetDb:
    """Test the reset-db command."""

    @patch("paidsearchnav.cli.debug.AnalysisRepository")
    @patch("paidsearchnav.cli.debug.Settings")
    @patch("paidsearchnav.cli.debug.asyncio")
    def test_reset_db_success(
        self, mock_asyncio, mock_settings_class, mock_repo_class, runner, mock_settings
    ):
        """Test successful database reset."""
        mock_settings_class.from_env.return_value = mock_settings
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_asyncio.run.return_value = True

        result = runner.invoke(cli, ["debug", "reset-db", "--confirm"])

        assert result.exit_code == 0
        assert "Database Reset" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_reset_db_cancelled(self, mock_settings_class, runner, mock_settings):
        """Test database reset cancellation."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "reset-db"], input="n\n")

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output


class TestDebugTestEmail:
    """Test the test-email command."""

    @patch("paidsearchnav.cli.debug.Settings")
    def test_email_test_no_config(self, mock_settings_class, runner, mock_settings):
        """Test email test with no configuration."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(
            cli, ["debug", "test-email", "--recipient", "test@example.com"]
        )

        assert result.exit_code == 0
        assert "Email alerts not configured" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_email_test_configured(self, mock_settings_class, runner, mock_settings):
        """Test email test with configuration."""
        mock_settings.logging.email_alerts_to = "admin@example.com"
        mock_settings.logging.email_recipients = ["admin@example.com"]
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(
            cli, ["debug", "test-email", "--recipient", "test@example.com"]
        )

        assert result.exit_code == 0
        assert "Testing email to: test@example.com" in result.output
        assert "admin@example.com" in result.output


class TestDebugTestWebhook:
    """Test the test-webhook command."""

    @patch("requests.post")
    @patch("paidsearchnav.cli.debug.Settings")
    def test_webhook_test_success(
        self, mock_settings_class, mock_requests_post, runner, mock_settings
    ):
        """Test successful webhook test."""
        mock_settings.logging.webhook_url = MagicMock()
        mock_settings.logging.webhook_url.get_secret_value.return_value = (
            "https://example.com/webhook"
        )
        mock_settings_class.from_env.return_value = mock_settings

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_requests_post.return_value = mock_response

        result = runner.invoke(cli, ["debug", "test-webhook"])

        assert result.exit_code == 0
        assert "Webhook test successful" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_webhook_test_no_config(self, mock_settings_class, runner, mock_settings):
        """Test webhook test with no configuration."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "test-webhook"])

        assert result.exit_code == 0
        assert "Webhook URL not configured" in result.output


class TestDebugTestSlack:
    """Test the test-slack command."""

    @patch("requests.post")
    @patch("paidsearchnav.cli.debug.Settings")
    def test_slack_test_success(
        self, mock_settings_class, mock_requests_post, runner, mock_settings
    ):
        """Test successful Slack test."""
        mock_settings.logging.slack_webhook_url = MagicMock()
        mock_settings.logging.slack_webhook_url.get_secret_value.return_value = (
            "https://hooks.slack.com/webhook"
        )
        mock_settings_class.from_env.return_value = mock_settings

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        result = runner.invoke(cli, ["debug", "test-slack"])

        assert result.exit_code == 0
        assert "Slack test message sent successfully" in result.output

    @patch("paidsearchnav.cli.debug.Settings")
    def test_slack_test_no_config(self, mock_settings_class, runner, mock_settings):
        """Test Slack test with no configuration."""
        mock_settings_class.from_env.return_value = mock_settings

        result = runner.invoke(cli, ["debug", "test-slack"])

        assert result.exit_code == 0
        assert "Slack webhook URL not configured" in result.output
