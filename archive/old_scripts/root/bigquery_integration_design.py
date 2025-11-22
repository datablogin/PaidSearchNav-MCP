"""
BigQuery Integration Design for PaidSearchNav

This module defines the complete BigQuery integration architecture including:
1. Configuration classes
2. Authentication methods
3. Data providers
4. Service layers
5. API endpoints
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, SecretStr

# =============================================================================
# 1. CONFIGURATION LAYER
# =============================================================================


class BigQueryTier(str, Enum):
    """BigQuery service tiers for different customer pricing."""

    DISABLED = "disabled"  # Standard CSV-only tier
    PREMIUM = "premium"  # BigQuery analytics tier
    ENTERPRISE = "enterprise"  # BigQuery ML + custom models


class BigQueryConfig(BaseModel):
    """BigQuery configuration for premium analytics tier."""

    # Core BigQuery settings
    enabled: bool = Field(default=False, description="Enable BigQuery integration")
    tier: BigQueryTier = Field(default=BigQueryTier.DISABLED)
    project_id: str | None = Field(default=None, description="Google Cloud Project ID")
    dataset_id: str = Field(
        default="paid_search_nav", description="BigQuery dataset name"
    )
    location: str = Field(default="US", description="BigQuery dataset location")

    # Authentication
    service_account_path: str | None = Field(
        default=None, description="Path to service account JSON"
    )
    service_account_json: SecretStr | None = Field(
        default=None, description="Service account JSON content"
    )
    use_default_credentials: bool = Field(
        default=True, description="Use default Google Cloud credentials"
    )

    # Performance & Cost Controls
    max_query_bytes: int = Field(
        default=1_000_000_000, description="Max bytes processed per query (1GB)"
    )
    query_timeout_seconds: int = Field(
        default=60, description="Query timeout in seconds"
    )
    streaming_insert_batch_size: int = Field(
        default=1000, description="Batch size for streaming inserts"
    )

    # Cost management
    daily_cost_limit_usd: float = Field(
        default=100.0, description="Daily BigQuery cost limit in USD"
    )
    cost_alert_threshold_usd: float = Field(
        default=80.0, description="Cost alert threshold in USD"
    )
    enable_query_cache: bool = Field(
        default=True, description="Enable query result caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600, description="Query cache TTL in seconds"
    )

    # Premium features
    enable_ml_models: bool = Field(
        default=False, description="Enable BigQuery ML features"
    )
    enable_real_time_streaming: bool = Field(
        default=True, description="Enable real-time data streaming"
    )
    enable_cross_project_queries: bool = Field(
        default=False, description="Allow cross-project queries"
    )


# =============================================================================
# 2. AUTHENTICATION & CONNECTION
# =============================================================================


class BigQueryAuthenticator:
    """Handles BigQuery authentication using multiple methods."""

    def __init__(self, config: BigQueryConfig):
        self.config = config

    async def get_client(self):
        """Get authenticated BigQuery client."""
        import google.auth
        from google.cloud import bigquery
        from google.oauth2 import service_account

        if self.config.service_account_path:
            # Service account file
            credentials = service_account.Credentials.from_service_account_file(
                self.config.service_account_path
            )
            return bigquery.Client(
                project=self.config.project_id,
                credentials=credentials,
                location=self.config.location,
            )

        elif self.config.service_account_json:
            # Service account JSON content
            service_account_info = json.loads(
                self.config.service_account_json.get_secret_value()
            )
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
            return bigquery.Client(
                project=self.config.project_id,
                credentials=credentials,
                location=self.config.location,
            )

        else:
            # Default credentials (Application Default Credentials)
            credentials, project = google.auth.default()
            return bigquery.Client(
                project=self.config.project_id or project,
                credentials=credentials,
                location=self.config.location,
            )


# =============================================================================
# 3. DATA MODELS & SCHEMA
# =============================================================================


class BigQueryTableSchema:
    """Defines BigQuery table schemas for all analyzer data."""

    @staticmethod
    def search_terms_schema():
        """Schema for search terms analyzer data."""
        from google.cloud import bigquery

        return [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("campaign_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ad_group_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ad_group_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("search_term", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("match_type", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("impressions", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("clicks", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("cost", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("conversions", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("ctr", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("cpc", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("local_intent_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("quality_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("negative_recommendation", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]

    @staticmethod
    def keywords_schema():
        """Schema for keywords analyzer data."""
        from google.cloud import bigquery

        return [
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("campaign_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("campaign_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ad_group_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ad_group_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("keyword_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("keyword_text", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("match_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("impressions", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("clicks", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("cost", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("conversions", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("ctr", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("cpc", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("quality_score", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("bid_recommendation", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("local_relevance", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField("performance_tier", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]


# =============================================================================
# 4. DATA STREAMING & INGESTION
# =============================================================================


class BigQueryDataStreamer:
    """Handles real-time data streaming to BigQuery."""

    def __init__(self, config: BigQueryConfig, authenticator: BigQueryAuthenticator):
        self.config = config
        self.authenticator = authenticator

    async def stream_search_terms(self, data: List[Dict[str, Any]], customer_id: str):
        """Stream search terms data to BigQuery."""
        if not self.config.enabled or self.config.tier == BigQueryTier.DISABLED:
            return {"success": False, "reason": "BigQuery not enabled"}

        client = await self.authenticator.get_client()
        table_id = f"{self.config.project_id}.{self.config.dataset_id}.search_terms"

        # Add metadata to each row
        enriched_data = []
        for row in data:
            enriched_row = {
                **row,
                "customer_id": customer_id,
                "created_at": "CURRENT_TIMESTAMP()",
                "updated_at": "CURRENT_TIMESTAMP()",
            }
            enriched_data.append(enriched_row)

        # Stream in batches
        batch_size = self.config.streaming_insert_batch_size
        results = []

        for i in range(0, len(enriched_data), batch_size):
            batch = enriched_data[i : i + batch_size]
            errors = client.insert_rows_json(table_id, batch)

            if errors:
                results.append({"success": False, "errors": errors, "batch": i})
            else:
                results.append(
                    {"success": True, "rows_inserted": len(batch), "batch": i}
                )

        return {
            "success": all(r["success"] for r in results),
            "total_rows": len(enriched_data),
            "batch_results": results,
        }


# =============================================================================
# 5. ANALYTICS & QUERY ENGINE
# =============================================================================


class BigQueryAnalyticsEngine:
    """Provides analytics capabilities using BigQuery SQL."""

    def __init__(self, config: BigQueryConfig, authenticator: BigQueryAuthenticator):
        self.config = config
        self.authenticator = authenticator

    async def get_search_terms_insights(
        self,
        customer_id: str,
        date_range: int = 30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Get search terms insights using BigQuery analytics."""

        client = await self.authenticator.get_client()

        query = f"""
        SELECT
            search_term,
            campaign_name,
            SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks,
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            AVG(local_intent_score) as avg_local_intent,
            AVG(quality_score) as avg_quality_score,
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > 50 THEN 'HIGH_PRIORITY_NEGATIVE'
                WHEN AVG(local_intent_score) < 0.3 THEN 'CONSIDER_NEGATIVE'
                ELSE 'KEEP_ACTIVE'
            END as recommendation_type,
            COUNT(*) as days_active,
            MAX(date) as last_seen_date
        FROM `{self.config.project_id}.{self.config.dataset_id}.search_terms`
        WHERE customer_id = @customer_id
        AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL @date_range DAY)
        GROUP BY search_term, campaign_name
        ORDER BY total_cost DESC
        LIMIT 1000
        """

        # TODO: Implement BigQuery job configuration
        # job_config = bigquery.QueryJobConfig(
        #     query_parameters=[
        #         bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
        #         bigquery.ScalarQueryParameter("date_range", "INT64", date_range),
        #     ],
        #     use_query_cache=self.config.enable_query_cache,
        #     maximum_bytes_billed=self.config.max_query_bytes,
        # )

        # query_job = client.query(query, job_config=job_config)
        # results = query_job.result(timeout=self.config.query_timeout_seconds)
        # return [dict(row) for row in results]
        return []  # TODO: Implement BigQuery query execution

    async def get_keyword_bid_recommendations(
        self, customer_id: str, performance_threshold: float = 0.02
    ) -> List[Dict[str, Any]]:
        """Get ML-powered keyword bid recommendations."""

        if self.config.tier != BigQueryTier.ENTERPRISE:
            raise ValueError("Bid recommendations require Enterprise tier")

        client = await self.authenticator.get_client()

        query = f"""
        WITH keyword_performance AS (
            SELECT
                keyword_text,
                campaign_name,
                ad_group_name,
                AVG(ctr) as avg_ctr,
                AVG(cpc) as avg_cpc,
                SUM(cost) as total_cost,
                SUM(conversions) as total_conversions,
                AVG(quality_score) as avg_quality_score
            FROM `{self.config.project_id}.{self.config.dataset_id}.keywords`
            WHERE customer_id = @customer_id
            AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            GROUP BY keyword_text, campaign_name, ad_group_name
        ),
        ml_predictions AS (
            SELECT
                *,
                ML.PREDICT(
                    MODEL `{self.config.project_id}.{self.config.dataset_id}.bid_optimization_model`,
                    (SELECT * FROM keyword_performance)
                ) as predicted_bid
            FROM keyword_performance
        )
        SELECT
            keyword_text,
            campaign_name,
            ad_group_name,
            avg_ctr,
            avg_cpc,
            total_cost,
            total_conversions,
            predicted_bid,
            CASE
                WHEN predicted_bid > avg_cpc * 1.25 THEN 'INCREASE_BID'
                WHEN predicted_bid < avg_cpc * 0.75 THEN 'DECREASE_BID'
                ELSE 'MAINTAIN_BID'
            END as bid_recommendation
        FROM ml_predictions
        WHERE avg_ctr > @performance_threshold
        ORDER BY total_cost DESC
        """

        # TODO: Implement BigQuery job configuration
        # job_config = bigquery.QueryJobConfig(
        #     query_parameters=[
        #         bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
        #         bigquery.ScalarQueryParameter(
        #             "performance_threshold", "FLOAT64", performance_threshold
        #         ),
        #     ]
        # )

        # query_job = client.query(query, job_config=job_config)
        # results = query_job.result()
        # return [dict(row) for row in results]
        return []  # TODO: Implement BigQuery query execution


# =============================================================================
# 6. COST MONITORING & MANAGEMENT
# =============================================================================


class BigQueryCostMonitor:
    """Monitors and manages BigQuery costs."""

    def __init__(self, config: BigQueryConfig, authenticator: BigQueryAuthenticator):
        self.config = config
        self.authenticator = authenticator

    async def get_daily_costs(self, customer_id: str) -> Dict[str, float]:
        """Get BigQuery costs for the current day."""
        client = await self.authenticator.get_client()

        query = f"""
        SELECT
            SUM(total_bytes_processed) / 1024 / 1024 / 1024 / 1024 as tb_processed,
            SUM(total_bytes_processed) / 1024 / 1024 / 1024 / 1024 * 5.0 as estimated_cost_usd
        FROM `{self.config.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= CURRENT_DATE()
        AND job_type = 'QUERY'
        AND user_email LIKE '%{customer_id}%'
        """

        query_job = client.query(query)
        results = list(query_job.result())

        if results:
            row = results[0]
            return {
                "tb_processed": float(row.tb_processed or 0),
                "estimated_cost_usd": float(row.estimated_cost_usd or 0),
                "daily_limit_usd": self.config.daily_cost_limit_usd,
                "remaining_budget_usd": self.config.daily_cost_limit_usd
                - float(row.estimated_cost_usd or 0),
            }

        return {
            "tb_processed": 0.0,
            "estimated_cost_usd": 0.0,
            "daily_limit_usd": self.config.daily_cost_limit_usd,
            "remaining_budget_usd": self.config.daily_cost_limit_usd,
        }


# =============================================================================
# 7. API INTEGRATION LAYER
# =============================================================================


class BigQueryService:
    """Main service class for BigQuery integration."""

    def __init__(self, config: BigQueryConfig):
        self.config = config
        self.authenticator = BigQueryAuthenticator(config)
        self.streamer = BigQueryDataStreamer(config, self.authenticator)
        self.analytics = BigQueryAnalyticsEngine(config, self.authenticator)
        self.cost_monitor = BigQueryCostMonitor(config, self.authenticator)

    async def health_check(self) -> Dict[str, Any]:
        """Check BigQuery service health."""
        try:
            client = await self.authenticator.get_client()

            # Test basic connectivity
            query = "SELECT 1 as test"
            query_job = client.query(query)
            results = list(query_job.result())

            return {
                "status": "healthy",
                "enabled": self.config.enabled,
                "tier": self.config.tier,
                "project_id": self.config.project_id,
                "dataset_id": self.config.dataset_id,
                "connectivity": "ok",
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "enabled": self.config.enabled,
                "tier": self.config.tier,
                "error": str(e),
            }


# =============================================================================
# 8. CONFIGURATION UPDATES FOR SETTINGS CLASS
# =============================================================================

"""
Add this to the main Settings class in config.py:

class Settings(BaseSettings):
    # ... existing fields ...

    # BigQuery Integration (NEW)
    bigquery: BigQueryConfig = Field(default_factory=BigQueryConfig)

    # ... rest of existing configuration ...
"""

# =============================================================================
# 9. ENVIRONMENT VARIABLES
# =============================================================================

"""
Environment variables to add:

# BigQuery Configuration
PSN_BIGQUERY__ENABLED=true
PSN_BIGQUERY__TIER=premium
PSN_BIGQUERY__PROJECT_ID=fitness-connection-469620
PSN_BIGQUERY__DATASET_ID=paid_search_nav
PSN_BIGQUERY__LOCATION=US

# Authentication (choose one)
PSN_BIGQUERY__SERVICE_ACCOUNT_PATH=/path/to/service-account.json
# OR
PSN_BIGQUERY__SERVICE_ACCOUNT_JSON={"type":"service_account",...}
# OR
PSN_BIGQUERY__USE_DEFAULT_CREDENTIALS=true

# Cost Controls
PSN_BIGQUERY__DAILY_COST_LIMIT_USD=100.0
PSN_BIGQUERY__MAX_QUERY_BYTES=1000000000

# Premium Features
PSN_BIGQUERY__ENABLE_ML_MODELS=true
PSN_BIGQUERY__ENABLE_REAL_TIME_STREAMING=true
"""
