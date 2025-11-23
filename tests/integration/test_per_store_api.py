"""Integration tests for Per Store API endpoints."""

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import app


class TestPerStoreAPI:
    """Test Per Store API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_per_store_csv(self):
        """Sample per store CSV data."""
        csv_content = '''Store locations,address_line_1,city,province,postal_code,country_code,phone_number,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"Fitness Connection - Mesquite, TX","1234 Town East Blvd","Mesquite","TX","75150","US","+1-214-555-0100","515,305","65,615","1,234","12,866","2,345"
"Fitness Connection - Houston, TX","12032 East Freeway","Houston","TX","77029","US","+1-713-555-0200","372,981","58,694","987","11,640","1,876"
"Fitness Connection - Charlotte, NC","8709 JW Clay Boulevard","Charlotte","NC","28262","US","+1-704-555-0400","389,472","50,419","765","7,309","1,203"
"Fitness Connection - Dallas, TX","9832 Forest Lane","Dallas","TX","75243","US","+1-214-555-0500","298,765","32,145","543","5,987","987"
"Fitness Connection - Raleigh, NC","5432 Capital Boulevard","Raleigh","NC","27616","US","+1-919-555-0600","245,876","28,432","432","4,876","765"'''
        return csv_content

    def test_parse_csv_per_store_success(self, client, sample_per_store_csv):
        """Test successful per store CSV parsing."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_per_store_csv)
            csv_file_path = f.name

        try:
            # Test parse-csv endpoint
            with open(csv_file_path, "rb") as f:
                response = client.post(
                    "/api/v1/parse-csv?data_type=per_store&show_sample=true&sample_size=3",
                    files={"file": ("test_per_store.csv", f, "text/csv")},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["data_type"] == "per_store"
            assert data["total_records"] == 5
            assert "sample_records" in data
            assert len(data["sample_records"]) <= 3
            assert "columns" in data
            assert "Store locations" in data["columns"]
            assert "Local reach (impressions)" in data["columns"]

        finally:
            # Cleanup
            Path(csv_file_path).unlink(missing_ok=True)

    def test_analyze_csv_per_store_success(self, client, sample_per_store_csv):
        """Test successful per store CSV analysis."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_per_store_csv)
            csv_file_path = f.name

        try:
            # Test analyze-csv endpoint
            with open(csv_file_path, "rb") as f:
                response = client.post(
                    "/api/v1/analyze-csv?data_type=per_store",
                    files={"file": ("test_per_store.csv", f, "text/csv")},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["filename"] == "test_per_store.csv"
            assert data["total_rows"] == 5
            assert "analysis_summary" in data

            # Check analysis summary structure
            summary = data["analysis_summary"]
            assert summary["data_type"] == "per_store"
            assert "total_stores" in summary
            assert "active_stores" in summary
            assert "total_local_impressions" in summary
            assert "local_action_metrics" in summary
            assert "geographic_distribution" in summary
            assert "performance_analysis" in summary

            # Verify geographic analysis
            assert "state_distribution" in summary["geographic_distribution"]
            assert "TX" in summary["geographic_distribution"]["state_distribution"]
            assert "NC" in summary["geographic_distribution"]["state_distribution"]

            # Verify local action metrics
            metrics = summary["local_action_metrics"]
            assert "avg_store_visit_rate" in metrics
            assert "avg_call_click_rate" in metrics
            assert "avg_directions_rate" in metrics
            assert "avg_website_visit_rate" in metrics

            # Verify performance analysis
            performance = summary["performance_analysis"]
            assert "high_performers" in performance
            assert "low_performers" in performance
            assert "top_performing_stores" in performance

        finally:
            # Cleanup
            Path(csv_file_path).unlink(missing_ok=True)

    def test_parse_csv_per_store_invalid_file(self, client):
        """Test per store CSV parsing with invalid file."""
        invalid_csv = "invalid,csv,data\n1,2"

        response = client.post(
            "/api/v1/parse-csv?data_type=per_store",
            files={
                "file": (
                    "invalid.csv",
                    io.BytesIO(invalid_csv.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        # Should still parse but with no meaningful results
        assert response.status_code == 200
        data = response.json()
        assert data["data_type"] == "per_store"
        assert data["total_records"] == 1  # One data row

    def test_parse_csv_per_store_empty_file(self, client):
        """Test per store CSV parsing with empty file."""
        response = client.post(
            "/api/v1/parse-csv?data_type=per_store",
            files={"file": ("empty.csv", io.BytesIO("".encode("utf-8")), "text/csv")},
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_analyze_csv_per_store_minimal_data(self, client):
        """Test per store CSV analysis with minimal data."""
        minimal_csv = '''Store locations,Local reach (impressions),Store visits
"Test Store 1","1000","50"
"Test Store 2","2000","100"'''

        response = client.post(
            "/api/v1/analyze-csv?data_type=per_store",
            files={
                "file": (
                    "minimal.csv",
                    io.BytesIO(minimal_csv.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        data = response.json()

        summary = data["analysis_summary"]
        assert summary["total_stores"] == 2
        assert summary["active_stores"] == 2
        assert summary["total_local_impressions"] > 0

    def test_parse_csv_per_store_large_numbers(self, client):
        """Test per store CSV parsing with large comma-separated numbers."""
        csv_with_large_numbers = '''Store locations,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"Large Store","1,234,567","123,456","12,345","23,456","3,456"'''

        response = client.post(
            "/api/v1/parse-csv?data_type=per_store&show_sample=true",
            files={
                "file": (
                    "large_numbers.csv",
                    io.BytesIO(csv_with_large_numbers.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_records"] == 1
        sample = data["sample_records"][0]
        assert "1,234,567" in str(sample["Local reach (impressions)"])

    def test_analyze_csv_per_store_performance_categorization(self, client):
        """Test per store analysis performance categorization."""
        # Create CSV with different performance levels
        performance_csv = '''Store locations,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"High Performer","10000","500","50","100","50"
"Low Performer","10000","50","5","10","5"
"Underperformer","10000","10","1","2","1"'''

        response = client.post(
            "/api/v1/analyze-csv?data_type=per_store",
            files={
                "file": (
                    "performance.csv",
                    io.BytesIO(performance_csv.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        data = response.json()

        summary = data["analysis_summary"]
        performance = summary["performance_analysis"]

        # Should categorize stores by performance
        assert performance["high_performers"] >= 1
        assert performance["low_performers"] >= 1
        assert len(performance["top_performing_stores"]) > 0

    def test_parse_csv_per_store_geographic_distribution(
        self, client, sample_per_store_csv
    ):
        """Test geographic distribution in per store analysis."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_per_store_csv)
            csv_file_path = f.name

        try:
            with open(csv_file_path, "rb") as f:
                response = client.post(
                    "/api/v1/analyze-csv?data_type=per_store",
                    files={"file": ("geographic.csv", f, "text/csv")},
                )

            assert response.status_code == 200
            data = response.json()

            summary = data["analysis_summary"]
            geo_dist = summary["geographic_distribution"]

            # Verify state distribution
            assert "TX" in geo_dist["state_distribution"]
            assert "NC" in geo_dist["state_distribution"]
            assert (
                geo_dist["state_distribution"]["TX"] == 3
            )  # Dallas, Houston, Mesquite
            assert geo_dist["state_distribution"]["NC"] == 2  # Charlotte, Raleigh

            # Verify top performing state and city
            assert geo_dist["top_state"] == "TX"  # Most stores
            assert geo_dist["top_city"] in [
                "Dallas",
                "Houston",
                "Charlotte",
                "Mesquite",
                "Raleigh",
            ]

        finally:
            # Cleanup
            Path(csv_file_path).unlink(missing_ok=True)

    def test_parse_csv_per_store_file_validation(self, client):
        """Test file validation for per store CSV."""
        # Test wrong file extension
        response = client.post(
            "/api/v1/parse-csv?data_type=per_store",
            files={
                "file": ("test.txt", io.BytesIO("data".encode("utf-8")), "text/plain")
            },
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

        # Test oversized content (mock large content)
        large_content = "x" * (100 * 1024 * 1024 + 1)  # Slightly over 100MB limit
        response = client.post(
            "/api/v1/parse-csv?data_type=per_store",
            files={
                "file": (
                    "large.csv",
                    io.BytesIO(large_content.encode("utf-8")),
                    "text/csv",
                )
            },
        )
        assert response.status_code == 413
        assert "large" in response.json()["detail"].lower()

    def test_analyze_csv_per_store_optimization_opportunities(self, client):
        """Test identification of optimization opportunities."""
        # Create CSV with stores that need optimization
        optimization_csv = '''Store locations,address_line_1,city,province,phone_number,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"Store with Call Issues","123 Main St","Dallas","TX","+1-214-555-0100","5000","100","0","20","10"
"Low Engagement Store","456 Oak Ave","Houston","TX","+1-713-555-0200","10000","50","5","10","5"
"High Performer","789 Pine St","Austin","TX","+1-512-555-0300","8000","400","40","80","40"'''

        response = client.post(
            "/api/v1/analyze-csv?data_type=per_store",
            files={
                "file": (
                    "optimization.csv",
                    io.BytesIO(optimization_csv.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        data = response.json()

        summary = data["analysis_summary"]

        # Should identify optimization opportunities
        assert summary["optimization_opportunities"] > 0
        assert "sample_optimization_opportunities" in summary

        # Should identify high performers
        assert summary["high_performing_stores"] > 0
        assert "sample_high_performers" in summary
