"""Tests for SQL injection prevention in database URL construction."""

from unittest.mock import Mock

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.storage.repository import AnalysisRepository


class TestSQLInjectionPrevention:
    """Test SQL injection prevention in database URL construction."""

    def test_malicious_host_rejected(self):
        """Test that malicious host values are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "evil'; DROP DATABASE test; --",
            "STORAGE_DB_PORT": "5432",
            "STORAGE_DB_USER": "user",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(ValueError, match="Invalid database host format"):
            repository._build_postgres_url()

    def test_malicious_database_name_rejected(self):
        """Test that malicious database names are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "5432",
            "STORAGE_DB_USER": "user",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "db'; DROP TABLE users; --",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(ValueError, match="Invalid database name format"):
            repository._build_postgres_url()

    def test_malicious_username_rejected(self):
        """Test that malicious usernames are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "5432",
            "STORAGE_DB_USER": "user'; DELETE FROM users; --",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(ValueError, match="Invalid database username format"):
            repository._build_postgres_url()

    def test_invalid_port_rejected(self):
        """Test that invalid ports are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "9999999",  # Invalid port
            "STORAGE_DB_USER": "user",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(
            ValueError, match="Database port must be between 1 and 65535"
        ):
            repository._build_postgres_url()

    def test_non_numeric_port_rejected(self):
        """Test that non-numeric ports are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "not_a_number",
            "STORAGE_DB_USER": "user",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(ValueError, match="Database port must be numeric"):
            repository._build_postgres_url()

    def test_control_characters_in_password_rejected(self):
        """Test that control characters in password are rejected."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "5432",
            "STORAGE_DB_USER": "user",
            "STORAGE_DB_PASSWORD": "pass\nword",  # Contains newline
            "STORAGE_DB_NAME": "db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        with pytest.raises(
            ValueError, match="Database password contains invalid control characters"
        ):
            repository._build_postgres_url()

    def test_valid_parameters_accepted(self):
        """Test that valid parameters are properly encoded and accepted."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = (
            lambda key, default: {
                "STORAGE_DB_HOST": "localhost",
                "STORAGE_DB_PORT": "5432",
                "STORAGE_DB_USER": "test_user",
                "STORAGE_DB_PASSWORD": "test@password",  # Special chars that should be encoded
                "STORAGE_DB_NAME": "test_db",
            }.get(key, default)
        )

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        url = repository._build_postgres_url()

        # Should contain URL-encoded password
        assert "test%40password" in url  # @ should be encoded as %40
        assert "postgresql://test_user:test%40password@localhost:5432/test_db" == url

    def test_no_password_case(self):
        """Test URL construction when no password is provided."""
        settings = Mock(spec=Settings)
        settings.environment = "development"
        settings.get_env.side_effect = lambda key, default: {
            "STORAGE_DB_HOST": "localhost",
            "STORAGE_DB_PORT": "5432",
            "STORAGE_DB_USER": "test_user",
            "STORAGE_DB_PASSWORD": "",
            "STORAGE_DB_NAME": "test_db",
        }.get(key, default)

        repository = AnalysisRepository.__new__(AnalysisRepository)
        repository.settings = settings

        url = repository._build_postgres_url()

        # Should not contain password in URL
        assert url == "postgresql://test_user@localhost:5432/test_db"
        assert ":" not in url.split("@")[0].split("//")[1]  # No colon after username
