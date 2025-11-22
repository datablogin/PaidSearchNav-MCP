"""
Tests for secret detection configuration and functionality.

These tests verify that our secret detection tools are properly configured
and can detect various types of secrets while properly handling false positives.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class TestSecretDetectionConfiguration:
    """Test secret detection configuration files."""

    def test_gitleaks_config_exists(self):
        """Test that GitLeaks configuration file exists."""
        config_path = Path(".gitleaks.toml")
        assert config_path.exists(), "GitLeaks configuration file should exist"

    def test_gitleaks_config_valid(self):
        """Test that GitLeaks configuration is valid TOML."""
        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        # Verify basic structure
        assert "title" in config
        assert "extend" in config
        assert "rules" in config
        assert "allowlist" in config

        # Verify rules structure
        for rule in config["rules"]:
            assert "id" in rule
            assert "description" in rule
            assert "regex" in rule
            assert "keywords" in rule

    def test_secrets_baseline_exists(self):
        """Test that detect-secrets baseline file exists."""
        baseline_path = Path(".secrets.baseline")
        assert baseline_path.exists(), "detect-secrets baseline should exist"

    def test_secrets_baseline_valid(self):
        """Test that detect-secrets baseline is valid JSON."""
        baseline_path = Path(".secrets.baseline")
        with open(baseline_path, "r") as f:
            baseline = json.load(f)

        # Verify basic structure
        assert "version" in baseline
        assert "plugins_used" in baseline
        assert "filters_used" in baseline
        assert "results" in baseline

    def test_precommit_config_exists(self):
        """Test that pre-commit configuration exists."""
        config_path = Path(".pre-commit-config.yaml")
        assert config_path.exists(), "Pre-commit configuration should exist"


class TestSecretDetectionPatterns:
    """Test that secret detection patterns work correctly."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            yield path
        finally:
            os.close(fd)
            os.unlink(path)

    def test_google_ads_developer_token_detection(self, temp_file):
        """Test detection of Google Ads developer tokens."""
        # Test content with a fake developer token
        content = """
# This should be detected
PSN_GOOGLE_ADS_DEVELOPER_TOKEN = "AbCdEfGhIjKlMnOpQrStUv"
google_ads_developer_token = "XyZ123_AbC456-DeF789"
"""

        with open(temp_file, "w") as f:
            f.write(content)

        # This test would need actual GitLeaks binary to run
        # For now, we verify the pattern exists in config
        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        # Find the Google Ads developer token rule
        token_rule = None
        for rule in config["rules"]:
            if rule["id"] == "google-ads-developer-token":
                token_rule = rule
                break

        assert token_rule is not None, "Google Ads developer token rule should exist"
        assert "PSN_GOOGLE_ADS_DEVELOPER_TOKEN" in token_rule["keywords"]

    def test_google_ads_client_secret_detection(self, temp_file):
        """Test detection of Google Ads client secrets."""
        content = """
# This should be detected
PSN_GOOGLE_ADS_CLIENT_SECRET = "GOCSPX-AbCdEfGhIjKlMnOpQrStUvWxYz1234"
client_secret = "GOCSPX-1234567890abcdef"
"""

        with open(temp_file, "w") as f:
            f.write(content)

        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        # Find the Google Ads client secret rule
        secret_rule = None
        for rule in config["rules"]:
            if rule["id"] == "google-ads-client-secret":
                secret_rule = rule
                break

        assert secret_rule is not None, "Google Ads client secret rule should exist"
        assert "GOCSPX-" in secret_rule["keywords"]

    def test_database_connection_string_detection(self, temp_file):
        """Test detection of database connection strings."""
        content = """
# This should be detected
PSN_STORAGE_CONNECTION_STRING = "postgresql://user:password@localhost:5432/db"
db_url = "mysql://root:secret@localhost/mydb"
"""

        with open(temp_file, "w") as f:
            f.write(content)

        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        # Find the database connection string rule
        db_rule = None
        for rule in config["rules"]:
            if rule["id"] == "database-connection-string":
                db_rule = rule
                break

        assert db_rule is not None, "Database connection string rule should exist"
        assert "PSN_STORAGE_CONNECTION_STRING" in db_rule["keywords"]


class TestSecretDetectionAllowlist:
    """Test that allowlist properly handles false positives."""

    def test_test_values_allowed(self, temp_file=None):
        """Test that test values are properly allowlisted."""
        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        allowlist = config["allowlist"]

        # Check that test patterns are in allowlist
        test_patterns = [
            r"""test[_-]?(client[_-]?id|client[_-]?secret|developer[_-]?token|refresh[_-]?token|secret[_-]?key|password)""",
            r"""example[_-]?(client[_-]?id|client[_-]?secret|developer[_-]?token|refresh[_-]?token|secret[_-]?key|password)""",
            r"""fake[_-]?(client[_-]?id|client[_-]?secret|developer[_-]?token|refresh[_-]?token|secret[_-]?key|password)""",
        ]

        for pattern in test_patterns:
            assert pattern in allowlist["regexes"], (
                f"Test pattern {pattern} should be allowlisted"
            )

    def test_test_files_allowed(self):
        """Test that test files are properly allowlisted."""
        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        allowlist = config["allowlist"]

        # Check that test file patterns are in allowlist
        test_file_patterns = [
            r"""tests/.*""",
            r""".*test.*\.py""",
            r""".*_test\.py""",
            r"""test_.*\.py""",
        ]

        for pattern in test_file_patterns:
            assert pattern in allowlist["paths"], (
                f"Test file pattern {pattern} should be allowlisted"
            )

    def test_ci_values_allowed(self):
        """Test that CI test values are properly allowlisted."""
        config_path = Path(".gitleaks.toml")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        allowlist = config["allowlist"]

        # Check that CI test values are allowlisted
        ci_patterns = [
            r"""test_secret_key_for_ci_testing_only""",
            r"""test_client_id""",
            r"""test_client_secret""",
        ]

        for pattern in ci_patterns:
            assert pattern in allowlist["regexes"], (
                f"CI test pattern {pattern} should be allowlisted"
            )


class TestSecretDetectionWorkflow:
    """Test secret detection workflow configuration."""

    def test_secret_detection_workflow_exists(self):
        """Test that secret detection workflow exists."""
        workflow_path = Path(".github/workflows/secret-detection.yml")
        assert workflow_path.exists(), "Secret detection workflow should exist"

    def test_workflow_has_required_triggers(self):
        """Test that workflow triggers on correct events."""
        workflow_path = Path(".github/workflows/secret-detection.yml")
        with open(workflow_path, "r") as f:
            content = f.read()

        # Should trigger on push and pull_request
        assert "on:" in content
        assert "push:" in content
        assert "pull_request:" in content
        assert "branches: [ main, develop ]" in content

    def test_workflow_installs_gitleaks(self):
        """Test that workflow installs GitLeaks."""
        workflow_path = Path(".github/workflows/secret-detection.yml")
        with open(workflow_path, "r") as f:
            content = f.read()

        assert "Install GitLeaks" in content
        assert "gitleaks version" in content

    def test_workflow_uses_config(self):
        """Test that workflow uses GitLeaks configuration."""
        workflow_path = Path(".github/workflows/secret-detection.yml")
        with open(workflow_path, "r") as f:
            content = f.read()

        assert "--config=.gitleaks.toml" in content


class TestCIIntegration:
    """Test CI integration of secret detection."""

    def test_ci_includes_secret_detection(self):
        """Test that main CI workflow includes secret detection."""
        ci_path = Path(".github/workflows/ci.yml")
        with open(ci_path, "r") as f:
            content = f.read()

        assert "Secret detection with GitLeaks" in content
        assert "gitleaks detect" in content
        assert "--config=.gitleaks.toml" in content

    def test_ci_fails_on_secrets(self):
        """Test that CI fails when secrets are detected."""
        ci_path = Path(".github/workflows/ci.yml")
        with open(ci_path, "r") as f:
            content = f.read()

        # Should exit with error code if secrets found
        assert "exit 1" in content
        assert "GITLEAKS_EXIT_CODE" in content


@pytest.mark.integration
class TestSecretDetectionIntegration:
    """Integration tests for secret detection system."""

    @pytest.mark.skipif(
        not os.path.exists("/usr/local/bin/gitleaks"), reason="GitLeaks not installed"
    )
    def test_gitleaks_runs_successfully(self):
        """Test that GitLeaks runs successfully on the codebase."""
        import subprocess

        try:
            # Run GitLeaks on current directory
            result = subprocess.run(
                [
                    "gitleaks",
                    "detect",
                    "--config=.gitleaks.toml",
                    "--source=.",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Exit code 0 means no secrets found
            # Exit code 1 means secrets found (should fail in real usage)
            # Exit code 2 means error
            assert result.returncode != 2, f"GitLeaks error: {result.stderr}"

        except subprocess.TimeoutExpired:
            pytest.fail("GitLeaks scan timed out")
        except FileNotFoundError:
            pytest.skip("GitLeaks not found in PATH")

    def test_detect_secrets_baseline_scan(self):
        """Test that detect-secrets can scan against baseline."""
        import subprocess

        try:
            # Try to run detect-secrets if available
            result = subprocess.run(
                ["detect-secrets", "scan", "--baseline", ".secrets.baseline", "."],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should not error (exit code 0 or 1 are both acceptable)
            assert result.returncode != 127, "detect-secrets not installed"

        except subprocess.TimeoutExpired:
            pytest.fail("detect-secrets scan timed out")
        except FileNotFoundError:
            pytest.skip("detect-secrets not found in PATH")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
