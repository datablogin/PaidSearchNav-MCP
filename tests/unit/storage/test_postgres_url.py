"""Test PostgreSQL URL building with environment variables."""

import os
from unittest.mock import patch

from paidsearchnav.core.config import Settings
from paidsearchnav.storage.repository import AnalysisRepository


class TestPostgresURLBuilding:
    """Test that PostgreSQL URL is built correctly from environment variables."""

    def test_build_postgres_url_with_password(self) -> None:
        """Test building PostgreSQL URL with all components including password."""
        settings = Settings(environment="production", data_dir="/tmp")
        repo = AnalysisRepository.__new__(AnalysisRepository)
        repo.settings = settings

        # Set up environment variables
        env_vars = {
            "PSN_STORAGE_DB_HOST": "dbserver.example.com",
            "PSN_STORAGE_DB_PORT": "5433",
            "PSN_STORAGE_DB_USER": "myuser",
            "PSN_STORAGE_DB_PASSWORD": "mypassword",
            "PSN_STORAGE_DB_NAME": "mydb",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            url = repo._build_postgres_url()

        expected_url = "postgresql://myuser:mypassword@dbserver.example.com:5433/mydb"
        assert url == expected_url

    def test_build_postgres_url_without_password(self) -> None:
        """Test building PostgreSQL URL without password."""
        settings = Settings(environment="production", data_dir="/tmp")
        repo = AnalysisRepository.__new__(AnalysisRepository)
        repo.settings = settings

        # Set up environment variables without password
        env_vars = {
            "PSN_STORAGE_DB_HOST": "localhost",
            "PSN_STORAGE_DB_PORT": "5432",
            "PSN_STORAGE_DB_USER": "postgres",
            "PSN_STORAGE_DB_PASSWORD": "",  # Empty password
            "PSN_STORAGE_DB_NAME": "testdb",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            url = repo._build_postgres_url()

        expected_url = "postgresql://postgres@localhost:5432/testdb"
        assert url == expected_url

    def test_build_postgres_url_with_defaults(self) -> None:
        """Test building PostgreSQL URL with default values."""
        settings = Settings(environment="production", data_dir="/tmp")
        repo = AnalysisRepository.__new__(AnalysisRepository)
        repo.settings = settings

        # Clear any DB environment variables to test defaults
        env_vars = {
            k: v for k, v in os.environ.items() if not k.startswith("PSN_STORAGE_DB_")
        }

        with patch.dict(os.environ, env_vars, clear=True):
            url = repo._build_postgres_url()

        expected_url = "postgresql://paidsearchnav@localhost:5432/paidsearchnav"
        assert url == expected_url

    def test_env_var_prefix_not_duplicated(self) -> None:
        """Test that PSN_ prefix is not duplicated when calling get_env."""
        settings = Settings(environment="production", data_dir="/tmp")

        # Set environment variable with PSN_ prefix
        with patch.dict(os.environ, {"PSN_DB_HOST": "testhost"}, clear=False):
            # Verify that get_env correctly retrieves the value
            # without requiring double prefix
            value = settings.get_env("DB_HOST", "default")
            assert value == "testhost"

            # Verify that calling with PSN_ prefix would look for PSN_PSN_
            # which should not exist
            value_with_prefix = settings.get_env("PSN_DB_HOST", "default")
            assert value_with_prefix == "default"
