"""Main BigQuery service for PaidSearchNav."""

import logging
from typing import Any, Dict, Optional

from paidsearchnav_mcp.core.config import BigQueryTier
from paidsearchnav_mcp.platforms.bigquery.analytics import BigQueryAnalyticsEngine
from paidsearchnav_mcp.platforms.bigquery.auth import BigQueryAuthenticator
from paidsearchnav_mcp.platforms.bigquery.cost_monitor import BigQueryCostMonitor
from paidsearchnav_mcp.platforms.bigquery.streaming import BigQueryDataStreamer
from paidsearchnav_mcp.platforms.bigquery.timeout_client import (
    BigQueryTimeoutClient,
    create_timeout_client,
)
from paidsearchnav_mcp.platforms.bigquery.timeout_config import CustomerTier

logger = logging.getLogger(__name__)


class BigQueryService:
    """Main service class for BigQuery integration."""

    def __init__(self, config):
        """Initialize BigQuery service with configuration."""
        self.config = config
        self.authenticator = BigQueryAuthenticator(config)
        self.analytics = BigQueryAnalyticsEngine(config, self.authenticator)
        self.streamer = BigQueryDataStreamer(config, self.authenticator)
        self.cost_monitor = BigQueryCostMonitor(config, self.authenticator)

        # Map BigQuery tiers to customer tiers for timeout configuration
        self._tier_mapping = {
            BigQueryTier.STANDARD: CustomerTier.STANDARD,
            BigQueryTier.PREMIUM: CustomerTier.PREMIUM,
            BigQueryTier.ENTERPRISE: CustomerTier.ENTERPRISE,
        }

        # Initialize timeout client
        self._timeout_client: Optional[BigQueryTimeoutClient] = None

    @property
    def is_enabled(self) -> bool:
        """Check if BigQuery is enabled."""
        return self.config.enabled and self.config.tier != BigQueryTier.DISABLED

    @property
    def is_premium(self) -> bool:
        """Check if premium tier is enabled."""
        return self.config.tier in [BigQueryTier.PREMIUM, BigQueryTier.ENTERPRISE]

    @property
    def is_enterprise(self) -> bool:
        """Check if enterprise tier is enabled."""
        return self.config.tier == BigQueryTier.ENTERPRISE

    def supports_advanced_analytics(self) -> bool:
        """Check if advanced analytics are supported."""
        return self.is_premium or self.is_enterprise

    def supports_ml_models(self) -> bool:
        """Check if ML models are supported."""
        return self.is_enterprise

    async def get_timeout_client(self) -> BigQueryTimeoutClient:
        """Get timeout-aware BigQuery client."""
        if self._timeout_client is None:
            customer_tier = self._tier_mapping.get(
                self.config.tier, CustomerTier.STANDARD
            )
            self._timeout_client = create_timeout_client(
                project_id=self.config.project_id, customer_tier=customer_tier
            )
        return self._timeout_client

    def get_customer_tier(self) -> CustomerTier:
        """Get customer tier for timeout configuration."""
        return self._tier_mapping.get(self.config.tier, CustomerTier.STANDARD)

    async def health_check(self) -> Dict[str, Any]:
        """Check BigQuery service health and connectivity with timeout handling."""
        try:
            if not self.is_enabled:
                return {
                    "status": "disabled",
                    "enabled": False,
                    "tier": self.config.tier,
                    "message": "BigQuery integration is disabled",
                }

            timeout_client = await self.get_timeout_client()

            # Test basic connectivity with a simple query using timeout-aware client
            query = "SELECT 1 as connectivity_test"
            query_job = await timeout_client.query_with_timeout(
                query, customer_tier=self.get_customer_tier()
            )
            results = list(query_job.result())

            if results and results[0].connectivity_test == 1:
                # Get timeout configuration for status info
                from paidsearchnav_mcp.platforms.bigquery.timeout_config import (
                    get_timeout_config,
                )

                timeout_config = get_timeout_config(self.get_customer_tier())

                return {
                    "status": "healthy",
                    "enabled": True,
                    "tier": self.config.tier,
                    "project_id": self.config.project_id,
                    "dataset_id": self.config.dataset_id,
                    "location": self.config.location,
                    "connectivity": "ok",
                    "timeout_config": {
                        "customer_tier": self.get_customer_tier().value,
                        "query_timeout": timeout_config.query_timeout,
                        "export_timeout": timeout_config.export_timeout,
                        "connection_timeout": timeout_config.connection_timeout,
                        "auth_timeout": timeout_config.auth_timeout,
                    },
                    "features": {
                        "premium_analytics": self.is_premium,
                        "ml_models": self.is_enterprise
                        and self.config.enable_ml_models,
                        "real_time_streaming": self.config.enable_real_time_streaming,
                        "query_cache": self.config.enable_query_cache,
                        "timeout_management": True,
                    },
                }
            else:
                return {
                    "status": "unhealthy",
                    "enabled": True,
                    "tier": self.config.tier,
                    "error": "Connectivity test failed",
                }

        except Exception as e:
            logger.error(f"BigQuery health check failed: {e}")
            return {
                "status": "unhealthy",
                "enabled": self.config.enabled,
                "tier": self.config.tier,
                "error": str(e),
            }

    async def ensure_dataset_exists(self) -> bool:
        """Ensure the BigQuery dataset exists, create if necessary."""
        try:
            if not self.is_enabled:
                return False

            client = await self.authenticator.get_client()

            # Check if dataset exists
            try:
                dataset = client.get_dataset(
                    f"{self.config.project_id}.{self.config.dataset_id}"
                )
                logger.info(f"Dataset {self.config.dataset_id} already exists")
                return True
            except Exception:
                # Dataset doesn't exist, create it
                logger.info(f"Creating dataset {self.config.dataset_id}")

                from google.cloud import bigquery

                dataset_id = f"{self.config.project_id}.{self.config.dataset_id}"
                dataset = bigquery.Dataset(dataset_id)
                dataset.location = self.config.location
                dataset.description = "PaidSearchNav analyzer data warehouse"

                # Create the dataset
                dataset = client.create_dataset(dataset, timeout=30)
                logger.info(f"Created dataset {dataset_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to ensure dataset exists: {e}")
            return False

    async def get_usage_stats(
        self, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get BigQuery usage statistics."""
        try:
            if not self.is_enabled:
                return {"enabled": False, "message": "BigQuery not enabled"}

            # Get cost information
            cost_info = await self.cost_monitor.get_daily_costs(customer_id or "all")

            # Get basic dataset info
            client = await self.authenticator.get_client()
            dataset = client.get_dataset(
                f"{self.config.project_id}.{self.config.dataset_id}"
            )

            return {
                "enabled": True,
                "tier": self.config.tier,
                "dataset_created": dataset.created.isoformat()
                if dataset.created
                else None,
                "dataset_location": dataset.location,
                "cost_info": cost_info,
                "limits": {
                    "daily_cost_limit_usd": self.config.daily_cost_limit_usd,
                    "max_query_bytes": self.config.max_query_bytes,
                    "query_timeout_seconds": self.config.query_timeout_seconds,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {"enabled": True, "error": str(e)}

    async def test_permissions(self) -> Dict[str, Any]:
        """Test BigQuery permissions for various operations."""
        permissions = {
            "bigquery.datasets.get": False,
            "bigquery.tables.list": False,
            "bigquery.jobs.create": False,
            "bigquery.tables.create": False,
            "bigquery.tables.insertData": False,
        }

        try:
            if not self.is_enabled:
                return {"enabled": False, "permissions": permissions}

            client = await self.authenticator.get_client()

            # Test dataset access
            try:
                client.get_dataset(f"{self.config.project_id}.{self.config.dataset_id}")
                permissions["bigquery.datasets.get"] = True
            except Exception:
                pass

            # Test table listing
            try:
                list(
                    client.list_tables(
                        f"{self.config.project_id}.{self.config.dataset_id}"
                    )
                )
                permissions["bigquery.tables.list"] = True
            except Exception:
                pass

            # Test query creation
            try:
                query = "SELECT 1"
                query_job = client.query(query)
                query_job.result()
                permissions["bigquery.jobs.create"] = True
            except Exception:
                pass

            return {
                "enabled": True,
                "permissions": permissions,
                "summary": {
                    "total_permissions": len(permissions),
                    "granted_permissions": sum(permissions.values()),
                    "permission_level": "full"
                    if all(permissions.values())
                    else "partial",
                },
            }

        except Exception as e:
            logger.error(f"Permission test failed: {e}")
            return {"enabled": True, "error": str(e), "permissions": permissions}
