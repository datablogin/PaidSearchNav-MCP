import asyncio
import os

from google.cloud import bigquery
from google.oauth2 import service_account


class BigQueryClient:
    """Client for executing BigQuery queries."""

    def __init__(
        self, project_id: str | None = None, credentials_path: str | None = None
    ):
        """Initialize BigQuery client with service account credentials."""
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")

        if not self.project_id:
            raise ValueError(
                "project_id must be provided or GCP_PROJECT_ID environment variable must be set"
            )

        if credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cred_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            credentials = service_account.Credentials.from_service_account_file(
                cred_path
            )
            self.client = bigquery.Client(
                project=self.project_id, credentials=credentials
            )
        else:
            # Use application default credentials
            self.client = bigquery.Client(project=self.project_id)

    async def execute_query(
        self, query: str, max_results: int = 10000, timeout: int = 300
    ) -> list[dict]:
        """
        Execute a SQL query and return results as list of dicts.

        Args:
            query: SQL query to execute
            max_results: Maximum number of rows to return (default 10000)
            timeout: Query timeout in seconds (default 300 = 5 minutes)

        Returns:
            List of dictionaries representing query results

        Raises:
            TimeoutError: If query exceeds timeout
            ValueError: If query is invalid
        """

        def _execute_query():
            query_job = self.client.query(query)
            results = query_job.result(max_results=max_results, timeout=timeout)
            # Convert to list of dicts
            return [dict(row) for row in results]

        return await asyncio.to_thread(_execute_query)

    async def get_table_schema(self, dataset_id: str, table_id: str) -> dict:
        """Get schema information for a table.

        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID

        Returns:
            Dictionary with table metadata and schema information
        """

        def _get_schema():
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            table = self.client.get_table(table_ref)

            return {
                "table": table_ref,
                "schema": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "mode": field.mode,
                        "description": field.description,
                    }
                    for field in table.schema
                ],
                "num_rows": table.num_rows,
                "size_bytes": table.num_bytes,
            }

        return await asyncio.to_thread(_get_schema)

    async def estimate_query_cost(self, query: str) -> dict:
        """
        Estimate the cost of a query before running it.

        Args:
            query: SQL query to estimate

        Returns:
            Dictionary with bytes processed, cost estimate, and cache status

        Note:
            Cost calculation based on BigQuery pricing as of January 2025:
            $6.25 per TB processed. Cached queries are free.
        """

        def _estimate_cost():
            # Create a dry run job
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            query_job = self.client.query(query, job_config=job_config)

            # Calculate cost ($6.25 per TB as of January 2025)
            # See: https://cloud.google.com/bigquery/pricing#on_demand_pricing
            bytes_processed = query_job.total_bytes_processed
            cost_per_tb = 6.25
            estimated_cost = (bytes_processed / (1024**4)) * cost_per_tb

            return {
                "bytes_processed": bytes_processed,
                "bytes_billed": query_job.total_bytes_billed,
                "estimated_cost_usd": round(estimated_cost, 4),
                "is_cached": bytes_processed == 0,  # Cached queries are free
            }

        return await asyncio.to_thread(_estimate_cost)
