"""Tests for premium export functionality."""

import csv
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from paidsearchnav.api.main import app
from paidsearchnav.core.config import BigQueryTier


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "sub": "test_user",
        "customer_id": "test_customer_123",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_premium_settings():
    """Mock settings with premium BigQuery tier."""
    settings = MagicMock()
    settings.bigquery.enabled = True
    settings.bigquery.tier = BigQueryTier.PREMIUM
    settings.bigquery.project_id = "test-project"
    settings.bigquery.dataset_id = "test_dataset"
    return settings


@pytest.fixture
def mock_export_data():
    """Mock export data from BigQuery."""
    return [
        {
            "search_term": "test keyword 1",
            "campaign_id": "123456789",
            "campaign_name": "Test Campaign 1",
            "impressions": 1000,
            "clicks": 50,
            "cost": 25.50,
            "conversions": 2,
            "ctr": 5.0,
        },
        {
            "search_term": "test keyword 2",
            "campaign_id": "987654321",
            "campaign_name": "Test Campaign 2",
            "impressions": 800,
            "clicks": 40,
            "cost": 20.00,
            "conversions": 1,
            "ctr": 5.0,
        },
    ]


@pytest.fixture
def mock_bigquery_client(mock_export_data):
    """Mock BigQuery client for exports."""
    client = AsyncMock()

    # Mock query results
    mock_dataframe = MagicMock()
    mock_dataframe.empty = False
    mock_dataframe.to_dict.return_value = mock_export_data
    mock_dataframe.to_csv.return_value = None

    # Mock CSV content
    csv_content = "search_term,campaign_id,campaign_name,impressions,clicks,cost,conversions,ctr\n"
    for row in mock_export_data:
        csv_content += f"{row['search_term']},{row['campaign_id']},{row['campaign_name']},{row['impressions']},{row['clicks']},{row['cost']},{row['conversions']},{row['ctr']}\n"

    def mock_to_csv(output, index=False):
        output.write(csv_content)

    mock_dataframe.to_csv = mock_to_csv

    mock_query_job = MagicMock()
    mock_query_job.to_dataframe.return_value = mock_dataframe

    client.query.return_value = mock_query_job
    return client


class TestExportJobManagement:
    """Test export job creation and management."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_create_export_job(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test creating a new export job."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        export_request = {
            "customer_id": "test_customer_123",
            "data_type": "search_terms",
            "date_range": "30d",
            "format": "csv",
            "filters": {"campaigns": ["123456789"]},
            "columns": ["search_term", "impressions", "clicks", "cost"],
        }

        response = client.post(
            "/api/v1/premium/exports/create",
            json=export_request,
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["progress"] == 0.0
        assert data["job_id"].startswith("export_test_customer_123_")

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_get_export_status(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test getting export job status."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/status/test_job_123",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_123"
        assert data["status"] == "completed"
        assert data["progress"] == 1.0
        assert "download_url" in data


class TestCSVExports:
    """Test CSV export functionality."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_csv_export_success(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test successful CSV export."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/download/csv",
            params={
                "customer_id": "test_customer_123",
                "data_type": "search_terms",
                "date_range": "30d",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert (
            "search_terms_test_customer_123_" in response.headers["content-disposition"]
        )

        # Check CSV content
        content = response.content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["search_term"] == "test keyword 1"
        assert rows[0]["impressions"] == "1000"

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_csv_export_with_filters(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test CSV export with filtering parameters."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/download/csv",
            params={
                "customer_id": "test_customer_123",
                "data_type": "keywords",
                "date_range": "7d",
                "campaigns": ["123456789", "987654321"],
                "min_cost": 10.0,
                "columns": ["keyword_text", "impressions", "cost"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"


class TestJSONExports:
    """Test JSON export functionality."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_json_export_success(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test successful JSON export."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/download/json",
            params={
                "customer_id": "test_customer_123",
                "data_type": "campaigns",
                "date_range": "14d",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "campaigns_test_customer_123_" in response.headers["content-disposition"]

        # Check JSON content
        content = response.content.decode("utf-8")
        data = json.loads(content)
        assert "export_info" in data
        assert "data" in data
        assert data["export_info"]["customer_id"] == "test_customer_123"
        assert data["export_info"]["data_type"] == "campaigns"
        assert len(data["data"]) == 2


class TestCustomQueries:
    """Test custom query functionality."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_custom_query_execution(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test execution of predefined custom queries."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        # Mock query job for custom query
        mock_query_job = MagicMock()
        mock_query_job.to_dataframe.return_value = MagicMock()
        mock_query_job.to_dataframe.return_value.empty = False
        mock_query_job.to_dataframe.return_value.to_dict.return_value = [
            {"keyword_text": "test keyword", "impressions": 1000, "conversions": 5}
        ]
        mock_query_job.total_bytes_processed = 1024 * 1024
        mock_bigquery_client.query.return_value = mock_query_job

        response = client.get(
            "/api/v1/premium/exports/custom-query",
            params={
                "customer_id": "test_customer_123",
                "query_template": "top_performing_keywords",
                "parameters": json.dumps({"limit": 50, "min_conversions": 1}),
                "format": "json",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "test_customer_123"
        assert data["query_template"] == "top_performing_keywords"
        assert "data" in data
        assert "metadata" in data
        assert data["parameters"]["limit"] == 50

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_custom_query_invalid_template(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test custom query with invalid template."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/custom-query",
            params={
                "customer_id": "test_customer_123",
                "query_template": "invalid_template",
                "format": "json",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 400
        assert "Invalid query template" in response.json()["detail"]

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_custom_query_csv_format(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test custom query with CSV format response."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        # Mock query results
        mock_query_job = MagicMock()
        mock_query_job.to_dataframe.return_value = MagicMock()
        mock_query_job.to_dataframe.return_value.empty = False
        mock_query_job.to_dataframe.return_value.to_dict.return_value = [
            {
                "campaign_name": "Test Campaign",
                "total_cost": 100.0,
                "total_conversions": 10,
            }
        ]
        mock_query_job.total_bytes_processed = 1024 * 1024
        mock_bigquery_client.query.return_value = mock_query_job

        response = client.get(
            "/api/v1/premium/exports/custom-query",
            params={
                "customer_id": "test_customer_123",
                "query_template": "budget_analysis",
                "format": "csv",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"


class TestDataSummary:
    """Test data summary functionality."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_export_data_summary(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test getting data availability summary."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        # Mock summary data for each table
        def mock_query_side_effect(query):
            mock_job = MagicMock()
            mock_df = MagicMock()
            mock_df.empty = False

            if "search_terms" in query:
                mock_df.iloc = [MagicMock()]
                mock_df.iloc[0] = MagicMock()
                mock_df.iloc[0].iloc = {
                    "total_rows": 15000,
                    "earliest_date": "2024-01-01T00:00:00Z",
                    "latest_date": "2024-12-31T23:59:59Z",
                    "unique_campaigns": 25,
                }
            elif "keyword" in query:
                mock_df.iloc = [MagicMock()]
                mock_df.iloc[0] = MagicMock()
                mock_df.iloc[0].iloc = {
                    "total_rows": 8500,
                    "earliest_date": "2024-01-01T00:00:00Z",
                    "latest_date": "2024-12-31T23:59:59Z",
                    "unique_campaigns": 20,
                }

            mock_job.to_dataframe.return_value = mock_df
            return mock_job

        mock_bigquery_client.query.side_effect = mock_query_side_effect

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/data-summary",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == "test_customer_123"
        assert "data_summary" in data
        assert "available_formats" in data
        assert "max_export_rows" in data
        assert data["available_formats"] == ["csv", "json"]
        assert data["max_export_rows"] == 100000


class TestQueryBuilding:
    """Test query building functionality."""

    def test_build_export_query_search_terms(self):
        """Test building export query for search terms."""
        from paidsearchnav.api.v1.premium_exports import build_export_query

        mock_service = MagicMock()
        mock_service.config.project_id = "test-project"
        mock_service.config.dataset_id = "test_dataset"

        query = build_export_query(
            mock_service,
            "search_terms",
            "test_customer",
            "30d",
            filters={"campaigns": ["123", "456"], "min_cost": 10.0},
            columns=["search_term", "impressions", "cost"],
        )

        assert (
            "test-project.test_dataset.analyzer_search_terms_recommendations" in query
        )
        assert "customer_id = 'test_customer'" in query
        assert "campaign_id IN ('123', '456')" in query
        assert "(cost_micros / 1000000) >= 10.0" in query
        assert "search_term, impressions, cost" in query
        assert "INTERVAL 30 DAY" in query

    def test_build_export_query_keywords(self):
        """Test building export query for keywords."""
        from paidsearchnav.api.v1.premium_exports import build_export_query

        mock_service = MagicMock()
        mock_service.config.project_id = "test-project"
        mock_service.config.dataset_id = "test_dataset"

        query = build_export_query(
            mock_service,
            "keywords",
            "test_customer",
            "7d",
            filters={"match_type": "EXACT", "min_impressions": 100},
        )

        assert "analyzer_keyword_recommendations" in query
        assert "match_type = 'EXACT'" in query
        assert "impressions >= 100" in query
        assert "INTERVAL 7 DAY" in query

    def test_build_export_query_invalid_data_type(self):
        """Test building query with invalid data type."""
        from paidsearchnav.api.v1.premium_exports import build_export_query

        mock_service = MagicMock()

        with pytest.raises(ValueError, match="Unsupported data type"):
            build_export_query(mock_service, "invalid_type", "test_customer", "30d")


class TestSecurityAndValidation:
    """Test security and validation features."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_requires_premium_tier(
        self, mock_get_service, mock_get_settings, mock_get_user, client, mock_user
    ):
        """Test that exports require premium tier."""
        mock_get_user.return_value = mock_user

        # Mock non-premium settings
        settings = MagicMock()
        settings.bigquery.enabled = False
        settings.bigquery.tier = BigQueryTier.DISABLED
        mock_get_settings.return_value = settings

        mock_service = MagicMock()
        mock_service.is_premium = False
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/download/csv",
            params={"customer_id": "test_customer_123", "data_type": "search_terms"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 402
        assert "Premium tier required" in response.json()["detail"]

    def test_column_sanitization(self):
        """Test that column names are properly sanitized."""
        from paidsearchnav.api.v1.premium_exports import build_export_query

        mock_service = MagicMock()
        mock_service.config.project_id = "test-project"
        mock_service.config.dataset_id = "test_dataset"

        # Test with potentially dangerous column names
        dangerous_columns = [
            "valid_column",
            "bad'; DROP TABLE",
            "another_valid",
            "x';--",
        ]

        query = build_export_query(
            mock_service,
            "search_terms",
            "test_customer",
            "30d",
            columns=dangerous_columns,
        )

        # Should only include safe columns
        assert "valid_column, another_valid" in query
        assert "DROP TABLE" not in query
        assert "x';--" not in query

    def test_invalid_customer_id_format(self, client):
        """Test validation of customer ID format."""
        response = client.get(
            "/api/v1/premium/exports/download/csv",
            params={
                "customer_id": "invalid; DROP TABLE users;--",
                "data_type": "search_terms",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        # Should be rejected by input validation
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_bigquery_connection_failure(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test handling of BigQuery connection failures."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_client = AsyncMock()
        mock_client.query.side_effect = Exception("Connection timeout")
        mock_service.authenticator.get_client = AsyncMock(return_value=mock_client)
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/download/csv",
            params={"customer_id": "test_customer_123", "data_type": "search_terms"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500
        assert "CSV export failed" in response.json()["detail"]

    @patch("paidsearchnav.api.v1.premium_exports.get_current_user")
    @patch("paidsearchnav.api.v1.premium_exports.get_settings")
    @patch("paidsearchnav.api.v1.premium_exports.get_bigquery_service")
    def test_invalid_json_parameters(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test handling of invalid JSON parameters."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/exports/custom-query",
            params={
                "customer_id": "test_customer_123",
                "query_template": "top_performing_keywords",
                "parameters": "invalid json {",
                "format": "json",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 400
        assert "Invalid JSON parameters" in response.json()["detail"]
