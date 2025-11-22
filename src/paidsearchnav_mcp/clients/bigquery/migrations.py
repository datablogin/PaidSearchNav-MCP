"""BigQuery schema migration scripts for analyzer data warehouse.

This module provides tools to create and manage BigQuery tables with proper
partitioning, clustering, and optimization for all analyzer data.
"""

import logging
from typing import Any, Dict, Optional

from paidsearchnav_mcp.platforms.bigquery.schema import BigQueryTableSchema

logger = logging.getLogger(__name__)


class BigQueryMigrations:
    """Handles BigQuery table creation and schema migrations."""

    def __init__(self, config):
        """Initialize migrations with BigQuery configuration."""
        self.config = config
        self._client = None

    async def get_client(self):
        """Get BigQuery client instance."""
        if not self._client:
            try:
                from google.cloud import bigquery

                self._client = bigquery.Client(project=self.config.project_id)
            except ImportError:
                raise ImportError("Google Cloud BigQuery library not available")
        return self._client

    async def ensure_dataset_exists(self) -> bool:
        """Ensure the BigQuery dataset exists, create if necessary."""
        try:
            client = await self.get_client()

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
                dataset.description = (
                    "PaidSearchNav analyzer data warehouse with optimized schemas"
                )

                # Set default table expiration (optional)
                # dataset.default_table_expiration_ms = 1000 * 60 * 60 * 24 * 365  # 1 year

                # Create the dataset
                dataset = client.create_dataset(dataset, timeout=30)
                logger.info(f"Created dataset {dataset_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to ensure dataset exists: {e}")
            return False

    async def create_table(
        self,
        table_name: str,
        schema: list,
        partition_field: Optional[str] = None,
        partition_type: Optional[str] = None,
        cluster_fields: Optional[list] = None,
    ) -> bool:
        """Create a BigQuery table with the specified schema and optimizations."""
        try:
            client = await self.get_client()

            from google.cloud import bigquery

            # Construct table reference
            table_id = f"{self.config.project_id}.{self.config.dataset_id}.{table_name}"
            table = bigquery.Table(table_id, schema=schema)

            # Set table description
            configurations = BigQueryTableSchema.get_table_configurations()
            if table_name in configurations:
                table.description = configurations[table_name]["description"]

            # Configure partitioning
            if partition_field and partition_type:
                if partition_type == "DAY":
                    table.time_partitioning = bigquery.TimePartitioning(
                        type_=bigquery.TimePartitioningType.DAY, field=partition_field
                    )
                    logger.info(f"Configured daily partitioning on {partition_field}")

            # Configure clustering
            if cluster_fields:
                table.clustering_fields = cluster_fields
                logger.info(f"Configured clustering on fields: {cluster_fields}")

            # Create the table
            table = client.create_table(table, exists_ok=True)
            logger.info(f"Created table {table_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            return False

    async def create_all_tables(self) -> Dict[str, bool]:
        """Create all analyzer tables with proper optimization."""
        # Ensure dataset exists first
        if not await self.ensure_dataset_exists():
            logger.error("Failed to create dataset, aborting table creation")
            return {}

        schemas = BigQueryTableSchema.get_all_schemas()
        configurations = BigQueryTableSchema.get_table_configurations()
        results = {}

        for table_name, schema in schemas.items():
            if not schema:  # Skip if schema is empty (ImportError)
                logger.warning(f"Skipping {table_name} - schema not available")
                results[table_name] = False
                continue

            config = configurations.get(table_name, {})

            success = await self.create_table(
                table_name=table_name,
                schema=schema,
                partition_field=config.get("partition_field"),
                partition_type=config.get("partition_type"),
                cluster_fields=config.get("cluster_fields"),
            )

            results[table_name] = success

        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        logger.info(f"Created {successful}/{total} tables successfully")

        return results

    async def validate_schema(self, table_name: str) -> Dict[str, Any]:
        """Validate that a table exists and has the expected schema."""
        try:
            client = await self.get_client()

            table_id = f"{self.config.project_id}.{self.config.dataset_id}.{table_name}"
            table = client.get_table(table_id)

            return {
                "exists": True,
                "table_id": table_id,
                "schema_fields": len(table.schema),
                "partitioning": {
                    "enabled": table.time_partitioning is not None,
                    "type": table.time_partitioning.type_
                    if table.time_partitioning
                    else None,
                    "field": table.time_partitioning.field
                    if table.time_partitioning
                    else None,
                },
                "clustering": {
                    "enabled": bool(table.clustering_fields),
                    "fields": table.clustering_fields or [],
                },
                "description": table.description,
                "num_rows": table.num_rows,
                "size_bytes": table.num_bytes,
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
            }

        except Exception as e:
            logger.error(f"Failed to validate schema for {table_name}: {e}")
            return {"exists": False, "error": str(e)}

    async def validate_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Validate all analyzer table schemas."""
        schemas = BigQueryTableSchema.get_all_schemas()
        results = {}

        for table_name in schemas.keys():
            results[table_name] = await self.validate_schema(table_name)

        return results

    async def get_storage_estimate(self) -> Dict[str, Any]:
        """Get storage size estimates for all tables."""
        try:
            client = await self.get_client()

            # Query INFORMATION_SCHEMA for table sizes
            query = f"""
            SELECT
                table_name,
                row_count,
                size_bytes,
                size_bytes / (1024*1024*1024) as size_gb,
                partitioning_type,
                clustering_ordinal_position,
                clustering_column_name
            FROM `{self.config.project_id}.{self.config.dataset_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
            ORDER BY size_bytes DESC
            """

            query_job = client.query(query)
            results = query_job.result()

            tables = []
            total_size_bytes = 0
            total_rows = 0

            for row in results:
                table_info = {
                    "table_name": row.table_name,
                    "row_count": row.row_count,
                    "size_bytes": row.size_bytes,
                    "size_gb": row.size_gb,
                    "partitioning_type": row.partitioning_type,
                    "clustering_enabled": row.clustering_ordinal_position is not None,
                }
                tables.append(table_info)
                total_size_bytes += row.size_bytes or 0
                total_rows += row.row_count or 0

            return {
                "tables": tables,
                "summary": {
                    "total_tables": len(tables),
                    "total_size_bytes": total_size_bytes,
                    "total_size_gb": total_size_bytes / (1024 * 1024 * 1024),
                    "total_rows": total_rows,
                    "estimated_monthly_cost_usd": (
                        total_size_bytes / (1024 * 1024 * 1024)
                    )
                    * 0.020,  # $0.020 per GB
                },
            }

        except Exception as e:
            logger.error(f"Failed to get storage estimate: {e}")
            return {"error": str(e)}

    async def drop_table(self, table_name: str) -> bool:
        """Drop a table (use with caution)."""
        try:
            client = await self.get_client()

            table_id = f"{self.config.project_id}.{self.config.dataset_id}.{table_name}"
            client.delete_table(table_id, not_found_ok=True)
            logger.info(f"Dropped table {table_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to drop table {table_name}: {e}")
            return False

    async def recreate_table(self, table_name: str) -> bool:
        """Drop and recreate a table with updated schema."""
        schemas = BigQueryTableSchema.get_all_schemas()
        configurations = BigQueryTableSchema.get_table_configurations()

        if table_name not in schemas:
            logger.error(f"Unknown table: {table_name}")
            return False

        # Drop existing table
        await self.drop_table(table_name)

        # Recreate with current schema
        config = configurations.get(table_name, {})
        return await self.create_table(
            table_name=table_name,
            schema=schemas[table_name],
            partition_field=config.get("partition_field"),
            partition_type=config.get("partition_type"),
            cluster_fields=config.get("cluster_fields"),
        )
