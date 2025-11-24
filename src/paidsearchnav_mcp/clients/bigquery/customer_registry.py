"""Customer Registry for dynamic BigQuery project routing.

This module provides customer-to-project mapping functionality for the MCP server
to dynamically route BigQuery queries to the correct GCP project based on customer ID.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from google.cloud import bigquery
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


@dataclass
class CustomerConfig:
    """Configuration for a customer's BigQuery access."""

    customer_id: str
    project_id: str
    dataset: str
    account_name: str
    status: str


class CustomerRegistry:
    """Registry for mapping customer IDs to BigQuery projects."""

    def __init__(
        self,
        registry_project: str | None = None,
        registry_dataset: str = "paidsearchnav_production",
        registry_table: str = "customer_registry",
        credentials_path: str | None = None,
    ):
        """Initialize the customer registry.

        Args:
            registry_project: GCP project containing the registry table
            registry_dataset: Dataset containing the registry table
            registry_table: Table name for customer registry
            credentials_path: Path to service account credentials
        """
        self.registry_project = registry_project or os.getenv("GCP_PROJECT_ID")
        self.registry_dataset = registry_dataset
        self.registry_table = registry_table

        if not self.registry_project:
            raise ValueError(
                "registry_project must be provided or GCP_PROJECT_ID must be set"
            )

        # Initialize BigQuery client for registry access
        if credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cred_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            credentials = service_account.Credentials.from_service_account_file(
                cred_path
            )
            self.client = bigquery.Client(
                project=self.registry_project, credentials=credentials
            )
        else:
            self.client = bigquery.Client(project=self.registry_project)

        # Cache for customer configs
        self._cache: dict[str, CustomerConfig] = {}

    def get_customer_config(self, customer_id: str) -> Optional[CustomerConfig]:
        """Get BigQuery configuration for a customer.

        Args:
            customer_id: Google Ads customer ID (10 digits, no dashes)

        Returns:
            CustomerConfig if found, None otherwise
        """
        # Check cache first
        if customer_id in self._cache:
            return self._cache[customer_id]

        # Query registry table
        query = f"""
            SELECT
                customer_id,
                project_id,
                dataset,
                google_ads_account_name as account_name,
                status
            FROM `{self.registry_project}.{self.registry_dataset}.{self.registry_table}`
            WHERE customer_id = @customer_id
                AND status = 'active'
            LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id)
            ]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if not results:
                logger.warning(
                    f"Customer {customer_id} not found in registry or not active"
                )
                return None

            row = results[0]
            config = CustomerConfig(
                customer_id=row["customer_id"],
                project_id=row["project_id"],
                dataset=row["dataset"],
                account_name=row["account_name"],
                status=row["status"],
            )

            # Cache the result
            self._cache[customer_id] = config

            logger.info(
                f"Loaded config for customer {customer_id}: "
                f"project={config.project_id}, dataset={config.dataset}"
            )

            return config

        except Exception as e:
            logger.error(f"Error querying customer registry: {e}")
            return None

    def get_project_for_customer(self, customer_id: str) -> Optional[str]:
        """Get the BigQuery project ID for a customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Project ID if found, None otherwise
        """
        config = self.get_customer_config(customer_id)
        return config.project_id if config else None

    def get_dataset_for_customer(self, customer_id: str) -> Optional[str]:
        """Get the BigQuery dataset for a customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Dataset name if found, None otherwise
        """
        config = self.get_customer_config(customer_id)
        return config.dataset if config else None

    def clear_cache(self):
        """Clear the customer configuration cache."""
        self._cache.clear()
        logger.info("Customer registry cache cleared")

    def list_customers(self) -> list[CustomerConfig]:
        """List all active customers in the registry.

        Returns:
            List of CustomerConfig objects
        """
        query = f"""
            SELECT
                customer_id,
                project_id,
                dataset,
                google_ads_account_name as account_name,
                status
            FROM `{self.registry_project}.{self.registry_dataset}.{self.registry_table}`
            WHERE status = 'active'
            ORDER BY google_ads_account_name
        """

        try:
            query_job = self.client.query(query)
            results = list(query_job.result())

            customers = [
                CustomerConfig(
                    customer_id=row["customer_id"],
                    project_id=row["project_id"],
                    dataset=row["dataset"],
                    account_name=row["account_name"],
                    status=row["status"],
                )
                for row in results
            ]

            logger.info(f"Listed {len(customers)} active customers from registry")
            return customers

        except Exception as e:
            logger.error(f"Error listing customers from registry: {e}")
            return []
