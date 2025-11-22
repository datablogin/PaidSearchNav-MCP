"""Tests for BigQuery schema migrations."""

from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav_mcp.platforms.bigquery.migrations import BigQueryMigrations


class TestBigQueryMigrations:
    """Test BigQuery migrations functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create mock BigQuery configuration."""
        config = MagicMock()
        config.project_id = "test-project"
        config.dataset_id = "test_dataset"
        config.location = "US"
        config.enabled = True
        return config

    @pytest.fixture
    def migrations(self, mock_config):
        """Create BigQueryMigrations instance."""
        return BigQueryMigrations(mock_config)

    @pytest.mark.asyncio
    async def test_get_client(self, migrations):
        """Test BigQuery client creation."""
        with patch("google.cloud.bigquery.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await migrations.get_client()

            assert client == mock_client
            mock_client_class.assert_called_once_with(project="test-project")

    @pytest.mark.asyncio
    async def test_get_client_import_error(self, migrations):
        """Test BigQuery client creation with import error."""
        with patch("google.cloud.bigquery.Client", side_effect=ImportError()):
            with pytest.raises(
                ImportError, match="Google Cloud BigQuery library not available"
            ):
                await migrations.get_client()

    @pytest.mark.asyncio
    async def test_ensure_dataset_exists_already_exists(self, migrations):
        """Test dataset creation when dataset already exists."""
        mock_client = MagicMock()
        mock_dataset = MagicMock()
        mock_client.get_dataset.return_value = mock_dataset

        migrations._client = mock_client

        result = await migrations.ensure_dataset_exists()

        assert result is True
        mock_client.get_dataset.assert_called_once_with("test-project.test_dataset")
        mock_client.create_dataset.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_dataset_exists_create_new(self, migrations):
        """Test dataset creation when dataset doesn't exist."""
        mock_client = MagicMock()
        mock_client.get_dataset.side_effect = Exception("Dataset not found")

        with patch("google.cloud.bigquery.Dataset") as mock_dataset_class:
            mock_dataset = MagicMock()
            mock_dataset_class.return_value = mock_dataset
            mock_client.create_dataset.return_value = mock_dataset

            migrations._client = mock_client

            result = await migrations.ensure_dataset_exists()

            assert result is True
            mock_dataset_class.assert_called_once_with("test-project.test_dataset")
            assert mock_dataset.location == "US"
            assert "PaidSearchNav analyzer data warehouse" in mock_dataset.description
            mock_client.create_dataset.assert_called_once_with(mock_dataset, timeout=30)

    @pytest.mark.asyncio
    async def test_create_table_basic(self, migrations):
        """Test basic table creation."""
        mock_client = MagicMock()
        mock_schema = [MagicMock()]

        with patch("google.cloud.bigquery.Table") as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_client.create_table.return_value = mock_table

            migrations._client = mock_client

            result = await migrations.create_table("test_table", mock_schema)

            assert result is True
            mock_table_class.assert_called_once_with(
                "test-project.test_dataset.test_table", schema=mock_schema
            )
            mock_client.create_table.assert_called_once_with(mock_table, exists_ok=True)

    @pytest.mark.asyncio
    async def test_create_table_with_partitioning(self, migrations):
        """Test table creation with partitioning."""
        mock_client = MagicMock()
        mock_schema = [MagicMock()]

        with (
            patch("google.cloud.bigquery.Table") as mock_table_class,
            patch("google.cloud.bigquery.TimePartitioning") as mock_partitioning_class,
            patch("google.cloud.bigquery.TimePartitioningType") as mock_partition_type,
        ):
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_partitioning = MagicMock()
            mock_partitioning_class.return_value = mock_partitioning
            mock_partition_type.DAY = "DAY"
            mock_client.create_table.return_value = mock_table

            migrations._client = mock_client

            result = await migrations.create_table(
                "test_table", mock_schema, partition_field="date", partition_type="DAY"
            )

            assert result is True
            assert mock_table.time_partitioning == mock_partitioning
            mock_partitioning_class.assert_called_once_with(type_="DAY", field="date")

    @pytest.mark.asyncio
    async def test_create_table_with_clustering(self, migrations):
        """Test table creation with clustering."""
        mock_client = MagicMock()
        mock_schema = [MagicMock()]
        cluster_fields = ["customer_id", "campaign_id"]

        with patch("google.cloud.bigquery.Table") as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_client.create_table.return_value = mock_table

            migrations._client = mock_client

            result = await migrations.create_table(
                "test_table", mock_schema, cluster_fields=cluster_fields
            )

            assert result is True
            assert mock_table.clustering_fields == cluster_fields

    @pytest.mark.asyncio
    async def test_create_all_tables(self, migrations):
        """Test creating all tables."""
        with (
            patch.object(migrations, "ensure_dataset_exists", return_value=True),
            patch.object(
                migrations, "create_table", return_value=True
            ) as mock_create_table,
            patch(
                "paidsearchnav.platforms.bigquery.schema.BigQueryTableSchema.get_all_schemas"
            ) as mock_schemas,
            patch(
                "paidsearchnav.platforms.bigquery.schema.BigQueryTableSchema.get_table_configurations"
            ) as mock_configs,
        ):
            # Mock schemas and configurations
            mock_schemas.return_value = {
                "search_terms": [MagicMock()],
                "keywords": [MagicMock()],
                "campaigns": [],  # Empty schema (ImportError case)
            }

            mock_configs.return_value = {
                "search_terms": {
                    "partition_field": "date",
                    "partition_type": "DAY",
                    "cluster_fields": ["customer_id"],
                },
                "keywords": {
                    "partition_field": "date",
                    "partition_type": "DAY",
                    "cluster_fields": ["customer_id"],
                },
                "campaigns": {
                    "partition_field": "date",
                    "partition_type": "DAY",
                    "cluster_fields": ["customer_id"],
                },
            }

            result = await migrations.create_all_tables()

            # Should create 2 tables (search_terms and keywords), skip campaigns
            assert len(result) == 3
            assert result["search_terms"] is True
            assert result["keywords"] is True
            assert result["campaigns"] is False  # Skipped due to empty schema

            # Verify create_table was called for available schemas
            assert mock_create_table.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_schema_existing_table(self, migrations):
        """Test schema validation for existing table."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # Mock table properties
        mock_table.schema = [MagicMock(), MagicMock()]  # 2 fields
        mock_table.time_partitioning = MagicMock()
        mock_table.time_partitioning.type_ = "DAY"
        mock_table.time_partitioning.field = "date"
        mock_table.clustering_fields = ["customer_id", "campaign_id"]
        mock_table.description = "Test table"
        mock_table.num_rows = 1000
        mock_table.num_bytes = 5000
        mock_table.created = MagicMock()
        mock_table.created.isoformat.return_value = "2024-01-01T00:00:00"
        mock_table.modified = MagicMock()
        mock_table.modified.isoformat.return_value = "2024-01-02T00:00:00"

        mock_client.get_table.return_value = mock_table
        migrations._client = mock_client

        result = await migrations.validate_schema("test_table")

        assert result["exists"] is True
        assert result["table_id"] == "test-project.test_dataset.test_table"
        assert result["schema_fields"] == 2
        assert result["partitioning"]["enabled"] is True
        assert result["partitioning"]["type"] == "DAY"
        assert result["partitioning"]["field"] == "date"
        assert result["clustering"]["enabled"] is True
        assert result["clustering"]["fields"] == ["customer_id", "campaign_id"]
        assert result["num_rows"] == 1000
        assert result["size_bytes"] == 5000

    @pytest.mark.asyncio
    async def test_validate_schema_missing_table(self, migrations):
        """Test schema validation for missing table."""
        mock_client = MagicMock()
        mock_client.get_table.side_effect = Exception("Table not found")
        migrations._client = mock_client

        result = await migrations.validate_schema("missing_table")

        assert result["exists"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_storage_estimate(self, migrations):
        """Test storage estimate calculation."""
        mock_client = MagicMock()

        # Mock query results
        mock_row_1 = MagicMock()
        mock_row_1.table_name = "search_terms"
        mock_row_1.row_count = 1000
        mock_row_1.size_bytes = 1024 * 1024 * 1024  # 1GB
        mock_row_1.size_gb = 1.0
        mock_row_1.partitioning_type = "DAY"
        mock_row_1.clustering_ordinal_position = 1

        mock_row_2 = MagicMock()
        mock_row_2.table_name = "keywords"
        mock_row_2.row_count = 500
        mock_row_2.size_bytes = 512 * 1024 * 1024  # 0.5GB
        mock_row_2.size_gb = 0.5
        mock_row_2.partitioning_type = "DAY"
        mock_row_2.clustering_ordinal_position = None

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [mock_row_1, mock_row_2]
        mock_client.query.return_value = mock_query_job

        migrations._client = mock_client

        result = await migrations.get_storage_estimate()

        assert "tables" in result
        assert "summary" in result
        assert len(result["tables"]) == 2
        assert result["summary"]["total_tables"] == 2
        assert result["summary"]["total_size_gb"] == 1.5
        assert result["summary"]["total_rows"] == 1500
        assert result["summary"]["estimated_monthly_cost_usd"] == pytest.approx(
            0.03, rel=1e-2
        )  # 1.5GB * $0.020

    @pytest.mark.asyncio
    async def test_drop_table(self, migrations):
        """Test table deletion."""
        mock_client = MagicMock()
        migrations._client = mock_client

        result = await migrations.drop_table("test_table")

        assert result is True
        mock_client.delete_table.assert_called_once_with(
            "test-project.test_dataset.test_table", not_found_ok=True
        )

    @pytest.mark.asyncio
    async def test_recreate_table(self, migrations):
        """Test table recreation."""
        with (
            patch.object(migrations, "drop_table", return_value=True) as mock_drop,
            patch.object(migrations, "create_table", return_value=True) as mock_create,
            patch(
                "paidsearchnav.platforms.bigquery.schema.BigQueryTableSchema.get_all_schemas"
            ) as mock_schemas,
            patch(
                "paidsearchnav.platforms.bigquery.schema.BigQueryTableSchema.get_table_configurations"
            ) as mock_configs,
        ):
            mock_schemas.return_value = {"test_table": [MagicMock()]}
            mock_configs.return_value = {
                "test_table": {
                    "partition_field": "date",
                    "partition_type": "DAY",
                    "cluster_fields": ["customer_id"],
                }
            }

            result = await migrations.recreate_table("test_table")

            assert result is True
            mock_drop.assert_called_once_with("test_table")
            mock_create.assert_called_once_with(
                table_name="test_table",
                schema=mock_schemas.return_value["test_table"],
                partition_field="date",
                partition_type="DAY",
                cluster_fields=["customer_id"],
            )

    @pytest.mark.asyncio
    async def test_recreate_table_unknown(self, migrations):
        """Test recreation of unknown table."""
        with patch(
            "paidsearchnav.platforms.bigquery.schema.BigQueryTableSchema.get_all_schemas"
        ) as mock_schemas:
            mock_schemas.return_value = {}

            result = await migrations.recreate_table("unknown_table")

            assert result is False
