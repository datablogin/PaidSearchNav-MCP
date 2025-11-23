"""Tests for GA4 BigQuery client integration."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.platforms.ga4.bigquery_client import GA4BigQueryClient


class TestGA4BigQueryClient:
    """Test GA4 BigQuery client functionality."""

    @pytest.fixture
    def client(self):
        """Create test GA4 BigQuery client."""
        return GA4BigQueryClient(
            project_id="test-project",
            ga4_dataset_id="analytics_123456789",
            location="US",
        )

    @pytest.fixture
    def mock_bigquery_client(self):
        """Mock BigQuery client."""
        with patch("paidsearchnav.platforms.ga4.bigquery_client.bigquery") as mock_bq:
            mock_client = Mock()
            mock_bq.Client.return_value = mock_client
            yield mock_client

    def test_client_initialization(self, client):
        """Test client initialization."""
        assert client.project_id == "test-project"
        assert client.ga4_dataset_id == "analytics_123456789"
        assert client.location == "US"
        assert client._client is None

    @patch("paidsearchnav.platforms.ga4.bigquery_client.BIGQUERY_AVAILABLE", False)
    def test_client_initialization_without_bigquery(self):
        """Test client initialization fails without BigQuery."""
        with pytest.raises(ImportError, match="Google Cloud BigQuery is required"):
            GA4BigQueryClient("test-project", "analytics_123456789")

    def test_discover_ga4_tables(self, client, mock_bigquery_client):
        """Test GA4 table discovery."""
        # Mock table listing
        mock_tables = [
            Mock(table_id="events_20241201"),
            Mock(table_id="events_20241202"),
            Mock(table_id="events_intraday_20241202"),
            Mock(table_id="other_table"),
        ]
        mock_bigquery_client.list_tables.return_value = mock_tables
        mock_bigquery_client.dataset.return_value = Mock()

        client._client = mock_bigquery_client

        tables = client.discover_ga4_tables()

        expected = ["events_20241201", "events_20241202", "events_intraday_20241202"]
        assert sorted(tables) == sorted(expected)

    def test_get_gclid_sessions(self, client, mock_bigquery_client):
        """Test GCLID session retrieval."""
        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)
        gclid_list = ["gclid1", "gclid2", "gclid3"]

        # Mock query results
        mock_results = [
            {
                "session_id": "session_1",
                "attribution_id": "gclid1",
                "gclid": "gclid1",
                "ga4_user_id": "user_1",
                "event_timestamp": "2024-12-01T10:00:00Z",
                "session_engaged": True,
                "engagement_time_msec": 45000,
                "bounce_rate": 25.0,
                "landing_page": "https://example.com/page1",
            },
            {
                "session_id": "session_2",
                "attribution_id": "gclid2",
                "gclid": "gclid2",
                "ga4_user_id": "user_2",
                "event_timestamp": "2024-12-02T11:00:00Z",
                "session_engaged": False,
                "engagement_time_msec": 5000,
                "bounce_rate": 100.0,
                "landing_page": "https://example.com/page2",
            },
        ]

        client._client = mock_bigquery_client
        with patch.object(client, "_execute_query", return_value=mock_results):
            sessions = client.get_gclid_sessions(start_date, end_date, gclid_list)

        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session_1"
        assert sessions[0]["session_engaged"] is True
        assert sessions[1]["bounce_rate"] == 100.0

    def test_get_store_visit_attribution(self, client, mock_bigquery_client):
        """Test store visit attribution data retrieval."""
        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)
        store_locations = [
            {"store_id": "store_001", "latitude": 40.7128, "longitude": -74.0060},
            {"store_id": "store_002", "latitude": 34.0522, "longitude": -118.2437},
        ]

        mock_results = [
            {
                "gclid": "gclid1",
                "session_id": "session_1",
                "ga4_user_id": "user_1",
                "store_location_id": "store_001",
                "distance_to_store": 2.5,
                "store_visit_converted": True,
                "conversion_value": 150.0,
            }
        ]

        client._client = mock_bigquery_client
        with patch.object(client, "_execute_query", return_value=mock_results):
            visits = client.get_store_visit_attribution(
                start_date, end_date, store_locations
            )

        assert len(visits) == 1
        assert visits[0]["store_location_id"] == "store_001"
        assert visits[0]["store_visit_converted"] is True
        assert visits[0]["distance_to_store"] == 2.5

    def test_get_ga4_revenue_attribution(self, client, mock_bigquery_client):
        """Test GA4 revenue attribution retrieval."""
        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        mock_results = [
            {
                "gclid": "gclid1",
                "session_id": "session_1",
                "ga4_user_id": "user_1",
                "transaction_id": "txn_001",
                "item_revenue_usd": 250.0,
                "item_purchase_quantity": 2,
                "attribution_model": "last_click",
                "attributed_revenue": 250.0,
            }
        ]

        client._client = mock_bigquery_client
        with patch.object(client, "_execute_query", return_value=mock_results):
            revenue = client.get_ga4_revenue_attribution(
                start_date, end_date, "last_click"
            )

        assert len(revenue) == 1
        assert revenue[0]["transaction_id"] == "txn_001"
        assert revenue[0]["attributed_revenue"] == 250.0
        assert revenue[0]["attribution_model"] == "last_click"

    def test_validate_gclid_matching(self, client):
        """Test GCLID matching validation."""
        google_ads_data = [
            {"gclid": "gclid1", "cost": 50.0, "clicks": 10},
            {"gclid": "gclid2", "cost": 75.0, "clicks": 15},
            {"gclid": "gclid3", "cost": 25.0, "clicks": 5},
        ]

        mock_ga4_sessions = [
            {"gclid": "gclid1", "session_id": "session_1"},
            {"gclid": "gclid2", "session_id": "session_2"},
            # gclid3 missing from GA4 data
        ]

        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        with patch.object(client, "get_gclid_sessions", return_value=mock_ga4_sessions):
            validation = client.validate_gclid_matching(
                google_ads_data, start_date, end_date
            )

        assert validation["total_google_ads_clicks"] == 3
        assert validation["matched_sessions"] == 2
        assert validation["match_rate_percent"] == 66.67
        assert len(validation["unmatched_gclids"]) == 1
        assert validation["unmatched_gclids"][0] == "gclid3"

    def test_estimate_query_cost(self, client, mock_bigquery_client):
        """Test query cost estimation."""
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024 * 1024  # 1GB
        mock_bigquery_client.query.return_value = mock_job

        client._client = mock_bigquery_client

        test_query = "SELECT * FROM test_table"
        cost_estimate = client.estimate_query_cost(test_query)

        assert cost_estimate["bytes_processed"] == 1024 * 1024 * 1024
        assert cost_estimate["estimated_cost_usd"] > 0
        assert cost_estimate["query_valid"] is True

    def test_date_range_formatting(self, client):
        """Test date range formatting for GA4 table suffixes."""
        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        date_range = client._get_date_range(start_date, end_date)

        assert date_range["start_suffix"] == "20241201"
        assert date_range["end_suffix"] == "20241207"

    def test_execute_query_error_handling(self, client, mock_bigquery_client):
        """Test query execution error handling."""
        from google.cloud.exceptions import GoogleCloudError

        mock_bigquery_client.query.side_effect = GoogleCloudError("Test error")
        client._client = mock_bigquery_client

        with pytest.raises(GoogleCloudError):
            client._execute_query("SELECT * FROM test_table")

    def test_empty_gclid_list_handling(self, client):
        """Test handling of empty GCLID lists."""
        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        sessions = client.get_gclid_sessions(start_date, end_date, [])
        assert sessions == []

        validation = client.validate_gclid_matching([], start_date, end_date)
        assert validation["total_google_ads_clicks"] == 0
        assert validation["match_rate_percent"] == 0.0
