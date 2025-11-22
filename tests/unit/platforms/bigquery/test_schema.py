"""Tests for BigQuery schema definitions."""

import pytest

from paidsearchnav.platforms.bigquery.schema import BigQueryTableSchema


class TestBigQueryTableSchema:
    """Test BigQuery table schema definitions."""

    def test_get_search_terms_schema(self):
        """Test search terms schema has required fields."""
        schema = BigQueryTableSchema.get_search_terms_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check required fields
        assert "date" in field_names
        assert "customer_id" in field_names
        assert "campaign_id" in field_names
        assert "search_term" in field_names
        assert "impressions" in field_names
        assert "clicks" in field_names
        assert "cost" in field_names
        assert "conversions" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names

        # Check analytics fields
        assert "local_intent_score" in field_names
        assert "negative_recommendation" in field_names

    def test_get_keywords_schema(self):
        """Test keywords schema has required fields."""
        schema = BigQueryTableSchema.get_keywords_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check required fields
        assert "date" in field_names
        assert "customer_id" in field_names
        assert "keyword_text" in field_names
        assert "match_type" in field_names
        assert "quality_score" in field_names
        assert "bid_recommendation" in field_names

    def test_get_campaigns_schema(self):
        """Test campaigns schema has required fields."""
        schema = BigQueryTableSchema.get_campaigns_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check required fields
        assert "date" in field_names
        assert "customer_id" in field_names
        assert "campaign_id" in field_names
        assert "campaign_name" in field_names
        assert "campaign_type" in field_names
        assert "optimization_recommendations" in field_names

    def test_get_demographics_schema(self):
        """Test demographics schema has required fields."""
        schema = BigQueryTableSchema.get_demographics_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check demographics-specific fields
        assert "demographic_type" in field_names
        assert "demographic_value" in field_names
        assert "performance_score" in field_names
        assert "bid_adjustment_recommendation" in field_names

    def test_get_device_performance_schema(self):
        """Test device performance schema has required fields."""
        schema = BigQueryTableSchema.get_device_performance_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check device-specific fields
        assert "device_type" in field_names
        assert "device_share_impressions" in field_names
        assert "device_share_clicks" in field_names

    def test_get_geo_performance_schema(self):
        """Test geographic performance schema has required fields."""
        schema = BigQueryTableSchema.get_geo_performance_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check geo-specific fields
        assert "location_type" in field_names
        assert "location_name" in field_names
        assert "location_level" in field_names
        assert "local_intent_score" in field_names
        assert "distance_from_business" in field_names

    def test_get_pmax_schema(self):
        """Test Performance Max schema has required fields."""
        schema = BigQueryTableSchema.get_pmax_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check Performance Max specific fields
        assert "asset_group_id" in field_names
        assert "asset_type" in field_names
        assert "asset_performance_score" in field_names
        assert "expansion_recommendations" in field_names
        assert "roas" in field_names

    def test_get_negative_conflicts_schema(self):
        """Test negative conflicts schema has required fields."""
        schema = BigQueryTableSchema.get_negative_conflicts_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check conflict detection fields
        assert "positive_keyword" in field_names
        assert "negative_keyword" in field_names
        assert "conflict_type" in field_names
        assert "severity" in field_names
        assert "resolution_recommendation" in field_names

    def test_get_cost_tracking_schema(self):
        """Test cost tracking schema has required fields."""
        schema = BigQueryTableSchema.get_cost_tracking_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check cost tracking fields
        assert "bytes_processed" in field_names
        assert "bytes_billed" in field_names
        assert "estimated_cost_usd" in field_names
        assert "tier" in field_names
        assert "api_endpoint" in field_names

    def test_get_ml_models_schema(self):
        """Test ML models schema has required fields."""
        schema = BigQueryTableSchema.get_ml_models_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_names = [field.name for field in schema]

        # Check ML model fields
        assert "model_id" in field_names
        assert "model_type" in field_names
        assert "model_accuracy" in field_names
        assert "training_rows" in field_names
        assert "retrain_frequency_days" in field_names

    def test_get_all_schemas_completeness(self):
        """Test that all schemas are included in get_all_schemas."""
        all_schemas = BigQueryTableSchema.get_all_schemas()

        # Check that we have schemas for all expected analyzers
        expected_tables = {
            "search_terms",
            "keywords",
            "campaigns",
            "ad_groups",
            "demographics",
            "device_performance",
            "geo_performance",
            "landing_page",
            "dayparting",
            "video_creative",
            "store_performance",
            "negative_conflicts",
            "shared_negatives",
            "bid_adjustments",
            "pmax",
            "analytics_data",
            "cost_tracking",
            "ml_models",
        }

        assert set(all_schemas.keys()) == expected_tables

        # Verify each schema is not empty (unless BigQuery lib unavailable)
        for table_name, schema in all_schemas.items():
            if schema:  # Only check if schema is available
                assert len(schema) > 0, f"Schema for {table_name} should not be empty"

    def test_get_table_configurations_completeness(self):
        """Test that table configurations cover all schemas."""
        all_schemas = BigQueryTableSchema.get_all_schemas()
        configurations = BigQueryTableSchema.get_table_configurations()

        # All tables should have configurations
        assert set(all_schemas.keys()) == set(configurations.keys())

        # Check configuration structure
        for table_name, config in configurations.items():
            assert "description" in config
            assert isinstance(config["description"], str)
            assert len(config["description"]) > 0

            # Most tables should have partitioning (except metadata tables)
            if table_name != "ml_models":
                assert config.get("partition_field") == "date"
                assert config.get("partition_type") == "DAY"

            # All tables should have clustering
            assert "cluster_fields" in config
            assert isinstance(config["cluster_fields"], list)
            assert len(config["cluster_fields"]) > 0
            assert "customer_id" in config["cluster_fields"]

    def test_schema_field_types(self):
        """Test that schema fields have appropriate data types."""
        schema = BigQueryTableSchema.get_search_terms_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_types = {field.name: field.field_type for field in schema}

        # Check data types are appropriate
        assert field_types["date"] == "DATE"
        assert field_types["customer_id"] == "STRING"
        assert field_types["impressions"] == "INTEGER"
        assert field_types["cost"] == "FLOAT"
        assert field_types["ctr"] == "FLOAT"
        assert field_types["created_at"] == "TIMESTAMP"
        assert field_types["updated_at"] == "TIMESTAMP"

    def test_schema_field_modes(self):
        """Test that schema fields have appropriate modes (REQUIRED/NULLABLE)."""
        schema = BigQueryTableSchema.get_search_terms_schema()

        if not schema:  # Skip if BigQuery library not available
            pytest.skip("BigQuery library not available")

        field_modes = {field.name: field.mode for field in schema}

        # Check required fields
        required_fields = [
            "date",
            "customer_id",
            "campaign_id",
            "search_term",
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "created_at",
            "updated_at",
        ]

        for field_name in required_fields:
            assert field_modes[field_name] == "REQUIRED", (
                f"{field_name} should be REQUIRED"
            )

        # Check nullable fields
        nullable_fields = [
            "local_intent_score",
            "quality_score",
            "negative_recommendation",
        ]

        for field_name in nullable_fields:
            assert field_modes[field_name] == "NULLABLE", (
                f"{field_name} should be NULLABLE"
            )

    def test_schema_field_descriptions(self):
        """Test that all schema fields have descriptions."""
        all_schemas = BigQueryTableSchema.get_all_schemas()

        for table_name, schema in all_schemas.items():
            if not schema:  # Skip if BigQuery library not available
                continue

            for field in schema:
                assert hasattr(field, "description"), (
                    f"Field {field.name} in {table_name} should have description"
                )
                assert field.description, (
                    f"Field {field.name} in {table_name} description should not be empty"
                )
                assert len(field.description) > 10, (
                    f"Field {field.name} in {table_name} description should be descriptive"
                )
