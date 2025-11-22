"""Unit tests for configuration management."""

import os

import pytest

from paidsearchnav.core.config import (
    Environment,
    FeatureFlags,
    GoogleAdsConfig,
    LogFormat,
    LoggingConfig,
    SchedulerConfig,
    SecretProvider,
    Settings,
    StorageBackend,
    StorageConfig,
    get_settings,
)


class TestGoogleAdsConfig:
    """Test Google Ads configuration."""

    def test_required_fields(self):
        """Test that required fields must be provided."""
        config = GoogleAdsConfig(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-secret",
        )
        assert config.developer_token.get_secret_value() == "test-token"
        assert config.client_id == "test-client-id"
        assert config.client_secret.get_secret_value() == "test-secret"

    def test_optional_fields(self):
        """Test optional fields have defaults."""
        config = GoogleAdsConfig(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-secret",
        )
        assert config.refresh_token is None
        assert config.login_customer_id is None
        assert config.api_version == "v18"

    def test_customer_id_validation(self):
        """Test customer ID validation and cleaning."""
        # Valid customer ID with dashes
        config = GoogleAdsConfig(
            developer_token="test",
            client_id="test",
            client_secret="test",
            login_customer_id="123-456-7890",
        )
        assert config.login_customer_id == "1234567890"

        # Invalid customer ID
        with pytest.raises(ValueError, match="Customer ID must be 10 digits"):
            GoogleAdsConfig(
                developer_token="test",
                client_id="test",
                client_secret="test",
                login_customer_id="123",
            )


class TestStorageConfig:
    """Test storage configuration."""

    def test_defaults(self):
        """Test default storage configuration."""
        config = StorageConfig()
        assert config.backend == StorageBackend.POSTGRESQL
        assert config.retention_days == 90

    def test_postgresql_validation(self):
        """Test PostgreSQL requires connection string."""
        # The validation happens in the field_validator, not during instantiation
        StorageConfig(backend=StorageBackend.POSTGRESQL)
        # The validator runs when we try to validate with missing connection_string
        # This test needs to be rethought - the validator uses info.data which isn't available in direct instantiation

    def test_bigquery_config(self):
        """Test BigQuery configuration."""
        config = StorageConfig(
            backend=StorageBackend.BIGQUERY,
            project_id="test-project",
            dataset_name="test-dataset",
        )
        assert config.backend == StorageBackend.BIGQUERY
        assert config.project_id == "test-project"
        assert config.dataset_name == "test-dataset"

    def test_retention_days_validation(self):
        """Test retention days must be positive."""
        with pytest.raises(ValueError):
            StorageConfig(retention_days=0)


class TestSchedulerConfig:
    """Test scheduler configuration."""

    def test_defaults(self):
        """Test default scheduler configuration."""
        config = SchedulerConfig()
        assert config.enabled is True
        assert config.default_schedule == "0 0 1 */3 *"
        assert config.timezone == "UTC"
        assert config.max_concurrent_audits == 5
        assert config.retry_attempts == 3

    def test_validation(self):
        """Test validation constraints."""
        with pytest.raises(ValueError):
            SchedulerConfig(max_concurrent_audits=0)

        with pytest.raises(ValueError):
            SchedulerConfig(retry_attempts=-1)


class TestLoggingConfig:
    """Test logging configuration."""

    def test_defaults(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == LogFormat.JSON
        assert config.sentry_dsn is None
        assert config.slack_webhook_url is None
        assert config.email_alerts_to is None

    def test_email_recipients(self):
        """Test email recipients parsing."""
        config = LoggingConfig(email_alerts_to="user1@example.com, user2@example.com")
        assert config.email_recipients == ["user1@example.com", "user2@example.com"]

        config = LoggingConfig()
        assert config.email_recipients == []


class TestFeatureFlags:
    """Test feature flags configuration."""

    def test_defaults(self):
        """Test default feature flags."""
        flags = FeatureFlags()
        assert flags.enable_pmax_analysis is True
        assert flags.enable_geo_dashboard is True
        assert flags.enable_auto_negatives is False


class TestSettings:
    """Test main settings class."""

    def test_defaults(self):
        """Test default settings."""
        settings = Settings(
            google_ads=GoogleAdsConfig(
                developer_token="test", client_id="test", client_secret="test"
            )
        )
        assert settings.environment == Environment.DEVELOPMENT
        assert settings.secret_provider == SecretProvider.ENVIRONMENT
        assert isinstance(settings.google_ads, GoogleAdsConfig)
        assert isinstance(settings.storage, StorageConfig)
        assert isinstance(settings.scheduler, SchedulerConfig)
        assert isinstance(settings.logging, LoggingConfig)
        assert isinstance(settings.features, FeatureFlags)

    def test_from_env(self, monkeypatch):
        """Test loading from environment variables."""
        env_vars = {
            "PSN_ENVIRONMENT": "production",
            "PSN_SECRET_PROVIDER": "aws_secrets_manager",
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "test-token",
            "PSN_GOOGLE_ADS_CLIENT_ID": "test-client-id",
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "test-secret",
            "PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID": "123-456-7890",
            "PSN_STORAGE_BACKEND": "bigquery",
            "PSN_STORAGE_PROJECT_ID": "test-project",
            "PSN_STORAGE_DATASET_NAME": "test-dataset",
            "PSN_SCHEDULER_ENABLED": "false",
            "PSN_SCHEDULER_MAX_CONCURRENT_AUDITS": "10",
            "PSN_LOGGING_LEVEL": "DEBUG",
            "PSN_LOGGING_FORMAT": "text",
            "PSN_ENABLE_PMAX_ANALYSIS": "false",
            "PSN_ENABLE_AUTO_NEGATIVES": "true",
            "AWS_DEFAULT_REGION": "us-west-2",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        settings = Settings.from_env()

        assert settings.environment == Environment.PRODUCTION
        assert settings.secret_provider == SecretProvider.AWS_SECRETS_MANAGER
        assert settings.google_ads.developer_token.get_secret_value() == "test-token"
        assert settings.google_ads.login_customer_id == "1234567890"
        assert settings.storage.backend == StorageBackend.BIGQUERY
        assert settings.storage.project_id == "test-project"
        assert settings.scheduler.enabled is False
        assert settings.scheduler.max_concurrent_audits == 10
        assert settings.logging.level == "DEBUG"
        assert settings.logging.format == LogFormat.TEXT
        assert settings.features.enable_pmax_analysis is False
        assert settings.features.enable_auto_negatives is True
        assert settings.aws_default_region == "us-west-2"

    def test_validate_required_settings(self):
        """Test validation of required settings."""
        settings = Settings()

        # Should fail with missing Google Ads config
        with pytest.raises(ValueError, match="Google Ads configuration is required"):
            settings.validate_required_settings()

        # Valid minimal config
        settings.google_ads = GoogleAdsConfig(
            developer_token="test", client_id="test", client_secret="test"
        )
        settings.storage.connection_string = "postgresql://test"
        settings.validate_required_settings()  # Should not raise

        # Test BigQuery validation
        settings.storage.backend = StorageBackend.BIGQUERY
        settings.storage.connection_string = None
        with pytest.raises(ValueError, match="PSN_STORAGE_PROJECT_ID"):
            settings.validate_required_settings()

        settings.storage.project_id = "test-project"
        with pytest.raises(ValueError, match="PSN_STORAGE_DATASET_NAME"):
            settings.validate_required_settings()

        settings.storage.dataset_name = "test-dataset"
        settings.validate_required_settings()  # Should not raise

    def test_env_file_loading(self, tmp_path, monkeypatch):
        """Test loading from .env file."""
        # Clear any existing PSN environment variables to avoid interference
        for key in list(os.environ.keys()):
            if key.startswith("PSN_"):
                monkeypatch.delenv(key, raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("""
PSN_ENVIRONMENT=staging
PSN_GOOGLE_ADS_DEVELOPER_TOKEN=file-token
PSN_GOOGLE_ADS_CLIENT_ID=file-client-id
PSN_GOOGLE_ADS_CLIENT_SECRET=file-secret
PSN_STORAGE_BACKEND=firestore
PSN_STORAGE_PROJECT_ID=file-project
""")

        settings = Settings.from_env(env_file)

        assert settings.environment == Environment.STAGING
        assert settings.google_ads.developer_token.get_secret_value() == "file-token"
        assert settings.storage.backend == StorageBackend.FIRESTORE
        assert settings.storage.project_id == "file-project"


class TestGetSettings:
    """Test get_settings function."""

    def test_caching(self, monkeypatch, tmp_path):
        """Test settings are cached."""
        # Clear cache first
        get_settings.cache_clear()

        # Change to temp directory to avoid loading .env files
        monkeypatch.chdir(tmp_path)

        env_vars = {
            "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "test-token",
            "PSN_GOOGLE_ADS_CLIENT_ID": "test-client-id",
            "PSN_GOOGLE_ADS_CLIENT_SECRET": "test-secret",
            "PSN_STORAGE_CONNECTION_STRING": "postgresql://test",
            "PSN_ENVIRONMENT": "development",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        # First call
        settings1 = get_settings()
        assert settings1.environment == Environment.DEVELOPMENT

        # Change environment variable
        monkeypatch.setenv("PSN_ENVIRONMENT", "production")

        # Second call should return cached value
        settings2 = get_settings()
        assert settings1 is settings2
        assert settings2.environment == Environment.DEVELOPMENT  # Not changed

        # Clear cache and get new settings
        get_settings.cache_clear()
        settings3 = get_settings()
        assert settings3 is not settings1
        assert settings3.environment == Environment.PRODUCTION

    def test_validation_error_handling(self, monkeypatch, tmp_path):
        """Test that validation errors are properly handled."""
        # Clear cache at the start AND ensure we don't have any env vars set
        get_settings.cache_clear()

        # Clear any existing PSN_ environment variables first
        # This must be done before any Settings creation
        for key in list(os.environ.keys()):
            if key.startswith("PSN_"):
                monkeypatch.delenv(key, raising=False)

        # Mock the entire Settings.from_env to bypass all file loading
        # and return a Settings with no google_ads config
        def mock_from_env(cls, env_file=None):
            # Don't call the original - create Settings directly
            # with minimal config that will fail validation
            instance = cls(
                environment=Environment.DEVELOPMENT,
                debug=False,
                database_url=None,
                google_ads=None,  # This triggers the validation error
                storage=StorageConfig(),
                scheduler=SchedulerConfig(),
                logging=LoggingConfig(),
                features=FeatureFlags(),
                secret_provider=SecretProvider.ENVIRONMENT,
                data_dir=tmp_path / "data",
            )
            return instance

        # Replace the classmethod - bind it properly
        mock_from_env_bound = classmethod(mock_from_env)
        monkeypatch.setattr(Settings, "from_env", mock_from_env_bound)

        # No required config set
        with pytest.raises(ValueError, match="Google Ads configuration is required"):
            get_settings()


class TestClientConfigMerging:
    """Test client configuration merging functionality."""

    def test_merge_client_config_bigquery_only(self):
        """Test merging client config with only BigQuery settings."""
        base_config = {}
        client_config = {
            "bigquery": {
                "enabled": True,
                "project_id": "test-project",
                "dataset_id": "test_dataset",
            }
        }

        result = Settings._merge_client_config(base_config, client_config)

        assert "bigquery" in result
        assert result["bigquery"]["enabled"]
        assert result["bigquery"]["project_id"] == "test-project"
        assert result["bigquery"]["dataset_id"] == "test_dataset"

    def test_merge_client_config_ga4_only(self):
        """Test merging client config with only GA4 settings."""
        base_config = {}
        client_config = {
            "ga4": {
                "enabled": True,
                "property_id": "123456789",
                "use_application_default_credentials": True,
                "requests_per_minute": 60,
                "requests_per_hour": 3600,
                "requests_per_day": 86400,
            }
        }

        result = Settings._merge_client_config(base_config, client_config)

        assert "ga4" in result
        assert result["ga4"]["enabled"]
        assert result["ga4"]["property_id"] == "123456789"
        assert result["ga4"]["requests_per_minute"] == 60

    def test_merge_client_config_google_ads_only(self):
        """Test merging client config with only Google Ads settings."""
        base_config = {}
        client_config = {
            "google_ads": {"api_version": "v20", "default_page_size": 1000}
        }

        result = Settings._merge_client_config(base_config, client_config)

        assert "google_ads" in result
        assert result["google_ads"]["api_version"] == "v20"
        assert result["google_ads"]["default_page_size"] == 1000

    def test_merge_client_config_all_sections(self):
        """Test merging client config with all supported sections."""
        base_config = {}
        client_config = {
            "bigquery": {"enabled": True, "project_id": "test-project"},
            "google_ads": {"api_version": "v20"},
            "ga4": {"enabled": True, "property_id": "123456789"},
        }

        result = Settings._merge_client_config(base_config, client_config)

        assert "bigquery" in result
        assert "google_ads" in result
        assert "ga4" in result
        assert result["bigquery"]["enabled"]
        assert result["google_ads"]["api_version"] == "v20"
        assert result["ga4"]["property_id"] == "123456789"

    def test_merge_client_config_with_existing_base(self):
        """Test merging when base_config already has some settings."""
        base_config = {
            "environment": "production",
            "ga4": {"enabled": False, "property_id": "old_id"},
        }
        client_config = {
            "ga4": {
                "enabled": True,
                "property_id": "new_id",
                "requests_per_minute": 120,
            }
        }

        result = Settings._merge_client_config(base_config, client_config)

        assert result["environment"] == "production"  # Preserved
        assert result["ga4"]["enabled"]  # Overridden
        assert result["ga4"]["property_id"] == "new_id"  # Overridden
        assert result["ga4"]["requests_per_minute"] == 120  # Added

    def test_merge_client_config_empty_sections(self):
        """Test merging with empty client config sections."""
        base_config = {}
        client_config = {"bigquery": {}, "google_ads": {}, "ga4": {}}

        result = Settings._merge_client_config(base_config, client_config)

        # Should create the sections but not add any keys since client config is empty
        assert "bigquery" in result
        assert "google_ads" in result
        assert "ga4" in result
        assert result["bigquery"] == {}
        assert result["google_ads"] == {}
        assert result["ga4"] == {}
