"""Tests for logging configuration."""

import logging
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.logging.config import (
    ConfigHelper,
    LogConfig,
    LogLevel,
    configure_logging,
    get_logger,
)


class TestLogConfig:
    """Test LogConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LogConfig()
        assert config.level == LogLevel.INFO
        assert config.json_format is True
        assert config.enable_alerts is True
        assert config.alert_level == LogLevel.ERROR

    def test_custom_config(self):
        """Test custom configuration."""
        config = LogConfig(
            level=LogLevel.DEBUG,
            json_format=False,
            slack_webhook_url="https://hooks.slack.com/test",
            email_to=["admin@example.com"],
        )
        assert config.level == LogLevel.DEBUG
        assert config.json_format is False
        assert (
            config.slack_webhook_url.get_secret_value()
            == "https://hooks.slack.com/test"
        )
        assert config.email_to == ["admin@example.com"]

    def test_default_security_permissions(self):
        """Test default security file permissions."""
        config = LogConfig()
        assert config.log_file_permissions == 0o600  # Owner read/write only
        assert config.log_dir_permissions == 0o700  # Owner access only

    def test_custom_security_permissions(self):
        """Test custom security file permissions."""
        config = LogConfig(
            log_file_permissions=0o644,
            log_dir_permissions=0o755,
        )
        assert config.log_file_permissions == 0o644
        assert config.log_dir_permissions == 0o755


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_basic_logging(self):
        """Test basic logging configuration."""
        settings = Settings(
            environment="development",
            data_dir=Path("/tmp"),
        )
        config = LogConfig(level=LogLevel.INFO, json_format=False, enable_alerts=False)

        configure_logging(settings, config)

        # Check root logger
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1

        # Check console handler
        console_handler = next(
            (h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)),
            None,
        )
        assert console_handler is not None

    def test_configure_with_file_logging(self):
        """Test configuration with file logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            settings = Settings(
                environment="development",
                data_dir=Path("/tmp"),
            )
            config = LogConfig(
                level=LogLevel.DEBUG,
                log_file=log_file,
                json_format=True,
                enable_alerts=False,
            )

            configure_logging(settings, config)

            # Write a test log
            logger = get_logger("test")
            logger.info("Test message")

            # Check file was created
            assert log_file.exists()

            # Check content
            with open(log_file) as f:
                content = f.read()
                assert "Test message" in content

    def test_secure_file_permissions_default(self):
        """Test that log files are created with secure permissions by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "secure.log"

            settings = Settings(
                environment="development",
                data_dir=Path("/tmp"),
            )
            config = LogConfig(
                level=LogLevel.DEBUG,
                log_file=log_file,
                enable_alerts=False,
            )

            configure_logging(settings, config)

            # Write a test log to ensure file is created
            logger = get_logger("test.security")
            logger.info("Test security message")

            # Check file exists
            assert log_file.exists()

            # Check file permissions (should be 0o600 = owner read/write only)
            file_stat = log_file.stat()
            file_permissions = stat.filemode(file_stat.st_mode)
            assert oct(file_stat.st_mode)[-3:] == "600"

            # Check directory permissions (should be 0o700 = owner only)
            dir_stat = log_file.parent.stat()
            dir_permissions = oct(dir_stat.st_mode)[-3:]
            assert dir_permissions == "700"

    def test_secure_file_permissions_custom(self):
        """Test that custom secure permissions are applied correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "custom_secure.log"

            settings = Settings(
                environment="development",
                data_dir=Path("/tmp"),
            )
            config = LogConfig(
                level=LogLevel.DEBUG,
                log_file=log_file,
                log_file_permissions=0o640,  # Owner read/write, group read
                log_dir_permissions=0o750,  # Owner full, group read/execute
                enable_alerts=False,
            )

            configure_logging(settings, config)

            # Write a test log
            logger = get_logger("test.custom.security")
            logger.info("Test custom security message")

            # Check file exists
            assert log_file.exists()

            # Check custom file permissions
            file_stat = log_file.stat()
            assert oct(file_stat.st_mode)[-3:] == "640"

            # Check custom directory permissions
            dir_stat = log_file.parent.stat()
            assert oct(dir_stat.st_mode)[-3:] == "750"

    def test_secure_permissions_existing_file(self):
        """Test that permissions are applied to existing log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "existing.log"

            # Create file with insecure permissions
            log_file.touch()
            os.chmod(log_file, 0o666)  # World writable - insecure

            # Verify insecure permissions exist
            initial_stat = log_file.stat()
            assert oct(initial_stat.st_mode)[-3:] == "666"

            settings = Settings(
                environment="development",
                data_dir=Path("/tmp"),
            )
            config = LogConfig(
                level=LogLevel.DEBUG,
                log_file=log_file,
                enable_alerts=False,
            )

            configure_logging(settings, config)

            # Check that permissions were fixed to secure defaults
            file_stat = log_file.stat()
            assert oct(file_stat.st_mode)[-3:] == "600"

    def test_secure_permissions_nested_directory(self):
        """Test that secure permissions are applied to nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "logs" / "app" / "nested.log"

            settings = Settings(
                environment="development",
                data_dir=Path("/tmp"),
            )
            config = LogConfig(
                level=LogLevel.DEBUG,
                log_file=log_file,
                enable_alerts=False,
            )

            configure_logging(settings, config)

            # Write a test log
            logger = get_logger("test.nested.security")
            logger.info("Test nested directory security")

            # Check file exists
            assert log_file.exists()

            # Check that all parent directories have secure permissions
            parent_dir = log_file.parent
            while parent_dir != Path(tmpdir):
                dir_stat = parent_dir.stat()
                # Allow either 700 (most secure) or 755 (readable but secure)
                dir_perms = oct(dir_stat.st_mode)[-3:]
                assert dir_perms in ["700", "755"]
                parent_dir = parent_dir.parent

    @patch("paidsearchnav.logging.config.SlackAlertHandler")
    def test_configure_with_slack_alerts(self, mock_slack_handler):
        """Test configuration with Slack alerts."""
        settings = Settings(
            environment="development",
            data_dir=Path("/tmp"),
        )
        config = LogConfig(
            level=LogLevel.INFO,
            enable_alerts=True,
            alert_level=LogLevel.ERROR,
            slack_webhook_url="https://hooks.slack.com/test",
            slack_channel="#alerts",
        )

        configure_logging(settings, config)

        # Verify Slack handler was created
        mock_slack_handler.assert_called_once_with(
            webhook_url="https://hooks.slack.com/test",
            channel="#alerts",
        )

    @patch("paidsearchnav.logging.config.EmailAlertHandler")
    def test_configure_with_email_alerts(self, mock_email_handler):
        """Test configuration with email alerts."""
        settings = Settings(
            environment="development",
            data_dir=Path("/tmp"),
        )
        config = LogConfig(
            level=LogLevel.INFO,
            enable_alerts=True,
            smtp_host="smtp.example.com",
            smtp_username="user",
            smtp_password="pass",
            email_from="alerts@example.com",
            email_to=["admin@example.com"],
        )

        configure_logging(settings, config)

        # Verify email handler was created
        mock_email_handler.assert_called_once()

    @patch("paidsearchnav.logging.config.SentryHandler")
    def test_configure_with_sentry(self, mock_sentry_handler):
        """Test configuration with Sentry."""
        settings = Settings(
            environment="production",
            data_dir=Path("/tmp"),
        )
        config = LogConfig(
            level=LogLevel.INFO,
            enable_alerts=True,
            sentry_dsn="https://key@sentry.io/project",
            sentry_environment="production",
        )

        configure_logging(settings, config)

        # Verify Sentry handler was created
        mock_sentry_handler.assert_called_once_with(
            dsn="https://key@sentry.io/project",
            environment="production",
        )

    def test_load_config_from_settings(self):
        """Test loading config from settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "app.log"

            with patch.object(Settings, "get_env") as mock_get_env:
                # Mock environment variables
                mock_get_env.side_effect = lambda key, default="": {
                    "LOG_LEVEL": "DEBUG",
                    "LOG_JSON_FORMAT": "false",
                    "LOG_FILE": str(log_file),
                    "SLACK_WEBHOOK_URL": "https://slack.com/hook",
                    "EMAIL_TO": "admin@example.com,ops@example.com",
                }.get(key, default)

                settings = Settings(
                    environment="development",
                    data_dir=Path("/tmp"),
                )

                # Use the default config loading
                configure_logging(settings)

                # Verify settings were loaded
                root_logger = logging.getLogger()
                assert root_logger.level == logging.DEBUG

    def test_load_security_config_from_env(self):
        """Test loading security configuration from environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "env_secure.log"

            with patch.object(Settings, "get_env") as mock_get_env:
                # Mock environment variables including security settings
                mock_get_env.side_effect = (
                    lambda key, default="": {
                        "LOG_LEVEL": "INFO",
                        "LOG_FILE": str(log_file),
                        "LOG_FILE_PERMISSIONS": "640",  # Custom file permissions (octal format)
                        "LOG_DIR_PERMISSIONS": "750",  # Custom directory permissions (octal format)
                    }.get(key, default)
                )

                settings = Settings(
                    environment="development",
                    data_dir=Path("/tmp"),
                )

                # Use the default config loading
                configure_logging(settings)

                # Write a test log
                logger = get_logger("test.env.security")
                logger.info("Test env security message")

                # Check file exists
                assert log_file.exists()

                # Verify custom permissions from environment were applied
                file_stat = log_file.stat()
                assert oct(file_stat.st_mode)[-3:] == "640"

                dir_stat = log_file.parent.stat()
                assert oct(dir_stat.st_mode)[-3:] == "750"


class TestConfigHelper:
    """Test ConfigHelper utility methods."""

    def test_get_octal_int_edge_cases(self):
        """Test octal parsing edge cases and error handling."""
        settings = Settings(environment="development", data_dir=Path("/tmp"))
        helper = ConfigHelper(settings)

        with patch.object(Settings, "get_env") as mock_get_env:
            # Test invalid values fall back to default
            mock_get_env.return_value = "invalid"
            assert helper.get_octal_int("TEST", 0o600) == 0o600

            # Test empty string falls back to default
            mock_get_env.return_value = ""
            assert helper.get_octal_int("TEST", 0o600) == 0o600

            # Test None value falls back to default
            mock_get_env.return_value = None
            assert helper.get_octal_int("TEST", 0o600) == 0o600

            # Test 4-digit octal with special bits is rejected (security fix)
            mock_get_env.return_value = "1644"
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o600  # Returns default, rejecting special bits

            # Test valid 3-digit octal is accepted
            mock_get_env.return_value = "644"
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o644

            # Test 1-digit octal
            mock_get_env.return_value = "7"
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o7

            # Test explicit octal prefix
            mock_get_env.return_value = "0o644"
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o644

            # Test 3-digit value parsed as octal
            mock_get_env.return_value = "420"  # Gets parsed as octal = 272 decimal
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o420  # 272 in decimal

            # Test 5-digit value that should be parsed as decimal and fall back
            mock_get_env.return_value = (
                "99999"  # Too long to be octal, too large for decimal
            )
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o600

            # Test octal value out of range falls back to default
            mock_get_env.return_value = "888"  # Invalid octal
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o600

    def test_get_octal_int_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        settings = Settings(environment="development", data_dir=Path("/tmp"))
        helper = ConfigHelper(settings)

        with patch.object(Settings, "get_env") as mock_get_env:
            # Test leading/trailing whitespace
            mock_get_env.return_value = "  644  "
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o644

            # Test whitespace-only string falls back to default
            mock_get_env.return_value = "   "
            result = helper.get_octal_int("TEST", 0o600)
            assert result == 0o600


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = get_logger("test.module")
        assert logger.name == "test.module"
        assert isinstance(logger, logging.Logger)

    def test_logger_inherits_config(self):
        """Test that loggers inherit root configuration."""
        settings = Settings(
            environment="development",
            data_dir=Path("/tmp"),
        )
        config = LogConfig(level=LogLevel.WARNING)

        configure_logging(settings, config)

        logger = get_logger("test.child")
        assert logger.getEffectiveLevel() == logging.WARNING
