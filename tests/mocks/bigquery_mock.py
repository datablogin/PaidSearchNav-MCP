"""Mock BigQuery infrastructure for testing and CI/CD."""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from paidsearchnav.exports.base import ExportStatus


class MockBigQueryClient:
    """Mock BigQuery client for testing."""

    def __init__(self, project_id: str = "test-project"):
        self.project_id = project_id
        self.datasets = {}
        self.tables = {}
        self.job_results = {}
        self.query_history = []
        self.failed_operations = set()

    def dataset(self, dataset_id: str):
        """Get dataset reference."""
        return MockDatasetRef(dataset_id, self)

    def get_dataset(self, dataset_ref):
        """Get dataset (raises NotFound if doesn't exist)."""
        if dataset_ref.dataset_id not in self.datasets:
            from google.cloud.exceptions import NotFound

            raise NotFound(f"Dataset {dataset_ref.dataset_id} not found")
        return self.datasets[dataset_ref.dataset_id]

    def create_dataset(self, dataset_ref):
        """Create dataset."""
        dataset = MockDataset(dataset_ref.dataset_id)
        self.datasets[dataset_ref.dataset_id] = dataset
        return dataset

    def get_table(self, table_ref):
        """Get table (raises NotFound if doesn't exist)."""
        table_key = f"{table_ref.dataset_id}.{table_ref.table_id}"
        if table_key not in self.tables:
            from google.cloud.exceptions import NotFound

            raise NotFound(f"Table {table_key} not found")
        return self.tables[table_key]

    def create_table(self, table_ref):
        """Create table."""
        table_key = f"{table_ref.dataset_id}.{table_ref.table_id}"
        table = MockTable(table_ref.table_id, table_ref.dataset_id)
        self.tables[table_key] = table
        return table

    def delete_table(self, table_ref):
        """Delete table."""
        table_key = f"{table_ref.dataset_id}.{table_ref.table_id}"
        if table_key in self.tables:
            del self.tables[table_key]

    def insert_rows_json(self, table, rows, **kwargs):
        """Insert rows into table."""
        table_key = f"{table.dataset_id}.{table.table_id}"

        # Simulate insertion errors for specific test cases
        if table_key in self.failed_operations:
            return [{"errors": [{"message": "Simulated insertion error"}]}]

        # Store rows in table
        if not hasattr(table, "rows"):
            table.rows = []
        table.rows.extend(rows)

        return []  # No errors

    def query(self, query_string, **kwargs):
        """Execute query."""
        job = MockQueryJob(query_string, self)
        self.query_history.append(
            {
                "query": query_string,
                "timestamp": datetime.utcnow(),
                "job_id": job.job_id,
            }
        )
        return job

    def simulate_failure(self, operation_type: str, resource_id: str):
        """Simulate failure for testing."""
        if operation_type == "insert":
            self.failed_operations.add(resource_id)

    def clear_failures(self):
        """Clear all simulated failures."""
        self.failed_operations.clear()


class MockDatasetRef:
    """Mock dataset reference."""

    def __init__(self, dataset_id: str, client: MockBigQueryClient):
        self.dataset_id = dataset_id
        self.client = client

    def table(self, table_id: str):
        """Get table reference."""
        return MockTableRef(table_id, self.dataset_id, self.client)


class MockTableRef:
    """Mock table reference."""

    def __init__(self, table_id: str, dataset_id: str, client: MockBigQueryClient):
        self.table_id = table_id
        self.dataset_id = dataset_id
        self.client = client


class MockDataset:
    """Mock BigQuery dataset."""

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self.created = datetime.utcnow()
        self.location = "US"
        self.tables = {}


class MockTable:
    """Mock BigQuery table."""

    def __init__(self, table_id: str, dataset_id: str):
        self.table_id = table_id
        self.dataset_id = dataset_id
        self.created = datetime.utcnow()
        self.schema = []
        self.time_partitioning = None
        self.rows = []

    @property
    def num_rows(self):
        """Get number of rows in table."""
        return len(self.rows) if hasattr(self, "rows") else 0


class MockQueryJob:
    """Mock BigQuery query job."""

    def __init__(self, query: str, client: MockBigQueryClient):
        self.query = query
        self.client = client
        self.job_id = f"job_{int(time.time() * 1000)}"
        self.state = "RUNNING"
        self.created = datetime.utcnow()

    def result(self, timeout=None):
        """Get query results."""
        # Simulate query execution time
        time.sleep(0.1)

        self.state = "DONE"

        # Return mock results based on query
        if "SELECT 1" in self.query:
            return [{"result": 1}]
        elif "usage_stats" in self.query.lower():
            return [
                {
                    "daily_cost_usd": 25.50,
                    "queries_today": 150,
                    "bytes_processed_today": 5368709120,
                    "last_query_time": datetime.utcnow(),
                }
            ]
        elif "search_terms" in self.query.lower():
            return [
                {
                    "search_term": "running shoes",
                    "total_cost": 125.50,
                    "conversions": 5,
                    "conversion_rate": 0.025,
                    "recommendation": "increase_bid",
                },
                {
                    "search_term": "winter boots",
                    "total_cost": 89.75,
                    "conversions": 8,
                    "conversion_rate": 0.045,
                    "recommendation": "optimize_keywords",
                },
            ]
        else:
            return [{"mock_result": "success"}]


class MockBigQueryExporter:
    """Mock BigQuery exporter for testing."""

    def __init__(self, config):
        self.config = config
        self.client = MockBigQueryClient(config.project_id)
        self.dataset_ref = None
        self._validated_credentials = True

    async def validate_connection(self):
        """Mock connection validation."""
        if self.config.project_id == "invalid-project":
            raise Exception("Invalid project")
        return True

    async def export_audit_results(
        self, customer_id: str, audit_data: List[Dict[str, Any]]
    ):
        """Mock audit results export."""
        from paidsearchnav.exports.base import ExportFormat, ExportResult

        # Simulate export processing
        await asyncio.sleep(0.1)

        # Check for simulated failures
        if customer_id == "failing_customer":
            return ExportResult(
                export_id=f"export_{int(time.time())}",
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                error_message="Simulated BigQuery export failure",
            )

        return ExportResult(
            export_id=f"export_{int(time.time())}",
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=len(audit_data),
            metadata={
                "table": f"audit_results_{datetime.now().strftime('%Y%m%d')}",
                "customer_id": customer_id,
                "schema_version": "v1.2",
                "processing_time_ms": 150,
            },
        )

    async def export_recommendations(
        self, customer_id: str, recommendations: List[Dict[str, Any]]
    ):
        """Mock recommendations export."""
        from paidsearchnav.exports.base import ExportFormat, ExportResult

        await asyncio.sleep(0.05)

        return ExportResult(
            export_id=f"export_{int(time.time())}",
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=len(recommendations),
            metadata={
                "table": f"recommendations_{datetime.now().strftime('%Y%m%d')}",
                "customer_id": customer_id,
            },
        )

    async def export_metrics(self, customer_id: str, metrics: List[Dict[str, Any]]):
        """Mock metrics export."""
        from paidsearchnav.exports.base import ExportFormat, ExportResult

        await asyncio.sleep(0.05)

        return ExportResult(
            export_id=f"export_{int(time.time())}",
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=len(metrics),
            metadata={
                "table": f"metrics_{datetime.now().strftime('%Y%m%d')}",
                "customer_id": customer_id,
            },
        )

    async def check_export_status(self, export_id: str):
        """Mock export status check."""
        from paidsearchnav.exports.base import ExportFormat, ExportResult

        return ExportResult(
            export_id=export_id,
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            metadata={"message": "Mock export completed synchronously"},
        )


class MockBigQueryService:
    """Mock BigQuery service for testing."""

    def __init__(self, config):
        self.config = config
        self.client = MockBigQueryClient(config.project_id)
        self.cost_tracker = {}
        self.analytics = MockAnalytics()
        self.cost_monitor = MockCostMonitor()

    @property
    def is_enabled(self):
        return self.config.enabled

    @property
    def is_premium(self):
        return self.config.tier in ["premium", "enterprise"]

    @property
    def is_enterprise(self):
        return self.config.tier == "enterprise"

    def supports_advanced_analytics(self):
        return self.is_premium

    def supports_ml_models(self):
        return self.is_enterprise

    async def health_check(self):
        """Mock health check."""
        if not self.is_enabled:
            return {"status": "disabled", "enabled": False}

        if self.config.project_id == "failing-project":
            return {
                "status": "unhealthy",
                "connectivity": False,
                "errors": ["Mock connection failure"],
            }

        return {
            "status": "healthy",
            "connectivity": True,
            "permissions": True,
            "dataset_accessible": True,
            "response_time_ms": 150,
        }

    async def ensure_dataset_exists(self):
        """Mock dataset creation."""
        if self.config.project_id == "no-permission-project":
            return False
        return True

    async def get_usage_stats(self, customer_id: Optional[str] = None):
        """Mock usage statistics."""
        if not self.is_enabled:
            return {"status": "disabled", "enabled": False}

        base_cost = 25.50 if customer_id != "high_usage_customer" else 85.0

        return {
            "customer_id": customer_id or "default",
            "daily_cost_usd": base_cost,
            "daily_limit_usd": self.config.daily_cost_limit_usd,
            "cost_percentage": (base_cost / self.config.daily_cost_limit_usd) * 100,
            "queries_today": 150,
            "bytes_processed_today": 5368709120,
            "last_query_time": datetime.utcnow().isoformat(),
        }

    async def test_permissions(self):
        """Mock permission testing."""
        if not self.is_enabled:
            return {"status": "disabled", "enabled": False}

        if self.config.project_id == "limited-permissions-project":
            return {
                "dataset_access": True,
                "table_create": False,
                "table_read": True,
                "table_write": False,
                "job_create": True,
                "permissions_summary": "Missing permissions: table_create, table_write",
            }

        return {
            "dataset_access": True,
            "table_create": True,
            "table_read": True,
            "table_write": True,
            "job_create": True,
            "permissions_summary": "All required permissions available",
        }

    async def _check_cost_limits(self, customer_id: str, estimated_cost: float):
        """Mock cost limit checking."""
        current_stats = await self.get_usage_stats(customer_id)
        current_cost = current_stats.get("daily_cost_usd", 0)
        limit = current_stats.get("daily_limit_usd", 100)

        return (current_cost + estimated_cost) <= limit


class MockAnalytics:
    """Mock BigQuery analytics service."""

    async def get_search_terms_insights(self, customer_id: str, date_range: int):
        """Mock search terms insights."""
        return [
            {
                "search_term": "running shoes",
                "total_cost": 125.50,
                "conversions": 5,
                "conversion_rate": 0.025,
                "recommendation": "increase_bid",
            },
            {
                "search_term": "winter boots",
                "total_cost": 89.75,
                "conversions": 8,
                "conversion_rate": 0.045,
                "recommendation": "optimize_keywords",
            },
        ]

    async def get_keyword_bid_recommendations(
        self, customer_id: str, performance_threshold: float
    ):
        """Mock bid recommendations."""
        return [
            {
                "keyword": "running shoes",
                "current_bid": 1.50,
                "recommended_bid": 1.75,
                "confidence": 0.85,
                "expected_improvement": "15% increase in conversions",
            },
            {
                "keyword": "winter boots",
                "current_bid": 1.20,
                "recommended_bid": 1.40,
                "confidence": 0.92,
                "expected_improvement": "12% increase in conversions",
            },
        ]


class MockCostMonitor:
    """Mock BigQuery cost monitoring service."""

    async def check_cost_alerts(self, customer_id: Optional[str] = None):
        """Mock cost alerts checking."""
        base_cost = 25.50 if customer_id != "high_cost_customer" else 85.0
        limit = 100.0
        percentage = (base_cost / limit) * 100

        alerts = []
        if percentage > 80:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"Cost is {percentage:.0f}% of daily limit",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        if percentage > 95:
            alerts.append(
                {
                    "level": "critical",
                    "message": "Cost is approaching daily limit",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return {
            "customer_id": customer_id or "default",
            "current_cost_usd": base_cost,
            "daily_limit_usd": limit,
            "cost_percentage": percentage,
            "alerts": alerts,
        }


# Test fixtures and utilities
def create_mock_bigquery_config(tier: str = "premium", enabled: bool = True):
    """Create mock BigQuery configuration."""
    from paidsearchnav.core.config import BigQueryConfig, BigQueryTier

    return BigQueryConfig(
        enabled=enabled,
        tier=getattr(BigQueryTier, tier.upper()),
        project_id=f"test-project-{tier}",
        dataset_id=f"test_dataset_{tier}",
        location="US",
        service_account_json='{"type": "service_account", "project_id": "test-project"}',
        daily_cost_limit_usd=100.0 if tier == "premium" else 500.0,
        enable_ml_models=tier == "enterprise",
        enable_real_time_streaming=tier == "enterprise",
    )


def create_test_data_fixtures():
    """Create test data fixtures for BigQuery testing."""
    return {
        "small_dataset": {
            "search_terms": [
                {
                    "campaign": "Test Campaign",
                    "search_term": "test keyword",
                    "clicks": 10,
                    "cost": 5.50,
                    "date": "2024-01-15",
                }
            ],
            "keywords": [
                {
                    "campaign": "Test Campaign",
                    "keyword": "test keyword",
                    "clicks": 15,
                    "cost": 7.25,
                    "date": "2024-01-15",
                }
            ],
        },
        "large_dataset": {
            "search_terms": [
                {
                    "campaign": f"Campaign_{i % 10}",
                    "search_term": f"keyword_{i}",
                    "clicks": i % 50,
                    "cost": (i % 50) * 1.5,
                    "date": "2024-01-15",
                }
                for i in range(1000)
            ]
        },
    }


# Async utilities
async def simulate_bigquery_operation(duration_ms: int = 100):
    """Simulate BigQuery operation with specified duration."""
    await asyncio.sleep(duration_ms / 1000)
    return {"status": "completed", "duration_ms": duration_ms}
