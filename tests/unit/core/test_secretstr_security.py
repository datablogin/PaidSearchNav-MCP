"""Tests to ensure SecretStr fields don't leak sensitive data."""

import json
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from paidsearchnav.core.config import (
    GoogleAdsConfig,
    LoggingConfig,
    SchedulerConfig,
    Settings,
    StorageBackend,
    StorageConfig,
)


class TestSecretStrSecurity:
    """Test that SecretStr fields properly hide sensitive data."""

    def test_settings_repr_hides_secrets(self):
        """Test that string representation of settings hides secrets."""
        settings = Settings(
            database_url=SecretStr("postgresql://user:password@localhost/db"),
            jwt_secret_key=SecretStr("super-secret-key"),
            api_key=SecretStr("api-key-123"),
        )

        settings_str = str(settings)
        settings_repr = repr(settings)

        # Secrets should not appear in string representation
        assert "password" not in settings_str
        assert "super-secret-key" not in settings_str
        assert "api-key-123" not in settings_str

        assert "password" not in settings_repr
        assert "super-secret-key" not in settings_repr
        assert "api-key-123" not in settings_repr

        # Should show masked values
        assert "**********" in settings_str or "SecretStr" in settings_str

    def test_google_ads_config_repr_hides_secrets(self):
        """Test that GoogleAdsConfig string representation hides secrets."""
        config = GoogleAdsConfig(
            developer_token=SecretStr("dev-token-123"),
            client_id="client-id",
            client_secret=SecretStr("client-secret-456"),
            refresh_token=SecretStr("refresh-token-789"),
        )

        config_str = str(config)
        config_repr = repr(config)

        # Secrets should not appear
        assert "dev-token-123" not in config_str
        assert "client-secret-456" not in config_str
        assert "refresh-token-789" not in config_str

        assert "dev-token-123" not in config_repr
        assert "client-secret-456" not in config_repr
        assert "refresh-token-789" not in config_repr

        # Non-secret fields should appear
        assert "client-id" in config_str

    def test_storage_config_repr_hides_connection_string(self):
        """Test that StorageConfig hides connection string."""
        config = StorageConfig(
            backend=StorageBackend.POSTGRESQL,
            connection_string=SecretStr("postgresql://user:password@localhost/db"),
        )

        config_str = str(config)
        config_repr = repr(config)

        # Connection string with password should not appear
        assert "password" not in config_str
        assert "password" not in config_repr
        assert "postgresql://user:password" not in config_str

    def test_scheduler_config_repr_hides_job_store_url(self):
        """Test that SchedulerConfig hides job store URL."""
        config = SchedulerConfig(
            job_store_url=SecretStr("postgresql://user:password@localhost/scheduler")
        )

        config_str = str(config)
        config_repr = repr(config)

        # Job store URL with password should not appear
        assert "password" not in config_str
        assert "password" not in config_repr

    def test_logging_config_repr_hides_secrets(self):
        """Test that LoggingConfig hides webhook URLs and DSNs."""
        config = LoggingConfig(
            sentry_dsn=SecretStr("https://key@sentry.io/project"),
            slack_webhook_url=SecretStr("https://hooks.slack.com/services/SECRET"),
        )

        config_str = str(config)
        config_repr = repr(config)

        # Secrets should not appear
        assert "key@sentry.io" not in config_str
        assert "hooks.slack.com/services/SECRET" not in config_str

    def test_json_serialization_excludes_secrets(self):
        """Test that JSON serialization doesn't include secret values."""
        settings = Settings(
            database_url=SecretStr("postgresql://user:password@localhost/db"),
            jwt_secret_key=SecretStr("super-secret-key"),
        )

        # Model dump should not include secret values by default
        data = settings.model_dump()

        # When serialized to JSON, secrets should be masked
        json_str = json.dumps(data, default=str)

        # Raw secret values should not appear in JSON
        assert "password" not in json_str
        assert "super-secret-key" not in json_str

    def test_model_dump_with_mode_excludes_secrets(self):
        """Test that model_dump with mode='json' properly handles secrets."""
        config = GoogleAdsConfig(
            developer_token=SecretStr("dev-token"),
            client_id="client-123",
            client_secret=SecretStr("secret-456"),
        )

        # Dump with JSON mode
        json_data = config.model_dump(mode="json")
        json_str = json.dumps(json_data)

        # Secrets should not be in plain text
        assert "dev-token" not in json_str
        assert "secret-456" not in json_str

        # But non-secret data should be there
        assert "client-123" in json_str

    def test_settings_from_env_creates_secretstr(self):
        """Test that Settings.from_env properly wraps sensitive values in SecretStr."""
        env_vars = {
            "PSN_DATABASE_URL": "postgresql://user:password@localhost/db",
            "PSN_JWT_SECRET_KEY": "jwt-secret",
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "dev-token",
            "PSN_GOOGLE_ADS_CLIENT_ID": "client-id",
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "client-secret",
            "PSN_STORAGE_CONNECTION_STRING": "postgresql://storage:pass@localhost/db",
            "PSN_SCHEDULER_JOB_STORE_URL": "postgresql://scheduler:pass@localhost/db",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings.from_env()

            # Verify that sensitive fields are SecretStr instances
            assert isinstance(settings.database_url, SecretStr)
            assert isinstance(settings.jwt_secret_key, SecretStr)

            if settings.google_ads:
                assert isinstance(settings.google_ads.developer_token, SecretStr)
                assert isinstance(settings.google_ads.client_secret, SecretStr)

            if settings.storage.connection_string:
                assert isinstance(settings.storage.connection_string, SecretStr)

            if settings.scheduler.job_store_url:
                assert isinstance(settings.scheduler.job_store_url, SecretStr)

            # Verify values can be retrieved with get_secret_value()
            assert (
                settings.database_url.get_secret_value() == env_vars["PSN_DATABASE_URL"]
            )
            assert (
                settings.jwt_secret_key.get_secret_value()
                == env_vars["PSN_JWT_SECRET_KEY"]
            )

    def test_accidental_logging_prevention(self):
        """Test that accidental logging doesn't expose secrets."""
        import logging
        from io import StringIO

        # Create a string buffer to capture log output
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Create settings with secrets
        settings = Settings(
            database_url=SecretStr("postgresql://user:password@localhost/db"),
            jwt_secret_key=SecretStr("super-secret-key"),
        )

        # Log the settings object
        logger.info(f"Settings: {settings}")
        logger.debug(f"Config: {settings}")

        # Get log output
        log_output = log_buffer.getvalue()

        # Secrets should not appear in logs
        assert "password" not in log_output
        assert "super-secret-key" not in log_output

    def test_error_messages_dont_expose_secrets(self):
        """Test that validation errors don't expose secret values."""
        from pydantic import ValidationError

        # Try to create config with invalid data that might trigger errors
        with pytest.raises(ValidationError) as exc_info:
            GoogleAdsConfig(
                developer_token=SecretStr(""),  # Empty token
                client_id="client-id",
                client_secret=SecretStr("secret"),
            )

        error_str = str(exc_info.value)

        # Even in error messages, actual secret values shouldn't appear
        # (though this specific test might not trigger secret exposure,
        # it's good practice to verify)
        assert "secret" not in error_str or "SecretStr" in error_str
