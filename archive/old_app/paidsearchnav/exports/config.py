"""Export configuration management."""

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .base import ExportConfig, ExportFormat


class ExportConfigManager:
    """Manage export configurations from various sources."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_file = config_file or os.getenv(
            "EXPORT_CONFIG_FILE", "export_config.yaml"
        )
        self.configs: Dict[str, List[ExportConfig]] = {}

    def load_from_file(self) -> Dict[str, List[ExportConfig]]:
        """Load export configurations from YAML file."""
        config_path = Path(self.config_file)
        if not config_path.exists():
            return {}

        with open(config_path, "r") as f:
            raw_config = yaml.safe_load(f)

        if not raw_config or "exports" not in raw_config:
            return {}

        exports_config = raw_config["exports"]
        if not exports_config.get("enabled", True):
            return {}

        configs = {}
        for dest in exports_config.get("destinations", []):
            customer_id = dest.get("customer_id", "default")

            if customer_id not in configs:
                configs[customer_id] = []

            # Parse destination type
            dest_type = dest.get("type", "").lower()
            if dest_type not in [e.value for e in ExportFormat]:
                continue

            # Create export config
            config = ExportConfig(
                destination_type=ExportFormat(dest_type),
                credentials=dest.get("credentials", {}),
                schedule=dest.get("schedule"),
                enabled=dest.get("enabled", True),
                options=dest.get("options", {}),
                # BigQuery specific
                project_id=dest.get("project_id"),
                dataset=dest.get("dataset"),
                # Snowflake specific
                account=dest.get("account"),
                warehouse=dest.get("warehouse"),
                database=dest.get("database"),
                schema=dest.get("schema"),
                # File export specific
                output_path=dest.get("output_path"),
                compression=dest.get("compression"),
            )

            configs[customer_id].append(config)

        self.configs = configs
        return configs

    def load_from_env(self) -> Dict[str, List[ExportConfig]]:
        """Load export configurations from environment variables."""
        configs = {}

        # Check for BigQuery configuration
        if os.getenv("BIGQUERY_EXPORT_ENABLED", "").lower() == "true":
            customer_id = os.getenv("BIGQUERY_CUSTOMER_ID", "default")

            if customer_id not in configs:
                configs[customer_id] = []

            config = ExportConfig(
                destination_type=ExportFormat.BIGQUERY,
                credentials={
                    "service_account_json": os.getenv(
                        "BIGQUERY_SERVICE_ACCOUNT_JSON", ""
                    )
                },
                project_id=os.getenv("BIGQUERY_PROJECT_ID"),
                dataset=os.getenv("BIGQUERY_DATASET"),
                schedule=os.getenv("BIGQUERY_EXPORT_SCHEDULE"),
                enabled=True,
            )

            configs[customer_id].append(config)

        # Update internal configs
        for customer_id, customer_configs in configs.items():
            if customer_id in self.configs:
                self.configs[customer_id].extend(customer_configs)
            else:
                self.configs[customer_id] = customer_configs

        return configs

    def get_configs_for_customer(self, customer_id: str) -> List[ExportConfig]:
        """Get all export configurations for a specific customer."""
        # Load configurations if not already loaded
        if not self.configs:
            self.load_from_file()
            self.load_from_env()

        # Return customer-specific configs or default configs
        return self.configs.get(customer_id, self.configs.get("default", []))

    def get_enabled_configs(self, customer_id: str) -> List[ExportConfig]:
        """Get only enabled export configurations for a customer."""
        return [
            config
            for config in self.get_configs_for_customer(customer_id)
            if config.enabled
        ]

    def add_config(self, customer_id: str, config: ExportConfig) -> None:
        """Add a new export configuration."""
        if customer_id not in self.configs:
            self.configs[customer_id] = []
        self.configs[customer_id].append(config)

    def remove_config(self, customer_id: str, destination_type: ExportFormat) -> bool:
        """Remove an export configuration."""
        if customer_id not in self.configs:
            return False

        original_length = len(self.configs[customer_id])
        self.configs[customer_id] = [
            config
            for config in self.configs[customer_id]
            if config.destination_type != destination_type
        ]

        return len(self.configs[customer_id]) < original_length
