"""Tests for secure file permissions in logging."""

import os
import platform
from unittest.mock import Mock, patch

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.logging.audit import AuditLogger, get_audit_logger
from paidsearchnav.logging.config import (
    LogConfig,
    SecureRotatingFileHandler,
    check_log_permissions,
    configure_logging,
)


class TestSecureRotatingFileHandler:
    """Test secure rotating file handler."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_creates_file_with_secure_permissions(self, tmp_path):
        """Test that files are created with secure permissions."""
        log_file = tmp_path / "test.log"
        handler = SecureRotatingFileHandler(
            str(log_file),
            maxBytes=1024,
            backupCount=3,
            permissions=0o600,
        )

        # Write to trigger file creation
        handler.emit(Mock(getMessage=lambda: "test message"))
        handler.close()

        # Check permissions
        assert log_file.exists()
        permissions = log_file.stat().st_mode & 0o777
        assert permissions == 0o600

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_rotated_files_have_secure_permissions(self, tmp_path):
        """Test that rotated backup files have secure permissions."""
        log_file = tmp_path / "test.log"
        handler = SecureRotatingFileHandler(
            str(log_file),
            maxBytes=50,  # Small size to force rotation
            backupCount=3,
            permissions=0o600,
        )

        # Write enough to trigger rotation
        for i in range(10):
            record = Mock(getMessage=lambda: f"test message {i}" * 10)
            handler.emit(record)

        handler.close()

        # Check all files have correct permissions
        for file in tmp_path.glob("test.log*"):
            permissions = file.stat().st_mode & 0o777
            assert permissions == 0o600, f"{file} has permissions {oct(permissions)}"

    def test_windows_compatibility(self, tmp_path):
        """Test that handler works on Windows without errors."""
        with patch("platform.system", return_value="Windows"):
            log_file = tmp_path / "test.log"
            handler = SecureRotatingFileHandler(
                str(log_file),
                maxBytes=1024,
                backupCount=3,
                permissions=0o600,
            )

            # Should not raise any errors
            handler.emit(Mock(getMessage=lambda: "test message"))
            handler.close()

            assert log_file.exists()


class TestAuditLogger:
    """Test audit logger secure file handling."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_creates_directories_with_secure_permissions(self, tmp_path):
        """Test that audit directories are created with secure permissions."""
        audit_dir = tmp_path / "audits"
        logger = AuditLogger(
            audit_dir=audit_dir,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Check main directory
        assert audit_dir.exists()
        permissions = audit_dir.stat().st_mode & 0o777
        assert permissions == 0o700

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_creates_log_files_with_secure_permissions(self, tmp_path):
        """Test that audit log files are created with secure permissions."""
        audit_dir = tmp_path / "audits"
        logger = AuditLogger(
            audit_dir=audit_dir,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Log an event
        logger._write_audit_log("customer123", "job456", {"test": "data"})

        # Check file permissions
        log_file = audit_dir / "customer123" / "job456.jsonl"
        assert log_file.exists()
        permissions = log_file.stat().st_mode & 0o777
        assert permissions == 0o600

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_api_call_logs_have_secure_permissions(self, tmp_path):
        """Test that API call logs have secure permissions."""
        audit_dir = tmp_path / "audits"
        logger = AuditLogger(
            audit_dir=audit_dir,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Log an API call
        logger.log_api_call(
            customer_id="customer123",
            service="google_ads",
            method="GET",
            endpoint="/customers/123",
            status_code=200,
            duration_ms=150.5,
        )

        # Check file and directory permissions
        api_dir = audit_dir / "api_calls"
        assert api_dir.exists()
        dir_perms = api_dir.stat().st_mode & 0o777
        assert dir_perms == 0o700

        # Check log file
        log_files = list(api_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        file_perms = log_files[0].stat().st_mode & 0o777
        assert file_perms == 0o600

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_analysis_result_files_have_secure_permissions(self, tmp_path):
        """Test that analysis result files have secure permissions."""
        from datetime import datetime

        from paidsearchnav.core.models.analysis import AnalysisResult

        audit_dir = tmp_path / "audits"
        logger = AuditLogger(
            audit_dir=audit_dir,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Save an analysis result
        result = AnalysisResult(
            analysis_id="test123",
            analysis_type="test",
            analyzer_name="test_analyzer",
            customer_id="customer123",
            start_date=datetime.now(),
            end_date=datetime.now(),
            recommendations=[],
            summary="Test summary",
        )
        logger._save_analysis_result("customer123", "job456", result)

        # Check permissions
        result_file = audit_dir / "customer123" / "results" / "job456_result.json"
        assert result_file.exists()
        permissions = result_file.stat().st_mode & 0o777
        assert permissions == 0o600

    def test_get_audit_logger_singleton(self, tmp_path, monkeypatch):
        """Test that get_audit_logger returns singleton instance."""
        # Reset singleton and override default path
        import paidsearchnav.logging.audit

        monkeypatch.setattr(paidsearchnav.logging.audit, "_audit_logger", None)

        # Create audit loggers with temporary directory
        original_init = AuditLogger.__init__

        def mock_init(self, audit_dir=None, **kwargs):
            # Always use tmp_path instead of default
            original_init(self, audit_dir=tmp_path / "audits", **kwargs)

        with patch.object(AuditLogger, "__init__", mock_init):
            logger1 = get_audit_logger()
            logger2 = get_audit_logger()
            assert logger1 is logger2

    def test_custom_permissions_passed_through(self, tmp_path):
        """Test that custom permissions are respected."""
        with patch("paidsearchnav.logging.audit._audit_logger", None):
            # Create a temporary audit logger with custom permissions
            logger = AuditLogger(
                audit_dir=tmp_path / "audits",
                log_file_permissions=0o640,
                log_dir_permissions=0o750,
            )
            assert logger.log_file_permissions == 0o640
            assert logger.log_dir_permissions == 0o750


class TestLogPermissionChecker:
    """Test log permission checking functionality."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_check_log_permissions_detects_issues(self, tmp_path):
        """Test that permission checker detects overly permissive files."""
        # Create test files with different permissions
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        os.chmod(log_dir, 0o755)  # Too permissive

        log_file = log_dir / "app.log"
        log_file.write_text("test")
        os.chmod(log_file, 0o644)  # Too permissive

        # Create config
        config = LogConfig(
            log_file=log_file,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Check permissions
        settings = Mock(spec=Settings)
        results = check_log_permissions(settings, config)

        assert not results["secure"]
        assert results["total_issues"] == 2
        assert len(results["issues"]) == 2

        # Check specific issues reported
        issue_texts = " ".join(results["issues"])
        assert "overly permissive permissions" in issue_texts
        assert str(log_dir) in issue_texts
        assert str(log_file) in issue_texts

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_check_log_permissions_passes_secure_files(self, tmp_path):
        """Test that permission checker passes for secure files."""
        # Create test files with secure permissions
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        os.chmod(log_dir, 0o700)

        log_file = log_dir / "app.log"
        log_file.write_text("test")
        os.chmod(log_file, 0o600)

        # Create config
        config = LogConfig(
            log_file=log_file,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Check permissions
        settings = Mock(spec=Settings)
        results = check_log_permissions(settings, config)

        assert results["secure"]
        assert results["total_issues"] == 0
        assert len(results["issues"]) == 0

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_check_rotated_log_files(self, tmp_path):
        """Test that permission checker includes rotated log files."""
        # Create test files
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        os.chmod(log_dir, 0o700)

        log_file = log_dir / "app.log"
        log_file.write_text("test")
        os.chmod(log_file, 0o600)

        # Create backup files with mixed permissions
        backup1 = log_dir / "app.log.1"
        backup1.write_text("backup1")
        os.chmod(backup1, 0o600)  # Good

        backup2 = log_dir / "app.log.2"
        backup2.write_text("backup2")
        os.chmod(backup2, 0o644)  # Too permissive

        # Create config
        config = LogConfig(
            log_file=log_file,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
        )

        # Check permissions
        settings = Mock(spec=Settings)
        results = check_log_permissions(settings, config)

        assert not results["secure"]
        assert results["total_issues"] == 1
        assert str(backup2) in results["issues"][0]

    def test_windows_platform_handling(self, tmp_path):
        """Test that permission checker handles Windows gracefully."""
        with patch("platform.system", return_value="Windows"):
            config = LogConfig(log_file=tmp_path / "test.log")
            settings = Mock(spec=Settings)
            settings.get_env = Mock(return_value=None)  # Mock get_env method
            results = check_log_permissions(settings, config)

            assert results["platform"] == "Windows"
            # Windows should have at least one warning about limited checks
            assert len(results.get("warnings", [])) >= 1
            assert any("limited on Windows" in w for w in results.get("warnings", []))

    def test_permission_check_error_handling(self, tmp_path):
        """Test that permission checker handles errors gracefully."""
        # Create a file that we'll make inaccessible
        log_file = tmp_path / "test.log"
        log_file.write_text("test")

        # Create a log directory
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file2 = log_dir / "app.log"
        log_file2.write_text("test")

        config = LogConfig(log_file=log_file2)
        settings = Mock(spec=Settings)
        settings.get_env = Mock(return_value=None)

        # Make the directory unreadable (will cause permission error on stat)
        if platform.system() != "Windows":
            import os

            os.chmod(log_dir, 0o000)

            try:
                results = check_log_permissions(settings, config)

                # Should have warnings but not crash
                assert results["checked"]
                # We expect warnings since we can't check the directory
                assert (
                    len(results.get("warnings", [])) > 0
                    or len(results.get("issues", [])) == 0
                )
            finally:
                # Restore permissions for cleanup
                os.chmod(log_dir, 0o755)
        else:
            # On Windows, just verify it doesn't crash
            results = check_log_permissions(settings, config)
            assert results["checked"]


class TestPermissionValidation:
    """Test permission validation logic."""

    def test_get_octal_int_rejects_setuid_setgid_bits(self):
        """Test that permission validation rejects setuid/setgid bits."""
        from paidsearchnav.logging.config import ConfigHelper

        settings = Mock(spec=Settings)
        helper = ConfigHelper(settings)

        # Test that values with setuid/setgid bits are rejected
        settings.get_env = Mock(return_value="4755")  # setuid bit
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o600  # Returns default

        settings.get_env = Mock(return_value="2755")  # setgid bit
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o600  # Returns default

        settings.get_env = Mock(return_value="6755")  # both bits
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o600  # Returns default

        # Test that normal permissions are accepted
        settings.get_env = Mock(return_value="755")
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o755

        settings.get_env = Mock(return_value="600")
        assert helper.get_octal_int("TEST_PERM", 0o755) == 0o600

        # Test that octal strings are interpreted as octal
        settings.get_env = Mock(return_value="777")
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o777

        # Test explicit octal prefix
        settings.get_env = Mock(return_value="0o755")
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o755

        # Test that 4-digit octal beyond 0o777 is rejected
        settings.get_env = Mock(return_value="1000")  # 0o1000 = sticky bit
        assert helper.get_octal_int("TEST_PERM", 0o600) == 0o600  # Returns default


class TestLogConfigIntegration:
    """Test integration with main logging configuration."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix permissions test")
    def test_configure_logging_creates_secure_files(self, tmp_path):
        """Test that configure_logging creates files with secure permissions."""
        log_file = tmp_path / "logs" / "app.log"

        settings = Mock(spec=Settings)
        settings.environment = "test"
        settings.get_env = Mock(return_value=None)  # Mock get_env method

        config = LogConfig(
            log_file=log_file,
            log_file_permissions=0o600,
            log_dir_permissions=0o700,
            json_format=False,  # Simpler for testing
            level="INFO",  # Use string instead of enum
        )

        # Configure logging
        configure_logging(settings, config)

        # Trigger log file creation
        import logging

        logger = logging.getLogger("test")
        logger.info("Test message")

        # Check permissions
        assert log_file.parent.exists()
        dir_perms = log_file.parent.stat().st_mode & 0o777
        assert dir_perms == 0o700

        assert log_file.exists()
        file_perms = log_file.stat().st_mode & 0o777
        assert file_perms == 0o600
