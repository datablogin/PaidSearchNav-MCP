"""Tests for export configuration management."""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from paidsearchnav.exports.base import ExportConfig, ExportFormat
from paidsearchnav.exports.config import ExportConfigManager


class TestExportConfigManager:
    """Test ExportConfigManager class."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "exports": {
                    "enabled": True,
                    "destinations": [
                        {
                            "customer_id": "customer123",
                            "type": "bigquery",
                            "project_id": "test-project",
                            "dataset": "test_dataset",
                            "credentials": {"key": "value"},
                            "schedule": "0 */6 * * *",
                            "enabled": True,
                        },
                        {
                            "customer_id": "customer123",
                            "type": "snowflake",
                            "account": "test.us-east-1",
                            "warehouse": "COMPUTE_WH",
                            "database": "ANALYTICS",
                            "schema": "PUBLIC",
                            "credentials": {"user": "test"},
                            "enabled": False,
                        },
                        {
                            "customer_id": "default",
                            "type": "parquet",
                            "output_path": "/tmp/exports",
                            "compression": "snappy",
                            "credentials": {},
                            "enabled": True,
                        },
                    ],
                }
            }
            yaml.dump(config, f)
            temp_file = f.name

        yield temp_file

        # Cleanup
        os.unlink(temp_file)

    @pytest.fixture
    def config_manager(self, temp_config_file):
        """Create config manager with temp file."""
        return ExportConfigManager(config_file=temp_config_file)

    def test_load_from_file(self, config_manager):
        """Test loading configurations from file."""
        configs = config_manager.load_from_file()

        assert "customer123" in configs
        assert "default" in configs

        # Check customer123 configs
        customer_configs = configs["customer123"]
        assert len(customer_configs) == 2

        # Check BigQuery config
        bq_config = next(
            c for c in customer_configs if c.destination_type == ExportFormat.BIGQUERY
        )
        assert bq_config.project_id == "test-project"
        assert bq_config.dataset == "test_dataset"
        assert bq_config.schedule == "0 */6 * * *"
        assert bq_config.enabled is True

        # Check Snowflake config
        sf_config = next(
            c for c in customer_configs if c.destination_type == ExportFormat.SNOWFLAKE
        )
        assert sf_config.account == "test.us-east-1"
        assert sf_config.warehouse == "COMPUTE_WH"
        assert sf_config.enabled is False

        # Check default config
        default_configs = configs["default"]
        assert len(default_configs) == 1
        assert default_configs[0].destination_type == ExportFormat.PARQUET
        assert default_configs[0].output_path == "/tmp/exports"

    def test_load_from_empty_file(self):
        """Test loading from empty config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
            f.write("")
            f.flush()

            manager = ExportConfigManager(config_file=f.name)
            configs = manager.load_from_file()

            assert configs == {}

    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file."""
        manager = ExportConfigManager(config_file="/does/not/exist.yaml")
        configs = manager.load_from_file()

        assert configs == {}

    def test_load_disabled_exports(self):
        """Test loading when exports are disabled globally."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
            config = {
                "exports": {
                    "enabled": False,
                    "destinations": [
                        {"type": "bigquery", "project_id": "test-project"}
                    ],
                }
            }
            yaml.dump(config, f)
            f.flush()

            manager = ExportConfigManager(config_file=f.name)
            configs = manager.load_from_file()

            assert configs == {}

    @patch.dict(
        os.environ,
        {
            "BIGQUERY_EXPORT_ENABLED": "true",
            "BIGQUERY_CUSTOMER_ID": "env-customer",
            "BIGQUERY_PROJECT_ID": "env-project",
            "BIGQUERY_DATASET": "env_dataset",
            "BIGQUERY_SERVICE_ACCOUNT_JSON": '{"test": "creds"}',
            "BIGQUERY_EXPORT_SCHEDULE": "0 2 * * *",
        },
    )
    def test_load_from_env(self):
        """Test loading configurations from environment variables."""
        manager = ExportConfigManager()
        configs = manager.load_from_env()

        assert "env-customer" in configs

        bq_config = configs["env-customer"][0]
        assert bq_config.destination_type == ExportFormat.BIGQUERY
        assert bq_config.project_id == "env-project"
        assert bq_config.dataset == "env_dataset"
        assert bq_config.schedule == "0 2 * * *"
        assert bq_config.credentials["service_account_json"] == '{"test": "creds"}'

    @patch.dict(os.environ, {"BIGQUERY_EXPORT_ENABLED": "false"})
    def test_load_from_env_disabled(self):
        """Test loading from env when disabled."""
        manager = ExportConfigManager()
        configs = manager.load_from_env()

        assert configs == {}

    def test_get_configs_for_customer(self, config_manager):
        """Test getting configs for specific customer."""
        configs = config_manager.get_configs_for_customer("customer123")

        assert len(configs) == 2
        types = [c.destination_type for c in configs]
        assert ExportFormat.BIGQUERY in types
        assert ExportFormat.SNOWFLAKE in types

    def test_get_configs_for_unknown_customer(self, config_manager):
        """Test getting configs for unknown customer falls back to default."""
        # Load configs first
        config_manager.load_from_file()

        configs = config_manager.get_configs_for_customer("unknown-customer")

        # Should get default configs
        assert len(configs) == 1
        assert configs[0].destination_type == ExportFormat.PARQUET

    def test_get_enabled_configs(self, config_manager):
        """Test getting only enabled configs."""
        enabled_configs = config_manager.get_enabled_configs("customer123")

        # Only BigQuery is enabled for customer123
        assert len(enabled_configs) == 1
        assert enabled_configs[0].destination_type == ExportFormat.BIGQUERY

    def test_add_config(self, config_manager):
        """Test adding new configuration."""
        new_config = ExportConfig(
            destination_type=ExportFormat.CSV, credentials={}, output_path="/tmp/csv"
        )

        config_manager.add_config("new-customer", new_config)

        configs = config_manager.get_configs_for_customer("new-customer")
        assert len(configs) == 1
        assert configs[0].destination_type == ExportFormat.CSV

    def test_remove_config(self, config_manager):
        """Test removing configuration."""
        # Load configs first
        config_manager.load_from_file()

        # Remove BigQuery config from customer123
        result = config_manager.remove_config("customer123", ExportFormat.BIGQUERY)

        assert result is True

        # Verify it's removed
        configs = config_manager.get_configs_for_customer("customer123")
        types = [c.destination_type for c in configs]
        assert ExportFormat.BIGQUERY not in types
        assert ExportFormat.SNOWFLAKE in types

    def test_remove_nonexistent_config(self, config_manager):
        """Test removing non-existent configuration."""
        result = config_manager.remove_config("no-such-customer", ExportFormat.BIGQUERY)
        assert result is False

    def test_invalid_destination_type(self):
        """Test handling invalid destination type in config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
            config = {
                "exports": {
                    "enabled": True,
                    "destinations": [{"type": "invalid-type", "project_id": "test"}],
                }
            }
            yaml.dump(config, f)
            f.flush()

            manager = ExportConfigManager(config_file=f.name)
            configs = manager.load_from_file()

            # Invalid configs should be skipped, but default key might exist with empty list
            assert len(configs) == 0 or (
                len(configs) == 1 and configs.get("default", []) == []
            )
